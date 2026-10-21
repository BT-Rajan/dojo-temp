#!/bin/sh
# Elite Academy: start the web app (gunicorn) in the background, plus Celery worker and beat when REDIS_URL is set.
# Run ./runonce.sh first. Logs go to logs/, process ids to run/. Stop with ./stop.sh
set -e
ROOT=$(cd "$(dirname "$0")" && pwd)
ENV_FILE="$ROOT/.env.staging"
RUN="$ROOT/run"
LOGS="$ROOT/logs"

[ -f "$RUN/.runonce-done" ] || { echo "Run ./runonce.sh first."; exit 1; }
[ -f "$ENV_FILE" ] || { echo "$ENV_FILE is missing: run ./runonce.sh"; exit 1; }
set -a; . "$ENV_FILE"; set +a
export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.staging}"
BIND="${ELITE_BIND:-127.0.0.1:8090}"
mkdir -p "$RUN" "$LOGS"

running() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

cd "$ROOT/backend"
. .venv/bin/activate

if running "$RUN/gunicorn.pid"; then
    echo "The web app is already running (pid $(cat "$RUN/gunicorn.pid"))."
else
    gunicorn config.wsgi:application --daemon --pid "$RUN/gunicorn.pid" \
        --bind "$BIND" --workers "${WEB_WORKERS:-3}" --timeout 120 --forwarded-allow-ips 127.0.0.1 \
        --access-logfile "$LOGS/access.log" --error-logfile "$LOGS/app.log" --capture-output
    i=0
    until running "$RUN/gunicorn.pid"; do
        i=$((i + 1)); [ $i -le 20 ] || { echo "The web app did not start: see $LOGS/app.log"; exit 1; }
        sleep 1
    done
    echo "Web app started on $BIND (pid $(cat "$RUN/gunicorn.pid"))."
fi

if [ -n "$REDIS_URL" ]; then
    if running "$RUN/celery-worker.pid"; then
        echo "Celery worker already running."
    else
        celery -A config worker --detach --pidfile "$RUN/celery-worker.pid" --logfile "$LOGS/celery-worker.log" -l info
        echo "Celery worker started."
    fi
    if running "$RUN/celery-beat.pid"; then
        echo "Celery beat already running."
    else
        celery -A config beat --detach --pidfile "$RUN/celery-beat.pid" --logfile "$LOGS/celery-beat.log" \
            --schedule "$RUN/celerybeat-schedule" -l info
        echo "Celery beat (scheduled jobs) started."
    fi
else
    echo "No REDIS_URL: scheduled jobs run from cron instead (DEPLOYMENT.md, step 6)."
fi

if command -v curl >/dev/null; then
    HOST="${BIND%%:*}"; [ "$HOST" = "0.0.0.0" ] && HOST=127.0.0.1
    sleep 2
    if curl -fsS -o /dev/null -H "Host: ${DJANGO_ALLOWED_HOSTS%%,*}" "http://$HOST:${BIND##*:}/healthz"; then
        echo "Health check OK."
    else
        echo "Health check failed: see $LOGS/app.log"
    fi
fi
