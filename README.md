# Risk Register

Web app for health & safety risk assessments: hazards, automatic risk rating,
existing controls, additional measures assigned as tasks with photo evidence,
versioned reassessment (v1 → v2), and client reports.

Stack: **Django 5 + PostgreSQL 16 + Caddy**, all in Docker Compose. No JavaScript
build step: pages are plain HTML templates, logic is plain Python.

---

## 1. First install on a VM

Needs Ubuntu 24.04 with Docker installed.

```bash
# copy the zip to the VM, then:
sudo apt install -y unzip
unzip risk-register.zip -d ~/ && cd ~/risk-register

cp .env.example .env
sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n=/+' | cut -c1-50)|" .env
sed -i "s|^DB_PASSWORD=.*|DB_PASSWORD=$(openssl rand -base64 32 | tr -d '\n=/+' | cut -c1-32)|" .env
VMIP=$(hostname -I | awk '{print $1}')
sed -i "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$VMIP,localhost|; s|^SITE_URL=.*|SITE_URL=http://$VMIP|" .env

docker compose up -d --build
docker compose ps
```

Open `http://<vm-ip>` in a browser.

### Load the demo data (demo/test installs only)

```bash
docker compose exec web python manage.py seed_demo --password 'Pick-A-Demo-Pass1'
```

Creates Telediexodos, Jupiterzone and Mindthegap with 8 users. Sign in as
`ca@jupiterzone.com` (consultant, sees all three, has admin access).
Other users: see `risk/management/commands/seed_demo.py`.

Every user sets up two-step verification (Microsoft/Google Authenticator) on first sign-in.
For quick local testing only, you can set `REQUIRE_TWO_STEP=False` in `.env` and run `docker compose up -d`.

### Real install: create the first admin

```bash
docker compose exec web python manage.py createsuperuser
```

Then sign in, open **Admin** (top right) and add companies and users.

---

## 2. Going live with HTTPS

Point a DNS record (e.g. `risk.example.com`) at the VM, open ports 80 and 443, then in `.env`:

```
SITE_ADDRESS=risk.example.com
ALLOWED_HOSTS=risk.example.com
SITE_URL=https://risk.example.com
CSRF_TRUSTED_ORIGINS=https://risk.example.com
HTTPS=True
```

```bash
docker compose up -d
```

Caddy gets and renews the certificate automatically.
If the VM sits behind a FortiGate or another reverse proxy that terminates HTTPS,
keep `SITE_ADDRESS=:80`, set `HTTPS=True`, and forward the proxy to port 80.

---

## 2b. Email (forgot password and task notices)

Until SMTP is set, emails are only written to the log (`docker compose logs web`).
For Microsoft 365, the sending mailbox needs SMTP AUTH enabled
(`Set-CASMailbox -Identity no-reply@telediexodos.com -SmtpClientAuthenticationDisabled $false`),
no MFA on that account, and must not be blocked by Security Defaults or Conditional Access.
Microsoft disables SMTP AUTH by default at the end of December 2026; re-enable it per mailbox if needed. Then in `.env`:

```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=no-reply@telediexodos.com
EMAIL_HOST_PASSWORD=the-mailbox-password
DEFAULT_FROM_EMAIL=no-reply@telediexodos.com
```

Then `docker compose up -d`. Reset links expire after `PASSWORD_RESET_MINUTES` (default 60).

## 3. One container set per customer

Each customer is a separate copy of this folder with its own `.env`, database and files:

```bash
cp -r ~/risk-register ~/risk-customerA && cd ~/risk-customerA
rm -f .env && cp .env.example .env      # new secrets, new SITE_ADDRESS
# If several customers share one VM, give each its own ports in .env, e.g.
#   HTTP_PORT=8081   HTTPS_PORT=8444
# and put one front proxy in front of them, or give each its own VM.
docker compose -p customerA up -d --build
```

The app is also multi-company inside one install (a consultant can manage several
client companies in the same instance), so you can choose per customer.

---

## 4. Everyday commands

| What | Command |
|---|---|
| See logs | `docker compose logs -f web` |
| Restart | `docker compose restart web` |
| Stop / start | `docker compose down` / `docker compose up -d` |
| Django shell | `docker compose exec web python manage.py shell` |
| Unlock a locked-out user | `docker compose exec web python manage.py axes_reset_username user@example.com` |
| Reset someone's two-step (lost phone) | Admin → OTP_TOTP → TOTP devices → delete their device. They set it up again at next sign-in. |
| Reset a password | Users click **Forgot password?** on the sign-in page (needs email set up, see below). Or: `docker compose exec web python manage.py changepassword user@example.com` |
| Add a user from the command line | `docker compose exec web python manage.py createsuperuser` (admin) or Admin → Users → Add |
| Run the tests | `docker compose exec web python manage.py test` |

### Backups

```bash
mkdir -p backups
docker compose exec -T db pg_dump -U riskregister riskregister | gzip > backups/db-$(date +%F).sql.gz
docker compose run --rm -v "$PWD/backups:/backups" --entrypoint "" web tar czf /backups/media-$(date +%F).tgz -C /app media
```

Restore the database (replaces everything in it):

```bash
docker compose down -v                 # removes the current database and files
docker compose up -d db && sleep 5
gunzip -c backups/db-YYYY-MM-DD.sql.gz | docker compose exec -T db psql -U riskregister riskregister
docker compose up -d
```

