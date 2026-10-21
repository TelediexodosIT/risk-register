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


class PasswordResetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", password=PW, stdout=open("/dev/null", "w"))

    def test_reset_flow_sends_link_and_changes_password(self):
        import re
        from django.core import mail
        self.assertContains(self.client.get("/login/"), "Forgot password?")
        r = self.client.post("/login/forgot/", {"email": "andreas.pavlou@telediexodos.demo"})
        self.assertRedirects(r, "/login/forgot/sent/")
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r"http://testserver(\S+)", mail.outbox[0].body).group(1)
        r = self.client.get(link, follow=True)
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "BrandNew-Pass-77", "new_password2": "BrandNew-Pass-77"})
        self.assertRedirects(r, "/login/reset/done/")
        self.assertTrue(User.objects.get(email="andreas.pavlou@telediexodos.demo").check_password("BrandNew-Pass-77"))

    def test_unknown_email_gives_same_answer(self):
        from django.core import mail
        r = self.client.post("/login/forgot/", {"email": "nobody@nowhere.demo"})
        self.assertRedirects(r, "/login/forgot/sent/")
        self.assertEqual(len(mail.outbox), 0)


class GraphBackendTests(TestCase):
    @override_settings(GRAPH_TENANT_ID="t", GRAPH_CLIENT_ID="c", GRAPH_CLIENT_SECRET="s",
                       DEFAULT_FROM_EMAIL="no-reply@example.com")
    def test_sends_via_graph(self):
        import io, json
        from unittest import mock
        from django.core.mail import EmailMessage
        from config import graph_email
        graph_email._token.update(value=None, expires=0)
        calls = []

        def fake(req, timeout=0):
            calls.append(req)
            body = b'{"access_token":"abc","expires_in":3600}' if "login.microsoftonline" in req.full_url else b""
            return io.BytesIO(body)

        with mock.patch("urllib.request.urlopen", fake):
            n = graph_email.GraphEmailBackend().send_messages([EmailMessage("Hi", "Body", to=["a@b.com"])])
        self.assertEqual(n, 1)
        self.assertIn("/users/no-reply%40example.com/sendMail", calls[1].full_url)
        self.assertEqual(json.loads(calls[1].data)["message"]["toRecipients"][0]["emailAddress"]["address"], "a@b.com")
        self.assertEqual(calls[1].headers["Authorization"], "Bearer abc")
