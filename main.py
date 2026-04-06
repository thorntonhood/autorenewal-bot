#!/usr/bin/env python3
"""
AutoRenewal Bot — checks Convoy for expiring permissions and renews them automatically.

Run manually:  cd ~/autorenewal-bot && .venv/bin/python3 main.py
Run via cron:  0 8 * * * /Users/shane.thornton/autorenewal-bot/.venv/bin/python3 /Users/shane.thornton/autorenewal-bot/main.py
"""

import os
from convoy_browser import run

SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "convoy_session.json")

if __name__ == "__main__":
    print("[bot] AutoRenewal Bot starting...")
    results = run(session_file=SESSION_FILE)

    succeeded = sum(1 for r in results if r.get("success"))
    failed = len(results) - succeeded

    print(f"\n[bot] Done. {succeeded} renewed, {failed} failed.")
