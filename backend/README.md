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
python manage.py runserver
```

Test logins after `seed_kuwait`: `ops@test.elite.local`, `admin.prm@test.elite.local`,
`admin.bed@test.elite.local`, `coach.prm@test.elite.local`, `parent@test.elite.local`, … —
password `Elite-Test-2026!`. These accounts exist only in development and test databases.

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
