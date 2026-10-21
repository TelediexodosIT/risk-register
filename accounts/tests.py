import time

from django.core.management import call_command
from django.test import TestCase, override_settings
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from accounts.models import User

PW = "DemoPass-2026"


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", password=PW, stdout=open("/dev/null", "w"))

    def test_pages_require_login(self):
        r = self.client.get("/assessments/")
        self.assertRedirects(r, "/login/?next=/assessments/", fetch_redirect_response=False)

    def test_wrong_password_shows_generic_error(self):
        r = self.client.post("/login/", {"username": "andreas.pavlou@telediexodos.demo", "password": "nope"})
        self.assertContains(r, "Email or password is incorrect.")

    def test_lockout_after_five_failures(self):
        for _ in range(5):
            self.client.post("/login/", {"username": "andreas.pavlou@telediexodos.demo", "password": "nope"})
        r = self.client.post("/login/", {"username": "andreas.pavlou@telediexodos.demo", "password": PW})
        self.assertEqual(r.status_code, 429)
        self.assertContains(r, "Sign-in paused", status_code=429)

    def test_first_login_requires_setup_then_code(self):
        r = self.client.post("/login/", {"username": "andreas.pavlou@telediexodos.demo", "password": PW})
        self.assertRedirects(r, "/login/setup/", fetch_redirect_response=False)
        # Blocked from the app until the code is entered
        self.assertRedirects(self.client.get("/tasks/"), "/login/verify/", fetch_redirect_response=False)
        self.client.get("/login/setup/")
        device = TOTPDevice.objects.get(user__email="andreas.pavlou@telediexodos.demo")
        r = self.client.post("/login/setup/", {"token": "000000"})
        self.assertContains(r, "did not match")
        time.sleep(1.2)  # a wrong code makes the next attempt wait a moment (brute-force protection)
        token = f"{totp(device.bin_key):06d}"
        r = self.client.post("/login/setup/", {"token": token})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/tasks/").status_code, 200)

    @override_settings(REQUIRE_TWO_STEP=False)
    def test_login_without_two_step_when_disabled(self):
        r = self.client.post("/login/", {"username": "andreas.pavlou@telediexodos.demo", "password": PW})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get("/tasks/").status_code, 200)
