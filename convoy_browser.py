"""
Browser automation for Convoy permission renewal.
Logs into Convoy, checks My Requests for expiring/expired permissions,
and automatically extends or re-requests each one.
"""

import os
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

CONVOY_MY_REQUESTS = "https://console.build.rhinternal.net/convoy/my-requests"
CONVOY_BASE = "https://console.build.rhinternal.net/convoy"
REASON_TEXT = "Needed for Full-Time Role"
DURATION_PREFERENCE = ["3 months", "90 days", "6 months", "1 year", "Indefinite"]
LOOKAHEAD_DAYS = 14


def run(session_file: str = "convoy_session.json", first_run: bool = False) -> list[dict]:
    """
    Main entry point. Opens Convoy, finds expiring permissions, renews them.
    Returns a list of results.
    """
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)

        # Try to reuse saved login session
        try:
            context = browser.new_context(storage_state=session_file)
            print("[convoy] Loaded saved session.")
        except Exception:
            context = browser.new_context()
            print("[convoy] No saved session — you may need to log in.")

        page = context.new_page()

        # Navigate to My Requests
        print("[convoy] Opening Convoy My Requests...")
        page.goto(CONVOY_MY_REQUESTS, timeout=20000)
        page.wait_for_load_state("networkidle")

        # If redirected to login, wait for user to log in
        if "login" in page.url.lower() or "okta" in page.url.lower():
            print("[convoy] Please log in to Convoy in the browser window that opened.")
            print("[convoy] Waiting up to 2 minutes...")
            page.wait_for_url("**/convoy**", timeout=120000)
            page.goto(CONVOY_MY_REQUESTS, timeout=20000)
            page.wait_for_load_state("networkidle")
            print("[convoy] Logged in! Saving session...")
            context.storage_state(path=session_file)

        # Find all permission rows on the page
        if first_run:
            print("[convoy] Scanning for ALL expiring permissions (first run)...")
            cutoff = None
        else:
            print("[convoy] Scanning for expiring permissions...")
            cutoff = datetime.now(timezone.utc) + timedelta(days=LOOKAHEAD_DAYS)

        # Get all rows in the requests table
        rows = page.locator("tr, [role='row'], .request-row, .permission-row").all()
        print(f"[convoy] Found {len(rows)} row(s) to check.")

        for row in rows:
            try:
                row_text = row.inner_text()
                if not row_text.strip():
                    continue

                # Look for an expiration date in the row
                exp_date = _parse_date_from_text(row_text)
                if exp_date is None:
                    continue

                # Check if expiring within lookahead window or already expired
                now = datetime.now(timezone.utc)
                if cutoff is not None and exp_date > cutoff:
                    continue  # Not expiring soon, skip

                print(f"[convoy] Found expiring permission: {row_text[:80].strip()}")
                print(f"[convoy]   Expiry: {exp_date.strftime('%Y-%m-%d')}")

                # Click "Extend Access" if active, or "Re-request" if expired
                btn = None
                for label in ["Extend Access", "Re-request", "Rerequest", "Renew"]:
                    candidate = row.locator(f"button, a", has_text=label)
                    if candidate.count() > 0:
                        btn = candidate.first
                        print(f"[convoy]   Clicking '{label}'...")
                        break

                if btn is None:
                    # Try clicking the row itself to open the detail page
                    row.click()
                    page.wait_for_load_state("networkidle")
                    for label in ["Extend Access", "Re-request", "Rerequest", "Renew"]:
                        candidate = page.locator(f"button, a", has_text=label)
                        if candidate.count() > 0:
                            btn = candidate.first
                            print(f"[convoy]   Clicking '{label}' on detail page...")
                            break

                if btn is None:
                    print("[convoy]   Could not find Extend/Re-request button. Skipping.")
                    results.append({"success": False, "row": row_text[:80], "error": "button not found"})
                    continue

                btn.click()
                page.wait_for_load_state("networkidle")

                # Fill in the form
                _fill_renewal_form(page)

                results.append({"success": True, "row": row_text[:80].strip()})
                print("[convoy]   Done.")

                # Go back to My Requests for the next one
                page.goto(CONVOY_MY_REQUESTS, timeout=20000)
                page.wait_for_load_state("networkidle")

            except PlaywrightTimeout:
                print("[convoy]   Timed out. Skipping.")
                results.append({"success": False, "row": "", "error": "timeout"})
            except Exception as e:
                print(f"[convoy]   Error: {e}")
                results.append({"success": False, "row": "", "error": str(e)})

        # Save session for next run
        context.storage_state(path=session_file)
        print("[convoy] Session saved.")
        browser.close()

    return results


def _fill_renewal_form(page):
    """Fill in the renewal form: set duration to 3 months and add reason."""
    # Set expiration dropdown
    for duration in DURATION_PREFERENCE:
        try:
            option = page.locator("option").filter(has_text=duration)
            if option.count() > 0:
                select = page.locator("select").first
                select.select_option(label=option.first.inner_text())
                print(f"[convoy]   Set expiration: {duration}")
                break
        except Exception:
            continue

    # Fill in reason
    try:
        reason = page.locator("textarea, input[placeholder*='eason'], input[name*='eason']").first
        reason.fill(REASON_TEXT)
        print(f"[convoy]   Set reason: {REASON_TEXT}")
    except Exception:
        print("[convoy]   Could not find reason field.")

    # Submit
    try:
        submit = page.locator("button[type='submit'], button").filter(
            has_text_regex="submit|confirm|request|extend"
        ).first
        submit.click()
        page.wait_for_load_state("networkidle")
    except Exception as e:
        print(f"[convoy]   Could not submit form: {e}")


def _parse_date_from_text(text: str):
    """Try to extract an expiration date from a row of text."""
    import re
    from dateutil import parser as dateparser

    # Look for date patterns like "Jan 15, 2025", "2025-01-15", "01/15/2025"
    patterns = [
        r'\b\d{4}-\d{2}-\d{2}\b',
        r'\b\d{1,2}/\d{1,2}/\d{4}\b',
        r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                dt = dateparser.parse(match.group(), ignoretz=True)
                return dt.replace(tzinfo=timezone.utc)
            except Exception:
                continue
    return None
