from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse


class RequireTwoStepMiddleware:
    """A signed-in user who hasn't entered their 6-digit code can only reach the sign-in pages."""

    ALLOWED = ("login", "otp_verify", "otp_setup", "logout")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (
            settings.REQUIRE_TWO_STEP
            and user.is_authenticated
            and not user.is_verified()
            and not request.path.startswith("/static/")
            and not request.path.startswith("/legal/")
            and request.path not in [reverse(n) for n in self.ALLOWED]
        ):
            return redirect("otp_verify")
        return self.get_response(request)
