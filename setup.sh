#!/bin/bash
set -e

echo ""
echo "AutoRenewal Bot Setup"
echo "====================="
echo ""

# Check Python 3
if ! command -v python3 &>/dev/null; then
  echo "Error: python3 is required but not installed."
  exit 1
fi

# Install dependencies
echo "Installing dependencies..."
python3 -m venv .venv
.venv/bin/python3 -m pip install -q -r requirements.txt
.venv/bin/python3 -m pip install -q playwright
.venv/bin/playwright install chromium
echo "Done."
echo ""

# Collect Slack token
echo "You need a Slack bot token (xoxb-...) to continue."
echo "Get one at: https://api.slack.com/apps"
echo "  1. Create New App -> From scratch"
echo "  2. OAuth & Permissions -> add scopes: channels:history, im:history, im:read, users:read"
echo "  3. Install to Workspace -> copy the Bot User OAuth Token"
echo ""
read -rp "Paste your Slack bot token: " SLACK_TOKEN
if [[ -z "$SLACK_TOKEN" ]]; then
  echo "Error: Slack token is required."
  exit 1
fi

# Collect Anthropic API key
echo ""
echo "You also need an Anthropic API key (sk-ant-...)."
echo "Get one at: https://console.anthropic.com -> API Keys -> Create Key"
echo ""
read -rp "Paste your Anthropic API key: " ANTHROPIC_KEY
if [[ -z "$ANTHROPIC_KEY" ]]; then
  echo "Error: Anthropic API key is required."
  exit 1
fi

# Write config.yaml
cat > config.yaml <<EOF
# AutoRenewal Bot Configuration
slack:
  bot_token: "$SLACK_TOKEN"
  app_names:
    - "Okta"
    - "Convoy"
  expiry_keywords:
    - "expiring"
    - "expires"
    - "access expiring"
    - "permission expiring"
    - "will expire"
  lookahead_days: 14
EOF
echo ""
echo "config.yaml written."

# Add ANTHROPIC_API_KEY to ~/.zshrc if not already there
if grep -q "ANTHROPIC_API_KEY" ~/.zshrc 2>/dev/null; then
  echo "ANTHROPIC_API_KEY already in ~/.zshrc, skipping."
else
  echo "export ANTHROPIC_API_KEY=\"$ANTHROPIC_KEY\"" >> ~/.zshrc
  echo "Added ANTHROPIC_API_KEY to ~/.zshrc."
fi
export ANTHROPIC_API_KEY="$ANTHROPIC_KEY"

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
