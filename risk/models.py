"""
Data model, in the order a consultant works:

  Scoring method   LikelihoodLevel, ConsequenceLevel, RiskRating, MatrixCell
                   (all editable in the admin panel, so the method can change without code)
  Hazard library   HazardTemplate, with ControlTemplate and MeasureTemplate (shared by all companies)
  Assessment       one register for a company area/activity, versioned (v1, v2 ...)
    Hazard         one row of the register: who is affected, inherent risk, controls, residual risk
      Control      an existing control already in place
      Task         an additional measure, assigned to a person with a deadline
        TaskUpdate progress note, comment or photo evidence
    HistoryEntry   dated log of what happened to the assessment
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Company


# --- Scoring method ----------------------------------------------------------

class LikelihoodLevel(models.Model):
    code = models.CharField(max_length=5, unique=True, help_text="e.g. A")
    label = models.CharField(max_length=60, help_text="e.g. Very likely")
    order = models.PositiveSmallIntegerField(default=0, help_text="Lower comes first (most likely first).")

    class Meta:
        ordering = ["order", "code"]

    def __str__(self):
        return f"{self.code} · {self.label}"


class ConsequenceLevel(models.Model):
    code = models.CharField(max_length=5, unique=True, help_text="e.g. 1")
    label = models.CharField(max_length=60, help_text="e.g. Major / fatal")
    order = models.PositiveSmallIntegerField(default=0, help_text="Lower comes first (most severe first).")

    class Meta:
        ordering = ["order", "code"]

    def __str__(self):
        return f"{self.code} · {self.label}"


class RiskRating(models.Model):
    code = models.CharField(max_length=5, unique=True, help_text="e.g. H")
    label = models.CharField(max_length=40, help_text="e.g. High")
    severity = models.PositiveSmallIntegerField(help_text="0 = lowest. Used to tell if risk went up or down.")
    color = models.CharField(max_length=7, default="#888888", help_text="Hex colour, e.g. #c94c1a")
    action = models.TextField(blank=True, help_text="What this rating means for the work.")

    class Meta:
        ordering = ["severity"]

    def __str__(self):
        return self.label


class MatrixCell(models.Model):
    likelihood = models.ForeignKey(LikelihoodLevel, on_delete=models.CASCADE)
    consequence = models.ForeignKey(ConsequenceLevel, on_delete=models.CASCADE)
    rating = models.ForeignKey(RiskRating, on_delete=models.PROTECT)

    class Meta:
        unique_together = [("likelihood", "consequence")]
        ordering = ["likelihood__order", "consequence__order"]

    def __str__(self):
        return f"{self.likelihood.code}-{self.consequence.code} = {self.rating}"


def rating_for(likelihood, consequence):
    """Look up the rating for a likelihood + consequence pair. Returns None if not scored."""
    if not likelihood or not consequence:
        return None
    cell = MatrixCell.objects.select_related("rating").filter(
        likelihood=likelihood, consequence=consequence).first()
    return cell.rating if cell else None


# --- Hazard library (shared by every company) -------------------------------

class HazardTemplate(models.Model):
    name = models.CharField(max_length=150, unique=True)
    category = models.CharField(max_length=150, blank=True)
    consequences = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ControlTemplate(models.Model):
    hazard = models.ForeignKey(HazardTemplate, on_delete=models.CASCADE, related_name="controls")
    text = models.CharField(max_length=300)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.text


class MeasureTemplate(models.Model):
    hazard = models.ForeignKey(HazardTemplate, on_delete=models.CASCADE, related_name="measures")
    text = models.CharField(max_length=300)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.text


# --- Assessments ---------------------------------------------------------------

class Assessment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUPERSEDED = "superseded", "Superseded"

    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="assessments")
    title = models.CharField(max_length=150, help_text="Area or activity, e.g. Production floor")
    site = models.CharField(max_length=150, blank=True)
    version = models.PositiveIntegerField(default=1)
    previous = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="next_version")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    rule_percent = models.PositiveSmallIntegerField(
        default=100, help_text="A hazard is ready for reassessment when this % of its measures are complete.")
    created_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["company__name", "title", "-version"]

    def __str__(self):
        return f"{self.title} v{self.version}"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    def log(self, text):
        HistoryEntry.objects.create(assessment=self, text=text)

    def chain(self):
        """All versions of this assessment, oldest first."""
        first = self
        while first.previous_id:
            first = first.previous
        out, cur = [], first
        while cur:
            out.append(cur)
            cur = getattr(cur, "next_version", None)
        return out


class Hazard(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="hazards")
    template = models.ForeignKey(HazardTemplate, null=True, blank=True, on_delete=models.SET_NULL)
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=150, blank=True)
    affects_operator = models.BooleanField("Operator", default=True)
    affects_employees = models.BooleanField("Other employees", default=False)
    affects_third_parties = models.BooleanField("Third parties", default=False)
    consequences = models.TextField(blank=True)
    inherent_likelihood = models.ForeignKey(LikelihoodLevel, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    inherent_consequence = models.ForeignKey(ConsequenceLevel, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    residual_likelihood = models.ForeignKey(LikelihoodLevel, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    residual_consequence = models.ForeignKey(ConsequenceLevel, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    # Residual risk from the previous version, kept for the before/after comparison.
    previous_likelihood = models.ForeignKey(LikelihoodLevel, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    previous_consequence = models.ForeignKey(ConsequenceLevel, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    needs_rescore = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.name

    @property
    def inherent_rating(self):
        return rating_for(self.inherent_likelihood, self.inherent_consequence)

    @property
    def residual_rating(self):
        return rating_for(self.residual_likelihood, self.residual_consequence)

    @property
    def previous_rating(self):
        return rating_for(self.previous_likelihood, self.previous_consequence)

    @property
    def affected_labels(self):
        return [label for flag, label in (
            (self.affects_operator, "Operator"),
            (self.affects_employees, "Other employees"),
            (self.affects_third_parties, "Third parties"),
        ) if flag]


class Control(models.Model):
    """An existing control already in place for a hazard."""
    hazard = models.ForeignKey(Hazard, on_delete=models.CASCADE, related_name="controls")
    text = models.CharField(max_length=300)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.text


class Task(models.Model):
    """An additional measure, assigned to one person."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        DONE = "done", "Done"

    hazard = models.ForeignKey(Hazard, on_delete=models.CASCADE, related_name="tasks")
    text = models.CharField("Measure", max_length=300)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tasks")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    progress = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateField(null=True, blank=True)
    # Set when a new version was created while this task was still open; the copy lives in the new version.
    carried_to = models.ForeignKey(Assessment, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date", "id"]

    def __str__(self):
        return self.text

    @property
    def assessment(self):
        return self.hazard.assessment

    @property
    def is_live(self):
        return self.carried_to_id is None

    @property
    def is_overdue(self):
        return (self.is_live and self.status != self.Status.DONE and self.due_date
                and self.due_date < timezone.localdate())


def evidence_path(instance, filename):
    return f"evidence/{instance.task.hazard.assessment.company_id}/{instance.task_id}/{filename}"


class TaskUpdate(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="updates")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    text = models.TextField(blank=True)
    photo = models.ImageField(upload_to=evidence_path, blank=True)

    class Meta:
        ordering = ["created_at"]


class HistoryEntry(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name="history")
    created_at = models.DateTimeField(default=timezone.now)
    text = models.CharField(max_length=300)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name_plural = "history entries"
