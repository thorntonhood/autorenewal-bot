#!/usr/bin/env python3
"""
AutoRenewal Bot Aggregator — reads today's run logs and sends a single DM summary.

Run manually:  cd ~/autorenewal-bot && .venv/bin/python3 aggregator.py
Run via cron:  30 8 * * * /Users/shane.thornton/autorenewal-bot/.venv/bin/python3 /Users/shane.thornton/autorenewal-bot/aggregator.py
"""

import os
import yaml
from slack_client import SlackClient

BOT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BOT_DIR, "config.yaml")


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    config = load_config()
    slack_cfg = config.get("slack", {})
    token = slack_cfg.get("bot_token")
    log_channel = slack_cfg.get("log_channel")
    recipient = slack_cfg.get("reporting_dm")

    if not all([token, log_channel, recipient]):
        print("[aggregator] Missing bot_token, log_channel, or reporting_dm in config.yaml.")
        raise SystemExit(1)

    client = SlackClient(token)
    print(f"[aggregator] Reading today's logs from {log_channel}...")
    entries = client.read_todays_logs(log_channel)
    print(f"[aggregator] Found {len(entries)} run(s). Sending summary to {recipient}...")
    client.post_aggregated_summary(recipient, entries)
    print("[aggregator] Done.")
