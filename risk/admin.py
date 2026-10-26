"""
Admin panel at /admin/. Use it to:
  - edit the dropdown lists on the risk task form (List items)
  - change the scoring method (likelihood/consequence levels, ratings, matrix cells)
  - fix data by hand (assessments, risk tasks, actions)
"""
from django import forms
from django.contrib import admin

from .models import (
    Assessment, ConsequenceLevel, Control, Hazard, HistoryEntry, LikelihoodLevel, ListItem,
    MatrixCell, RiskRating, Task, TaskUpdate,
)


@admin.register(ListItem)
class ListItemAdmin(admin.ModelAdmin):
    list_display = ("text", "text_el", "kind", "order", "is_active")
    list_editable = ("text_el", "order", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("text", "text_el")


@admin.register(LikelihoodLevel)
class LikelihoodAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "label_el", "order")
    list_editable = ("label", "label_el", "order")


@admin.register(ConsequenceLevel)
class ConsequenceAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "label_el", "order")
    list_editable = ("label", "label_el", "order")


@admin.register(RiskRating)
class RiskRatingAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "label_el", "severity", "color")
    list_editable = ("label", "label_el", "severity", "color")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        # Show the browser's colour picker instead of a text box for the hex colour.
        if db_field.name == "color":
            kwargs["widget"] = forms.TextInput(attrs={"type": "color", "style": "width:64px;height:34px;padding:2px;cursor:pointer"})
        return super().formfield_for_dbfield(db_field, request, **kwargs)


@admin.register(MatrixCell)
class MatrixCellAdmin(admin.ModelAdmin):
    list_display = ("likelihood", "consequence", "rating")
    list_editable = ("rating",)
    list_filter = ("likelihood", "rating")


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
    fields = ("text", "owner", "due_date", "remind_days", "status", "progress", "carried_to")


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
