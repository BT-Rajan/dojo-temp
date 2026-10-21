# Elite Academy — Deployment Requirements

How to put the Elite Academy system (Django back end, website, staff desk and family portal) on a Linux server
**without Docker**, load the prepared database, and start/stop it with three scripts:

| Script | When | What it does |
|---|---|---|
| `runonce.sh` | First install, and again after every `git pull` | Writes `.env.staging`, builds the Python environment, loads the database dump into an empty database, applies newer migrations, collects static files, sets the test-account password |
| `start.sh` | To start | Starts gunicorn in the background (and Celery worker + beat when Redis is configured), then runs a health check |
| `stop.sh` | To stop | Stops everything `start.sh` started (gracefully, forced after 30 s) |

This is a **dev instance**: the dump, its keys and its passwords are demo values and are kept in git on purpose.
The settings used are `config.settings.staging`: production-like (no debug pages, real secrets, gunicorn), with the
test payment page and console messaging. It is for the fictional test data only. Going live with real members uses
`config.settings.prod`, which refuses to start until a payment gateway, email and messaging provider are set.

---

## 1. Server requirements

| Item | Requirement |
|---|---|
| OS | Linux, Ubuntu 22.04/24.04 or Debian 12 (CloudPanel servers work) |
| CPU / RAM / disk | 2 vCPU, 4 GB RAM, 10 GB free disk (minimum for review use) |
| Python | 3.11 or newer, with `venv` |
| Database | **MySQL 8.0** (the dump uses `utf8mb4_0900_ai_ci`; MariaDB will not import it) |
| Redis | Optional. Without it, the cache and sessions are kept in MySQL and the scheduled jobs run from cron |
| Network | Outbound HTTPS to pypi.org during `runonce.sh`. Inbound: 443 via a reverse proxy (domain), or the chosen app port (IP only) |
| Account | A normal (non-root) user that owns the repository folder; root only for installing packages and cron/systemd |

Packages (as root, once):

```bash
apt update
apt install -y git python3 python3-venv python3-dev build-essential pkg-config \
               default-libmysqlclient-dev default-mysql-client openssl curl
# Only if MySQL is not already on the server (CloudPanel has it):
apt install -y mysql-server
# Optional:
apt install -y redis-server
```

## 2. Database

Create an empty database and user (in CloudPanel: **Databases → Add Database**; or as MySQL root):

```sql
CREATE DATABASE elite CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
CREATE USER 'elite'@'127.0.0.1' IDENTIFIED BY 'a-long-random-password';
GRANT ALL PRIVILEGES ON elite.* TO 'elite'@'127.0.0.1';
```

The dump (`deploy/db/elite.sql`, a `mysqldump` of MySQL 8.0.46, 216 tables) contains the full schema **and** the
fictional Kuwait test data: test staff accounts (`…@test.elite.local`), members, families, classes, sales, website
pages. `runonce.sh` loads it only when the database has no tables, so re-running never overwrites data. To start
over, drop and re-create the database, then run `runonce.sh` again.

> **Encryption keys.** Civil IDs and medical notes in the dump are encrypted with the demo keys of the dev
> instance, which are also the defaults in `config/settings/dev.py`:
> `FIELD_ENCRYPTION_KEYS=bG9jYWwtZGV2LW9ubHkta2V5LTMyLWJ5dGVzLWxvbmc=` and
> `BLIND_INDEX_KEY=local-dev-only-blind-index-key`. `runonce.sh` uses them when you press Enter. With other keys the
> member pages fail, and `runonce.sh` stops with an error that says so. These keys are public: never use them with
> real member data.

## 3. Get the code

```bash
git clone https://github.com/BT-Rajan/dojo-temp.git elite
cd elite
```

Only the `backend` folder, the three scripts and the dump are needed on the server. Do not copy any folder of real
member documents to a review server.

## 4. First install: `./runonce.sh`

```bash
./runonce.sh                      # uses deploy/db/elite.sql
./runonce.sh /path/to/elite.sql   # or another dump
```

The first time, it asks for:

| Question | Example | Notes |
|---|---|---|
| Address | `review.example.com` or `169.58.13.213:8095` | A domain means HTTPS through a reverse proxy, app on `127.0.0.1:8090`. An IP means plain HTTP on `0.0.0.0:<port>` |
| MySQL host / port / database / user / password | `127.0.0.1` / `3306` / `elite` / `elite` / … | From step 2 |
| Test-account password | Enter, or at least 12 characters | Enter keeps the demo password `Elite-Test-2026!`; anything else replaces it on every `…@test.elite.local` account |
| `FIELD_ENCRYPTION_KEYS`, `BLIND_INDEX_KEY` | Enter | Demo keys of the dump (step 2) |

It writes the answers to `.env.staging` (mode 600, never committed), with a new random `DJANGO_SECRET_KEY`.

### `.env.staging` reference

