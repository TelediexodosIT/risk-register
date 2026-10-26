from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView, TemplateView

admin.site.site_header = "Risk Register administration"
admin.site.site_title = "Risk Register admin"

urlpatterns = [
    # The admin uses the same sign-in (password + 6-digit code) as the app.
    path("admin/login/", RedirectView.as_view(url="/login/?next=/admin/", query_string=False)),
    path("admin/", admin.site.urls),
    path("i18n/", include("django.conf.urls.i18n")),  # language switch (set_language)
    # Public legal pages (no sign-in needed). Text lives in templates/legal/.
    path("legal/privacy/", TemplateView.as_view(template_name="legal/privacy.html"), name="legal_privacy"),
    path("legal/terms/", TemplateView.as_view(template_name="legal/terms.html"), name="legal_terms"),
    path("legal/cookies/", TemplateView.as_view(template_name="legal/cookies.html"), name="legal_cookies"),
    path("", include("accounts.urls")),
    path("", include("risk.urls")),
]
