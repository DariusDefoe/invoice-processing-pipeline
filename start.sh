#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Start MySQL
docker compose up -d

# Activate venv (portable, no source command)
VENV_DIR="$(pwd)/venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install -r requirements.txt
fi

# Run the app using the venv's Python
"$VENV_DIR/bin/python" app/run_gui.py
