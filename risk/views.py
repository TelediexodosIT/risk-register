"""
Pages of the app. Each function is one page; URLs are in risk/urls.py,
templates in templates/risk/.

Words used in the app:
  Assessment         a register for one area/activity of a tenant, versioned (v1, v2 ...)
  Risk task          one row of an assessment (model: Hazard)
  Action             an additional measure assigned to a person (model: Task)
"""
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.utils.translation import ngettext
from django.views.decorators.http import require_POST

from accounts.models import User

from . import services
from .access import can_edit_assessment, can_update_task, current_company, get_assessment, get_task
from .forms import AssessmentForm, TaskUpdateForm
from .models import (
    Assessment, ConsequenceLevel, Control, Hazard, LikelihoodLevel, ListItem, MatrixCell, RiskRating, Task,
    TaskUpdate,
)

def lifecycle_label(key):
    # Translated at render time so the current language is used.
    return {
        "draft": _("Draft"), "needs_action": _("Needs measures"), "open": _("Open"),
        "in_progress": _("In progress"), "overdue": _("Overdue"), "complete": _("Actions complete"),
        "archived": _("Archived"),
    }[key]


def _hazards_qs():
    return Hazard.objects.select_related(
        "inherent_likelihood", "inherent_consequence", "residual_likelihood",
        "residual_consequence", "previous_likelihood", "previous_consequence", "assessment__company",
    ).prefetch_related("controls", Prefetch("tasks", queryset=Task.objects.select_related("owner", "carried_to")))


def _with_lifecycle(hazards):
    for h in hazards:
        h.state = services.hazard_state(h)
        key, css = services.hazard_lifecycle(h)
        h.life_key, h.life_css, h.life_label = key, css, lifecycle_label(key)
    return hazards


# --- Assessments ------------------------------------------------------------

@login_required
def home(request):
    current_company(request)  # applies ?company= from the tenant switch
    if request.user.can_manage:
        return redirect("risk_tasks")
    return redirect("task_list")


@login_required
def assessment_list(request):
    company = current_company(request)
    if company is None:
        return render(request, "risk/no_company.html")
    if not request.user.can_manage:
        raise Http404
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
    form = AssessmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        a = form.save(commit=False)
        a.company = company
        a.created_by = request.user
        a.save()
        a.log("Version 1 created")
        messages.success(request, _("Assessment created. Add the first hazard."))
        return redirect("hazard_create", a.id)
    return render(request, "risk/assessment_form.html", {"form": form, "company": company})


@login_required
def assessment_detail(request, pk):
    a = get_assessment(request.user, pk)
    if not request.user.can_manage:
        raise Http404
    hazards = _with_lifecycle(list(_hazards_qs().filter(assessment=a)))
    a._prefetched_objects_cache = {"hazards": hazards}
    state = services.assessment_state(a)
    tab = request.GET.get("tab", "register")
    ctx = {
        "a": a, "hazards": hazards, "state": state, "tab": tab,
        "can_edit": can_edit_assessment(request.user, a),
        "inherent": services.rating_counts(hazards, "inherent"),
        "residual": services.rating_counts(hazards, "residual"),
    }
    if tab == "tasks":
        ctx["tasks"] = [t for h in hazards for t in h.tasks.all()]
    if tab == "history":
        ctx["chain"] = a.chain()
    return render(request, "risk/assessment_detail.html", ctx)


@login_required
@require_POST
def assessment_reassess(request, pk):
    a = get_assessment(request.user, pk)
    # The consultant decides when to reassess: actions differ in seriousness, so nothing is automatic.
    if not can_edit_assessment(request.user, a):
        raise Http404
    new = services.create_next_version(a, request.user)
    messages.success(request, _("Version %(new)s created. Version %(old)s is kept as a record. "
                                "Re-score the hazards marked “Re-score”.") % {"new": new.version, "old": a.version})
    return redirect("assessment_detail", new.id)


# --- Risk assessment tasks (model: Hazard) -------------------------------------

