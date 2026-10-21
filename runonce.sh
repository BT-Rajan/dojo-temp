#!/bin/sh
# Elite Academy: one-time server setup (no Docker). Run as the site user from the repository folder:
#   ./runonce.sh                      uses deploy/db/elite.sql
#   ./runonce.sh /path/to/elite.sql   uses another dump
# It writes .env.staging (asks a few questions the first time), creates the Python environment, loads the database
# dump into an EMPTY database, applies newer migrations, collects static files and sets the test-account password.
# Safe to run again after `git pull` (stop first): it never re-imports into a database that already has tables.
set -e
ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$ROOT"
ENV_FILE="$ROOT/.env.staging"
DUMP="${1:-$ROOT/deploy/db/elite.sql}"

say() { printf '\n==> %s\n' "$1"; }
die() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }
ask() { printf "%s" "$1"; read -r REPLY; }
ask_secret() { printf "%s" "$1"; stty -echo 2>/dev/null || true; read -r REPLY; stty echo 2>/dev/null || true; echo; }
rand() { openssl rand -base64 "$1" | tr -d '\n/+='; }

say "Checking the server"
command -v python3 >/dev/null || die "python3 is missing (3.11 or newer)."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || die "Python 3.11 or newer is needed (found $(python3 -V))."
python3 -c 'import venv' 2>/dev/null || die "python3-venv is missing: apt install -y python3-venv"
command -v mysql >/dev/null || die "The mysql client is missing: apt install -y default-mysql-client"
command -v openssl >/dev/null || die "openssl is missing: apt install -y openssl"
command -v pkg-config >/dev/null || die "Build packages are missing: apt install -y python3-dev build-essential pkg-config default-libmysqlclient-dev"

# 1. Settings file ---------------------------------------------------------------------------------------------------
if [ ! -f "$ENV_FILE" ]; then
    say "Creating .env.staging (first run)"
    ask "Address staff will use: a domain (review.example.com) or IP:port (169.58.13.213:8095): "; ADDRESS="$REPLY"
    [ -n "$ADDRESS" ] || die "An address is needed."
    PORT=8090
    case "$ADDRESS" in *:*) PORT="${ADDRESS##*:}"; ADDRESS="${ADDRESS%%:*}" ;; esac
    case "$PORT" in ''|*[!0-9]*) die "The port must be a number." ;; esac
    case "$ADDRESS" in
        *[a-zA-Z]*) HTTPS=true; ORIGIN="https://$ADDRESS"; BIND="127.0.0.1:$PORT" ;;
        *) HTTPS=false; ORIGIN="http://$ADDRESS:$PORT"; BIND="0.0.0.0:$PORT" ;;
    esac
    ask "MySQL host [127.0.0.1]: "; DBHOST="${REPLY:-127.0.0.1}"
    ask "MySQL port [3306]: "; DBPORT="${REPLY:-3306}"
    ask "Database name [elite]: "; DBNAME="${REPLY:-elite}"
    ask "Database user [elite]: "; DBUSER="${REPLY:-elite}"
    ask_secret "Database user password: "; DBPASS="$REPLY"
    [ -n "$DBPASS" ] || die "The database password is needed."
    ask_secret "Password for the test accounts on this server (min 12 characters, no ' quote): "; REVIEW="$REPLY"
    [ ${#REVIEW} -ge 12 ] || die "Too short."
    case "$REVIEW" in *"'"*) die "Please choose a password without the ' character." ;; esac
    echo "Encryption keys: the dump's Civil IDs and medical notes can only be read with the keys of the server it"
    echo "was taken from. Paste them. Press Enter to generate new ones only for a database without members."
    ask_secret "FIELD_ENCRYPTION_KEYS [generate]: "; FEK="${REPLY:-$(openssl rand -base64 32 | tr '+/' '-_')}"
    ask_secret "BLIND_INDEX_KEY [generate]: "; BIK="${REPLY:-$(rand 48)}"
    URL=$(DBUSER="$DBUSER" DBPASS="$DBPASS" DBNAME="$DBNAME" DBHOST="$DBHOST" DBPORT="$DBPORT" python3 -c "
import os, urllib.parse as u
q = lambda k: u.quote(os.environ[k], safe='')
print(f\"mysql://{q('DBUSER')}:{q('DBPASS')}@{os.environ['DBHOST']}:{os.environ['DBPORT']}/{q('DBNAME')}\")")
    umask 077
    {
        echo "DJANGO_SETTINGS_MODULE=config.settings.staging"
        echo "DJANGO_ALLOWED_HOSTS=$ADDRESS"
        echo "CSRF_TRUSTED_ORIGINS=$ORIGIN"
        echo "STAGING_HTTPS=$HTTPS"
        echo "DJANGO_SECRET_KEY=$(rand 64)"
        echo "FIELD_ENCRYPTION_KEYS='$FEK'"
        echo "BLIND_INDEX_KEY='$BIK'"
        echo "REVIEW_PASSWORD='$REVIEW'"
        echo "DATABASE_URL='$URL'"
        echo "REDIS_URL="
        echo "ELITE_BIND=$BIND"
        echo "WEB_WORKERS=3"
    } > "$ENV_FILE"
    umask 022
    echo "Written $ENV_FILE (readable only by you). Address: $ORIGIN"
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
sql -e "SELECT 1" >/dev/null || die "Can't connect with DATABASE_URL in .env.staging. Create the database and user first (DEPLOYMENT.md, step 2)."
TABLES=$(sql -N -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()")
if [ "$TABLES" -eq 0 ]; then
    [ -f "$DUMP" ] || die "Database dump not found: $DUMP"
    say "Loading the database dump $(basename "$DUMP") (a minute)"
    sql < "$DUMP"
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
pip install -q -r requirements.txt

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
