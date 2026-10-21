"""
Create demo companies, users and assessments so the app has something to show.

    python manage.py seed_demo --password 'Choose-A-Demo-Pass1'

Every demo user gets that password. Do NOT run this on a real customer install.
"""
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Company, User
from risk.models import (
    Assessment, ConsequenceLevel, Control, Hazard, HazardTemplate, HistoryEntry, LikelihoodLevel, Task, TaskUpdate,
)

COMPANIES = [
    ("Telediexodos", "IT managed services"),
    ("Jupiterzone", "Private cloud hosting"),
    ("Mindthegap", "ISO consultancy"),
]

# email, first, last, job title, role, company
USERS = [
    ("elena.markou@mindthegap.demo", "Elena", "Markou", "Lead consultant", "consultant", "Mindthegap"),
    ("sofia.ioannou@mindthegap.demo", "Sofia", "Ioannou", "Office manager", "safety_officer", "Mindthegap"),
    ("nikos.georgiou@mindthegap.demo", "Nikos", "Georgiou", "Administrator", "member", "Mindthegap"),
    ("andreas.pavlou@telediexodos.demo", "Andreas", "Pavlou", "Health & safety officer", "safety_officer", "Telediexodos"),
    ("maria.kyriakou@telediexodos.demo", "Maria", "Kyriakou", "Office manager", "member", "Telediexodos"),
    ("giorgos.loizou@telediexodos.demo", "Giorgos", "Loizou", "Field technician", "member", "Telediexodos"),
    ("eleni.christou@jupiterzone.demo", "Eleni", "Christou", "Health & safety officer", "safety_officer", "Jupiterzone"),
    ("stelios.michael@jupiterzone.demo", "Stelios", "Michael", "Data centre lead", "member", "Jupiterzone"),
]


def lvl(code_l, code_c):
    return LikelihoodLevel.objects.get(code=code_l), ConsequenceLevel.objects.get(code=code_c)


