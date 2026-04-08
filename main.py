#!/usr/bin/env python3
"""
AutoRenewal Bot — checks Convoy for expiring permissions and renews them automatically.

Run manually:  cd ~/autorenewal-bot && .venv/bin/python3 main.py
Run via cron:  0 8 * * * /Users/shane.thornton/autorenewal-bot/.venv/bin/python3 /Users/shane.thornton/autorenewal-bot/main.py
"""

import os
import getpass
import yaml
from convoy_browser import run
from slack_client import SlackClient

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
SESSION_FILE = os.path.join(BOT_DIR, "convoy_session.json")
CONFIG_FILE = os.path.join(BOT_DIR, "config.yaml")


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    first_run = not os.path.exists(SESSION_FILE)
    if first_run:
        print("[bot] First run detected — will extend all expiring permissions immediately.")
    print("[bot] AutoRenewal Bot starting...")
    results = run(session_file=SESSION_FILE, first_run=first_run)

    succeeded = sum(1 for r in results if r.get("success"))
    failed = len(results) - succeeded
    print(f"\n[bot] Done. {succeeded} renewed, {failed} failed.")

    try:
        config = load_config()
        slack_cfg = config.get("slack", {})
        token = slack_cfg.get("bot_token")
        log_channel = slack_cfg.get("log_channel")
        if token and log_channel:
            SlackClient(token).post_run_log(log_channel, results, getpass.getuser())
        else:
            print("[bot] Skipping Slack log — bot_token or log_channel not set in config.yaml.")
    except Exception as e:
        print(f"[bot] Could not post Slack log: {e}")
