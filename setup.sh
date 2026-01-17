#!/usr/bin/env bash
set -e

echo "🔧 VAT Refunder setup script"
echo "---------------------------"

# --- 1️⃣ Check and install Docker ---
if ! command -v docker &> /dev/null; then
  echo "🐳 Docker not found — installing..."
  sudo dnf install -y docker docker-compose-plugin
  sudo systemctl enable --now docker
else
  echo "✅ Docker is already installed."
fi

# --- 2️⃣ Check Docker daemon ---
if ! sudo docker info &> /dev/null; then
  echo "🚫 Docker daemon not running. Starting it now..."
  sudo systemctl start docker
fi

# --- 3️⃣ Build Python environment ---
if ! command -v python3 &> /dev/null; then
  echo "🐍 Python3 not found — installing..."
  sudo dnf install -y python3 python3-venv python3-pip python3-tkinter tk
fi

if [ ! -d "venv" ]; then
  echo "📦 Creating virtual environment..."
  python3 -m venv venv
  venv/bin/pip install -r requirements.txt
else
  echo "✅ Virtual environment already exists."
fi

# --- 4️⃣ Create exports folder ---
mkdir -p ~/Desktop/exports

# --- 5️⃣ Test Docker Compose setup ---
echo "🐬 Starting MySQL container (first run may take a minute)..."
docker compose up -d

# --- 6️⃣ Install desktop shortcut ---
DESKTOP_FILE="invoice_processing_pipeline.desktop"
TARGET_DIR="$HOME/.local/share/applications"

if [ -f "$DESKTOP_FILE" ]; then
  mkdir -p "$TARGET_DIR"
  cp "$DESKTOP_FILE" "$TARGET_DIR/"
  chmod +x "$TARGET_DIR/$DESKTOP_FILE"
  echo "🖥️  Desktop launcher installed to $TARGET_DIR/$DESKTOP_FILE"
else
  echo "⚠️  $DESKTOP_FILE not found — skipping launcher copy."
fi

echo "🎉 Setup complete!"
echo "Next time, just run ./start.sh or open VAT Refunder from your app menu."
