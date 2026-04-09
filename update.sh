#!/bin/bash
set -e

INSTALL_DIR="$HOME/autorenewal-bot"

if [ ! -d "$INSTALL_DIR" ]; then
  echo "AutoRenewal Bot not found. Run the setup command from the README first."
  exit 1
fi

echo "Updating AutoRenewal Bot..."
cd "$INSTALL_DIR" && git pull
echo "Done. Running bot..."
.venv/bin/python3 main.py
