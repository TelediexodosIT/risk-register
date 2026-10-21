from django.core.management.base import BaseCommand
from django.db import transaction

from risk import defaults
from risk.models import (
    ConsequenceLevel, ControlTemplate, HazardTemplate, LikelihoodLevel, MatrixCell, MeasureTemplate, RiskRating,
)


class Command(BaseCommand):
    help = "Load the default scoring matrix and hazard library. Safe to run again: existing items are left alone."

    @transaction.atomic
    def handle(self, *args, **opts):
        for i, (code, label) in enumerate(defaults.LIKELIHOOD):
            LikelihoodLevel.objects.get_or_create(code=code, defaults={"label": label, "order": i})
        for i, (code, label) in enumerate(defaults.CONSEQUENCE):
            ConsequenceLevel.objects.get_or_create(code=code, defaults={"label": label, "order": i})
        for code, label, sev, color, action in defaults.RATINGS:
            RiskRating.objects.get_or_create(code=code, defaults={"label": label, "severity": sev, "color": color, "action": action})
        for l_code, row in defaults.MATRIX.items():
            for c_code, r_code in zip([c for c, _ in defaults.CONSEQUENCE], row):
                MatrixCell.objects.get_or_create(
                    likelihood=LikelihoodLevel.objects.get(code=l_code),
                    consequence=ConsequenceLevel.objects.get(code=c_code),
                    defaults={"rating": RiskRating.objects.get(code=r_code)},
                )
        added = 0
        for name, category, consequences, controls, measures in defaults.LIBRARY:
            h, created = HazardTemplate.objects.get_or_create(
                name=name, defaults={"category": category, "consequences": consequences})
            if created:
                added += 1
                ControlTemplate.objects.bulk_create([ControlTemplate(hazard=h, text=t) for t in controls])
                MeasureTemplate.objects.bulk_create([MeasureTemplate(hazard=h, text=t) for t in measures])
        self.stdout.write(self.style.SUCCESS(f"Matrix ready. {added} hazard(s) added to the library."))
