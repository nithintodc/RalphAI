#!/usr/bin/env bash
# Local prep before GCP deploy — installs deps and builds static bundles.
# Usage: ./scripts/prepare-deploy.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "▸ Python dependencies"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate
pip install -r requirements.txt -q

echo "▸ Dashboard (RalphAI workspace UI)"
( cd dashboard
  [[ -d node_modules ]] || npm ci
  npm run build
)

echo "▸ The Super App (embedded in API at /internal-apps/the-super-app)"
( cd agents/the_super_app/app
  [[ -d node_modules ]] || npm ci
  npm run build
)

echo "▸ Tests (quick)"
PYTHONPATH=. python3 -m pytest tests/ -q --tb=no -q 2>/dev/null || PYTHONPATH=. python3 -m pytest tests/ -q --tb=line

echo ""
echo "✓ Ready to build Docker image or run ./deploy.sh for standalone Super App."
echo "  Full orchestrator: see README.md → Deployment → Full orchestrator on GCP"