@login_required
def risk_tasks(request):
    """All risk assessment tasks of the current tenant, with their automatic status."""
    company = current_company(request)
    if company is None:
        return render(request, "risk/no_company.html")
    if not request.user.can_manage:
        raise Http404
    hazards = _with_lifecycle(list(_hazards_qs().filter(
        assessment__company=company, assessment__status=Assessment.Status.ACTIVE).order_by("assessment__title", "order")))
    f = request.GET.get("f", "all")
    counts = {}
    for h in hazards:
        counts[h.life_key] = counts.get(h.life_key, 0) + 1
    shown = hazards if f == "all" else [h for h in hazards if h.life_key == f]
    filters = [("all", _("All"), len(hazards))] + [
        (k, lifecycle_label(k), counts[k]) for k in
        ("overdue", "needs_action", "open", "in_progress", "complete", "draft") if counts.get(k)]
    return render(request, "risk/risk_tasks.html", {
        "company": company, "hazards": shown, "f": f, "filters": filters,
        "assessments": company.assessments.filter(status=Assessment.Status.ACTIVE),
    })


def _lists():
    out = {}
    for item in ListItem.objects.filter(is_active=True):
        out.setdefault(item.kind, []).append(item)
    return out


def _levels():
    """Likelihood and consequence levels ordered for the sliders: lowest risk on the left."""
    return list(LikelihoodLevel.objects.order_by("-order")), list(ConsequenceLevel.objects.order_by("-order"))


def _pick_many(request, field):
    values = [v.strip() for v in request.POST.getlist(field) if v.strip()]
    values += [v.strip() for v in request.POST.get(f"{field}_manual", "").splitlines() if v.strip()]
    return list(dict.fromkeys(values))


def _level_from_slider(request, name, levels):
    raw = request.POST.get(name, "")
    if raw.isdigit() and int(raw) < len(levels):
        return levels[int(raw)]
    return None


@login_required
def hazard_create(request, pk=None):
    if not request.user.can_manage:
        raise Http404
    company = current_company(request)
    a = get_assessment(request.user, pk) if pk else None
    if a and not can_edit_assessment(request.user, a):
        raise Http404
    return _risk_task_page(request, company=(a.company if a else company), assessment=a)


@login_required
def hazard_edit(request, pk, hazard_id):
    a = get_assessment(request.user, pk)
    if not request.user.can_manage:
        raise Http404
    hazard = get_object_or_404(a.hazards, pk=hazard_id)
    return _risk_task_page(request, company=a.company, assessment=a, hazard=hazard)


