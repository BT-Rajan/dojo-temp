#!/bin/sh
# Elite Academy: one-time server setup (no Docker). Runs silently: no questions. From the repository folder:
#   ./runonce.sh                      uses deploy/db/elite.sql
#   ./runonce.sh /path/to/elite.sql   uses another dump
# It writes .env.staging, creates the Python environment, loads the database dump into an EMPTY database (MySQL 8 or
# MariaDB), applies newer migrations and collects static files.
# Safe to run again after `git pull` (stop first): it never re-imports into a database that already has tables.
#
# Defaults below are this dev instance's; override any of them on the command line, e.g.
#   DB_PASSWORD='other' ELITE_PORT=8095 ./runonce.sh
# They are used only when .env.staging does not exist yet; delete it to write a new one.
set -e
ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"
ENV_FILE="$ROOT/.env.staging"
DUMP="${1:-$ROOT/deploy/db/elite.sql}"

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-dojomanager}"
DB_USER="${DB_USER:-dojomanager}"
DB_PASSWORD="${DB_PASSWORD:-Chennai#44}"
ELITE_PORT="${ELITE_PORT:-8090}"
# A domain served over HTTPS by a reverse proxy (the app then listens on 127.0.0.1 only). Empty: plain HTTP by IP.
ELITE_DOMAIN="${ELITE_DOMAIN:-}"
# Demo keys of the dev instance: deploy/db/elite.sql was encrypted with them (same as config/settings/dev.py).
FIELD_ENCRYPTION_KEYS="${FIELD_ENCRYPTION_KEYS:-bG9jYWwtZGV2LW9ubHkta2V5LTMyLWJ5dGVzLWxvbmc=}"
BLIND_INDEX_KEY="${BLIND_INDEX_KEY:-local-dev-only-blind-index-key}"
# Empty keeps the demo password of the test accounts (Elite-Test-2026!).
REVIEW_PASSWORD="${REVIEW_PASSWORD:-}"

say() { printf '\n==> %s\n' "$1"; }
die() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
rand() { openssl rand -base64 "$1" | tr -d '\n/+='; }

say "Checking the server"
command -v python3 >/dev/null || die "python3 is missing (3.11 or newer)."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || die "Python 3.11 or newer is needed (found $(python3 -V))."
python3 -c 'import venv' 2>/dev/null || die "python3-venv is missing: apt install -y python3-venv"
command -v mysql >/dev/null || die "The mysql client is missing: apt install -y mariadb-client (or default-mysql-client)"
command -v openssl >/dev/null || die "openssl is missing: apt install -y openssl"
command -v pkg-config >/dev/null || die "Build packages are missing: apt install -y python3-dev build-essential pkg-config default-libmysqlclient-dev"

# 1. Settings file ---------------------------------------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    say "Creating .env.staging"
    if [ -n "$ELITE_DOMAIN" ]; then
        HOSTS="$ELITE_DOMAIN"; ORIGINS="https://$ELITE_DOMAIN"; HTTPS=true; BIND="127.0.0.1:$ELITE_PORT"
    else
        # Every address of this server, so it answers by IP, host name and localhost.
        HOSTS="localhost,127.0.0.1"; ORIGINS="http://localhost:$ELITE_PORT,http://127.0.0.1:$ELITE_PORT"
        for h in $(hostname -I 2>/dev/null) $(hostname -f 2>/dev/null || hostname); do
            case "$h" in *:*) continue ;; esac   # skip IPv6
            HOSTS="$HOSTS,$h"; ORIGINS="$ORIGINS,http://$h:$ELITE_PORT"
        done
        HTTPS=false; BIND="0.0.0.0:$ELITE_PORT"
    fi
    URL=$(DBUSER="$DB_USER" DBPASS="$DB_PASSWORD" DBNAME="$DB_NAME" DBHOST="$DB_HOST" DBPORT="$DB_PORT" python3 -c "
import os, urllib.parse as u
q = lambda k: u.quote(os.environ[k], safe='')
print(f\"mysql://{q('DBUSER')}:{q('DBPASS')}@{os.environ['DBHOST']}:{os.environ['DBPORT']}/{q('DBNAME')}\")")
    umask 077
    {
        echo "DJANGO_SETTINGS_MODULE=config.settings.staging"
        echo "DJANGO_ALLOWED_HOSTS=$HOSTS"
        echo "CSRF_TRUSTED_ORIGINS=$ORIGINS"
        echo "STAGING_HTTPS=$HTTPS"
        echo "DJANGO_SECRET_KEY=$(rand 64)"
        echo "FIELD_ENCRYPTION_KEYS='$FIELD_ENCRYPTION_KEYS'"
        echo "BLIND_INDEX_KEY='$BLIND_INDEX_KEY'"
        echo "REVIEW_PASSWORD='$REVIEW_PASSWORD'"
        echo "DATABASE_URL='$URL'"
        echo "REDIS_URL="
        echo "ELITE_BIND=$BIND"
        echo "WEB_WORKERS=3"
    } > "$ENV_FILE"
    umask 022
    echo "Written $ENV_FILE. The app will listen on $BIND."
fi

set -a; . "$ENV_FILE"; set +a
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.staging}"

