"""
Sign-in flow:
  1. /login/        email + password (failed attempts are counted by django-axes)
  2. /login/setup/  first sign-in only: scan a QR code into an authenticator app
     /login/verify/ every later sign-in: enter the 6-digit code
  3. signed in. Until step 2 is done, RequireTwoStepMiddleware blocks every other page.
"""
import base64
import io

import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice


def _next_url(request):
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return nxt
    return settings.LOGIN_REDIRECT_URL


@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated and getattr(request.user, "is_verified", lambda: False)():
        return redirect("home")
    error = None
    email = ""
    if request.method == "POST":
        email = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password", "")
        user = authenticate(request, username=email, password=password)
        if user is not None and user.is_active:
            login(request, user)
            request.session["next"] = _next_url(request)
            if not settings.REQUIRE_TWO_STEP:
                return redirect(request.session.pop("next", "home"))
            has_device = TOTPDevice.objects.filter(user=user, confirmed=True).exists()
            return redirect("otp_verify" if has_device else "otp_setup")
        # Same message whether the email exists or not, so accounts can't be guessed.
        error = _("Email or password is incorrect.")
    return render(request, "accounts/login.html", {"error": error, "email": email, "next": request.GET.get("next", "")})


def _verify_and_finish(request, device, token):
    if device.verify_token(token):
        otp_login(request, device)
        return redirect(request.session.pop("next", "home"))
    return None


@require_http_methods(["GET", "POST"])
def otp_verify(request):
    if not request.user.is_authenticated:
        return redirect("login")
    device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    if device is None:
        return redirect("otp_setup")
    error = None
    if request.method == "POST":
        allowed, _info = device.verify_is_allowed()
        if not allowed:
            error = _("Too many wrong codes. Wait a moment and try again.")
        else:
            done = _verify_and_finish(request, device, request.POST.get("token", "").replace(" ", ""))
            if done:
                return done
            error = _("That code is not valid. Check your authenticator app and try again.")
    return render(request, "accounts/otp_verify.html", {"error": error})


@require_http_methods(["GET", "POST"])
def otp_setup(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if TOTPDevice.objects.filter(user=request.user, confirmed=True).exists():
        return redirect("otp_verify")
    device, _created = TOTPDevice.objects.get_or_create(
        user=request.user, confirmed=False, defaults={"name": "Authenticator app"}
    )
    error = None
    if request.method == "POST":
        allowed, _info = device.verify_is_allowed()
        if not allowed:
            error = _("Too many wrong codes. Wait a few seconds and try again.")
        elif device.verify_token(request.POST.get("token", "").replace(" ", "")):
            device.confirmed = True
            device.save()
            otp_login(request, device)
            messages.success(request, _("Two-step verification is set up."))
            return redirect(request.session.pop("next", "home"))
        else:
            error = _("That code did not match. Make sure your phone's clock is correct and try again.")

    img = qrcode.make(device.config_url, image_factory=qrcode.image.svg.SvgPathImage, box_size=8)
    buf = io.BytesIO()
    img.save(buf)
    secret = base64.b32encode(device.bin_key).decode()
    return render(request, "accounts/otp_setup.html", {
        "qr_svg": buf.getvalue().decode(),
        "secret": " ".join(secret[i:i + 4] for i in range(0, len(secret), 4)),
        "error": error,
    })


def logout_view(request):
    logout(request)
    messages.info(request, _("You have been signed out."))
    return redirect("login")
