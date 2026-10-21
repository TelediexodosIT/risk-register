from django.urls import path

from . import views

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("login/verify/", views.otp_verify, name="otp_verify"),
    path("login/setup/", views.otp_setup, name="otp_setup"),
    path("logout/", views.logout_view, name="logout"),
]
