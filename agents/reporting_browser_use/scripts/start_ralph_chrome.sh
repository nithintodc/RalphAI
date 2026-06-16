#!/usr/bin/env bash
# Start Ralph's dedicated Chrome with CDP on port 9222.
#
# - Completely separate from your regular Chrome (different user-data-dir).
# - Syncs DoorDash cookies from your Work profile automatically — no 2FA.
# - Run once; leave the Chrome window open while running agents.
#
# Usage:
#   ./start_ralph_chrome.sh          # port 9222 (default)
#   ./start_ralph_chrome.sh 9223     # custom port

set -e
CDP_PORT="${1:-9222}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"

if [[ -f "$PROJECT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$PROJECT_DIR/.env"
  set +a
fi

cd "$PROJECT_DIR"
PYTHONPATH=. python3 -c "
import os
from shared.local_chrome_cdp import ensure_local_chrome_cdp, resolve_chrome_launch_config
cfg = resolve_chrome_launch_config()
src = os.getenv('CHROME_COOKIE_SOURCE_PROFILE', '(none)')
print(f'Ralph Chrome profile : {cfg.effective_profile_path}')
print(f'Cookie source        : {src}')
ensure_local_chrome_cdp('http://localhost:${CDP_PORT}', wait_seconds=45.0)
print(f'Ralph Chrome CDP ready at http://localhost:${CDP_PORT}')
print('Keep your regular Chrome open — no conflicts.')
"
