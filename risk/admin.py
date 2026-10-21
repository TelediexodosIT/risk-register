"""
Admin panel at /admin/. Use it to:
  - change the scoring method (likelihood/consequence levels, ratings, matrix cells)
  - maintain the shared hazard library
  - fix data by hand (assessments, hazards, tasks)
"""
from django.contrib import admin

from .models import (
    Assessment, ConsequenceLevel, Control, ControlTemplate, Hazard, HazardTemplate, HistoryEntry,
    LikelihoodLevel, MatrixCell, MeasureTemplate, RiskRating, Task, TaskUpdate,
)


@admin.register(LikelihoodLevel)
class LikelihoodAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "order")
    list_editable = ("label", "order")


@admin.register(ConsequenceLevel)
class ConsequenceAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "order")
    list_editable = ("label", "order")


@admin.register(RiskRating)
class RiskRatingAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "severity", "color")
    list_editable = ("label", "severity", "color")


@admin.register(MatrixCell)
class MatrixCellAdmin(admin.ModelAdmin):
    list_display = ("likelihood", "consequence", "rating")
    list_editable = ("rating",)
    list_filter = ("likelihood", "rating")


class ControlTemplateInline(admin.TabularInline):
    model = ControlTemplate
    extra = 2
    verbose_name = "Existing control"
    verbose_name_plural = "Common existing controls"


class MeasureTemplateInline(admin.TabularInline):
    model = MeasureTemplate
    extra = 2
    verbose_name = "Additional measure"
    verbose_name_plural = "Suggested additional measures"


@admin.register(HazardTemplate)
class HazardTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "category")
    search_fields = ("name", "category")
    inlines = [ControlTemplateInline, MeasureTemplateInline]


class HazardInline(admin.TabularInline):
    model = Hazard
    extra = 0
    fields = ("name", "inherent_likelihood", "inherent_consequence", "residual_likelihood",
              "residual_consequence", "needs_rescore")
    show_change_link = True


class HistoryInline(admin.TabularInline):
    model = HistoryEntry
    extra = 0


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = ("title", "version", "company", "status", "created_at")
    list_filter = ("company", "status")
    search_fields = ("title", "site")
    inlines = [HazardInline, HistoryInline]


class ControlInline(admin.TabularInline):
    model = Control
    extra = 0


class TaskInline(admin.TabularInline):
    model = Task
    extra = 0
    fields = ("text", "owner", "due_date", "status", "progress", "carried_to")


@admin.register(Hazard)
class HazardAdmin(admin.ModelAdmin):
    list_display = ("name", "assessment")
    list_filter = ("assessment__company",)
    search_fields = ("name",)
    inlines = [ControlInline, TaskInline]


class TaskUpdateInline(admin.TabularInline):
    model = TaskUpdate
    extra = 0


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("text", "owner", "due_date", "status", "progress")
    list_filter = ("status", "hazard__assessment__company")
    search_fields = ("text",)
    inlines = [TaskUpdateInline]
