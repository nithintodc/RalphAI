#!/usr/bin/env bash
#
# Global run.sh for RalphAI
# Usage: ./run.sh [agent_name]
# Defaults to launching the RalphAI Orchestrator (API + Dashboard) if no agent is provided.
#
set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [ -f ".env" ]; then
    echo "Loading global .env file..."
    set -a
    source .env
    set +a
fi

activate_venv() {
    if [ -d ".venv" ]; then
        # shellcheck disable=SC1091
        source .venv/bin/activate
    fi
}

AGENT=${1:-}

if [ -n "$AGENT" ]; then
    if [ ! -d "agents/$AGENT" ]; then
        echo "Error: Agent '$AGENT' does not exist."
        exit 1
    fi
    echo "================================================="
    echo "🚀 Launching Agent: $AGENT"
    echo "================================================="
    activate_venv
    PYTHONPATH=. python -c "import agents.${AGENT} as agent; print(agent.run_app(wait=True))"
    exit 0
fi

echo "================================================="
echo "🚀 Launching RalphAI Orchestrator Workspace"
echo "================================================="

# Check for venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment and installing packages..."
    python3 -m venv .venv
    activate_venv
    pip install -r requirements.txt || true
else
    activate_venv
fi

# Health Check PDF export (Playwright Chromium)
if python -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    if ! python -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    b.close()
" 2>/dev/null; then
        echo "Installing Playwright Chromium for Health Check PDF reports..."
        python -m playwright install chromium
    fi
fi

# The Super App is a pre-built static bundle at /internal-apps/the-super-app (not Vite HMR).
# Rebuild when sources change; optional background watch keeps dist/ fresh during ./run.sh.
SUPERAPP_DIR="agents/the_super_app/app"
SUPERAPP_WATCH_PID=""
SUPERAPP_WATCH="${SUPERAPP_WATCH:-1}"

superapp_needs_build() {
    local dir="$1"
    if [ ! -d "$dir/dist" ] || [ ! -f "$dir/dist/index.html" ]; then
        return 0
    fi
    if [ "${REBUILD_SUPERAPP:-0}" = "1" ]; then
        return 0
    fi
    local marker="$dir/dist/index.html"
    find "$dir/src" "$dir/index.html" "$dir/vite.config.js" -type f \
        \( -name '*.jsx' -o -name '*.js' -o -name '*.css' -o -name '*.tsx' -o -name '*.ts' -o -name '*.html' \) \
        -newer "$marker" 2>/dev/null | grep -q .
}

if [ -d "$SUPERAPP_DIR" ]; then
    if [ ! -d "$SUPERAPP_DIR/node_modules" ]; then
        echo "Installing Super App dependencies..."
        (cd "$SUPERAPP_DIR" && npm ci)
    fi
    if superapp_needs_build "$SUPERAPP_DIR"; then
        echo "Building Super App (static bundle for /internal-apps/the-super-app)..."
        (cd "$SUPERAPP_DIR" && npm run build)
    else
        echo "Super App bundle up to date."
    fi
    if [ "$SUPERAPP_WATCH" = "1" ]; then
        echo "Super App: watching src/ for changes (auto-rebuild; hard-refresh browser after edits)."
        (cd "$SUPERAPP_DIR" && npm run build:watch) &
        SUPERAPP_WATCH_PID=$!
    fi
fi

# Start the FastAPI backend
echo "Starting API on port 8000..."
PYTHONPATH=. uvicorn api.main:app --reload --port 8000 &
API_PID=$!

# Start the Vite dashboard
echo "Starting Dashboard..."
cd dashboard
if [ ! -d "node_modules" ]; then
    echo "Installing dashboard dependencies..."
    npm install
fi
npm run dev &
DASH_PID=$!

cd "$ROOT"

echo ""
echo "✅ RalphAI is running!"
echo "🌐 Workspace UI available at: http://localhost:5173"
echo "🔌 API available at: http://localhost:8000"
if [ -n "$SUPERAPP_WATCH_PID" ]; then
    echo "📦 Super App: auto-rebuild on save (Cmd+Shift+R in browser to pick up UI changes)"
fi
echo "Press Ctrl+C to stop, or run ./stop.sh from another terminal."
echo "   ./stop.sh stops API, dashboard, agents, and Chrome CDP even if this terminal was closed."

# Wait for background processes to keep the script running
trap 'echo "Shutting down..."; kill $API_PID $DASH_PID ${SUPERAPP_WATCH_PID:-} 2>/dev/null; exit' SIGINT SIGTERM
wait $API_PID $DASH_PID
