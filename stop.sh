#!/usr/bin/env bash
#
# Stop everything started by ./run.sh (API, dashboard, Super App watch, agents, Chrome CDP).
# Usage: ./stop.sh [--keep-chrome]
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

KEEP_CHROME=0
for arg in "$@"; do
  case "$arg" in
    --keep-chrome) KEEP_CHROME=1 ;;
    -h|--help)
      echo "Usage: ./stop.sh [--keep-chrome]"
      echo "  Stops RalphAI API (8000), dashboard (5173), Super App build:watch, and marks agent runs interrupted."
      echo "  Chrome CDP (LOCAL_BROWSER_CDP_URL) is stopped unless --keep-chrome is passed."
      exit 0
      ;;
    *)
      echo "Unknown option: $arg (try --help)"
      exit 1
      ;;
  esac
done

if [ -f ".env" ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

activate_venv() {
  if [ -d ".venv" ]; then
    # shellcheck disable=SC1091
    source .venv/bin/activate
  fi
}

is_our_process() {
  local pid="$1"
  local cmd
  cmd="$(ps -ww -p "$pid" -o command= 2>/dev/null || true)"
  [[ -z "$cmd" ]] && return 1
  [[ "$cmd" == *"$ROOT"* ]] && return 0
  [[ "$cmd" == *"uvicorn api.main:app"* ]] && return 0
  [[ "$cmd" == *"api.main:app"* ]] && return 0
  return 1
}

kill_pid_gracefully() {
  local pid="$1"
  local label="$2"
  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  echo "  stopping $label (pid $pid)"
  kill -TERM "$pid" 2>/dev/null || true
}

wait_pid_gone() {
  local pid="$1"
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.3
  done
  kill -KILL "$pid" 2>/dev/null || true
}

kill_port() {
  local port="$1"
  local label="$2"
  if ! command -v lsof >/dev/null 2>&1; then
    return 0
  fi
  local pids
  pids="$(lsof -ti ":$port" 2>/dev/null || true)"
  [ -z "$pids" ] && return 0
  local killed=0
  for pid in $pids; do
    if is_our_process "$pid"; then
      kill_pid_gracefully "$pid" "$label :$port"
      wait_pid_gone "$pid"
      killed=1
    fi
  done
  if [ "$killed" = 0 ] && [ -n "$pids" ]; then
    echo "  port $port in use by non-RalphAI process(es); left running"
  fi
}

kill_by_pattern() {
  local pattern="$1"
  local label="$2"
  local pids
  pids="$(pgrep -f "$pattern" 2>/dev/null || true)"
  [ -z "$pids" ] && return 0
  for pid in $pids; do
    if is_our_process "$pid"; then
      kill_pid_gracefully "$pid" "$label"
      wait_pid_gone "$pid"
    fi
  done
}

mark_stale_agent_jobs() {
  if [ ! -d ".venv" ]; then
    return 0
  fi
  activate_venv
  PYTHONPATH=. python - <<'PY' || true
from shared.browser_agent_jobs import reconcile_stale_browser_jobs

reconcile_stale_browser_jobs()
print("  marked in-flight browser agent jobs as interrupted")
PY
}

stop_chrome_cdp() {
  if [ "$KEEP_CHROME" = 1 ]; then
    echo "  keeping Chrome CDP (--keep-chrome)"
    return 0
  fi
  local cdp_url="${LOCAL_BROWSER_CDP_URL:-}"
  if [ -z "$cdp_url" ]; then
    return 0
  fi
  if [ ! -d ".venv" ]; then
    return 0
  fi
  activate_venv
  PYTHONPATH=. python - <<PY || true
import os
from shared.local_chrome_cdp import stop_local_chrome_cdp

url = os.environ.get("LOCAL_BROWSER_CDP_URL", "").strip()
if url:
    stop_local_chrome_cdp(url)
    print(f"  stopped Chrome CDP at {url}")
PY
}

echo "================================================="
echo "Stopping RalphAI workspace"
echo "================================================="

echo "API (port 8000)..."
kill_port 8000 "uvicorn"
kill_by_pattern "${ROOT}/.venv/bin/python3.*uvicorn api.main:app" "uvicorn"

echo "Dashboard (port 5173)..."
kill_port 5173 "vite dev"

echo "Super App build:watch..."
kill_by_pattern "${ROOT}/agents/the_super_app/app.*vite build --watch" "super-app watch"
kill_by_pattern "${ROOT}/agents/the_super_app/app.*build:watch" "super-app watch"

echo "Standalone agent CLI (./run.sh <agent>)..."
kill_by_pattern "${ROOT}.*PYTHONPATH=.*python -c import agents\\." "agent CLI"

echo "Browser agent jobs..."
mark_stale_agent_jobs

echo "Chrome CDP..."
stop_chrome_cdp

# Second pass — uvicorn --reload leaves a child worker behind sometimes
sleep 0.5
kill_port 8000 "uvicorn (cleanup)"
kill_port 5173 "vite (cleanup)"

echo ""
echo "Done. RalphAI services should be stopped."
if command -v lsof >/dev/null 2>&1; then
  remaining=""
  for port in 8000 5173; do
    if lsof -ti ":$port" >/dev/null 2>&1; then
      remaining="${remaining} ${port}"
    fi
  done
  if [ -n "$remaining" ]; then
    echo "Note: port(s) still in use:${remaining} (may be another app)."
  fi
fi
