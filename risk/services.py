"""
Business rules in one place:
  - hazard_state / assessment_state: derived status from task completion
  - create_next_version: the "Start version N+1" button
  - notify_assignment: email to the person responsible for a new task
"""
import math
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Assessment, Control, Hazard, Task


@dataclass
class HazardState:
    done: int
    total: int
    required: int

    @property
    def state(self):
        if self.total == 0:
            return "none"
        return "ready" if self.done >= self.required else "pending"


def hazard_state(hazard):
    tasks = [t for t in hazard.tasks.all() if t.is_live]
    done = sum(1 for t in tasks if t.status == Task.Status.DONE)
    required = math.ceil(len(tasks) * hazard.assessment.rule_percent / 100)
    return HazardState(done=done, total=len(tasks), required=required)


@dataclass
class AssessmentState:
    total: int
    done: int
    overdue: int
    ready: bool
    rescore: bool
    superseded: bool = False

    @property
    def label(self):
        return self.key[1]

    @property
    def key(self):
        if self.superseded:
            return ("muted", "Superseded")
        if self.rescore:
            return ("warn", "Re-score needed")
        if self.ready:
            return ("good", "Ready for reassessment")
        if self.total == 0:
            return ("muted", "No open actions")
        return ("info", "Measures in progress")


def assessment_state(assessment):
    hazards = list(assessment.hazards.all())
    states = [hazard_state(h) for h in hazards]
    tasks = [t for h in hazards for t in h.tasks.all() if t.is_live]
    with_tasks = [s for s in states if s.total]
    st = AssessmentState(
        total=len(tasks),
        done=sum(1 for t in tasks if t.status == Task.Status.DONE),
        overdue=sum(1 for t in tasks if t.is_overdue),
        ready=assessment.is_active and bool(with_tasks) and all(s.state == "ready" for s in with_tasks),
        rescore=any(h.needs_rescore for h in hazards),
        superseded=not assessment.is_active,
    )
    return st


def rating_counts(hazards, which):
    """Count hazards per rating, for the coloured distribution bars. which = 'inherent' or 'residual'."""
    counts = {}
    for h in hazards:
        r = getattr(h, f"{which}_rating")
        if r:
            counts.setdefault(r.id, {"rating": r, "count": 0})["count"] += 1
    return sorted(counts.values(), key=lambda x: -x["rating"].severity)


@transaction.atomic
def create_next_version(old, user):
    """
    Lock the current version as a record and start the next one:
      - completed measures become existing controls
      - open measures are copied forward (the original is marked 'carried to vN')
      - each hazard keeps its old residual risk for comparison and is flagged for re-scoring
    """
    new = Assessment.objects.create(
        company=old.company, title=old.title, site=old.site, version=old.version + 1,
        previous=old, rule_percent=old.rule_percent, created_by=user,
    )
    for h in old.hazards.all():
        tasks = list(h.tasks.filter(carried_to__isnull=True))
        done = [t for t in tasks if t.status == Task.Status.DONE]
        nh = Hazard.objects.create(
            assessment=new, template=h.template, name=h.name, category=h.category,
            affects_operator=h.affects_operator, affects_employees=h.affects_employees,
            affects_third_parties=h.affects_third_parties, consequences=h.consequences,
            inherent_likelihood=h.inherent_likelihood, inherent_consequence=h.inherent_consequence,
            residual_likelihood=h.residual_likelihood, residual_consequence=h.residual_consequence,
            previous_likelihood=h.residual_likelihood, previous_consequence=h.residual_consequence,
            needs_rescore=bool(done), order=h.order,
        )
        texts = [c.text for c in h.controls.all()]
        texts += [t.text for t in done if t.text not in texts]
        Control.objects.bulk_create([Control(hazard=nh, text=t) for t in texts])
        for t in tasks:
            if t.status != Task.Status.DONE:
                Task.objects.create(hazard=nh, text=t.text, owner=t.owner, due_date=t.due_date,
                                    status=t.status, progress=t.progress)
                t.carried_to = new
                t.save(update_fields=["carried_to"])
    old.status = Assessment.Status.SUPERSEDED
    old.save(update_fields=["status"])
    old.log(f"Superseded by version {new.version}")
    new.log(f"Version {new.version} created from version {old.version}")
    return new


def notify_assignment(task):
    """Email the person responsible. Uses the console backend until SMTP is set in .env."""
    if not task.owner.email:
        return
    url = settings.SITE_URL.rstrip("/") + reverse("task_detail", args=[task.id])
    due = task.due_date.strftime("%d %b %Y") if task.due_date else "no deadline"
    send_mail(
        subject=f"New task: {task.text[:80]}",
        message=(
            f"Hello {task.owner.first_name or ''},\n\n"
            f"You have been assigned a safety measure.\n\n"
            f"Measure:    {task.text}\n"
            f"Hazard:     {task.hazard.name}\n"
            f"Assessment: {task.assessment}\n"
            f"Deadline:   {due}\n\n"
            f"Open it here: {url}\n"
        ),
        from_email=None,
        recipient_list=[task.owner.email],
        fail_silently=True,
    )


def today():
    return timezone.localdate()


def notifications(user, company):
    """
    Kept deliberately quiet: managers see assessment-level updates only (individual task
    changes roll up into the assessment); everyone sees the open tasks assigned to them.
    """
    items = []
    if company is None:
        return items
    if user.can_manage:
        for a in company.assessments.filter(status=Assessment.Status.ACTIVE):
            st = assessment_state(a)
            if st.ready:
                items.append({"title": "Ready for reassessment", "detail": f"{a}: the required measures are complete.",
                              "url": reverse("assessment_detail", args=[a.id])})
            if st.overdue:
                items.append({"title": f"{st.overdue} overdue task{'s' if st.overdue > 1 else ''}", "detail": str(a),
                              "url": reverse("assessment_detail", args=[a.id]) + "?tab=tasks"})
    for t in Task.objects.filter(owner=user, carried_to__isnull=True, hazard__assessment__company=company).exclude(
            status=Task.Status.DONE).select_related("hazard__assessment"):
        items.append({"title": "Overdue task" if t.is_overdue else "Assigned to you", "detail": t.text,
                      "url": reverse("task_detail", args=[t.id])})
    return items
