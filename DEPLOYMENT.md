# Elite Academy — Deployment Requirements

How to put the Elite Academy system (Django back end, website, staff desk and family portal) on a Linux server
**without Docker**, load the prepared database, and start/stop it with three scripts:

| Script | When | What it does |
|---|---|---|
| `runonce.sh` | First install, and again after every `git pull` | Runs silently (no questions): writes `.env.staging`, builds the Python environment, loads the database dump into an empty database, applies newer migrations, collects static files |
| `start.sh` | To start | Starts gunicorn under **pm2** as `dojomanager` (plus `dojomanager-worker` and `dojomanager-beat` for Celery when Redis is configured), saves the pm2 list, then runs a health check |
| `stop.sh` | To stop | Removes those processes from pm2 (and stops an instance left by the older pid-file scripts) |

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
| pm2 | `npm install -g pm2` (Node.js 18+) |
| Database | **MariaDB 10.6+** (this dev server: `localhost:3306`, database `dojomanager`) or MySQL 8.0. The dump is from MySQL 8; on MariaDB `runonce.sh` loads it with `utf8mb4_unicode_ci` |
| Redis | Optional. Without it, the cache and sessions are kept in MySQL and the scheduled jobs run from cron |
| Network | Outbound HTTPS to pypi.org during `runonce.sh`. Inbound: 443 via a reverse proxy (domain), or the chosen app port (IP only) |
| Account | A normal (non-root) user that owns the repository folder; root only for installing packages and cron/systemd |

Packages (as root, once):

```bash
apt update
apt install -y git python3 python3-venv python3-dev build-essential pkg-config \
               default-libmysqlclient-dev mariadb-client openssl curl
# Only if the database server is not already installed:
apt install -y mariadb-server
# Optional:
apt install -y redis-server
```

## 2. Database

Create the database and user by hand, once (as the MariaDB root user, `sudo mariadb`). The dev server uses database
`dojomanager`, user `app_user`, password `Chennai#44`, on `localhost:3306`. These are the defaults in `runonce.sh`:

```sql
CREATE DATABASE dojomanager CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'app_user'@'localhost' IDENTIFIED BY 'Chennai#44';
CREATE USER 'app_user'@'127.0.0.1' IDENTIFIED BY 'Chennai#44';
GRANT ALL PRIVILEGES ON dojomanager.* TO 'app_user'@'localhost';
GRANT ALL PRIVILEGES ON dojomanager.* TO 'app_user'@'127.0.0.1';
-- for the unit tests (step 8):
GRANT ALL PRIVILEGES ON test_dojomanager.* TO 'app_user'@'localhost';
GRANT ALL PRIVILEGES ON test_dojomanager.* TO 'app_user'@'127.0.0.1';
```

`runonce.sh` connects over TCP to `127.0.0.1`, hence the `@'127.0.0.1'` user. If the database already exists with
another character set, `runonce.sh` switches its default to utf8mb4 (needed for Arabic).

The dump (`deploy/db/elite.sql`, a `mysqldump` of MySQL 8.0.46, 216 tables; loads into MariaDB too) contains the full schema **and** the
fictional Kuwait test data: test staff accounts (`…@test.elite.local`), members, families, classes, sales, website
pages. `runonce.sh` loads it only when the database has no tables, so re-running never overwrites data. To start
over, drop and re-create the database, then run `runonce.sh` again.

> **Encryption keys.** Civil IDs and medical notes in the dump are encrypted with the demo keys of the dev
> instance, which are also the defaults in `config/settings/dev.py`:
> `FIELD_ENCRYPTION_KEYS=bG9jYWwtZGV2LW9ubHkta2V5LTMyLWJ5dGVzLWxvbmc=` and
> `BLIND_INDEX_KEY=local-dev-only-blind-index-key`. `runonce.sh` uses them by default. With other keys the
> member pages fail, and `runonce.sh` stops with an error that says so. These keys are public: never use them with
> real member data.

## 3. Get the code

```bash
git clone -b main https://github.com/BT-Rajan/dojo-temp.git elite
cd elite
```

Only the `backend` folder, the three scripts and the dump are needed on the server. Do not copy any folder of real
member documents to a review server.

## 4. First install: `./runonce.sh`

```bash
./runonce.sh                      # uses deploy/db/elite.sql
./runonce.sh /path/to/elite.sql   # or another dump
```

It asks nothing. On the first run it writes `.env.staging` (mode 600, never committed) from these defaults, with a
new random `DJANGO_SECRET_KEY`. To change one, set it on the command line, e.g.
`ELITE_PORT=8095 ./runonce.sh`, or delete `.env.staging` and run again:

