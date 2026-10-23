from datetime import timedelta

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from risk.models import Assessment, Hazard, LikelihoodLevel, ListItem, Task
from risk.services import hazard_lifecycle, send_due_reminders

PW = "DemoPass-2026"


@override_settings(REQUIRE_TWO_STEP=False)
class RiskFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", password=PW, stdout=open("/dev/null", "w"))

    def login(self, email):
        self.client.force_login(User.objects.get(email=email))

    def test_every_page_renders_for_consultant_in_both_languages(self):
        self.login("ca@jupiterzone.com")
        for lang in ("en", "el"):
            self.client.post("/i18n/setlang/", {"language": lang, "next": "/"})
            for a in Assessment.objects.all():
                for tab in ("register", "tasks", "history"):
                    self.assertEqual(self.client.get(f"/assessments/{a.id}/?tab={tab}").status_code, 200)
                self.assertEqual(self.client.get(f"/reports/{a.id}/").status_code, 200)
                h = a.hazards.first()
                self.assertEqual(self.client.get(f"/assessments/{a.id}/hazards/{h.id}/").status_code, 200)
                self.assertEqual(self.client.get(f"/assessments/{a.id}/hazards/new/").status_code,
                                 200 if a.is_active else 404)  # superseded versions are read-only
            for url in ("/risk-tasks/", "/risk-tasks/new/", "/risk-tasks/?f=overdue", "/assessments/", "/tasks/",
                        "/library/", "/matrix/", "/reports/", "/updates/", "/assessments/new/", "/search/?q=first",
                        f"/tasks/{Task.objects.first().id}/"):
                self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get("/risk-tasks/"), "Εργασίες Εκτίμησης Κινδύνου")
        self.client.post("/i18n/setlang/", {"language": "en", "next": "/"})
        self.assertContains(self.client.get("/risk-tasks/"), "Risk Assessment Tasks")
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_tenant_switch(self):
        self.login("ca@jupiterzone.com")
        r = self.client.get("/?company=" + str(User.objects.get(email="andreas.pavlou@telediexodos.demo").company_id),
                            follow=True)
        self.assertContains(r, "Office and workshop")

    def test_companies_cannot_see_each_other(self):
        self.login("andreas.pavlou@telediexodos.demo")
        other = Assessment.objects.filter(company__name="Jupiterzone").first()
        self.assertEqual(self.client.get(f"/assessments/{other.id}/").status_code, 404)
        self.assertNotContains(self.client.get(f"/risk-tasks/?company={other.company_id}"), "Data centre operations")
        t = Task.objects.filter(hazard__assessment=other).first()
        self.assertEqual(self.client.get(f"/tasks/{t.id}/").status_code, 404)
        self.assertNotContains(self.client.get("/search/?q=server"), "Server room")

    def test_member_sees_only_own_actions(self):
        self.login("maria.kyriakou@telediexodos.demo")
        r = self.client.get("/tasks/?f=all")
        self.assertContains(r, "Check the route")
        self.assertNotContains(r, "Train staff in first aid")
        self.assertEqual(self.client.get("/assessments/new/").status_code, 404)
        self.assertEqual(self.client.get("/risk-tasks/").status_code, 404)

    def test_complete_actions_then_new_version(self):
        self.login("andreas.pavlou@telediexodos.demo")
        a = Assessment.objects.get(company__name="Telediexodos")
        for t in Task.objects.filter(hazard__assessment=a).exclude(status="done"):
            self.client.post(f"/tasks/{t.id}/", {"action": "complete", "text": "Done"})
        self.client.post(f"/assessments/{a.id}/reassess/")
        a.refresh_from_db()
        self.assertEqual(a.status, "superseded")
        v2 = a.next_version
        self.assertEqual(v2.version, 2)
        slips = v2.hazards.get(name="Slips, trips and falls")
        self.assertIn("Check the route for wet or obstructed areas before moving materials",
                      [c.text for c in slips.controls.all()])
        self.assertEqual(slips.affected_list, ["Operator", "Other employees"])

    def test_new_risk_task_with_lists_manual_entries_sliders_and_action(self):
        self.login("andreas.pavlou@telediexodos.demo")
        a = Assessment.objects.get(company__name="Telediexodos")
        maria = User.objects.get(email="maria.kyriakou@telediexodos.demo")
        mail.outbox = []
        r = self.client.post("/risk-tasks/new/", {
            "assessment": a.id, "hazard": "__manual__", "hazard_manual": "Working on a ladder",
            "affected": ["Operator", "Visitors"], "affected_manual": "Cleaning crew",
            "consequence": ["Falls and injury"], "consequence_manual": "",
            "inherent_l": "3", "inherent_c": "2",   # slider positions: most likely, consequence level 3 from the right
            "control": ["Equipment inspected periodically"], "control_manual": "Ladder checked before use",
            "residual_l": "1", "residual_c": "1",
            "m_text": ["Buy a podium step"], "m_owner": [str(maria.id)], "m_due": ["2030-01-01"], "m_remind": ["7"],
        })
        self.assertEqual(r.status_code, 302)
        h = Hazard.objects.get(name="Working on a ladder")
        self.assertEqual(h.affected_list, ["Operator", "Visitors", "Cleaning crew"])
        self.assertEqual(h.inherent_likelihood.code, "A")
        self.assertEqual([c.text for c in h.controls.all()], ["Equipment inspected periodically", "Ladder checked before use"])
        t = Task.objects.get(text="Buy a podium step")
        self.assertEqual((t.owner, t.remind_days), (maria, 7))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Νέα ενέργεια", mail.outbox[0].subject)
        self.assertEqual(hazard_lifecycle(h)[0], "open")

    def test_cannot_assign_action_to_other_tenant(self):
        self.login("andreas.pavlou@telediexodos.demo")
        a = Assessment.objects.get(company__name="Telediexodos")
        outsider = User.objects.get(email="stelios.michael@jupiterzone.demo")
        self.client.post(f"/assessments/{a.id}/hazards/new/", {
            "hazard": "Fire", "inherent_l": "0", "inherent_c": "0", "residual_l": "0", "residual_c": "0",
            "m_text": ["Sneaky"], "m_owner": [str(outsider.id)], "m_due": [""], "m_remind": ["3"]})
        self.assertTrue(Hazard.objects.filter(name="Fire", assessment=a).exists())
        self.assertFalse(Task.objects.filter(text="Sneaky").exists())

    def test_admin_can_save_manual_entries_to_lists(self):
        self.login("ca@jupiterzone.com")
        a = Assessment.objects.get(company__name="Telediexodos")
        self.client.post(f"/assessments/{a.id}/hazards/new/", {
            "hazard": "__manual__", "hazard_manual": "Noise from generator", "affected_manual": "Neighbours",
            "inherent_l": "1", "inherent_c": "1", "residual_l": "0", "residual_c": "0", "save_to_lists": "on"})
        self.assertTrue(ListItem.objects.filter(kind="hazard", text="Noise from generator").exists())
        self.assertTrue(ListItem.objects.filter(kind="affected", text="Neighbours").exists())

    def test_reminders_sent_once(self):
        t = Task.objects.filter(status="open", carried_to__isnull=True, hazard__assessment__status="active").first()
        today = timezone.localdate()
        t.due_date, t.remind_days = today + timedelta(days=2), 3
        t.save()
        mail.outbox = []
        sent = send_due_reminders(today)
        self.assertGreaterEqual(sent[0], 1)
        n = len(mail.outbox)
        send_due_reminders(today)
        self.assertEqual(len(mail.outbox), n)  # nothing sent twice
        self.assertTrue(any("Reminder" in m.subject for m in mail.outbox))
        call_command("send_reminders", stdout=open("/dev/null", "w"))

    def test_lifecycle_detects_overdue_and_complete(self):
        h = Hazard.objects.get(name="Delayed first aid")
        self.assertEqual(hazard_lifecycle(h)[0], "overdue")
        h2 = Hazard.objects.get(name="Manual handling", assessment__company__name="Telediexodos")
        self.assertEqual(hazard_lifecycle(h2)[0], "complete")
        self.assertEqual(LikelihoodLevel.objects.get(code="A").label_el, "Πολύ πιθανό")


