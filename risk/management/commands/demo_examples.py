"""
Add a second assessment (area) to each demo company, so the Hazards page shows
hazards from more than one assessment side by side.

    docker compose exec web python manage.py demo_examples

Safe to run again: an area that already exists is skipped. Demo installs only.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Company, User
from risk.models import Assessment, ConsequenceLevel, Control, Hazard, HistoryEntry, LikelihoodLevel, Task, TaskUpdate

# company: (area, site, [(hazard, who, consequences, inherent, residual, controls, [(action, owner email, due in days, status, note)])])
EXAMPLES = {
    "Telediexodos": ("Warehouse", "Head office", [
        ("Forklift and vehicle movement", ["Operator", "Other employees", "Visitors"], ["Crush injuries"], "A2", "B3",
         ["Only licensed operators drive forklifts", "Pedestrian walkways marked"],
         [("Fit convex mirrors at blind corners", "giorgos.loizou@telediexodos.demo", -4, "open", None)]),
        ("Electrical equipment", ["Operator"], ["Electric shock and burns"], "C2", "C3",
         ["Equipment inspected periodically"],
         [("Test and label portable electrical equipment", "andreas.pavlou@telediexodos.demo", 9, "in_progress",
           "Half of the equipment tested and labelled.")]),
    ]),
    "Jupiterzone": ("Office", "Larnaca office", [
        ("Display screen equipment", ["Operator"], ["Eye strain", "Back injury and musculoskeletal strain"], "B3", "C4",
         ["Adjustable chairs provided"],
         [("Complete a workstation assessment for each employee", "eleni.christou@jupiterzone.demo", 12, "open", None)]),
        ("Fire", ["Operator", "Other employees", "Visitors"], ["Worsened injury or death"], "C1", "D3",
         ["Emergency numbers displayed"], []),
    ]),
    "Mindthegap": ("Client site visits", "Various client sites", [
        ("Slips, trips and falls", ["Operator"], ["Falls and injury", "Sprains and fractures"], "C3", "C4",
         ["Staff wear anti-slip footwear"],
         [("Check the route for wet or obstructed areas before moving materials", "nikos.georgiou@mindthegap.demo", 6,
           "open", None)]),
    ]),
}


def _lvl(code):
    return LikelihoodLevel.objects.get(code=code[0]), ConsequenceLevel.objects.get(code=code[1:])


class Command(BaseCommand):
    help = "Add a second demo assessment per company (demo installs only). Safe to run again."

    @transaction.atomic
    def handle(self, *args, **opts):
        today = timezone.localdate()
        added = 0
        for company_name, (area, site, hazards) in EXAMPLES.items():
            company = Company.objects.filter(name=company_name).first()
            if company is None or company.assessments.filter(title=area).exists():
                continue
            a = Assessment.objects.create(company=company, title=area, site=site, version=1,
                                          created_at=timezone.now() - timedelta(days=7))
            HistoryEntry.objects.create(assessment=a, text="Version 1 created")
            for i, (name, who, cons, inh, res, controls, actions) in enumerate(hazards):
                il, ic = _lvl(inh)
                rl, rc = _lvl(res)
                h = Hazard.objects.create(assessment=a, name=name, order=i, affected="\n".join(who),
                                          consequences="\n".join(cons), inherent_likelihood=il, inherent_consequence=ic,
                                          residual_likelihood=rl, residual_consequence=rc)
                Control.objects.bulk_create([Control(hazard=h, text=c) for c in controls])
                for text, email, due, status, note in actions:
                    owner = User.objects.filter(email=email).first()
                    if owner is None:
                        continue
                    t = Task.objects.create(hazard=h, text=text, owner=owner, due_date=today + timedelta(days=due),
                                            status=status, progress=50 if status == "in_progress" else 0)
                    if note:
                        TaskUpdate.objects.create(task=t, author=owner, text=note)
            added += 1
        self.stdout.write(self.style.SUCCESS(f"{added} demo assessment(s) added."))