| Variable | Default | Meaning |
|---|---|---|
| `DB_HOST` / `DB_PORT` | `127.0.0.1` / `3306` | Database server |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `dojomanager` / `app_user` / `Chennai#44` | From step 2 |
| `ELITE_PORT` | `8090` | App port |
| `ELITE_DOMAIN` | empty | Empty: plain HTTP on `0.0.0.0:<port>`, reachable by every IP and the host name of the server. A domain: HTTPS through a reverse proxy, app on `127.0.0.1:<port>` |
| `FIELD_ENCRYPTION_KEYS`, `BLIND_INDEX_KEY` | demo keys | Keys of the dump (step 2) |
| `REVIEW_PASSWORD` | empty | Empty keeps the demo password `Elite-Test-2026!`; otherwise (12+ characters) it replaces it on every `…@test.elite.local` account |

It also detects MariaDB vs MySQL and records the collation it uses (`DB_COLLATION`).

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
| `DATABASE_URL` | yes | `mysql://user:password@127.0.0.1:3306/dojomanager` (URL-encoded, so `#` is `%23`) |
| `DB_COLLATION` | no | `utf8mb4_unicode_ci` on MariaDB, `utf8mb4_0900_ai_ci` on MySQL 8 (used for the unit-test database) |
| `REVIEW_PASSWORD` | no | New shared password of the test accounts; empty keeps `Elite-Test-2026!` |
| `ELITE_BIND` | yes | Where gunicorn listens, e.g. `127.0.0.1:8090` or `0.0.0.0:8095` |
| `WEB_WORKERS` | no | gunicorn workers, default 3 (about 2 × CPU + 1) |
| `REDIS_URL` | no | e.g. `redis://127.0.0.1:6379/0`. Empty means MySQL cache/sessions and no Celery |
| `ENFORCE_PRIVILEGED_MFA` | no | `true` to require authenticator codes for privileged roles |
| `AI_ENABLED`, `ANTHROPIC_API_KEY`, `AI_MODEL` | no | AI assistant; off by default (rule-based fallback) |

## 5. Start and stop

```bash
./start.sh     # starts pm2 process "dojomanager"; prints "Health check OK"
./stop.sh
```

Day to day you can also use pm2 directly:

```bash
pm2 status                  # dojomanager online, its pid, memory, restarts
pm2 logs dojomanager        # live log
pm2 restart dojomanager     # restart (keeps the settings it was started with)
```

After changing `.env.staging`, use `./stop.sh && ./start.sh` so the new settings are picked up.

| Path | Contents |
|---|---|
| `logs/app.log` | Application log and errors. **Portal sign-in codes** (WhatsApp is not sent on a review server) appear here |
| `logs/access.log` | Requests |
| `logs/celery-*.log` | Background jobs (only with Redis) |

**Publishing it**

- *With a domain (CloudPanel):* add a **Reverse Proxy** site pointing to `http://127.0.0.1:8090`, then issue a
  Let's Encrypt certificate. Use `STAGING_HTTPS=true`.
- *IP only (default):* open port 8090 in the firewall and browse to `http://IP:8090/en/`.

URLs: website `/en/` and `/ar/`, staff desk `/en/desk/`, family portal `/en/portal/`, CMS `/cms/`, health `/healthz`.
Sign in to the desk with a test account, e.g. `ops@test.elite.local`, `ceo@test.elite.local`,
`admin.prm@test.elite.local`, with `Elite-Test-2026!` (or your `REVIEW_PASSWORD`).

**Start after a reboot:** `start.sh` runs `pm2 save`, so once pm2's boot service is installed it brings
`dojomanager` back by itself. Install it once with `pm2 startup` (it prints a command to run as root).
Don't also use `backend/scripts/elite-review.service`: both would start the app on the same port.

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
creates its own empty database `test_<database name>` (`test_dojomanager`), fills it from fixtures, and keeps it for
the next run (`--reuse-db`). The database user therefore also needs rights on that database (the last two `GRANT`s
in step 2).

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

- Database, daily: `mariadb-dump --single-transaction --routines dojomanager | gzip > dojomanager-$(date +%F).sql.gz`, kept off the server.
  Test a restore regularly.
- Keep `.env.staging` in a password manager (on a live system, above all its own `FIELD_ENCRYPTION_KEYS` and `BLIND_INDEX_KEY`).
- `backend/media` and `backend/private_media` (uploaded images, member photos and signatures), once people upload files.

## 10. Checklist

- [ ] MariaDB 10.6+ (or MySQL 8.0), Python 3.11+, build packages installed
- [ ] Database `dojomanager` and its user created (plus rights on `test_dojomanager` for unit tests)
- [ ] Dump present at `deploy/db/elite.sql`
- [ ] `./runonce.sh` finished with "Done"
- [ ] `./start.sh` printed "Health check OK"
- [ ] Reverse proxy + HTTPS (domain) or firewall port (IP) set up
- [ ] Scheduled jobs: Redis + Celery, or the cron lines
- [ ] pm2 installed; `pm2 startup` run once (start on reboot)
- [ ] Daily database backup configured
