#!/usr/bin/env bash
# ── run.sh ── Run the TODC Analytics app locally
set -e

cd "$(dirname "$0")"

# Create venv if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo ""
echo "Starting TODC Analytics..."
echo "Open http://localhost:8501 in your browser"
echo ""

streamlit run app.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.maxUploadSize=1024
