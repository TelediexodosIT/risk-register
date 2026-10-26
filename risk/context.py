import hashlib

from django.conf import settings
from django.contrib.staticfiles import finders

_asset_version = None


def asset_version():
    """Short hash of app.css + app.js. Added to their URLs (?v=...) so browsers and
    Cloudflare fetch the new files after every update instead of a cached old copy."""
    global _asset_version
    if _asset_version is None:
        h = hashlib.sha1()
        for name in ("css/app.css", "js/app.js"):
            path = finders.find(name)
            if path:
                with open(path, "rb") as f:
                    h.update(f.read())
        _asset_version = h.hexdigest()[:10]
    return _asset_version

from . import services


def app_context(request):
    """Values available in every template: app name, company switcher, update count."""
    ctx = {"APP_NAME": settings.APP_NAME, "ASSET_V": asset_version(), "LEGAL": {
        "entity": settings.LEGAL_ENTITY, "address": settings.LEGAL_ADDRESS, "email": settings.LEGAL_EMAIL,
        "reg_no": settings.LEGAL_REG_NO, "updated": settings.LEGAL_UPDATED,
    }}
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
