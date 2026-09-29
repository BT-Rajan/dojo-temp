# Elite Academy System — Back End

Python (Django 5.2 + Django REST Framework) with MySQL 8 and Redis. This is Phase 0 of
EA-SYS-SCOPE-01: the secure foundation that every later module builds on.

The front end (website, staff system, member portal) will be built from the approved
Claude Design template and talks to this back end through the REST API at `/api/v1/`.

## What Phase 0 contains

| Area | What's there |
|---|---|
| Accounts | One login for staff, coaches, parents and adult members; Argon2 passwords; two-factor login (authenticator app); lockout after 5 failed attempts; idle and absolute session timeouts; "sign out everywhere". |
| Role-based access control | 13 default roles and 38 permissions (`apps/rbac/catalog.py`), branch-scoped assignments with start/end dates, deny-by-default API, need-to-know fields, no privilege escalation. See `docs/security/RBAC_MATRIX.md`. |
| Audit log | Every change, login and denied access attempt recorded; append-only; SHA-256 hash chain with tamper detection (`python manage.py verify_audit`). |
| Organisation | Branches, disciplines, programs, pricing options (with an explicit membership type instead of the ">12 KD" rule). |
| Members | Members, guardians / family accounts, emergency contacts, media consent history. Civil IDs and medical notes encrypted at rest. |
| Staff | Staff profiles with employment type (full-time, part-time, hourly, freelance) ready for payroll. |
| Portal | Parents see only their own family. |
| Test data | Fictional Kuwait test data package (`seed_kuwait`). |
| Simultaneous users | Per-request transactions, optimistic locking (HTTP 409 on edit collisions), row locks for counters, Redis sessions, rate limits, load test script. |

## Run it locally

Requirements: Python 3.11+, MySQL 8, Redis, and the MySQL client headers (`libmysqlclient-dev pkg-config` on Ubuntu).

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# MySQL: the database must be utf8mb4 so Arabic text is stored correctly
mysql -uroot -e "CREATE DATABASE elite CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
                 CREATE USER 'elite'@'localhost' IDENTIFIED BY 'choose-a-password';
                 GRANT ALL PRIVILEGES ON elite.* TO 'elite'@'localhost';
                 GRANT ALL PRIVILEGES ON test_elite.* TO 'elite'@'localhost';"

