#!/usr/bin/env bash
# Start Chrome with remote debugging using your real Chrome profile (e.g. Work).
#
# Env (from .env or shell):
#   CHROME_USER_DATA_DIR   — profile folder OR Chrome user-data root
#   CHROME_PROFILE_DIRECTORY — e.g. "Profile 2" when dir is the Chrome root
#   CHROME_PROFILE_NAME    — e.g. "Work" (resolved via Local State)

set -e
PORT="${1:-9222}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

if [[ -f "$PROJECT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

cd "$PROJECT_DIR"
PYTHONPATH=. python -c "
from shared.local_chrome_cdp import ensure_local_chrome_cdp, resolve_chrome_launch_config
cfg = resolve_chrome_launch_config()
print(f'Profile: {cfg.launch_label}')
print(f'Path:    {cfg.effective_profile_path}')
ensure_local_chrome_cdp('http://localhost:${PORT}', wait_seconds=45.0)
print(f'Chrome CDP ready at http://localhost:${PORT}')
"
