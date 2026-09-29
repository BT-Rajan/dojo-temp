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

## Try it on a PC (Windows, Mac or Linux) with Docker

Install Docker Desktop, then from the repository folder run `docker compose up --build`. The first start builds the
app, creates the database and loads the fictional test data (a few minutes); later starts take seconds. Open
http://localhost:8000/en/ (website) and http://localhost:8000/en/desk/ (staff desk). The test logins and the test
parent's mobile are printed in the window; portal sign-in codes appear there too (no real messages are sent).
`docker compose down` stops it; `docker compose down -v` also deletes the trial database. The passwords and keys in
`docker-compose.yml` are for this local trial only.

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

## Phase 3: inventory, purchasing and replacing Mindbody

Code: `apps/inventory` (M8), stock reservation for online orders in `apps/shop` (M19 provision), `apps/mindbody`
(M18), screens in `apps/desk/views/{inventory,mindbody}.py`. Daily jobs (overdue purchase requests, monthly counts)
run with the Phase 2 jobs.

| Area | What the desk does |
| --- | --- |
| Stock ledger | Every change to a branch's shelf (opening, import, sale, free issue, refund, receipt, transfer, count, online order, correction) is one ledger line with who, when, reference and running balance; nothing else writes stock. Stock value at cost per branch. Corrections outside the count: OM only, with a reason code. |
| Catalogue | Products with sizes and colours, barcode, supplier, program, cost, retail price, reorder and maximum levels, sold online or not (belts never). The OM edits costs and prices. |
| Purchase requests (FRM-05) | Branches request (from the reorder list or free text); one local request per branch per month; the OM approves, amends or rejects within 2 business days (Sun–Thu, not holidays; reminder if late) — never their own. |
| Purchase orders (EA-PO-YYYY-NNN) | Only from approved requests; vendor prices in any currency; landed cost per unit = price × rate × (1 + customs %) + freight shared by value; margin at retail and the counter-price that reaches the target margin; order document for the vendor in Arabic or English (PDF/Excel). |
| Receiving (FRM-01) and discrepancies (FRM-04) | All deliveries at Promenade against the vendor's invoice; landed cost becomes the item's cost; any difference opens a discrepancy that is resolved only after the vendor is told. |
| Transfers (FRM-03) | Stock is held at the sender while travelling and moves only when the receiving branch counts and accepts it; a short count needs a call to the sender and OM and an explanation, and the OM is told. |
| Monthly count (FRM-08) | Sheet made automatically on the last working day, due by the 3rd working day; two people; every difference recounted with a reason code (US, UT, D, FI, EE, U); the OM approves (not a counter) and only then is stock corrected; items short two months running are flagged. PDF/Excel. |
| Vendors | Local and international vendors, contacts, currency, quotations with documents and validity. |
| Online orders (M19 provision) | Front desk and website share one stock record per branch: an online order reserves stock (pick-up branch first), a failed payment releases it, and the desk hands it over to take it off the shelf. The storefront opens in Phase 6. |
| Mindbody import (M18) | Clients, families, inventory on hand, pricing option expirations, visits and sales from Mindbody's CSV, Excel or ".xls" (HTML) exports. Each file is a dry run first with a report (what would change, rows skipped, warnings); nothing changes until Apply. Re-running is safe (matched by Mindbody ID), so the final delta uses the same screen. Pricing options are mapped (or skipped) before memberships come across; test products are skipped. |
| Parallel run and cut-over | Mindbody's weekly KNET, card, cash and active members typed next to the system's figures, with differences explained; the cut-over checklist with who ticked each step. |

## Phase 4: training and progression

Code: `apps/training` (M7), screens in `apps/desk/views/training.py`. Load the curriculum once with
`python manage.py load_curriculum` (safe to run again; it never overwrites edits made in the desk). Evaluation
reminders (Sundays) and the monthly progress-note drafts (the 1st) run with the daily jobs.