@override_settings(REQUIRE_TWO_STEP=False)
class ManualReassessmentTests(TestCase):
    """The client asked: completing actions must never lower a risk level by itself."""

    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", password=PW, stdout=open("/dev/null", "w"))

    def test_completing_all_actions_does_not_change_risk_levels(self):
        self.client.force_login(User.objects.get(email="andreas.pavlou@telediexodos.demo"))
        a = Assessment.objects.get(company__name="Telediexodos")
        before = {h.id: (h.residual_likelihood_id, h.residual_consequence_id) for h in a.hazards.all()}
        for t in Task.objects.filter(hazard__assessment=a).exclude(status="done"):
            self.client.post(f"/tasks/{t.id}/", {"action": "complete"})
        after = {h.id: (h.residual_likelihood_id, h.residual_consequence_id) for h in a.hazards.all()}
        self.assertEqual(before, after)
        a.refresh_from_db()
        self.assertEqual(a.status, "active")  # no new version is created automatically

    def test_consultant_can_start_new_version_any_time(self):
        self.client.force_login(User.objects.get(email="andreas.pavlou@telediexodos.demo"))
        a = Assessment.objects.get(company__name="Telediexodos")
        self.assertTrue(Task.objects.filter(hazard__assessment=a).exclude(status="done").exists())
        self.client.post(f"/assessments/{a.id}/reassess/")
        a.refresh_from_db()
        self.assertEqual(a.status, "superseded")

    def test_staff_member_cannot_start_new_version(self):
        self.client.force_login(User.objects.get(email="maria.kyriakou@telediexodos.demo"))
        a = Assessment.objects.get(company__name="Telediexodos")
        self.assertEqual(self.client.post(f"/assessments/{a.id}/reassess/").status_code, 404)
