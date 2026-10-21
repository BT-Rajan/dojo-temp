#!/bin/sh
# Elite Academy: stop the pm2 processes started by ./start.sh (dojomanager, and the Celery ones if any).
ROOT=$(cd "$(dirname "$0")" && pwd)
RUN="$ROOT/run"
NAME=dojomanager

if command -v pm2 >/dev/null; then
    for app in "$NAME-beat" "$NAME-worker" "$NAME"; do
        if pm2 describe "$app" >/dev/null 2>&1; then
            pm2 delete "$app" >/dev/null && echo "$app: stopped."
        else
            echo "$app: not running."
        fi
    done
    pm2 save --force >/dev/null 2>&1 || true
fi

# An instance started by the older pid-file version of start.sh.
for f in celery-beat celery-worker gunicorn; do
    PIDFILE="$RUN/$f.pid"
    [ -f "$PIDFILE" ] || continue
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill -TERM "$PID"
        i=0
        while kill -0 "$PID" 2>/dev/null && [ $i -lt 30 ]; do i=$((i + 1)); sleep 1; done
        kill -KILL "$PID" 2>/dev/null || true
        echo "$f (old pid-file instance): stopped."
    fi
    rm -f "$PIDFILE"
done
