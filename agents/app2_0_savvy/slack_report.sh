#!/usr/bin/env bash
set -euo pipefail

# One-command runner for Slack report bot.
# - Creates/uses local .venv
# - Installs required dependencies
# - Loads .env
# - Validates required Slack credentials (Socket Mode)
# - Starts slack_report_bot.py

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"
PORT="${PORT:-3000}"
TODC_APP2_DIR="${TODC_APP2_DIR:-${SCRIPT_DIR}}"

echo "==> App directory: ${SCRIPT_DIR}"
echo "==> Python command: ${PYTHON_BIN}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "ERROR: Python not found: ${PYTHON_BIN}"
  exit 1
fi

if [ ! -d "${VENV_DIR}" ]; then
  echo "==> Creating virtual environment at ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

echo "==> Activating virtual environment"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

echo "==> Installing dependencies"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "${SCRIPT_DIR}/requirements.txt" slack_bolt flask python-dotenv certifi >/dev/null

if [ -f "${SCRIPT_DIR}/.env" ]; then
  echo "==> Loading ${SCRIPT_DIR}/.env"
  # Export all variables loaded from .env
  set -a
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/.env"
  set +a
else
  echo "WARN: ${SCRIPT_DIR}/.env not found (using current environment variables only)"
fi

if [ -z "${SLACK_BOT_TOKEN:-}" ]; then
  echo "ERROR: SLACK_BOT_TOKEN is missing."
  echo "Add it to ${SCRIPT_DIR}/.env (xoxb-...)"
  exit 1
fi

if [ -z "${SLACK_APP_TOKEN:-}" ]; then
  echo "ERROR: SLACK_APP_TOKEN is missing."
  echo "Add it to ${SCRIPT_DIR}/.env (xapp-...)"
  exit 1
fi

export PORT
export TODC_APP2_DIR

echo "==> Starting Slack report bot in Socket Mode"
echo "==> Using TODC_APP2_DIR=${TODC_APP2_DIR}"
exec python "${SCRIPT_DIR}/slack_report_bot.py"

