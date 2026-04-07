#!/bin/bash
set -e

INSTALL_DIR="$HOME/autorenewal-bot"

echo ""
echo "AutoRenewal Bot Setup"
echo "====================="
echo ""

# Check Python 3
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required but not installed."
  exit 1
fi

# Clone repo if not already present
if [ ! -d "$INSTALL_DIR" ]; then
  echo "Downloading AutoRenewal Bot..."
  git clone -q https://github.com/thorntonhood/autorenewal-bot.git "$INSTALL_DIR"
fi
cd "$INSTALL_DIR"

# Install dependencies
echo "Installing dependencies..."
python3 -m venv .venv
.venv/bin/python3 -m pip install -q -r requirements.txt
.venv/bin/python3 -m pip install -q playwright
.venv/bin/playwright install chromium
echo "Done."
echo ""

# Set up cron job
CRON_CMD="0 8 * * * /Users/$USER/autorenewal-bot/.venv/bin/python3 /Users/$USER/autorenewal-bot/main.py"
if crontab -l 2>/dev/null | grep -q "autorenewal-bot"; then
  echo "Cron job already set up, skipping."
else
  (crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -
  echo "Cron job added (runs daily at 8am)."
fi

# First run
echo ""
echo "Setup complete! Running the bot for the first time..."
echo "A browser window will open — log in to Convoy when prompted."
echo ""
.venv/bin/python3 main.py
