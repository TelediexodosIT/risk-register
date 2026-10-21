from django.conf import settings

from . import services


def app_context(request):
    """Values available in every template: app name, company switcher, update count."""
    ctx = {"APP_NAME": settings.APP_NAME}
    user = getattr(request, "user", None)
    if user and user.is_authenticated and (not settings.REQUIRE_TWO_STEP or user.is_verified()):
        from .access import current_company
        company = current_company(request)
        ctx.update({
            "companies": user.visible_companies(),
            "current_company": company,
            "update_count": len(services.notifications(user, company)),
        })
    return ctx