| Area | What the desk does |
| --- | --- |
| Curriculum | The Kajukenbo scalable curriculum from the Master Curriculum workbook: 8 belts with their Jiu-Jitsu stripe, BJJ equivalent and seminar total, and the skills of the Kickboxing, Jiu-Jitsu and Self-Defence & Traditional tracks by category. Kyokushin, Shin-Kyokushin and Taekwondo have their belt lists. Coaches see the track sheet for what they teach; Training and Track Leads edit skills, the numbers needed for each belt, and which belt in stock goes with it. |
| Students and progress cards | Every student's belt per art (followed through their programs), classes since the last belt, seminar points (check-ins at seminars plus earlier seminars added by a lead), evaluation due/overdue, skills ticked off, what's still needed for the next belt, tournament eligibility and the belt history. Existing students' belts are set once (placement) with a note. |
| Evaluations | Every 4–6 weeks, by the member's own instructors or a lead: each skill scored 1 Not yet – 4 Strong (3 or 4 ticks it off), notes, "ready for test". |
| Test days | A lead plans the day and examiners; eligible students are listed (anyone else only with a reason); examiners record each part (Kickboxing, Jiu-Jitsu, Self-Defence demo; the seminar check is automatic); a lead confirms each promotion. |
| Belts | A promotion tells the family by WhatsApp and puts the belt on the branch's hand-over list; the front desk issues it from stock as a 0 KD free issue ("Grading belt"). |
| Progress notes | Drafted on the 1st for each child who trained last month (classes, new skills, what's next); the instructor edits and sends it to the guardian. |

## Phase 5: leads, marketing and the assistants

Code: `apps/leads` (M3 leads, trials and group sales; M13 campaigns, referrals, reviews, broadcasts) and
`apps/assistant` (M16 knowledge base, SAQR and the Staff Assistant); screens in `apps/desk/views/{leads,assistant}.py`.

| Area | What the desk does |
| --- | --- |
| Leads | Every enquiry — website form, SAQR, walk-in, phone, referral — becomes one lead (a second enquiry from the same mobile updates the open lead). The first person to contact it owns it; only the OM or Marketing Lead reassigns, with a reason. Every open lead has a next action and due time; new web leads are due within 2 hours, overdue ones show on the owner's task list. Stages New → Contacted → Trial booked → Trial done → Joined, or Lost with a reason. |
| Trials | Booked from the lead (name and phone only); the instructor gets a trial brief by WhatsApp and gives feedback (1–5) on the class list; the follow-up is due 24 hours after the class. The lead is marked Joined automatically when the family's first membership is sold. |
| Group sales | Schools and companies from Contact to Delivery; a named receiving owner in Operations confirms before Training delivers, and Training is told. |
| Conversion | Leads, trials, joins and conversion rate by source, campaign, owner and branch. |
| Campaigns | Code for links (`?c=CODE`, or `utm_campaign`), spend, leads and joins counted automatically, cost per lead and per join. |
| Referrals and reviews | A referral code and printable QR card per member; a lead arriving with it records the referrer, and the Phase 1 referral reward follows. Google review requests after a trial rated 4–5 and after a belt promotion (at most once per family every 90 days; links set per branch). |
| WhatsApp broadcasts | Only to families who opted in (recorded on the member page); by branch, program and age; drafted by Marketing, approved and sent by the Marketing Lead (never their own draft). A withdrawn media consent sends that member's gallery photos back to review. |
| Knowledge base | Articles in English and Arabic, public or staff-only, with an owner and every version kept (restore in one click). Only published articles are used. |
| SAQR | Every chat is stored (session key hashed; kept 90 days unless it became a lead). Refunds, cancellations, complaints, injuries, asking for a person or two misses hand over to the desk's queue; staff take the chat, create the lead and spot-check answers (3 per shift). |
| Staff Assistant | "How do I…" from articles and numbers from live data (active members, expiring members, payments by method, leads) — read-only, limited to the asking person's role and branch, with sources shown and every question logged. |

**The AI engine** (open item O-20) uses the Anthropic API (`anthropic` SDK, model `AI_MODEL`, default
`claude-opus-5-5`) with a manual tool loop over read-only tools, strict tool schemas and server-side refusal
fallbacks (`fallbacks: "default"`). Set `AI_ENABLED=true` and `ANTHROPIC_API_KEY` to switch it on. Until then —
and whenever the provider is unreachable or declines — SAQR uses the rule-based engine and the Staff Assistant
routes by keywords over the same tools.

## Phase 6: the family portal and messaging

Code: `apps/portal` (M15: `services.py`, pages in `site_views.py` at `/en/my/…` and `/ar/my/…`, online renewals in
`RenewalPayment`) and `apps/notifications` (M17: message log, family preferences, wording). The shop storefront
was built with the website; Phase 6 adds "ready for pick-up" messages for online orders.

| Area | What it does |
| --- | --- |
| Family portal | After the mobile + WhatsApp code sign-in, each child (or the adult member) has a page: membership and expiry, this week's classes (book up to 7 days ahead if the membership covers the class; full classes go on the waiting list; cancel any time, within 2 hours recorded as late), recent attendance, belt progress from Training (skills, next-belt requirements, seminar points, test days, evaluation and monthly notes), receipts, photo consent (withdrawal takes effect at once) and signing the academy rules. Records are only ever reached through the signed-in family. |
| Online renewal | The current membership option at its listed price, paid by KNET or card through the payment gateway (`apps/shop/payments.py`; the test gateway stands in until O-6). A verified payment records the sale at the member's branch, extends the membership from the day after it ends, and sends the receipt. Freeze requests go to the OM's approval queue. |
| Account and messages | Email, the family's choice of service messages (reminders, test days, progress notes) and broadcasts, and the family's recent messages. The mobile number (the sign-in) is changed at the desk. |
| Messaging | Every message goes through `apps.core.messaging.send_message` with a category: essential (always sent), service (the family can turn off), marketing (opt-in only) or staff. All are logged (Desk → Messages); the Marketing Lead can reword the family messages (trial confirmation, test-day invitation, booking and waiting-list, online renewal, order ready/sent) without a code change, keeping the placeholders. |

## Phase 7: management and the Quarterly Business Report

Code: `apps/management` (M12: `services.py`; RPT-01: `quarterly.py`; scheduled jobs in `tasks.py`) and the desk
screens under Desk → Management. Reporting lines come from the staff records (`StaffProfile.reports_to` and
`second_lead`). Everything follows the Communication Procedure (EA-COMM-PROC-01): the next person accepts a message
before the sender lets go of it.

| Area | What it does |
| --- | --- |
| Announcements | The CEO or a function lead posts once; each person confirms receipt; leads forward the same text, unchanged, to their team within 2 working days (Sunday–Thursday); the sender sees who has confirmed at every level; daily reminders after the deadline. Anyone with two leads is copied to the other lead automatically. |
| Handoffs and IT requests | The §5.2 handoffs between leads, requests to Systems & IT (what, why, who benefits, how urgent — also the change requests of scope 7.1), IT change notices with a go-live date, and updates to the CEO between monthly reports. The receiver confirms within 1 working day; Systems & IT must give a committed date. |
| Leads meeting | Minutes in the MOM layout (attendance, agenda, decisions with owners, action items, next meeting); open actions from earlier meetings shown; locked once sent; attendees acknowledge; action items go on the owners' task lists. |
| Monthly reports | Each function lead's monthly report to the CEO, pre-filled from the system and frozen when sent; the CEO acknowledges. |
| Escalation log | Safety and conduct concerns: same day to the lead, an owner named, the CEO within 24 hours for member safety or a removal (automatic after 24 hours), and the "called the CEO directly" route, seen only by the person and the CEO. |
| Procedure library | Document number, owner, version, effective date, what changed, file; approved by the CEO (never the preparer); the people it applies to confirm they have read it. |
| Directory and org chart | Built from the staff records and roles, including dotted lines. |
| Quarterly Business Report | RPT-01, all 11 sections for Promenade, Bedaya and Combined; live while in draft, frozen when the OM submits it; the headline-sales check must be explained; the CEO approves or returns it; PDF and Excel; a "quarter so far" view; reminders up to the due date (15 days after quarter end). |
| Staff & access | Desk → Staff & access: the CEO or OM adds a staff member (the login gets a one-time password shown once, changed at first sign-in) and gives roles per branch with a reason; Systems & IT manages access too. No one changes their own access or hands out powers they don't hold; ending a role signs the person out at once. |
| Coaches | Desk → Coaches (CEO and OM): everyone with a teaching role, their weekly classes, classes and hours taught in the month, check-ins in their classes, evaluations, pay arrangement and alerts (no pay set up, not on the timetable, document expiring), with a profile page per coach. |

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
