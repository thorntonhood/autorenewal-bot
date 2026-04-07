# AutoRenewal Bot

Automatically renews your Convoy permissions before they expire. Reads expiry notifications from your Slack DMs (Okta, Convoy), parses them with Claude, and re-requests access via the Convoy web UI.

Runs daily via cron. Setup takes about 10 minutes.

---

## Prerequisites

- macOS with Python 3.11+
- Access to Convoy at `console.build.rhinternal.net`
- A personal Slack bot token (see Step 2)
- An Anthropic API key (see Step 3)

---

## Setup

### Step 1 — Clone the repo and run setup

```bash
git clone https://github.com/thorntonhood/autorenewal-bot.git ~/autorenewal-bot
cd ~/autorenewal-bot && bash setup.sh
```

The setup script will:
- Install all dependencies
- Walk you through getting your Slack bot token and Anthropic API key
- Write your `config.yaml`
- Add your API key to `~/.zshrc`
- Set up the daily cron job
- Run the bot for the first time

### Step 2 — Log in to Convoy

When the setup script runs the bot, a browser window will open. Log in to Convoy when prompted. After that, your session is saved and everything runs automatically.

That's it. The bot runs every morning at 8am and renews anything expiring within 14 days.

---

## Files

| File | Description |
|------|-------------|
| `config.yaml` | Your personal config (gitignored, never committed) |
| `convoy_session.json` | Saved Convoy browser session (gitignored, never committed) |
| `main.py` | Entry point |
| `slack_client.py` | Reads expiry notifications from your Slack DMs |
| `parser.py` | Uses Claude to extract structured permission data from messages |
| `convoy_browser.py` | Automates Convoy in a browser to renew permissions |

---

## Troubleshooting

**Bot says "No App DM channels found"**
The `app_names` in `config.yaml` must match the display names of the Slack apps exactly. Check what the bots are called in your Slack sidebar.

**Browser opens but nothing is renewed**
Your Convoy session may have expired. Delete `convoy_session.json` and run `main.py` again to re-authenticate.

**`ANTHROPIC_API_KEY` not set error**
Make sure you added the export line to `~/.zshrc` and ran `source ~/.zshrc`.
