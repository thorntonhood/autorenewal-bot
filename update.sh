#!/bin/bash
set -e

INSTALL_DIR="$HOME/autorenewal-bot"

if [ ! -d "$INSTALL_DIR" ]; then
  echo "AutoRenewal Bot not found. Run the setup command from the README first."
  exit 1
fi

echo "Updating AutoRenewal Bot..."
curl -fsSL https://raw.githubusercontent.com/thorntonhood/autorenewal-bot/main/convoy_browser.py -o "$INSTALL_DIR/convoy_browser.py"
echo "Done. Running bot..."
cd "$INSTALL_DIR" && .venv/bin/python3 main.py
