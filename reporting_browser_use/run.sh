#!/usr/bin/env bash
#
# Standalone runner for reporting_browser_use (local browser only).
# Usage:
#   ./run.sh              # full pipeline (main.py)
#   ./run.sh reports      # report download only (run_browser_use.py)
#
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$ROOT/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="${REPO_ROOT}:${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

if [ -f ".env" ]; then
    echo "Loading .env..."
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
else
    echo "Warning: .env not found. Copy .env.example to .env and fill in credentials."
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

ensure_chrome_cdp() {
    if [ -z "${LOCAL_BROWSER_CDP_URL:-}" ]; then
        return 0
    fi
    echo "Ensuring Chrome CDP at ${LOCAL_BROWSER_CDP_URL}..."
    PYTHONPATH="${REPO_ROOT}:${ROOT}" python -c "
import os
from shared.local_chrome_cdp import ensure_local_chrome_cdp, resolve_user_data_dir
url = os.environ['LOCAL_BROWSER_CDP_URL']
profile = resolve_user_data_dir()
ensure_local_chrome_cdp(url, user_data_dir=profile)
print(f'Chrome CDP ready at {url} (profile: {profile})')
" || echo "Warning: Chrome CDP could not be started. The agent will retry on first browser run."
}

ensure_chrome_cdp

MODE=${1:-main}

case "$MODE" in
    reports)
        echo "Running report download only (run_browser_use.py)..."
        python run_browser_use.py
        ;;
    main|*)
        echo "Running full pipeline (main.py)..."
        python main.py
        ;;
esac