# MySQL client credentials go in a private temporary file, never on the command line.
MYCNF=$(mktemp)
trap 'rm -f "$MYCNF"' EXIT
python3 - "$MYCNF" <<'EOF'
import os, sys, urllib.parse as u
p = u.urlparse(os.environ["DATABASE_URL"])
esc = lambda s: u.unquote(s or "").replace("\\", "\\\\").replace('"', '\\"')
with open(sys.argv[1], "w") as f:
    f.write('[client]\nuser="%s"\npassword="%s"\nhost="%s"\nport=%d\n' % (esc(p.username), esc(p.password), p.hostname or "127.0.0.1", p.port or 3306))
    f.write('[mysql]\ndatabase="%s"\ndefault-character-set=utf8mb4\n' % esc(p.path.lstrip("/")))
EOF
chmod 600 "$MYCNF"
sql() { mysql --defaults-extra-file="$MYCNF" "$@"; }

# 2. Database ---------------------------------------------------------------------------------------------------------
say "Checking the database"
sql -e "SELECT 1" >/dev/null || die "Can't connect to database $DB_NAME as $DB_USER on $DB_HOST:$DB_PORT (DATABASE_URL in .env.staging). Create the database and user first (DEPLOYMENT.md, step 2)."
# The dump is from MySQL 8 (collation utf8mb4_0900_ai_ci); MariaDB before 11.4.5 lacks it, so use utf8mb4_unicode_ci.
if [ "$(sql -N -e "SELECT COUNT(*) FROM information_schema.collations WHERE collation_name = 'utf8mb4_0900_ai_ci'")" -gt 0 ]; then
    COLLATION=utf8mb4_0900_ai_ci
else
    COLLATION=utf8mb4_unicode_ci
fi
echo "$(sql -N -e "SELECT VERSION()"), collation $COLLATION"
grep -q '^DB_COLLATION=' "$ENV_FILE" || echo "DB_COLLATION=$COLLATION" >> "$ENV_FILE"
export DB_COLLATION="$COLLATION"
# Tables created later by migrations take the database default: make it utf8mb4 so Arabic is stored correctly.
sql -e "ALTER DATABASE CHARACTER SET utf8mb4 COLLATE $COLLATION"
TABLES=$(sql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()")
if [ "$TABLES" -eq 0 ]; then
    [ -f "$DUMP" ] || die "Database dump not found: $DUMP"
    say "Loading the database dump $(basename "$DUMP") (a minute)"
    sed "s/utf8mb4_0900_ai_ci/$COLLATION/g" "$DUMP" | sql
    echo "Loaded $(sql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()") tables."
else
    echo "The database already has $TABLES tables: dump not loaded (updates only)."
fi

# 3. Application --------------------------------------------------------------------------------------------------------
say "Python environment and packages"
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements-dev.txt   # includes requirements.txt, plus pytest for the unit tests

say "Database updates, cache table, static files"
python manage.py migrate --noinput
python manage.py createcachetable
python manage.py collectstatic --noinput >/dev/null
if ! python manage.py shell -c "from apps.members.models import Member; list(Member.objects.all()[:1])" >/dev/null 2>&1; then
    die "Member records can't be decrypted: FIELD_ENCRYPTION_KEYS in .env.staging is not the key the dump was made
with. Put the source server's FIELD_ENCRYPTION_KEYS and BLIND_INDEX_KEY in .env.staging and run ./runonce.sh again."
fi
if [ -n "$REVIEW_PASSWORD" ] && [ "$DJANGO_SETTINGS_MODULE" != "config.settings.prod" ]; then
    python manage.py set_review_password
    echo "Test accounts (…@test.elite.local) now use REVIEW_PASSWORD."
fi

mkdir -p "$ROOT/run" "$ROOT/logs"
date > "$ROOT/run/.runonce-done"
say "Done. Start the system with ./start.sh"