cp .env.example .env        # then fill in DJANGO_SECRET_KEY and DATABASE_URL
python manage.py migrate    # also creates the default roles and permissions
python manage.py seed_kuwait   # fictional test data; prints the test logins
python manage.py seed_website  # the website pages (EN/AR), sample timetable and shop
python manage.py runserver     # website: /en/ and /ar/ · staff desk: /en/desk/ · CMS: /cms/
python manage.py run_daily_jobs  # (or Celery beat) prices, sessions 4 weeks ahead, reminders, no-shows
```

Test logins after `seed_kuwait`: `ops@test.elite.local`, `admin.prm@test.elite.local`,
`admin.bed@test.elite.local`, `coach.prm@test.elite.local`, `parent@test.elite.local`, … —
password `Elite-Test-2026!`. These accounts exist only in development and test databases.

## Phase 1: the staff desk (members, classes and sales)

The front desk, coaches and managers work at `/en/desk/` or `/ar/desk/` (sign in with the staff email; privileged
roles need an authenticator code in production). Code: `apps/classes` (M4), `apps/sales` (M5), `apps/renewals` (M6),
`apps/desk` (screens), plus additions to `apps/organization` (M1) and `apps/members` (M2). Rules live in each app's
`services.py`; the desk screens and the API (`/api/v1/class-sessions/`, `bookings/`, `check-ins/`, `sales/`,
`memberships/`, `price-changes/`, `rooms/`) both call them, so the rules are the same everywhere.

| Area | What the desk does |
| --- | --- |
| Prices (M1) | Membership / non-membership types; packages as sessions × weeks (10×4); All-Access; family, Elite Member (off until its rule is set), referral (5.000 KD credit on the referrer's next renewal) and manual discounts. New prices and price changes go live only after the Operations Manager approves — never by the person who asked. |
| Members (M2) | Register with guardian, emergency contact, medical notes, media consent and the rules signed on screen; photo (stored privately, served only to staff); QR member card; status calculated (Active, Expiring ≤5 days, Expired, Frozen, Trial, Lead, Former); one timeline. |
| Classes (M4) | Weekly timetable with room, coaches, capacity and striking/grappling focus; sessions made 4 weeks ahead; regular places; bookings with a waiting list (first in line moves up and is told); seminars, camps, events and private sessions. Check-in by name, mobile or QR at the desk, or from the coach's class list with photos and medical flags. Walk-ins allowed; an expired membership warns but still checks in. No-shows and late cancellations (under 2 hours) are recorded, no penalty. |
| Class changes (M4) | Cancel, move or substitute: requested by coaches or the desk, approved by the Training Lead or OM (not the requester), then everyone expecting the class is messaged; the log keeps time, channel and count (replaces FRM-04). Under 2 hours' notice is allowed but flagged urgent. |
| Sales (M5) | Sell from the member's profile: memberships (early renewals start after the current period), passes, sessions, equipment by exact size from this branch's shelf, 0 KD free issues. KNET / card (terminal reference typed in) / cash, split payments; receipts numbered per branch (PRM-000123), printed, WhatsApp or email; category set automatically (New, Renew, Trial Pass, Day Pass, Equipment). |
| Requests (M5) | Freeze (1–4 weeks, once per membership, no fee), refund (negative receipt; equipment back on the shelf) and cancellation: the desk logs, the OM decides. |
| Cash-up (M5) | Counted cash and terminal totals against the system; any difference is recorded, above 1.000 KD needs a written reason; sent to the OM and the Accountant, verified by someone other than the preparer. |
| Renewals (M6) | Daily list (expired ≤30 days, expiring ≤5, anyone checked in without a membership), one-tap WhatsApp with the renewal message, outcomes R/W/F/L/N; after 3 unanswered attempts the member's coach is asked to have a word. Reminders 5 days and 1 day before expiry. At-risk list: no visit in 14 days. |
| Reports | Visits per day, class utilisation, no-shows, late cancellations, sales by category. |

The website schedule, SAQR and the portal's "next class" and membership dates now read this timetable and these
memberships (scope rule 18); the website's separate sample timetable has been removed.

## Phase 2: operations, reports, finance and payroll

Code: `apps/operations` (M9), `apps/reports` (M10), `apps/finance` (M11), `apps/payroll` (M20), staff documents in
`apps/staff`, screens in `apps/desk/views/{ops,reports,finance,payroll}.py`. Scheduled jobs are in
`apps/reports/tasks.py` (Celery beat) and can be run by hand with `python manage.py run_phase2_jobs`.

| Area | What the desk does |
| --- | --- |
| My tasks | Everything waiting for the signed-in person with due dates: shift opening, cash-up, renewals, approvals, expenses, incidents, complaints, handovers, weekly reports, payroll, leave, expiring documents. Shown on the home page too. |
| Shift opening (FRM-01) | The 9 checks, each ticked or explained, signed before the first class; hazards go to the OM at once. |
| Incidents (FRM-09) | Children need the guardian's name and time; the OM is told the same day; safety or removal matters show a 24-hour countdown and go to the CEO automatically if nobody escalates them; follow-up owner and closure. |
| Complaints (FRM-10) | One Voice opener on screen; money, refunds, staff conduct, safety and "threat to leave" go to the OM; reply due in 24 hours (reminder if missed); closed only with the time the member was told the outcome. |
| Cover & handover (FRM-11) | The OM names cover; the open-items list is built from live data; the incoming person accepts each item. A leaver's roles end after their last day and the daily job closes the account. |
| Weekly reports (FRM-06, FRM-07) | Built from live data, week Saturday–Friday, due Saturday 12:00. The Branch Admin prepares (figures are frozen then), the OM verifies — never the same person. "Matches cash-up and terminal settlement?" per method; expenses with receipts; members lost, trials booked/attended/converted, incidents, complaints, class changes, this week vs last week. |
| Active members (EA-DOC-003) | Business rule 1, per branch and program, roster with last visit and visit count ("verified by attendance"), week-over-week change from the Friday snapshot. |
| Dashboards | Daily (visits, no-shows, class fill, sales by method, cash-up status), weekly (new vs returning, cancellations, revenue mix, leads), monthly (sales growth, membership growth/churn, branch comparison, instructor hours), training and marketing. Promenade, Bedaya or both. |
| Exports and emails | Every report as PDF (English or Arabic, right-to-left) and Excel; "Email me this report" daily, weekly, Friday or monthly — stops automatically when the person's access ends. |
| Finance (M11) | Branch expenses with a receipt photo (or a reason), approved by the OM or Accountant; cash paid from the drawer comes off that day's expected cash. Reconciliation of every cash-up; revenue by category, program, branch and month; monthly/quarterly income statement with the headline-sales check (difference must be explained before it is finalised); vendor invoices (Accountant records, OM approves, Accountant pays); sales and expense exports (Excel/CSV). |
| Payroll (M20) | Any mix of salary, allowances, hourly rate, rate per class (per program / session type) and commission on own sales. The run is built from classes actually taught, sales, leave, advances and the OM's adjustments (overtime, bonus, absence…); the OM submits, the Accountant approves (never their own submission, and only after confirming the Kuwait rules: overtime, end-of-service, PIFSS, leave). Bilingual payslips released to each person, bank transfer file, summary by branch and function, cost into the income statement. Leave (annual/sick/unpaid, Fridays and public holidays not counted, classes needing cover listed), salary advances repaid automatically, staff documents with 60/30/7-day expiry reminders, end-of-service preview and final settlement. Nobody sets their own pay. |

Emails print to the console in development; set `DJANGO_EMAIL_BACKEND` and the `EMAIL_*` settings before going live
(production refuses to start without them). PDF fonts are IBM Plex Sans Arabic (SIL Open Font License,
`apps/reports/fonts/OFL.txt`).

## The website (elitemaacademy.com)

Built with Wagtail from the Elite Academy design system (direction B · The Path). Code lives in
`apps/website` (pages, blocks, forms, portal, SAQR) and `apps/shop` (products, stock, orders, payments).

- **One page tree, two languages.** URLs are `/en/…` and `/ar/…`; every page and CMS block has English and
  Arabic fields, and empty Arabic falls back to English. Arabic copy is a draft until the academy signs it off.
- **Design tokens.** `apps/website/design/tokens.json` is the source; run `python scripts/build_design_tokens.py`
  to regenerate `static/website/css/tokens.css`. `blocks.css` is the design's reference CSS; `site.css` holds
  the page layout. No hex colours in either — only token variables.
- **CMS (/cms/).** Open to roles with `cms.edit` (drafts) and `cms.publish` (publish, settings). Wagtail's
  Editors/Moderators groups follow the RBAC roles on every visit. Privileged users need two-factor sign-in
  when MFA is enforced.
- **Blocks.** Every block in the design system is a CMS block (`apps/website/blocks.py`, templates in
  `templates/website/blocks/`), with its empty and error states.
- **Book a trial / contact / event sign-up** post to the page itself (CSRF, honeypot, 8 per 10 minutes per
  address) and land in `TrialRequest`, `ContactMessage`, `EventRegistration`. Staff read trial requests and
  messages at `/api/v1/website/…` with `leads.manage`, limited to their branch.
- **Member portal.** Mobile number + 4-digit WhatsApp code (hashed, 5 minutes, 5 attempts, rate-limited,
  same answer for unknown numbers). Parents see only their own family.
- **Gallery consent.** A photo is public only when it is marked reviewed and every tagged member's latest
  media consent allows website use.
- **Shop.** Stock is reserved with row locks at checkout and released when a payment fails; the cart is
  kept. Belts are never sold online.
- **SAQR** (`/api/v1/saqr/`) is a rule-based assistant for now: prices, times and branches from live data,
  and the Customer Management hand-off (refund, complaint, injury, asking for a person, two misses) to
  WhatsApp. The AI engine replaces it behind the same interface later.
- **Content security policy.** Public pages allow only this site's own scripts, styles, fonts and images.

Decisions still open, so the code has stand-ins that production refuses to start with:

| Open decision | Stand-in today | Where to plug in the real one |
| --- | --- | --- |
| KNET / card provider | `PAYMENT_GATEWAY=test` (a local approve/decline page) | `apps/shop/payments.py` |
| WhatsApp provider (portal codes, confirmations) | `MESSAGING_BACKEND=console` (logged; the code is shown on the page in development) | `apps/core/messaging.py` |
| Hosting | none | settings `prod.py` |

Content still to come from the academy (never invented by `seed_website`): vector logo, official Arabic name,
Arabic sign-off, real class times (seeded times are marked "sample"), instructor profiles (seeded as unpublished
drafts), shop prices (marked "sample price"), parent quotes (seeded unapproved, so none shows), belt orders
other than Kajukenbo.

## Checks

```bash
pytest                                   # 50 tests on real MySQL (RBAC, security, concurrency)
ruff check . && ruff format --check .    # lint and format
bandit -q -r apps config -c pyproject.toml   # code security scan
pip-audit -r requirements.txt            # known-vulnerable dependencies
python manage.py verify_audit            # audit log integrity
```

Load test with many simultaneous users (start the server with gunicorn first):

```bash
THROTTLE_ANON=100000/min THROTTLE_LOGIN=100000/min THROTTLE_USER=100000/min \
  gunicorn config.wsgi:application --env DJANGO_SETTINGS_MODULE=config.settings.dev -w 4 --threads 8
