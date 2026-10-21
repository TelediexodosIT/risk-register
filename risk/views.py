"""
Pages of the app. Each function is one page; URLs are in risk/urls.py,
templates in templates/risk/.
"""
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.models import User

from . import services
from .access import can_edit_assessment, can_update_task, current_company, get_assessment, get_task
from .forms import AssessmentForm, HazardForm, TaskUpdateForm
from .models import (
    Assessment, ConsequenceLevel, Control, Hazard, HazardTemplate, LikelihoodLevel,
    MatrixCell, RiskRating, Task, TaskUpdate,
)


def _hazards_qs():
    return Hazard.objects.select_related(
        "inherent_likelihood", "inherent_consequence", "residual_likelihood",
        "residual_consequence", "previous_likelihood", "previous_consequence", "assessment",
    ).prefetch_related("controls", Prefetch("tasks", queryset=Task.objects.select_related("owner")))


# --- Assessments ------------------------------------------------------------

@login_required
def home(request):
    if request.user.can_manage:
        return redirect("assessment_list")
    return redirect("task_list")


@login_required
def assessment_list(request):
    company = current_company(request)
    if company is None:
        return render(request, "risk/no_company.html")
    rows = []
    for a in company.assessments.prefetch_related(Prefetch("hazards", queryset=_hazards_qs())):
        hazards = list(a.hazards.all())
        rows.append({"a": a, "state": services.assessment_state(a), "residual": services.rating_counts(hazards, "residual"),
                     "hazard_count": len(hazards)})
    return render(request, "risk/assessment_list.html", {
        "company": company,
        "active": [r for r in rows if r["a"].is_active],
        "older": [r for r in rows if not r["a"].is_active],
    })


@login_required
def assessment_create(request):
    company = current_company(request)
    if not request.user.can_manage or company is None:
        raise Http404
    form = AssessmentForm(request.POST or None, initial={"rule_percent": 100})
    if request.method == "POST" and form.is_valid():
        a = form.save(commit=False)
        a.company = company
        a.created_by = request.user
        a.save()
        a.log("Version 1 created")
        messages.success(request, "Assessment created. Add the first hazard.")
        return redirect("hazard_create", a.id)
    return render(request, "risk/assessment_form.html", {"form": form, "company": company})


@login_required
def assessment_detail(request, pk):
    a = get_assessment(request.user, pk)
    hazards = list(_hazards_qs().filter(assessment=a))
    for h in hazards:
        h.state = services.hazard_state(h)
    a._prefetched_objects_cache = {"hazards": hazards}
    state = services.assessment_state(a)
    tab = request.GET.get("tab", "register")
    ctx = {
        "a": a, "hazards": hazards, "state": state, "tab": tab,
        "can_edit": can_edit_assessment(request.user, a),
        "inherent": services.rating_counts(hazards, "inherent"),
        "residual": services.rating_counts(hazards, "residual"),
        "rule_choices": [100, 80, 75, 50],
    }
    if tab == "tasks":
        ctx["tasks"] = [t for h in hazards for t in h.tasks.all()]
    if tab == "history":
        ctx["chain"] = a.chain()
    return render(request, "risk/assessment_detail.html", ctx)


@login_required
@require_POST
def assessment_rule(request, pk):
    a = get_assessment(request.user, pk)
    if can_edit_assessment(request.user, a):
        value = int(request.POST.get("rule_percent", 100))
        if value in (100, 80, 75, 50):
            a.rule_percent = value
            a.save(update_fields=["rule_percent"])
            a.log(f"Reassessment rule set to {value}% of measures complete")
    return redirect("assessment_detail", a.id)


@login_required
@require_POST
def assessment_reassess(request, pk):
    a = get_assessment(request.user, pk)
    if not can_edit_assessment(request.user, a) or not services.assessment_state(a).ready:
        messages.error(request, "This assessment is not ready for a new version yet.")
        return redirect("assessment_detail", a.id)
    new = services.create_next_version(a, request.user)
    messages.success(request, f"Version {new.version} created. Version {a.version} is kept as a record. "
                              "Re-score the hazards marked “Re-score”.")
    return redirect("assessment_detail", new.id)


# --- Hazards ----------------------------------------------------------------

