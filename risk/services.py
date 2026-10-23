"""
Business rules in one place:
  - hazard_state / assessment_state: derived status from task completion
  - create_next_version: the "Start version N+1" button
  - notify_assignment: email to the person responsible for a new task
"""
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_noop, ngettext

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
    required = len(tasks)  # every action counts; review of the risk level is always done by a person
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
            return ("muted", gettext_noop("Superseded"))
        if self.rescore:
            return ("warn", gettext_noop("Re-score needed"))
        if self.ready:
            return ("good", gettext_noop("Actions complete – review"))
        if self.total == 0:
            return ("muted", gettext_noop("No open actions"))
        return ("info", gettext_noop("Measures in progress"))


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
        previous=old, created_by=user,
    )
    for h in old.hazards.all():
        tasks = list(h.tasks.filter(carried_to__isnull=True))
        done = [t for t in tasks if t.status == Task.Status.DONE]
        nh = Hazard.objects.create(
            assessment=new, name=h.name, category=h.category,
            affected=h.affected, consequences=h.consequences,
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
                                    status=t.status, progress=t.progress, remind_days=t.remind_days,
                                    reminder_sent_on=t.reminder_sent_on, overdue_sent_on=t.overdue_sent_on)
                t.carried_to = new
                t.save(update_fields=["carried_to"])
    old.status = Assessment.Status.SUPERSEDED
    old.save(update_fields=["status"])
    old.log(f"Superseded by version {new.version}")
    new.log(f"Version {new.version} created from version {old.version}")
    return new


def _send_action_email(task, subject_en, subject_el, intro_en, intro_el):
    """One bilingual email (English, then Greek) to the person responsible for an action."""
    if not task.owner.email:
        return
    url = settings.SITE_URL.rstrip("/") + reverse("task_detail", args=[task.id])
    due = task.due_date.strftime("%d/%m/%Y") if task.due_date else "-"
    send_mail(
        subject=f"{subject_en} / {subject_el}: {task.text[:70]}",
        message=(
            f"Hello {task.owner.first_name or ''},\n\n{intro_en}\n\n"
            f"Action:     {task.text}\n"
            f"Hazard:     {task.hazard.name}\n"
            f"Assessment: {task.assessment}\n"
            f"Deadline:   {due}\n\n"
            f"Open it here: {url}\n\n"
            f"----------------------------------------\n\n"
            f"Γεια σας {task.owner.first_name or ''},\n\n{intro_el}\n\n"
            f"Ενέργεια:     {task.text}\n"
            f"Κίνδυνος:     {task.hazard.name}\n"
            f"Εκτίμηση:     {task.assessment}\n"
            f"Προθεσμία:    {due}\n\n"
            f"Άνοιγμα: {url}\n"
        ),
        from_email=None,
        recipient_list=[task.owner.email],
        fail_silently=True,
    )


def notify_assignment(task):
    """Sent when an action is assigned. Uses the console backend until SMTP works (see .env)."""
    _send_action_email(task, "New action", "Νέα ενέργεια",
                       "You have been assigned a safety action.",
                       "Σας έχει ανατεθεί μια ενέργεια ασφάλειας.")


def send_due_reminders(now=None):
    """
    Called every hour by the scheduler container (manage.py send_reminders). Sends at most:
      - one reminder `remind_days` before the deadline
      - one overdue notice on the first day past the deadline, then one a week
    Returns (reminders, overdue_notices) sent.
    """
    today_ = now or today()
    sent = [0, 0]
    open_tasks = Task.objects.filter(
        carried_to__isnull=True, due_date__isnull=False, hazard__assessment__status=Assessment.Status.ACTIVE,
    ).exclude(status=Task.Status.DONE).select_related("owner", "hazard__assessment")
    for t in open_tasks:
        days_left = (t.due_date - today_).days
        if 0 <= days_left <= t.remind_days and t.remind_days and not t.reminder_sent_on:
            _send_action_email(t, "Reminder", "Υπενθύμιση",
                               f"This action is due in {days_left} day(s).",
                               f"Η προθεσμία για αυτή την ενέργεια λήγει σε {days_left} ημέρα(ες).")
            t.reminder_sent_on = today_
            t.save(update_fields=["reminder_sent_on"])
            sent[0] += 1
        elif days_left < 0 and (not t.overdue_sent_on or (today_ - t.overdue_sent_on).days >= 7):
            _send_action_email(t, "Overdue", "Εκπρόθεσμη",
                               f"This action is {-days_left} day(s) overdue.",
                               f"Αυτή η ενέργεια έχει καθυστέρηση {-days_left} ημέρα(ες).")
            t.overdue_sent_on = today_
            t.save(update_fields=["overdue_sent_on"])
            sent[1] += 1
    return tuple(sent)


def hazard_lifecycle(hazard):
    """
    Status of a risk assessment task, worked out automatically (never typed by hand):
      archived     the assessment version was superseded
      draft        inherent risk not scored yet
      needs_action residual risk is High/Extreme and no additional measures are set
      overdue      at least one action is past its deadline
      complete     no actions needed, or all actions done (the risk level is then reviewed by a person)
      in_progress  some actions done or started
      open         actions assigned, none started
    Returns (key, css class).
    """
    if not hazard.assessment.is_active:
        return "archived", "muted"
    if not hazard.inherent_rating:
        return "draft", "muted"
    st = hazard_state(hazard)
    tasks = [t for t in hazard.tasks.all() if t.is_live]
    if not tasks:
        res = hazard.residual_rating or hazard.inherent_rating
        return ("needs_action", "warn") if res and res.severity >= 2 else ("complete", "good")
    if any(t.is_overdue for t in tasks):
        return "overdue", "bad"
    if st.state == "ready":
        return "complete", "good"
    if st.done or any(t.progress for t in tasks):
        return "in_progress", "info"
    return "open", "muted"


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
                items.append({"title": _("Actions complete – review"), "detail": _("%(a)s: all actions are complete. Review the risk levels.") % {"a": a},
                              "url": reverse("assessment_detail", args=[a.id])})
            if st.overdue:
                items.append({"title": ngettext("%(n)d overdue action", "%(n)d overdue actions", st.overdue) % {"n": st.overdue},
                              "detail": str(a),
                              "url": reverse("assessment_detail", args=[a.id]) + "?tab=tasks"})
    for t in Task.objects.filter(owner=user, carried_to__isnull=True, hazard__assessment__company=company).exclude(
            status=Task.Status.DONE).select_related("hazard__assessment"):
        items.append({"title": _("Overdue action") if t.is_overdue else _("Assigned to you"), "detail": t.text,
                      "url": reverse("task_detail", args=[t.id])})
    return items
