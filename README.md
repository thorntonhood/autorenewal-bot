# AutoRenewal Bot

Automatically renews your Convoy permissions before they expire. Reads expiry notifications from your Slack DMs (Okta, Convoy), parses them with Claude, and re-requests access via the Convoy web UI.

Runs daily via cron. Setup takes about 1 minute.

---

## Prerequisites

- macOS with Python 3.11+
- Access to Convoy at `console.build.rhinternal.net`

---

## Setup

### Step 1 — Run the setup command

Open Terminal and paste this:

```bash
curl -fsSL https://raw.githubusercontent.com/thorntonhood/autorenewal-bot/main/setup.sh | bash
```

That's it. A browser window will open — log in to Convoy once, and everything runs automatically from there. The bot runs every morning at 8am and renews anything expiring soon.

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
