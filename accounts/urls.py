from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("login/verify/", views.otp_verify, name="otp_verify"),
    path("login/setup/", views.otp_setup, name="otp_setup"),
    path("logout/", views.logout_view, name="logout"),
    # Forgot password: Django's built-in, secure reset flow (one-time link by email, expires after
    # PASSWORD_RESET_TIMEOUT). Two-step verification is still required after resetting.
    path("login/forgot/", auth_views.PasswordResetView.as_view(
        template_name="accounts/password_reset_form.html",
        email_template_name="accounts/password_reset_email.txt",
        subject_template_name="accounts/password_reset_subject.txt",
    ), name="password_reset"),
    path("login/forgot/sent/", auth_views.PasswordResetDoneView.as_view(
        template_name="accounts/password_reset_done.html"), name="password_reset_done"),
    path("login/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html"), name="password_reset_confirm"),
    path("login/reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"), name="password_reset_complete"),
]