def _risk_task_page(request, company, assessment=None, hazard=None):
    likelihoods, consequences = _levels()
    lists = _lists()
    people = User.objects.filter(company=company, is_active=True)
    can_edit = assessment is None or can_edit_assessment(request.user, assessment)
    errors = []

    if request.method == "POST":
        if not can_edit:
            raise Http404
        a = assessment
        if a is None:
            a = company.assessments.filter(status=Assessment.Status.ACTIVE, id=request.POST.get("assessment")).first()
            if a is None:
                errors.append(_("Choose the assessment this hazard belongs to."))
        name = request.POST.get("hazard", "").strip()
        if name == "__manual__":
            name = request.POST.get("hazard_manual", "").strip()
        if not name:
            errors.append(_("Choose a hazard or type one in."))
        if not errors:
            is_new = hazard is None
            h = hazard or Hazard(assessment=a, order=a.hazards.count())
            h.name = name
            h.affected = "\n".join(_pick_many(request, "affected"))
            h.consequences = "\n".join(_pick_many(request, "consequence"))
            h.inherent_likelihood = _level_from_slider(request, "inherent_l", likelihoods)
            h.inherent_consequence = _level_from_slider(request, "inherent_c", consequences)
            h.residual_likelihood = _level_from_slider(request, "residual_l", likelihoods)
            h.residual_consequence = _level_from_slider(request, "residual_c", consequences)
            h.needs_rescore = False
            h.save()
            controls = _pick_many(request, "control")
            h.controls.all().delete()
            Control.objects.bulk_create([Control(hazard=h, text=t) for t in controls])

            created = 0
            for text, owner_id, due, remind in zip(request.POST.getlist("m_text"), request.POST.getlist("m_owner"),
                                                   request.POST.getlist("m_due"), request.POST.getlist("m_remind")):
                owner = people.filter(id=owner_id).first()
                text = text.strip()
                if not text or not owner:
                    continue
                task = Task.objects.create(
                    hazard=h, text=text, owner=owner,
                    due_date=datetime.strptime(due, "%Y-%m-%d").date() if due else None,
                    remind_days=int(remind) if remind.isdigit() else 3,
                )
                services.notify_assignment(task)
                created += 1

            if request.POST.get("save_to_lists") and request.user.is_staff:
                _save_new_entries(h, controls, [t.text for t in h.tasks.all()])
            if is_new:
                a.log(f"Hazard added: {h.name}")
            msg = _("Hazard saved.")
            if created:
                msg += " " + ngettext("%(n)d action assigned; the person responsible was notified.",
                                      "%(n)d actions assigned; the people responsible were notified.", created) % {"n": created}
            messages.success(request, msg)
            return redirect("assessment_detail", a.id)

    def idx(levels, level, default):
        for i, x in enumerate(levels):
            if level and x.id == level.id:
                return i
        return default

    mid_l, mid_c = len(likelihoods) // 2, len(consequences) // 2
    h = hazard
    inh_l = idx(likelihoods, h.inherent_likelihood if h else None, mid_l)
    inh_c = idx(consequences, h.inherent_consequence if h else None, mid_c)
    matrix = {f"{c.likelihood_id}-{c.consequence_id}": {
        "code": f"{c.likelihood.code}-{c.consequence.code}", "color": c.rating.color,
        "label": c.rating.label_el or c.rating.label, "label_en": c.rating.label,
        "action": c.rating.action_el or c.rating.action, "action_en": c.rating.action}
        for c in MatrixCell.objects.select_related("likelihood", "consequence", "rating")}
    list_texts = {k: {i.text for i in v} for k, v in lists.items()}
    affected = h.affected_list if h else []
    cons = h.consequence_list if h else []
    ctrls = [c.text for c in h.controls.all()] if h else []
    return render(request, "risk/risk_task_form.html", {
        "a": assessment, "company": company, "hazard": h, "errors": errors, "can_edit": can_edit,
        "assessments": company.assessments.filter(status=Assessment.Status.ACTIVE) if assessment is None else None,
        "lists": lists, "people": people,
        "hazard_manual": h.name if h and h.name not in list_texts.get("hazard", set()) else "",
        "affected_sel": affected, "affected_extra": [x for x in affected if x not in list_texts.get("affected", set())],
        "cons_sel": cons, "cons_extra": [x for x in cons if x not in list_texts.get("consequence", set())],
        "ctrl_sel": ctrls, "ctrl_extra": [x for x in ctrls if x not in list_texts.get("control", set())],
        "likelihoods": likelihoods, "consequences": consequences,
        "lmax": len(likelihoods) - 1, "cmax": len(consequences) - 1,
        "inh_l": inh_l, "inh_c": inh_c,
        "res_l": idx(likelihoods, h.residual_likelihood if h else None, inh_l),
        "res_c": idx(consequences, h.residual_consequence if h else None, inh_c),
        "rt_data": {"matrix": matrix, "levels": {
            "l": [{"id": x.id, "code": x.code, "label": x.label_el or x.label, "label_en": x.label} for x in likelihoods],
            "c": [{"id": x.id, "code": x.code, "label": x.label_el or x.label, "label_en": x.label} for x in consequences]}},
        "tasks": h.tasks.select_related("owner", "carried_to") if h else [],
        "default_due": (services.today() + timedelta(days=14)).isoformat(),
    })


def _save_new_entries(h, controls, measures):
    """Admins can tick "save new entries to the lists" so manual additions become dropdown options."""
    for kind, values in (("hazard", [h.name]), ("affected", h.affected_list),
                         ("consequence", h.consequence_list), ("control", controls), ("measure", measures)):
        for v in values:
            ListItem.objects.get_or_create(kind=kind, text=v[:300], defaults={"order": 999})