---

## 5. Making changes yourself

The code is tracked in git. Before editing, run `git status`; after editing, commit:

```bash
git add -A && git commit -m "Describe the change"
docker compose up -d --build        # rebuild and restart with your change
```

To undo a change that broke something: `git log --oneline`, then `git revert <commit>`.

### Where things are

| You want to change… | Edit |
|---|---|
| The risk matrix, likelihood/consequence labels, rating colours and meanings | **No code.** Admin → Risk → Matrix cells / Likelihood levels / Consequence levels / Risk ratings |
| Dropdown lists on the risk task form (hazards, who is involved, consequences, existing controls, additional measures), in English and Greek | **No code.** Admin → List items (or the "Lists" page → Edit in admin). Untick "Is active" to hide an entry |
| Companies and users | **No code.** Admin → Companies / Users |
| Text and layout of a page | `templates/risk/<page>.html` (sign-in pages: `templates/accounts/`) |
| Colours, fonts, spacing | `static/css/app.css` (colour tokens are at the top) |
| App name in the top bar | `APP_NAME` in `.env` |
| Who can see / edit what | `risk/access.py` |
| Rules: status, "ready for reassessment", new version, notifications, emails | `risk/services.py` |
| What each page does | `risk/views.py` (one function per page; URLs in `risk/urls.py`) |
| Database fields | `risk/models.py`, then `docker compose exec web python manage.py makemigrations` and rebuild |
| Default matrix/lists for new installs | `risk/defaults.py` |
| Greek wording of the screens | `locale/el/LC_MESSAGES/django.po` (edit the `msgstr` lines, then rebuild). After adding new `{% translate %}` text: `docker compose exec web python manage.py makemessages -l el` |
| Reminder timing (how often the check runs) | `scheduler` service in `docker-compose.yml` |
| Sign-in, two-step, lockout | `accounts/views.py`, settings in `config/settings.py` ("Login protection") |
| Session timeout, lockout limits, email server | `.env` |

### Running it without Docker (for development)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DEBUG=True REQUIRE_TWO_STEP=False
python manage.py migrate && python manage.py seed_demo --password 'DemoPass-2026'
python manage.py runserver
```

Uses SQLite when `DATABASE_URL` isn't set. Open http://127.0.0.1:8000.

---

## 6. How the app works

- **Roles.** *Consultant*: manages one or more client companies (set "Managed companies" on the user).
  *Safety officer*: creates and edits assessments for their own company. *Staff member*: sees only tasks assigned to them.
- **Assessment** = one register for an area or activity. It holds **hazards**. Each hazard has who is affected,
  consequences, inherent risk (likelihood × consequence), existing controls, residual risk, and additional measures.
- **Additional measure** = a **task** with an owner and deadline. The owner gets an email, updates progress,
  adds comments or photos, and marks it complete. Photos are only viewable by people allowed to see the task.
- **Status is derived**, not typed: when the required share of a hazard's measures is complete (the
  "Reassess a hazard when…" setting: 100/80/75/50%), the hazard meets the rule. When every hazard with
  measures meets it, the assessment shows *Ready for reassessment*.
- **Start version N+1** locks the current version as read-only, copies hazards forward, turns completed
  measures into existing controls, carries open measures forward, and flags each hazard to be re-scored.
  History shows every version and a before/after comparison of residual risk.
- **Notifications are restrained**: managers see assessment-level updates (ready, overdue); individual task
  changes roll up into the assessment instead of producing alerts.
- **Reports** page → *Save as PDF* uses the browser's print-to-PDF.

## 6b. Risk assessment tasks, actions and reminders

- **Risk Assessment Tasks** (menu) lists every risk entry of the tenant. **+ New task** opens the form:
  hazard, who is involved, consequences and existing control measures each come from a dropdown list
  (managed in Admin → List items) with a **manual add** box; inherent and residual risk use
  likelihood and consequence **sliders** and the rating is calculated live from the matrix.
- **Add measure** opens a pop-up: measure (list or manual), assigned user (only that tenant's people),
  deadline and reminder. The person gets an email straight away (English + Greek).
- **Reminders**: the `scheduler` container checks every hour and emails a reminder before the deadline
  (1, 3 or 7 days, chosen per action) and an overdue notice (then weekly). Each is sent once.
  Run it by hand: `docker compose exec web python manage.py send_reminders`.
- **Status is automatic**: Draft → Open → In progress → Complete, or Overdue / Needs measures,
  worked out from scores, actions, progress and deadlines (`hazard_lifecycle` in `risk/services.py`).
- **Top bar**: search (tasks, actions, assessments, people), tenant switch, light/dark toggle,
  EN/ΕΛ language toggle. On phones these move into the ☰ menu.

## 7. Security summary

- Passwords hashed by Django (PBKDF2), minimum 10 characters, common passwords rejected.
- Two-step verification (TOTP) required for every user, admin included.
- Lockout after 5 failed sign-ins per account + IP for 15 minutes (django-axes); all attempts logged in Admin → Axes.
- Sessions expire after 30 idle minutes and when the browser closes; cookies are HttpOnly, and Secure when `HTTPS=True`.
- CSRF protection on every form; clickjacking blocked; HSTS when on HTTPS.
- Every page filters data through `user.visible_companies()` so companies never see each other's data (covered by tests).
- Evidence photos are served through a permission check, never as public files.
