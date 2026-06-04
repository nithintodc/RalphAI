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

AGENT=${1:-}

if [ -n "$AGENT" ]; then
    if [ ! -d "agents/$AGENT" ]; then
        echo "Error: Agent '$AGENT' does not exist."
        exit 1
    fi
    echo "================================================="
    echo "🚀 Launching Agent: $AGENT"
    echo "================================================="
    python -c "import agents.${AGENT} as agent; print(agent.run_app(wait=True))"
    exit 0
fi

echo "================================================="
echo "🚀 Launching RalphAI Orchestrator Workspace"
echo "================================================="

# Check for venv
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment and installing packages..."
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt || true
else
    source .venv/bin/activate
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

# Build the Super App static bundle (served internally by the API at /internal-apps/the-super-app)
SUPERAPP_DIR="agents/the_super_app/app"
if [ -d "$SUPERAPP_DIR" ]; then
    if [ ! -d "$SUPERAPP_DIR/node_modules" ]; then
        echo "Installing Super App dependencies..."
        (cd "$SUPERAPP_DIR" && npm ci)
    fi
    NEED_SUPERAPP_BUILD=0
    if [ ! -d "$SUPERAPP_DIR/dist" ] || [ "${REBUILD_SUPERAPP:-0}" = "1" ]; then
        NEED_SUPERAPP_BUILD=1
    elif find "$SUPERAPP_DIR/src" -type f \( -name '*.jsx' -o -name '*.js' -o -name '*.css' -o -name '*.tsx' -o -name '*.ts' \) -newer "$SUPERAPP_DIR/dist/index.html" 2>/dev/null | grep -q .; then
        NEED_SUPERAPP_BUILD=1
    fi
    if [ "$NEED_SUPERAPP_BUILD" = "1" ]; then
        echo "Building Super App..."
        (cd "$SUPERAPP_DIR" && npm run build)
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
echo "Press Ctrl+C to stop."

# Wait for background processes to keep the script running
trap "echo 'Shutting down...'; kill $API_PID $DASH_PID; exit" SIGINT SIGTERM
wait $API_PID $DASH_PID