# --- Actions (model: Task) --------------------------------------------------------

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
        "filters": [("open", _("Open")), ("overdue", _("Overdue")), ("done", _("Done")), ("all", _("All"))],
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
            else:
                if form.cleaned_data["progress"] is not None and task.status != Task.Status.DONE:
                    task.progress = form.cleaned_data["progress"]
                # Lifecycle is detected automatically: any progress or evidence moves it to "in progress".
                if task.status != Task.Status.DONE:
                    task.status = Task.Status.IN_PROGRESS if (task.progress or text or photo) else Task.Status.OPEN
            task.save()
            if before != "ready" and services.hazard_state(task.hazard).state == "ready":
                a.log(f"{task.hazard.name}: required measures complete")
            if action == "complete":
                msg = _("Action marked complete.")
                if services.assessment_state(a).ready:
                    msg += " " + _("All actions of this assessment are complete. Review the risk levels and start a new version when ready.")
                messages.success(request, msg)
            else:
                messages.success(request, _("Update saved."))
            return redirect("task_detail", task.id)
    return render(request, "risk/task_detail.html", {
        "task": task, "a": task.assessment, "form": form, "can_update": can_update,
        "updates": task.updates.select_related("author"),
    })


@login_required
def evidence_photo(request, pk):
    """Photos are never public: they are served only after the same access check as their action."""
    upd = get_object_or_404(TaskUpdate.objects.select_related("task"), pk=pk)
    get_task(request.user, upd.task_id)
    if not upd.photo:
        raise Http404
    return FileResponse(upd.photo.open("rb"))


# --- Search -------------------------------------------------------------------------

@login_required
def search(request):
    q = request.GET.get("q", "").strip()
    company = current_company(request)
    results = {"risk_tasks": [], "assessments": [], "actions": [], "people": []}
    if len(q) >= 2 and company:
        user = request.user
        actions = Task.objects.filter(hazard__assessment__company=company, carried_to__isnull=True).filter(
            Q(text__icontains=q) | Q(hazard__name__icontains=q) | Q(owner__first_name__icontains=q)
            | Q(owner__last_name__icontains=q)).select_related("owner", "hazard__assessment")
        if not user.can_manage:
            actions = actions.filter(owner=user)
        results["actions"] = list(actions[:20])
        if user.can_manage:
            results["risk_tasks"] = _with_lifecycle(list(_hazards_qs().filter(
                assessment__company=company, assessment__status=Assessment.Status.ACTIVE).filter(
                Q(name__icontains=q) | Q(affected__icontains=q) | Q(consequences__icontains=q)
                | Q(controls__text__icontains=q)).distinct()[:20]))
            results["assessments"] = list(company.assessments.filter(Q(title__icontains=q) | Q(site__icontains=q))[:20])
            results["people"] = list(User.objects.filter(company=company, is_active=True).filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
                | Q(job_title__icontains=q))[:20])
    total = sum(len(v) for v in results.values())
    return render(request, "risk/search.html", {"q": q, "company": company, "total": total, **results})


# --- Lists, matrix, reports ---------------------------------------------------------

@login_required
def library(request):
    if not request.user.can_manage:
        raise Http404
    kinds = [(k, label) for k, label in ListItem.Kind.choices]
    lists = _lists()
    return render(request, "risk/library.html", {
        "groups": [{"kind": k, "label": label, "items": lists.get(k, [])} for k, label in kinds]})


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
    if not request.user.can_manage:
        raise Http404
    company = current_company(request)
    assessments = list(company.assessments.all()) if company else []
    if pk:
        a = get_assessment(request.user, pk)
    else:
        a = next((x for x in assessments if x.is_active), assessments[0] if assessments else None)
    if a is None:
        return render(request, "risk/report.html", {"company": company, "a": None})
    hazards = _with_lifecycle(list(_hazards_qs().filter(assessment=a)))
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
