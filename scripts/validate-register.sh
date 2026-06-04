#!/usr/bin/env bash
# Run register smoke-test against bican-sample-data (from repo root or anywhere).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/agents/the_super_app/app"
cd "$APP"
exec npx vite-node scripts/validate-register.mjs "$@"
