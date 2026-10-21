from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Company, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "sector", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "company", "role", "is_active")
    list_filter = ("role", "company", "is_active")
    search_fields = ("email", "first_name", "last_name")
    filter_horizontal = ("managed_companies", "groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Person", {"fields": ("first_name", "last_name", "job_title")}),
        ("Access", {"fields": ("company", "role", "managed_companies", "is_active")}),
        ("Admin panel", {"classes": ("collapse",), "fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"classes": ("collapse",), "fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": (
            "email", "first_name", "last_name", "job_title", "company", "role", "password1", "password2")}),
    )
