#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$ROOT_DIR/venv"
DASHBOARD_DIR="$ROOT_DIR/dashboard"
API_PORT="${API_PORT:-8000}"
DASHBOARD_PORT="${DASHBOARD_PORT:-5173}"

PIDS=()

log() {
  printf '[RalphAI] %s\n' "$1"
}

cleanup() {
  log "Stopping services..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
  wait >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

cd "$ROOT_DIR"

if [[ -f "$ROOT_DIR/.env" ]]; then
  log "Loading environment from .env"
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

if [[ ! -d "$VENV_DIR" ]]; then
  log "Creating Python virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

log "Installing Python dependencies..."
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "$ROOT_DIR/requirements.txt"

if [[ ! -d "$DASHBOARD_DIR/node_modules" ]]; then
  log "Installing dashboard dependencies..."
  (cd "$DASHBOARD_DIR" && npm install)
fi

log "Starting API on http://127.0.0.1:${API_PORT}"
(
  cd "$ROOT_DIR"
  PYTHONPATH=. python -m uvicorn api.main:app --reload --port "$API_PORT"
) &
PIDS+=("$!")

log "Starting dashboard on http://127.0.0.1:${DASHBOARD_PORT}"
(
  cd "$DASHBOARD_DIR"
  npm run dev -- --host 0.0.0.0 --port "$DASHBOARD_PORT"
) &
PIDS+=("$!")

if [[ -n "${SLACK_BOT_TOKEN:-}" && -n "${SLACK_SIGNING_SECRET:-}" ]]; then
  log "Starting Slack bot"
  (
    cd "$ROOT_DIR"
    PYTHONPATH=. python -m slack_bot.app
  ) &
  PIDS+=("$!")
else
  log "Slack bot not started. Set SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET in .env to enable it."
fi

cat <<EOF

RalphAI is starting up.
  API:        http://127.0.0.1:${API_PORT}
  Dashboard:  http://127.0.0.1:${DASHBOARD_PORT}

Press Ctrl+C to stop everything.
EOF

wait
