from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "Risk Register administration"
admin.site.site_title = "Risk Register admin"

urlpatterns = [
    # The admin uses the same sign-in (password + 6-digit code) as the app.
    path("admin/login/", RedirectView.as_view(url="/login/?next=/admin/", query_string=False)),
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("risk.urls")),
]