python scripts/load_test.py --users 150 --actions 15
```

The same checks run automatically on GitHub for every change (`.github/workflows/backend.yml`).

## How to add a protected endpoint

1. Add the permission to `PERMISSIONS` in `apps/rbac/catalog.py` and grant it to the right roles in `ROLES`.
2. In the view, declare what each action needs:

   ```python
   class InvoiceViewSet(BranchScopedMixin, OptimisticLockMixin, viewsets.ModelViewSet):
       required_perms = {"list": "finance.manage", "retrieve": "finance.manage", "create": "finance.manage"}
   ```

   `BranchScopedMixin` filters lists to the user's branches and blocks writes to other branches.
   `OptimisticLockMixin` rejects edits made on an out-of-date copy (409).
3. Use `VersionedSerializerMixin` on the serializer, and register the model with `track_changes()` in the app's `ready()` so it is audited. List sensitive fields in the model's `AUDIT_REDACT`.
4. Write tests for who may and may not use it.

A view that declares no permission is closed to everyone.

## API overview

| Path | Purpose |
|---|---|
| `GET /healthz` | Load-balancer health check |
| `/api/v1/auth/` | `csrf/`, `login/`, `logout/`, `me/`, `change-password/`, `mfa/setup/`, `mfa/confirm/` |
| `/api/v1/rbac/` | `permissions/`, `roles/`, `assignments/` (+ `assignments/{id}/end/`) |
| `/api/v1/audit/events/` | Audit log (+ `verify/`) |
| `/api/v1/branches/`, `disciplines/`, `programs/`, `pricing-options/` | Organisation |
| `/api/v1/members/` | Members (+ `deactivate/`, `consent/`, `guardians/`, `emergency-contacts/`) |
| `/api/v1/guardians/`, `/api/v1/staff/` | Families and staff |
| `/api/v1/portal/my-family/` | Parent / member portal |
| `/api/v1/schema/` | OpenAPI schema |

## Production notes

- Settings module `config.settings.prod`; it refuses to start without `FIELD_ENCRYPTION_KEYS`, `BLIND_INDEX_KEY` and a 50+ character `DJANGO_SECRET_KEY`.
- Run behind HTTPS (HSTS on). Two-factor login is enforced for privileged roles by default.
- Run Celery worker + beat for background jobs; schedule `apps.audit.tasks.seal_audit_events` every minute.
- Give the application's MySQL user only `SELECT, INSERT` on `audit_auditevent` plus `UPDATE` on its `seal_seq, prev_hash, hash` columns, so the audit log cannot be rewritten even with application credentials.
- Back up MySQL daily and test restores (ISO 27001 A.8.13).
