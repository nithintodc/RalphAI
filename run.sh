#!/bin/bash
# Run Python App with Virtual Environment
if [ ! -d "venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi
source venv/bin/activate
if [ -f "requirements.txt" ]; then
  pip install -r requirements.txt
fi
# Add your python run command here
