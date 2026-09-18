#!/usr/bin/env bash
#
# mm.sh — start/stop/status the Media Manager stack without Docker.
#
# Usage:
#   ./mm.sh start    # launch API + web in the background
#   ./mm.sh stop     # stop both
#   ./mm.sh restart  # stop, then start
#   ./mm.sh status   # show whether each process is up
#
# Env overrides:
#   MM_API_PORT (default 8001 — 8000 is taken by job-scraper here)
#   MM_WEB_PORT (default 5173)
#
# Pids/logs live in ./.mm/ (gitignored). Data + sqlite live in ./data/.

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_PORT="${MM_API_PORT:-8001}"
WEB_PORT="${MM_WEB_PORT:-5173}"
API_URL="http://localhost:${API_PORT}"
WEB_URL="http://localhost:${WEB_PORT}"

RUNDIR="$ROOT/.mm"
PIDDIR="$RUNDIR/pids"
LOGDIR="$RUNDIR/logs"
VENV="$ROOT/.venv"

API_PID="$PIDDIR/api.pid"
WEB_PID="$PIDDIR/web.pid"
API_PORT_FILE="$PIDDIR/api.port"
WEB_PORT_FILE="$PIDDIR/web.port"
API_LOG="$LOGDIR/api.log"
WEB_LOG="$LOGDIR/web.log"

mkdir -p "$PIDDIR" "$LOGDIR" "$ROOT/data/downloads"

# First free port in [preferred, preferred+9] (5173 is often taken here).
pick_port() {
    local p end
    p="$1"
    end=$((p + 9))
    while [ "$p" -le "$end" ]; do
        if ! (: </dev/tcp/127.0.0.1/"$p") 2>/dev/null; then
            echo "$p"
            return 0
        fi
        p=$((p + 1))
    done
    echo "$1"
}

alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }

saved_pid() { [ -f "$1" ] && cat "$1" || true; }

ensure_venv() {
    if [ ! -x "$VENV/bin/python" ]; then
        echo "Creating venv at $VENV (one-time setup)..."
        python3 -m venv "$VENV"
        "$VENV/bin/pip" install -q -r "$ROOT/backend/requirements.txt"
    fi
}

wait_healthy() {
    local i
    for i in $(seq 1 30); do
        if curl -sf "$API_URL/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
    done
    return 1
}

start_one() { # name, pidfile, logfile, then command...
    local name="$1" pidfile="$2" logfile="$3"
    shift 3
    local old_pid
    old_pid="$(saved_pid "$pidfile")"
    if alive "$old_pid"; then
        echo "$name already running (pid $old_pid)."
        return 0
    fi
    rm -f "$pidfile"
    nohup "$@" >"$logfile" 2>&1 &
    echo $! >"$pidfile"
    echo "$name started (pid $!, log $logfile)."
}

stop_one() { # name, pidfile
    local name="$1" pidfile="$2" pid
    pid="$(saved_pid "$pidfile")"
    if ! alive "$pid"; then
        rm -f "$pidfile"
        echo "$name not running."
        return 0
    fi
    kill "$pid" 2>/dev/null
    local i
    for i in $(seq 1 10); do
        alive "$pid" || break
        sleep 1
    done
    if alive "$pid"; then
        kill -9 "$pid" 2>/dev/null
        echo "$name force-killed."
    else
        echo "$name stopped."
    fi
    rm -f "$pidfile"
}

cmd_start() {
    ensure_venv
    if [ ! -d "$ROOT/frontend/node_modules" ]; then
        echo "Installing frontend dependencies (one-time setup)..."
        (cd "$ROOT/frontend" && npm install --no-audit --no-fund)
    fi
    API_PORT="$(pick_port "$API_PORT")"
    WEB_PORT="$(pick_port "$WEB_PORT")"
    API_URL="http://localhost:${API_PORT}"
    WEB_URL="http://localhost:${WEB_PORT}"
    echo "$API_PORT" >"$API_PORT_FILE"
    echo "$WEB_PORT" >"$WEB_PORT_FILE"
    start_one "API" "$API_PID" "$API_LOG" \
        env DOWNLOAD_DIR="$ROOT/data/downloads" \
            DATABASE_URL="sqlite:///$ROOT/data/media-manager.db" \
            PYTHONPATH="$ROOT/backend" \
            "$VENV/bin/python" -m uvicorn app.main:app \
            --host 0.0.0.0 --port "$API_PORT"
    if ! wait_healthy; then
        echo "API did not become healthy — see $API_LOG"
        return 1
    fi
    echo "API healthy at $API_URL"
    start_one "WEB" "$WEB_PID" "$WEB_LOG" \
        bash -c "cd '$ROOT/frontend' && exec env VITE_API_URL='$API_URL' '$ROOT/frontend/node_modules/.bin/vite' --host 0.0.0.0 --port '$WEB_PORT' --strictPort"
    local i
    for i in $(seq 1 20); do
        if curl -sf "$WEB_URL/" >/dev/null 2>&1; then
            echo "Open the UI at $WEB_URL (API at $API_URL)"
            return 0
        fi
        sleep 1
    done
    echo "WEB did not come up on $WEB_URL — see $WEB_LOG"
    return 1
}

cmd_stop() {
    stop_one "WEB" "$WEB_PID"
    stop_one "API" "$API_PID"
}

cmd_status() {
    local api_pid web_pid
    if [ -f "$API_PORT_FILE" ]; then API_PORT="$(cat "$API_PORT_FILE")"; fi
    if [ -f "$WEB_PORT_FILE" ]; then WEB_PORT="$(cat "$WEB_PORT_FILE")"; fi
    API_URL="http://localhost:${API_PORT}"
    WEB_URL="http://localhost:${WEB_PORT}"
    api_pid="$(saved_pid "$API_PID")"
    web_pid="$(saved_pid "$WEB_PID")"
    if alive "$api_pid" && curl -sf "$API_URL/health" >/dev/null 2>&1; then
        echo "API: up (pid $api_pid) — $API_URL"
    else
        echo "API: down"
    fi
    if alive "$web_pid" && curl -sf "$WEB_URL/" >/dev/null 2>&1; then
        echo "WEB: up (pid $web_pid) — $WEB_URL"
    else
        echo "WEB: down"
    fi
}

case "${1:-status}" in
    start) cmd_start ;;
    stop) cmd_stop ;;
    restart) cmd_stop; cmd_start ;;
    status) cmd_status ;;
    *) echo "Usage: $0 {start|stop|restart|status}"; exit 1 ;;
esac
