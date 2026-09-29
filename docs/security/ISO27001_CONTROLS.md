# ISO/IEC 27001:2022 — How the Elite Academy System Supports Annex A Controls

| Field | Detail |
|---|---|
| Document Number | EA-SYS-SEC-01 |
| Version | 0.1 (Phase 0) |
| Date | 28-Sep-2026 |
| Owner | Systems & IT Lead |
| Related | EA-SYS-SCOPE-01 Scope of Work; EA-SYS-SEC-02 RBAC Matrix (`RBAC_MATRIX.md`) |

## What this document is — and is not

ISO/IEC 27001 certifies an **organisation's Information Security Management System (ISMS)**, not a piece of software. No application can be "ISO certified" on its own. What the software can do is **implement the technical controls** of Annex A and **produce the evidence** an auditor asks for.

This document maps each relevant Annex A control to where it is implemented in the code (`backend/`) and how it is tested (`backend/tests/`). Section 3 lists the controls that Elite Academy itself must put in place for certification.

Status key: **Done** = implemented and tested in Phase 0 · **Planned** = scheduled in a later phase · **Elite** = organisational responsibility.

## 1. Technological and access controls implemented in the system

| Control | What the system does | Where | Test | Status |
|---|---|---|---|---|
| **5.15 Access control** | Role-based access control, deny by default: every API endpoint must declare the permission it needs or it is closed. | `apps/rbac/drf.py`, `apps/rbac/services.py` | `test_rbac.py::test_logged_in_user_without_roles_gets_nothing` | Done |
| **5.16 Identity management** | One named account per person (unique email and mobile); no shared logins. Staff, coaches, parents and adult members use the same identity system. | `apps/accounts/models.py` | — | Done |
| **5.17 Authentication information** | Argon2 password hashing; minimum 12 characters; common, numeric and name-similar passwords rejected; "must change password" flag for first login. | `config/settings/base.py`, `apps/accounts` | `test_security.py::test_weak_passwords_are_rejected` | Done |
| **5.18 Access rights** | Access is granted by time-bound role assignments with a reason and the name of the person who granted it. Ending an assignment, or deactivating a leaver, signs the user out of every device immediately. Naming cover for a leaver ends their roles after the last day and the daily job closes the account (rule 16); emailed reports stop when access ends. | `apps/rbac/models.py`, `apps/rbac/views.py`, `User.deactivate()`, `apps/operations/services.py`, `apps/reports/tasks.py` | `test_ending_a_role_takes_effect_immediately`, `test_deactivated_user_is_logged_out_everywhere`, `test_handover_is_accepted_item_by_item_and_a_leaver_loses_access`, `test_emailed_reports_stop_when_access_ends` | Done |
| **5.3 Segregation of duties** | Nobody can change their own access; a user can only grant powers they hold themselves. Approvers never approve their own work: prices, freezes/refunds, class changes, cash-ups, expenses, vendor invoices, weekly reports (prepare → verify) and payroll (the OM prepares and submits, the Accountant approves; nobody sets their own pay or adds their own adjustments). | `apps/rbac/views.py`, `apps/rbac/catalog.py`, `apps/*/services.py` | `test_no_privilege_escalation_when_granting_roles`, `test_cannot_change_own_access`, `test_payroll_builds_from_classes_sales_leave_and_adjustments`, `test_payroll_rules_must_be_confirmed_and_nobody_sets_their_own_pay`, `test_weekly_sales_report_totals_matching_and_frozen_copy` | Done |
| **5.33 Protection of records** | Audit events are append-only (cannot be edited or deleted through the application) and sealed into a SHA-256 hash chain; tampering is detected. | `apps/audit/` | `test_audit_events_cannot_be_edited_or_deleted`, `test_audit_chain_detects_tampering` | Done |
| **5.34 Privacy and protection of PII** | Civil IDs, medical notes and allergies encrypted at rest; media consent recorded with full history; children's data visible only to roles that need it. | `apps/core/crypto.py`, `apps/members/` | `test_sensitive_fields_are_encrypted_at_rest` | Done |
| **8.2 Privileged access rights** | Privileged roles (CEO, Operations Manager, Systems & IT, Accountant) are flagged; production requires two-factor login for them. Django's superuser flag grants **no** business data access. | `apps/rbac/catalog.py`, `apps/rbac/drf.py` | `test_privileged_roles_must_use_two_factor` | Done |
| **8.3 Information access restriction** | Branch scoping on every list and record; need-to-know fields (full Civil ID, medical notes) shown only to roles with explicit permission; parents see only their own family. | `apps/rbac/drf.py`, `apps/members/serializers.py`, `apps/portal/` | `test_branch_admin_sees_only_own_branch`, `test_marketing_sees_members_without_medical_or_full_civil_id`, `test_portal_parent_sees_only_own_family` | Done |
| **8.5 Secure authentication** | TOTP two-factor login (authenticator app); lockout after 5 failed attempts for 15 minutes; CSRF protection including on login; HttpOnly session cookies; 30-minute idle timeout and 8-hour maximum session; sessions revocable server-side. | `apps/accounts/views.py`, `apps/core/middleware.py`, `config/settings/*` | `test_account_locks_after_five_failures`, `test_login_requires_csrf_token` | Done |
| **8.6 Capacity management** | Stateless application servers with Redis sessions (scale out by adding servers); database connection reuse; per-user and per-IP rate limits; load test script. | `config/settings/base.py`, `scripts/load_test.py` | Load test: 150 simultaneous users, 0 server errors | Done |
| **8.8 Management of technical vulnerabilities** | Dependencies pinned; `pip-audit` and `bandit` run in CI on every change. | `requirements.txt`, `.github/workflows/backend.yml` | CI | Done |
| **8.9 Configuration management** | Secrets only from environment variables; production refuses to start without encryption keys and a strong secret key; separate dev / test / production settings. | `config/settings/prod.py` | — | Done |
| **8.10 Information deletion** | Retention periods from EA-OPS-PROC-01 §8 enforced by scheduled jobs. | — | — | Planned (Phase 2) |
| **8.11 Data masking** | Civil IDs masked (`********1234`) for roles without `members.view_sensitive`; staff Civil IDs masked for non-HR roles. | `apps/core/crypto.py::mask` | `test_instructor_sees_medical_but_masked_civil_id` | Done |
| **8.12 Data leakage prevention** | API responses marked `Cache-Control: no-store`; branch filtering in the query itself (other branches' data is never sent). | `apps/core/middleware.py` | `test_api_responses_are_not_cached_and_carry_security_headers`; load test leak check = 0 | Done |
| **8.15 Logging** | Every create / update / delete of business records, logins, failed logins, lockouts, 2FA changes, role grants and ends, and denied access attempts are logged with user, time, IP, and request ID. Sensitive values are redacted from the log. | `apps/audit/services.py` | `test_changes_are_audited_with_sensitive_values_redacted`, `test_denied_access_is_audited` | Done |
| **8.16 Monitoring activities** | Security events also go to a dedicated `elite.security` log stream for forwarding to a monitoring service; `verify_audit` command checks log integrity. | `config/settings/base.py` LOGGING, `verify_audit` | — | Done (alerting setup: Elite / hosting) |
| **8.20 / 8.21 Network security** | HTTPS enforced with HSTS in production; secure cookies. | `config/settings/prod.py` | — | Done (firewall, TLS certificates: hosting) |
| **8.24 Use of cryptography** | Field encryption with Fernet (AES + HMAC) and key rotation (MultiFernet); keyed HMAC blind index for Civil ID uniqueness without decryption; TLS in transit. | `apps/core/crypto.py` | `test_sensitive_fields_are_encrypted_at_rest` | Done |
| **8.25 Secure development life cycle** | Git history, pull requests, automated tests, lint and security scans on every change. | `.github/workflows/backend.yml` | CI | Done |
| **8.26 Application security requirements** | Input validation (Kuwait Civil ID check digit, mobile format); security headers (nosniff, frame deny, referrer policy, permissions policy, CSP for API); optimistic locking prevents lost updates. | `apps/core/validators.py`, `apps/core/middleware.py`, `apps/core/concurrency.py` | `test_validators_and_crypto.py`, `test_concurrency.py` | Done |
| **8.28 Secure coding** | ORM with parameterised queries only; Ruff security rules (flake8-bandit) and Bandit. | `pyproject.toml` | CI | Done |
| **8.29 Security testing** | Automated security test suite runs on every change. | `backend/tests/` | 50 tests | Done |
| **8.31 Separation of environments** | Separate settings for development, test and production; test data loader refuses to run in production. | `config/settings/`, `seed_kuwait` | — | Done |
| **8.32 Change management** | All changes through Git with review; database changes through versioned migrations. | `*/migrations/` | CI migration check | Done |
| **8.33 Test information** | Only fictional test data (M21 Kuwait package); never real member, child or staff data. | `apps/testdata/` | — | Done |

## 2. Many users at the same time (supports 8.6 and data integrity)

| Mechanism | Purpose |
|---|---|
| Each request runs in its own database transaction (`ATOMIC_REQUESTS`) at READ COMMITTED isolation | Changes are all-or-nothing; users never see half-saved data. |
| Optimistic locking with a `version` on every record | If two people edit the same record, the second save gets "changed by someone else — reload" (HTTP 409) instead of silently overwriting. |
| Row locks (`SELECT … FOR UPDATE`) for shared counters | Stock quantities and class places stay correct when many people act at once. |
| Per-request context in context variables | Each user's identity and IP are kept separate even under heavy parallel load. |
| Redis-backed sessions and cache | Any application server can serve any user; add servers to handle more people. |
| Rate limits per user and per IP | One misbehaving client cannot slow the system down for everyone else. |

Measured in the development environment (4 CPU cores shared by MySQL, the application and the load generator): 150 simultaneous users, 3,283 requests, **0 server errors, 0 cross-branch data leaks**, and every editing collision safely rejected. Single-user median response time is 34 ms.

## 3. Controls Elite Academy must put in place (not software)

For certification, Elite Academy needs an ISMS around the system. These are organisational, people and physical controls:

- **ISMS foundations (clauses 4–10):** scope, information security policy, risk assessment and treatment, Statement of Applicability, internal audit, management review.
- **5.1 Policies**, **5.2 Roles and responsibilities** (the RBAC matrix is a good starting point), **5.10 Acceptable use**.
- **5.19–5.23 Suppliers and cloud services:** security terms with the hosting provider, payment gateway, WhatsApp/SMS provider and AI provider.
- **5.24–5.28 Incident management:** a written process for reporting and handling security incidents (the system's audit log is the evidence source).
- **5.29–5.30 Business continuity:** backup schedule, restore tests and recovery time targets (**8.13 Information backup** is operated by hosting).
- **6.1–6.8 People controls:** screening, confidentiality agreements, security awareness training, and the leaver process (the system automates access removal).
- **7.x Physical controls:** front-desk screens, locked offices, clear desk and screen lock.
- **8.1 User endpoint devices:** screen locks and updates on front-desk tablets and staff phones.
- **8.17 Clock synchronisation:** provided by the hosting platform (NTP).