class Command(BaseCommand):
    help = "Create demo companies, users and assessments."

    def add_arguments(self, parser):
        parser.add_argument("--password", required=True, help="Password given to every demo user (min 10 characters).")

    @transaction.atomic
    def handle(self, *args, password, **opts):
        if len(password) < 10:
            raise CommandError("Use a password of at least 10 characters.")
        if Company.objects.filter(name="Telediexodos").exists():
            raise CommandError("Demo data already exists.")
        call_command("load_defaults")
        today = timezone.localdate()
        d = lambda n: today + timedelta(days=n)
        ago = lambda n: timezone.now() - timedelta(days=n)

        companies = {name: Company.objects.create(name=name, sector=sector) for name, sector in COMPANIES}
        users = {}
        for email, first, last, title, role, company in USERS:
            u = User.objects.create_user(email=email, password=password, first_name=first, last_name=last,
                                         job_title=title, role=role, company=companies[company])
            users[first] = u
        elena = users["Elena"]
        elena.is_staff = True
        elena.is_superuser = True
        elena.save()
        elena.managed_companies.set(companies.values())

        def hazard(a, template_name, aff, inh, res, n_controls, extra_controls=(), prev=None, rescore=False):
            t = HazardTemplate.objects.get(name=template_name)
            il, ic = lvl(*inh)
            rl, rc = lvl(*res)
            pl, pc = lvl(*prev) if prev else (None, None)
            h = Hazard.objects.create(
                assessment=a, template=t, name=t.name, category=t.category, consequences=t.consequences,
                affects_operator="op" in aff, affects_employees="emp" in aff, affects_third_parties="third" in aff,
                inherent_likelihood=il, inherent_consequence=ic, residual_likelihood=rl, residual_consequence=rc,
                previous_likelihood=pl, previous_consequence=pc, needs_rescore=rescore, order=a.hazards.count())
            texts = [c.text for c in t.controls.all()[:n_controls]] + list(extra_controls)
            Control.objects.bulk_create([Control(hazard=h, text=x) for x in texts])
            return h

        def task(h, text, owner, due, status="open", progress=0, note=None, done_days_ago=None):
            t = Task.objects.create(hazard=h, text=text, owner=owner, due_date=due, status=status, progress=progress,
                                    completed_at=d(-done_days_ago) if done_days_ago is not None else None)
            if note:
                TaskUpdate.objects.create(task=t, author=owner, text=note)
            return t

        def assessment(company, title, site, version, created_days_ago, rule=100, previous=None, status="active"):
            a = Assessment.objects.create(company=company, title=title, site=site, version=version, previous=previous,
                                          rule_percent=rule, status=status, created_at=ago(created_days_ago), created_by=elena)
            return a

        # Telediexodos: one active assessment, partly done
        a1 = assessment(companies["Telediexodos"], "Office and workshop", "Head office", 1, 21)
        HistoryEntry.objects.create(assessment=a1, created_at=ago(21), text="Version 1 created")
        andreas, maria, giorgos = users["Andreas"], users["Maria"], users["Giorgos"]
        h = hazard(a1, "Slips, trips and falls", ["op", "emp"], "C3", "D4", 4)
        task(h, "Check the route for wet or obstructed areas before moving materials", maria, d(-3), "done", 100,
             "Added to the morning checklist. Signed off daily.", 4)
        h = hazard(a1, "Unsuitable work environment", ["op"], "B4", "C4", 7)
        task(h, "Install thermometers and hygrometers in storage areas", giorgos, d(5), "in_progress", 40, "Two units ordered, one installed.")
        task(h, "Rotate tasks and schedule deliveries in the morning during heatwaves", andreas, d(12))
        h = hazard(a1, "Delayed first aid", ["op", "emp", "third"], "B4", "C3", 1)
        task(h, "Train staff in first aid and keep certificates current", andreas, d(-2))
        task(h, "Check first-aid kit contents against legal requirements and restock", andreas, d(7))
        h = hazard(a1, "Manual handling", ["op", "emp"], "B3", "C4", 2)
        task(h, "Deliver manual handling training to all staff", andreas, d(-6), "done", 100, "Training delivered to 14 staff.", 6)
        task(h, "Move heavy items to waist-height storage", giorgos, d(-1), "done", 100, "Shelving moved in the store room.", 2)

        # Jupiterzone: v1 superseded, v2 active
        eleni, stelios = users["Eleni"], users["Stelios"]
        a2 = assessment(companies["Jupiterzone"], "Data centre operations", "Data centre", 1, 90, status="superseded")
        for days, text in ((90, "Version 1 created"), (32, "All required measures complete"), (30, "Superseded by version 2")):
            HistoryEntry.objects.create(assessment=a2, created_at=ago(days), text=text)
        h = hazard(a2, "Server room working conditions", ["op", "emp"], "B3", "C3", 3)
        task(h, "Provide hearing protection at the server room entrance", stelios, d(-40), "done", 100, None, 41)
        h = hazard(a2, "Electrical equipment", ["op", "emp"], "C2", "C3", 2)
        task(h, "Test and label portable electrical equipment", eleni, d(-35), "done", 100, None, 36)
        task(h, "Replace damaged extension leads", stelios, d(-35), "done", 100, None, 33)

        a3 = assessment(companies["Jupiterzone"], "Data centre operations", "Data centre", 2, 30, rule=80, previous=a2)
        for days, text in ((30, "Version 2 created from version 1"), (12, "Hazard added: Manual handling")):
            HistoryEntry.objects.create(assessment=a3, created_at=ago(days), text=text)
        h = hazard(a3, "Server room working conditions", ["op", "emp"], "B3", "D3", 3,
                   ["Provide hearing protection at the server room entrance"], prev="C3")
        task(h, "Install floor-tile lifters and mark open tiles", stelios, d(10), "in_progress", 60, "Lifters bought. Marking tape on order.")
        hazard(a3, "Electrical equipment", ["op", "emp"], "C2", "D3", 2,
               ["Test and label portable electrical equipment", "Replace damaged extension leads"], prev="C3")
        h = hazard(a3, "Manual handling", ["op"], "B3", "C4", 1)
        task(h, "Deliver manual handling training to all staff", eleni, d(20))
        task(h, "Use a server lift for every rack install", stelios, d(-5), "done", 100, "Lift in use since last week.", 6)

        # Mindthegap: their own office
        sofia, nikos = users["Sofia"], users["Nikos"]
        a4 = assessment(companies["Mindthegap"], "Head office", "Head office", 1, 10)
        HistoryEntry.objects.create(assessment=a4, created_at=ago(10), text="Version 1 created")
        h = hazard(a4, "Display screen equipment", ["op", "emp"], "C3", "C4", 2)
        task(h, "Complete a workstation assessment for each employee", nikos, d(9))
        h = hazard(a4, "Low morale and work stress", ["op", "emp"], "C3", "C4", 1)
        task(h, "Run an anonymous staff wellbeing survey", sofia, d(-1))

        self.stdout.write(self.style.SUCCESS(
            f"Demo data created: {len(COMPANIES)} companies, {len(USERS)} users. "
            f"Sign in as elena.markou@mindthegap.demo (consultant + admin) with the password you chose."))
