"""
Send email through Microsoft Graph (Microsoft 365) instead of SMTP.

Microsoft is retiring password-based SMTP for Exchange Online, so this uses an
Entra app registration (client ID + secret) that may send only as one mailbox.
Setup steps are in the README ("Email"). Enable in .env with:

    EMAIL_BACKEND=config.graph_email.GraphEmailBackend
    GRAPH_TENANT_ID=...
    GRAPH_CLIENT_ID=...
    GRAPH_CLIENT_SECRET=...
    DEFAULT_FROM_EMAIL=no-reply@yourdomain.com
"""
import json
import logging
import time
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

log = logging.getLogger(__name__)

_token = {"value": None, "expires": 0}


def _get_token():
    if _token["value"] and _token["expires"] > time.time() + 60:
        return _token["value"]
    data = urllib.parse.urlencode({
        "client_id": settings.GRAPH_CLIENT_ID,
        "client_secret": settings.GRAPH_CLIENT_SECRET,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }).encode()
    url = f"https://login.microsoftonline.com/{settings.GRAPH_TENANT_ID}/oauth2/v2.0/token"
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=15) as r:
        body = json.load(r)
    _token["value"] = body["access_token"]
    _token["expires"] = time.time() + int(body.get("expires_in", 3600))
    return _token["value"]


def _payload(message):
    return {
        "message": {
            "subject": message.subject,
            "body": {"contentType": "Text", "content": message.body},
            "toRecipients": [{"emailAddress": {"address": a}} for a in message.to],
            "ccRecipients": [{"emailAddress": {"address": a}} for a in message.cc],
            "bccRecipients": [{"emailAddress": {"address": a}} for a in message.bcc],
        },
        "saveToSentItems": False,
    }


class GraphEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            sender = settings.DEFAULT_FROM_EMAIL
            try:
                req = urllib.request.Request(
                    f"https://graph.microsoft.com/v1.0/users/{urllib.parse.quote(sender)}/sendMail",
                    data=json.dumps(_payload(message)).encode(),
                    headers={"Authorization": f"Bearer {_get_token()}", "Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=15):
                    sent += 1
            except Exception as exc:
                # Log and carry on: a mail problem must never break a page, and an error on
                # "forgot password" would reveal which email addresses have accounts.
                detail = getattr(exc, "read", lambda: b"")()[:500]
                log.error("Graph sendMail failed for %s: %s %s", message.to, exc, detail)
        return sent