def _save_controls_and_measures(request, hazard):
    texts = request.POST.getlist("control")
    texts += [line.strip() for line in request.POST.get("other_controls", "").splitlines() if line.strip()]
    hazard.controls.all().delete()
    seen = set()
    Control.objects.bulk_create([Control(hazard=hazard, text=t) for t in texts if not (t in seen or seen.add(t))])

    allowed_owners = User.objects.filter(company=hazard.assessment.company, is_active=True)
    created = 0
    for text, owner_id, due in zip(request.POST.getlist("m_text"), request.POST.getlist("m_owner"),
                                   request.POST.getlist("m_due")):
        text = text.strip()
        owner = allowed_owners.filter(id=owner_id).first()
        if not text or not owner:
            continue
        due_date = datetime.strptime(due, "%Y-%m-%d").date() if due else None
        task = Task.objects.create(hazard=hazard, text=text, owner=owner, due_date=due_date)
        services.notify_assignment(task)
        created += 1
    return created


def _hazard_page(request, a, hazard=None):
    if not can_edit_assessment(request.user, a) and request.method == "POST":
        raise Http404
    template = None
    if hazard is None and request.GET.get("template"):
        template = HazardTemplate.objects.filter(id=request.GET["template"]).first()
    initial = {}
    if template:
        initial = {"name": template.name, "category": template.category, "consequences": template.consequences}
    form = HazardForm(request.POST or None, instance=hazard, initial=initial)

    if request.method == "POST" and form.is_valid():
        is_new = hazard is None
        h = form.save(commit=False)
        h.assessment = a
        if is_new:
            h.template_id = request.POST.get("template_id") or None
            h.order = a.hazards.count()
        if h.residual_likelihood_id and h.residual_consequence_id:
            h.needs_rescore = False
        h.save()
        created = _save_controls_and_measures(request, h)
        if is_new:
            a.log(f"Hazard added: {h.name}")
        msg = "Hazard saved."
        if created:
            msg += f" {created} task{'s' if created > 1 else ''} assigned and the people responsible notified."
        messages.success(request, msg)
        return redirect("assessment_detail", a.id)

    tpl = template or (hazard.template if hazard else None)
    current = [c.text for c in hazard.controls.all()] if hazard else []
    preset = [c.text for c in tpl.controls.all()] if tpl else []
    taken = [t.text for t in hazard.tasks.all()] if hazard else []
    matrix = {f"{c.likelihood_id}-{c.consequence_id}": {
        "code": f"{c.likelihood.code}-{c.consequence.code}", "label": c.rating.label,
        "color": c.rating.color, "action": c.rating.action}
        for c in MatrixCell.objects.select_related("likelihood", "consequence", "rating")}
    return render(request, "risk/hazard_form.html", {
        "a": a, "hazard": hazard, "form": form, "template": tpl,
        "library": HazardTemplate.objects.all() if hazard is None else None,
        "control_options": list(dict.fromkeys(preset + current)),
        "checked_controls": set(current) if hazard else set(),
        "other_controls": "",
        "suggested_measures": [m.text for m in tpl.measures.all() if m.text not in taken] if tpl else [],
        "tasks": hazard.tasks.select_related("owner") if hazard else [],
        "people": User.objects.filter(company=a.company, is_active=True),
        "likelihoods": LikelihoodLevel.objects.all(),
        "consequences": ConsequenceLevel.objects.all(),
        "matrix": matrix,
        "can_edit": can_edit_assessment(request.user, a),
        "default_due": (services.today() + timedelta(days=14)).isoformat(),
    })


@login_required
def hazard_create(request, pk):
    a = get_assessment(request.user, pk)
    if not can_edit_assessment(request.user, a):
        raise Http404
    return _hazard_page(request, a)


@login_required
def hazard_edit(request, pk, hazard_id):
    a = get_assessment(request.user, pk)
    hazard = get_object_or_404(a.hazards, pk=hazard_id)
    return _hazard_page(request, a, hazard)


# --- Tasks ------------------------------------------------------------------

