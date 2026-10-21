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

Until email is set up, messages are only written to the log (`docker compose logs web`).
The app sends through **Microsoft Graph** (Microsoft is retiring password-based SMTP for Exchange Online).

**One-time setup in Microsoft 365** (the app may only send as the one mailbox):

1. Entra admin center → App registrations → New registration, name `Risk Register mail`. Note the
   **Application (client) ID** and **Directory (tenant) ID**. Do **not** add any API permissions.
2. Certificates & secrets → New client secret (24 months). Copy the **Value**.
3. Enterprise applications → `Risk Register mail` → note its **Object ID**.
4. Exchange Online PowerShell (`Connect-ExchangeOnline`):

```powershell
New-ServicePrincipal -AppId <client-id> -ObjectId <enterprise-app-object-id> -DisplayName "Risk Register mail"
New-ManagementScope -Name "RiskRegister-NoReply" -RecipientRestrictionFilter "PrimarySmtpAddress -eq 'no-reply@telediexodos.com'"
New-ManagementRoleAssignment -App <client-id> -Role "Application Mail.Send" -CustomResourceScope "RiskRegister-NoReply"
Test-ServicePrincipalAuthorization -Identity <client-id> -Resource no-reply@telediexodos.com
```

Then in `.env`:

```
EMAIL_BACKEND=config.graph_email.GraphEmailBackend
GRAPH_TENANT_ID=<tenant-id>
GRAPH_CLIENT_ID=<client-id>
GRAPH_CLIENT_SECRET=<secret-value>
DEFAULT_FROM_EMAIL=no-reply@telediexodos.com
```

`docker compose up -d`, then test with **Forgot password?** on the sign-in page. Errors appear in
`docker compose logs web | grep Graph`. The secret expires: set a reminder to renew it.

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
| The hazard library | **No code.** Admin → Hazard templates (or "Hazard library" page → Edit in admin) |
| Companies and users | **No code.** Admin → Companies / Users |
| Text and layout of a page | `templates/risk/<page>.html` (sign-in pages: `templates/accounts/`) |
| Colours, fonts, spacing | `static/css/app.css` (colour tokens are at the top) |
| App name in the top bar | `APP_NAME` in `.env` |
| Who can see / edit what | `risk/access.py` |
| Rules: status, "ready for reassessment", new version, notifications, emails | `risk/services.py` |
| What each page does | `risk/views.py` (one function per page; URLs in `risk/urls.py`) |
| Database fields | `risk/models.py`, then `docker compose exec web python manage.py makemigrations` and rebuild |
| Default matrix/library for new installs | `risk/defaults.py` |
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

## 7. Security summary

- Passwords hashed by Django (PBKDF2), minimum 10 characters, common passwords rejected.
- Two-step verification (TOTP) required for every user, admin included.
- Lockout after 5 failed sign-ins per account + IP for 15 minutes (django-axes); all attempts logged in Admin → Axes.
- Sessions expire after 30 idle minutes and when the browser closes; cookies are HttpOnly, and Secure when `HTTPS=True`.
- CSRF protection on every form; clickjacking blocked; HSTS when on HTTPS.
- Every page filters data through `user.visible_companies()` so companies never see each other's data (covered by tests).
- Evidence photos are served through a permission check, never as public files.
