"""
Template helpers.

  {{ obj|tr }}         Greek label of a list item, likelihood, consequence or rating when the page is in Greek
  {{ "some text"|ltr }} translate a stored text (e.g. a hazard name) if it matches a list item
"""
import time

from django import template
from django.utils.translation import get_language

register = template.Library()

_cache = {"at": 0, "map": {}}


def _is_greek():
    return (get_language() or "en").startswith("el")


@register.filter
def tr(obj):
    if obj is None:
        return ""
    if _is_greek():
        for field in ("text_el", "label_el"):
            value = getattr(obj, field, "")
            if value:
                return value
    return getattr(obj, "text", None) or getattr(obj, "label", None) or str(obj)


@register.filter
def tr_action(rating):
    if rating is None:
        return ""
    return rating.action_el if _is_greek() and rating.action_el else rating.action


@register.filter
def ltr(text):
    """Stored English text → Greek list label (cached for 30 s)."""
    if not text or not _is_greek():
        return text
    if time.time() - _cache["at"] > 30:
        from risk.models import ListItem
        _cache["map"] = {i.text: i.text_el for i in ListItem.objects.exclude(text_el="")}
        _cache["at"] = time.time()
    return _cache["map"].get(text, text)
