#!/bin/sh
# Elite Academy: stop the web app and the Celery processes started by ./start.sh
ROOT=$(cd "$(dirname "$0")" && pwd)
RUN="$ROOT/run"

stop() {
    PIDFILE="$RUN/$1.pid"
    if [ ! -f "$PIDFILE" ]; then
        echo "$1: not running."
        return
    fi
    PID=$(cat "$PIDFILE")
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "$1: not running (stale pid file removed)."
        rm -f "$PIDFILE"
        return
    fi
    kill -TERM "$PID"
    i=0
    while kill -0 "$PID" 2>/dev/null; do
        i=$((i + 1))
        if [ $i -gt 30 ]; then
            echo "$1: still running after 30 s, forcing it."
            kill -KILL "$PID" 2>/dev/null
            break
        fi
        sleep 1
    done
    rm -f "$PIDFILE"
    echo "$1: stopped."
}

stop celery-beat
stop celery-worker
stop gunicorn