| Variable | Required | Meaning |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | yes | `config.settings.staging` |
| `DJANGO_ALLOWED_HOSTS` | yes | Domain or IP, comma separated |
| `CSRF_TRUSTED_ORIGINS` | yes | `https://domain` or `http://IP:port` |
| `STAGING_HTTPS` | yes | `true` behind HTTPS (secure cookies), `false` for plain HTTP by IP |
| `DJANGO_SECRET_KEY` | yes | 50+ random characters |
| `FIELD_ENCRYPTION_KEYS` | yes | Fernet key(s), comma separated, newest first. Must match the dump |
| `BLIND_INDEX_KEY` | yes | Must match the dump |
| `DATABASE_URL` | yes | `mysql://user:password@127.0.0.1:3306/elite` (URL-encoded) |
| `REVIEW_PASSWORD` | no | New shared password of the test accounts; empty keeps `Elite-Test-2026!` |
| `ELITE_BIND` | yes | Where gunicorn listens, e.g. `127.0.0.1:8090` or `0.0.0.0:8095` |
| `WEB_WORKERS` | no | gunicorn workers, default 3 (about 2 × CPU + 1) |
| `REDIS_URL` | no | e.g. `redis://127.0.0.1:6379/0`. Empty means MySQL cache/sessions and no Celery |
| `ENFORCE_PRIVILEGED_MFA` | no | `true` to require authenticator codes for privileged roles |
| `AI_ENABLED`, `ANTHROPIC_API_KEY`, `AI_MODEL` | no | AI assistant; off by default (rule-based fallback) |

## 5. Start and stop

```bash
./start.sh     # web app in the background; prints "Health check OK"
./stop.sh
```

| Path | Contents |
|---|---|
| `logs/app.log` | Application log and errors. **Portal sign-in codes** (WhatsApp is not sent on a review server) appear here |
| `logs/access.log` | Requests |
| `logs/celery-*.log` | Background jobs (only with Redis) |
| `run/*.pid` | Process ids used by `stop.sh` |

**Publishing it**

- *With a domain (CloudPanel):* add a **Reverse Proxy** site pointing to `http://127.0.0.1:8090`, then issue a
  Let's Encrypt certificate. Use `STAGING_HTTPS=true`.
- *IP only:* open the chosen port (e.g. 8095) in the firewall and browse to `http://IP:8095/en/`.

URLs: website `/en/` and `/ar/`, staff desk `/en/desk/`, family portal `/en/portal/`, CMS `/cms/`, health `/healthz`.
Sign in to the desk with a test account, e.g. `ops@test.elite.local`, `ceo@test.elite.local`,
`admin.prm@test.elite.local`, with `Elite-Test-2026!` (or your `REVIEW_PASSWORD`).

**Start after a reboot:** as the site user, `crontab -e` and add
`@reboot /path/to/elite/start.sh >> /path/to/elite/logs/boot.log 2>&1`.
(Or use `backend/scripts/elite-review.service` with systemd instead of `start.sh`/`stop.sh`; don't use both.)

## 6. Scheduled jobs

With `REDIS_URL` set, `start.sh` runs Celery beat, which runs every scheduled job. Without Redis, add these to the
site user's crontab (`crontab -e`; replace `/path/to/elite`):

```cron
SHELL=/bin/sh
E=cd /path/to/elite/backend && set -a && . ../.env.staging && set +a && .venv/bin/python manage.py
0 6 * * *   eval "$E run_daily_jobs"   >> /path/to/elite/logs/jobs.log 2>&1
15 * * * *  eval "$E run_phase2_jobs"  >> /path/to/elite/logs/jobs.log 2>&1
30 23 * * 5 eval "$E run_phase2_jobs --snapshot" >> /path/to/elite/logs/jobs.log 2>&1
0 12 * * 6  eval "$E run_phase2_jobs --remind-reports" >> /path/to/elite/logs/jobs.log 2>&1
```

## 7. Updating

```bash
./stop.sh
git pull
./runonce.sh      # packages, migrations, static files; the dump is not re-loaded
./start.sh
```

## 8. Unit tests

`runonce.sh` installs the test tools (`requirements-dev.txt`). The unit tests do **not** touch the loaded data: pytest
creates its own empty database `test_<database name>` (e.g. `test_elite`), fills it from fixtures, and keeps it for
the next run (`--reuse-db`). The database user therefore also needs rights on that database (as MySQL root):

```sql
GRANT ALL PRIVILEGES ON test_elite.* TO 'elite'@'127.0.0.1';
```

Then:

```bash
cd backend
set -a; . ../.env.staging; set +a
.venv/bin/pytest                    # whole suite
.venv/bin/pytest tests/test_x.py -k name   # one file / test
.venv/bin/pytest --create-db        # rebuild the test database after new migrations
```

The loaded dump is for testing the running system by hand (desk, portal, reports) with realistic data.

## 9. Backups

- Database, daily: `mysqldump --single-transaction --routines elite | gzip > elite-$(date +%F).sql.gz`, kept off the server.
  Test a restore regularly.
- Keep `.env.staging` in a password manager (on a live system, above all its own `FIELD_ENCRYPTION_KEYS` and `BLIND_INDEX_KEY`).
- `backend/media` and `backend/private_media` (uploaded images, member photos and signatures), once people upload files.

## 10. Checklist

- [ ] MySQL 8.0, Python 3.11+, build packages installed
- [ ] Empty `utf8mb4_0900_ai_ci` database and user created (plus rights on `test_elite` for unit tests)
- [ ] Dump present at `deploy/db/elite.sql`
- [ ] `./runonce.sh` finished with "Done"
- [ ] `./start.sh` printed "Health check OK"
- [ ] Reverse proxy + HTTPS (domain) or firewall port (IP) set up
- [ ] Scheduled jobs: Redis + Celery, or the cron lines
- [ ] Start on reboot configured
- [ ] Daily database backup configured
