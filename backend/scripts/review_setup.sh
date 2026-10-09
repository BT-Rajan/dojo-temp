#!/bin/sh
# Review server without Docker (a CloudPanel Python site). Run as the site user from the repository folder,
# after .env.staging exists:   sh backend/scripts/review_setup.sh
# Safe to run again after `git pull`: it updates packages and the database, and loads the test data only once.
set -e
ROOT=$(pwd)
[ -f "$ROOT/.env.staging" ] || { echo "Create .env.staging first (backend/scripts/make_review_env.sh)."; exit 1; }
cd "$ROOT/backend"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
set -a; . "$ROOT/.env.staging"; set +a
export DJANGO_SETTINGS_MODULE=config.settings.staging
python manage.py migrate --noinput
python manage.py createcachetable
if [ ! -f "$ROOT/.seeded" ]; then
    echo "Loading the fictional Kuwait test data (first time only)..."
    python manage.py seed_kuwait
    python manage.py seed_website
    python manage.py run_daily_jobs || true
    touch "$ROOT/.seeded"
fi
python manage.py collectstatic --noinput >/dev/null
python manage.py set_review_password
echo "Ready. Start or restart the service:  sudo systemctl restart elite-review"
