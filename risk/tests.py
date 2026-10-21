from django.core.management import call_command
from django.test import TestCase, override_settings

from accounts.models import User
from risk.models import Assessment, Task

PW = "DemoPass-2026"


@override_settings(REQUIRE_TWO_STEP=False)
class RiskFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", password=PW, stdout=open("/dev/null", "w"))

    def login(self, email):
        self.client.force_login(User.objects.get(email=email))

    def test_every_page_renders_for_consultant(self):
        self.login("ca@jupiterzone.com")
        for a in Assessment.objects.all():
            for tab in ("register", "tasks", "history"):
                self.assertEqual(self.client.get(f"/assessments/{a.id}/?tab={tab}").status_code, 200)
            self.assertEqual(self.client.get(f"/reports/{a.id}/").status_code, 200)
            h = a.hazards.first()
            self.assertEqual(self.client.get(f"/assessments/{a.id}/hazards/{h.id}/").status_code, 200)
        for url in ("/assessments/", "/tasks/", "/library/", "/matrix/", "/reports/", "/updates/",
                    "/assessments/new/", f"/assessments/{Assessment.objects.first().id}/hazards/new/?template=1"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_companies_cannot_see_each_other(self):
        self.login("andreas.pavlou@telediexodos.demo")
        other = Assessment.objects.filter(company__name="Jupiterzone").first()
        self.assertEqual(self.client.get(f"/assessments/{other.id}/").status_code, 404)
        self.assertNotContains(self.client.get(f"/assessments/?company={other.company_id}"), "Data centre operations")
        t = Task.objects.filter(hazard__assessment=other).first()
        self.assertEqual(self.client.get(f"/tasks/{t.id}/").status_code, 404)

    def test_member_sees_only_own_tasks(self):
        self.login("maria.kyriakou@telediexodos.demo")
        r = self.client.get("/tasks/?f=all")
        self.assertContains(r, "Check the route")
        self.assertNotContains(r, "Train staff in first aid")
        self.assertEqual(self.client.get("/assessments/new/").status_code, 404)

    def test_complete_tasks_then_new_version(self):
        self.login("andreas.pavlou@telediexodos.demo")
        a = Assessment.objects.get(company__name="Telediexodos")
        r = self.client.post(f"/assessments/{a.id}/reassess/")
        self.assertEqual(Assessment.objects.filter(company=a.company).count(), 1)  # not ready yet
        for t in Task.objects.filter(hazard__assessment=a).exclude(status="done"):
            self.client.post(f"/tasks/{t.id}/", {"action": "complete", "text": "Done"})
        self.client.post(f"/assessments/{a.id}/reassess/")
        a.refresh_from_db()
        self.assertEqual(a.status, "superseded")
        v2 = a.next_version
        self.assertEqual(v2.version, 2)
        self.assertTrue(all(h.needs_rescore for h in v2.hazards.all()))
        slips = v2.hazards.get(name="Slips, trips and falls")
        self.assertIn("Check the route for wet or obstructed areas before moving materials",
                      [c.text for c in slips.controls.all()])

    def test_add_hazard_with_measure_creates_task(self):
        self.login("andreas.pavlou@telediexodos.demo")
        a = Assessment.objects.get(company__name="Telediexodos")
        maria = User.objects.get(email="maria.kyriakou@telediexodos.demo")
        r = self.client.post(f"/assessments/{a.id}/hazards/new/", {
            "name": "Working at height", "affects_operator": "on", "control": ["Ladders inspected"],
            "inherent_likelihood": "1", "inherent_consequence": "1",
            "m_text": ["Buy a podium step"], "m_owner": [str(maria.id)], "m_due": ["2030-01-01"],
        })
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Task.objects.filter(text="Buy a podium step", owner=maria).exists())

    def test_cannot_assign_task_to_other_company(self):
        self.login("andreas.pavlou@telediexodos.demo")
        a = Assessment.objects.get(company__name="Telediexodos")
        outsider = User.objects.get(email="stelios.michael@jupiterzone.demo")
        self.client.post(f"/assessments/{a.id}/hazards/new/", {
            "name": "X", "m_text": ["Sneaky"], "m_owner": [str(outsider.id)], "m_due": [""]})
        self.assertFalse(Task.objects.filter(text="Sneaky").exists())