@login_required
def task_list(request):
    company = current_company(request)
    qs = Task.objects.filter(hazard__assessment__company=company, carried_to__isnull=True).select_related(
        "owner", "hazard__assessment")
    if not request.user.can_manage or request.GET.get("mine"):
        qs = qs.filter(owner=request.user)
    f = request.GET.get("f", "open")
    if f == "open":
        qs = qs.exclude(status=Task.Status.DONE)
    elif f == "done":
        qs = qs.filter(status=Task.Status.DONE)
    tasks = list(qs)
    if f == "overdue":
        tasks = [t for t in tasks if t.is_overdue]
    return render(request, "risk/task_list.html", {
        "company": company, "tasks": tasks, "f": f, "mine": bool(request.GET.get("mine")),
        "filters": [("open", "Open"), ("overdue", "Overdue"), ("done", "Done"), ("all", "All")],
    })


@login_required
def task_detail(request, pk):
    task = get_task(request.user, pk)
    can_update = can_update_task(request.user, task)
    form = TaskUpdateForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if not can_update:
            raise Http404
        if form.is_valid():
            a = task.assessment
            before = services.hazard_state(task.hazard).state
            action = request.POST.get("action", "save")
            text, photo = form.cleaned_data["text"], form.cleaned_data["photo"]
            if text or photo:
                TaskUpdate.objects.create(task=task, author=request.user, text=text, photo=photo)
            if action == "complete":
                task.status, task.progress, task.completed_at = Task.Status.DONE, 100, services.today()
            elif action == "reopen":
                task.status, task.completed_at = Task.Status.IN_PROGRESS, None
                task.progress = min(task.progress, 90)
            elif task.status != Task.Status.DONE and form.cleaned_data["progress"] is not None:
                task.progress = form.cleaned_data["progress"]
                task.status = Task.Status.IN_PROGRESS if task.progress else Task.Status.OPEN
            task.save()
            if before != "ready" and services.hazard_state(task.hazard).state == "ready":
                a.log(f"{task.hazard.name}: required measures complete")
            if action == "complete":
                msg = "Task marked complete."
                if services.assessment_state(a).ready:
                    msg += " The assessment is now ready for reassessment."
                messages.success(request, msg)
            else:
                messages.success(request, "Update saved.")
            return redirect("task_detail", task.id)
    return render(request, "risk/task_detail.html", {
        "task": task, "a": task.assessment, "form": form, "can_update": can_update,
        "updates": task.updates.select_related("author"),
    })


@login_required
def evidence_photo(request, pk):
    """Photos are never public: they are served only after the same access check as their task."""
    upd = get_object_or_404(TaskUpdate.objects.select_related("task"), pk=pk)
    get_task(request.user, upd.task_id)
    if not upd.photo:
        raise Http404
    return FileResponse(upd.photo.open("rb"))


# --- Library, matrix, reports -------------------------------------------------

@login_required
def library(request):
    if not request.user.can_manage:
        raise Http404
    return render(request, "risk/library.html", {
        "items": HazardTemplate.objects.prefetch_related("controls", "measures")})


@login_required
def matrix(request):
    likelihoods = list(LikelihoodLevel.objects.all())
    consequences = list(ConsequenceLevel.objects.all())
    cells = {(c.likelihood_id, c.consequence_id): c.rating for c in MatrixCell.objects.select_related("rating")}
    rows = [{"level": l, "cells": [{"c": c, "rating": cells.get((l.id, c.id))} for c in consequences]} for l in likelihoods]
    return render(request, "risk/matrix.html", {"consequences": consequences, "rows": rows,
                                                "ratings": RiskRating.objects.all()})


@login_required
def report(request, pk=None):
    company = current_company(request)
    assessments = list(company.assessments.all()) if company else []
    if pk:
        a = get_assessment(request.user, pk)
    else:
        a = next((x for x in assessments if x.is_active), assessments[0] if assessments else None)
    if a is None:
        return render(request, "risk/report.html", {"company": company, "a": None})
    hazards = list(_hazards_qs().filter(assessment=a))
    rows = []
    for h in hazards:
        tasks = [t for t in h.tasks.all() if t.is_live]
        rows.append({"h": h, "tasks": tasks, "span": max(len(tasks), 1)})
    a._prefetched_objects_cache = {"hazards": hazards}
    return render(request, "risk/report.html", {
        "company": a.company, "a": a, "assessments": assessments, "rows": rows,
        "state": services.assessment_state(a), "residual": services.rating_counts(hazards, "residual"),
        "hazards": hazards, "today": services.today(),
    })


@login_required
def updates(request):
    return render(request, "risk/updates.html", {"items": services.notifications(request.user, current_company(request))})
