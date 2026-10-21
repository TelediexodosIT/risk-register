from django.core.management.base import BaseCommand
from django.db import transaction

from risk import defaults
from risk.models import ConsequenceLevel, LikelihoodLevel, ListItem, MatrixCell, RiskRating


def _fill_greek(obj, field, value):
    """Add a Greek label only if it is still empty, so edits made in the admin are kept."""
    if value and not getattr(obj, field):
        setattr(obj, field, value)
        obj.save(update_fields=[field])


class Command(BaseCommand):
    help = "Load the default scoring matrix and dropdown lists. Safe to run again: existing items are left alone."

    @transaction.atomic
    def handle(self, *args, **opts):
        for i, (code, label, label_el) in enumerate(defaults.LIKELIHOOD):
            obj, _ = LikelihoodLevel.objects.get_or_create(code=code, defaults={"label": label, "order": i})
            _fill_greek(obj, "label_el", label_el)
        for i, (code, label, label_el) in enumerate(defaults.CONSEQUENCE):
            obj, _ = ConsequenceLevel.objects.get_or_create(code=code, defaults={"label": label, "order": i})
            _fill_greek(obj, "label_el", label_el)
        for code, label, label_el, sev, color, action, action_el in defaults.RATINGS:
            obj, _ = RiskRating.objects.get_or_create(
                code=code, defaults={"label": label, "severity": sev, "color": color, "action": action})
            _fill_greek(obj, "label_el", label_el)
            _fill_greek(obj, "action_el", action_el)
        for l_code, row in defaults.MATRIX.items():
            for (c_code, _, _), r_code in zip(defaults.CONSEQUENCE, row):
                MatrixCell.objects.get_or_create(
                    likelihood=LikelihoodLevel.objects.get(code=l_code),
                    consequence=ConsequenceLevel.objects.get(code=c_code),
                    defaults={"rating": RiskRating.objects.get(code=r_code)},
                )
        added = 0
        for kind, items in defaults.LISTS.items():
            for i, (text, text_el) in enumerate(items):
                obj, created = ListItem.objects.get_or_create(kind=kind, text=text, defaults={"text_el": text_el, "order": i})
                added += created
                _fill_greek(obj, "text_el", text_el)
        self.stdout.write(self.style.SUCCESS(f"Matrix ready. {added} list item(s) added."))
