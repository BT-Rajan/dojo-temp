#!/bin/sh
# Elite Academy: start the web app (gunicorn) under pm2 as "dojomanager", plus "dojomanager-worker" and
# "dojomanager-beat" (Celery) when REDIS_URL is set. Run ./runonce.sh first. Stop with ./stop.sh
#   pm2 status | pm2 logs dojomanager | pm2 restart dojomanager
# Logs also go to logs/app.log (application, errors, portal sign-in codes) and logs/access.log (requests).
set -e
ROOT=$(cd "$(dirname "$0")" && pwd)
ENV_FILE="$ROOT/.env.staging"
RUN="$ROOT/run"
LOGS="$ROOT/logs"
NAME=dojomanager

command -v pm2 >/dev/null || { echo "pm2 is missing: npm install -g pm2"; exit 1; }
[ -f "$RUN/.runonce-done" ] || { echo "Run ./runonce.sh first."; exit 1; }
[ -f "$ENV_FILE" ] || { echo "$ENV_FILE is missing: run ./runonce.sh"; exit 1; }
set -a; . "$ENV_FILE"; set +a
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.staging}"
BIND="${ELITE_BIND:-127.0.0.1:8090}"
mkdir -p "$RUN" "$LOGS"

online() { [ "$(pm2 pid "$1" 2>/dev/null | tail -1)" -gt 0 ] 2>/dev/null; }

if online "$NAME"; then
    echo "$NAME is already running under pm2 (pid $(pm2 pid "$NAME" | tail -1)). Restart: ./stop.sh && ./start.sh"
    exit 0
fi
# Clear a stopped pm2 entry, or an instance started by the older pid-file version of these scripts.
"$ROOT/stop.sh" >/dev/null

VENV="$ROOT/backend/.venv/bin"
# pm2 keeps the environment of this shell (the settings from .env.staging) for its restarts.
pm2 start "$VENV/gunicorn" --name "$NAME" --interpreter none --cwd "$ROOT/backend" \
    --output "$LOGS/access.log" --error "$LOGS/app.log" --time \
    -- config.wsgi:application --bind "$BIND" --workers "${WEB_WORKERS:-3}" --timeout 120 \
    --forwarded-allow-ips 127.0.0.1 --access-logfile - --error-logfile - >/dev/null

if [ -n "$REDIS_URL" ]; then
    pm2 start "$VENV/celery" --name "$NAME-worker" --interpreter none --cwd "$ROOT/backend" \
        --output "$LOGS/celery-worker.log" --error "$LOGS/celery-worker.log" --time \
        -- -A config worker -l info >/dev/null
    pm2 start "$VENV/celery" --name "$NAME-beat" --interpreter none --cwd "$ROOT/backend" \
        --output "$LOGS/celery-beat.log" --error "$LOGS/celery-beat.log" --time \
        -- -A config beat -l info --schedule "$RUN/celerybeat-schedule" >/dev/null
    echo "Celery worker and beat (scheduled jobs) started as $NAME-worker and $NAME-beat."
else
    echo "No REDIS_URL: scheduled jobs run from cron instead (DEPLOYMENT.md, step 6)."
fi
# Remember the process list, so `pm2 resurrect` (or pm2's boot service, `pm2 startup`) brings it back.
pm2 save >/dev/null

HOST="${BIND%%:*}"; [ "$HOST" = "0.0.0.0" ] && HOST=127.0.0.1
i=0
until curl -fsS -o /dev/null -H "Host: ${DJANGO_ALLOWED_HOSTS%%,*}" "http://$HOST:${BIND##*:}/healthz" 2>/dev/null; do
    i=$((i + 1))
    if [ $i -gt 30 ] || ! online "$NAME"; then
        echo "The web app did not come up: see $LOGS/app.log or pm2 logs $NAME"
        exit 1
    fi
    sleep 1
done
echo "Web app started under pm2 as $NAME on $BIND (pid $(pm2 pid "$NAME" | tail -1)). Health check OK."
