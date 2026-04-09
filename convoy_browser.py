"""
Browser automation for Convoy permission renewal.
Logs into Convoy, checks My Requests for expiring/expired permissions,
and automatically extends or re-requests each one.
"""

import os
import re
from datetime import datetime, timedelta, timezone
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

CONVOY_MY_REQUESTS = "https://console.build.rhinternal.net/convoy/my-requests"
CONVOY_BASE = "https://console.build.rhinternal.net/convoy"
REASON_TEXT = "Provide Financial Services"
DURATION_PREFERENCE = ["3 months", "1 month", "1 week", "1 day", "6 hours", "2 hours"]
LOOKAHEAD_DAYS = 21


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

        # If session expired, Convoy shows an inline login button rather than redirecting
        needs_login = (
            "login" in page.url.lower()
            or "okta" in page.url.lower()
            or "log in" in page.inner_text("body").lower()
        )
        if needs_login:
            print("[convoy] Session expired — please log in to Convoy in the browser window.")
            print("[convoy] Waiting up to 2 minutes (includes Kolide verification)...")
            try:
                page.wait_for_selector("tr.clickable-row", timeout=120000)
            except PlaywrightTimeout:
                print("[convoy] Timed out waiting for login. Please run again and log in promptly.")
                return results
            print("[convoy] Logged in! Saving session...")
            context.storage_state(path=session_file)

        # Find all permission rows on the page
        if first_run:
            print("[convoy] Scanning for ALL expiring permissions (first run)...")
            cutoff = None
        else:
            print("[convoy] Scanning for expiring permissions...")
            cutoff = datetime.now(timezone.utc) + timedelta(days=LOOKAHEAD_DAYS)

        # Wait for the table to render, then get all permission rows
        try:
            page.wait_for_selector("tr.clickable-row", timeout=30000)
        except PlaywrightTimeout:
            print(f"[convoy] Timed out waiting for rows. Current URL: {page.url}")
            return results
        rows = page.locator("tr.clickable-row").all()
        print(f"[convoy] Found {len(rows)} row(s) to check.")

        # First pass: collect permission names that already have an active or pending row
        active_or_pending = set()
        for row in rows:
            try:
                row_text = row.inner_text()
                if "active" in row_text.lower() or "pending" in row_text.lower():
                    cells = row.locator("td").all()
                    if len(cells) >= 3:
                        active_or_pending.add(cells[2].inner_text().strip())
            except Exception:
                continue

        for row in rows:
            try:
                row_text = row.inner_text()
                if not row_text.strip():
                    continue

                cells = row.locator("td").all()
                perm_name = cells[2].inner_text().strip() if len(cells) >= 3 else ""
                is_active = "active" in row_text.lower()
                is_expired = "expir" in row_text.lower()

                # Skip rows that already have a pending request
                if "pending" in row_text.lower():
                    continue

                # Case 1: Active permission expiring soon — extend it
                # Case 2: Expired permission with no active/pending version — re-request it
                if is_active:
                    exp_date = _parse_date_from_text(row_text)
                    if exp_date is None:
                        continue
                    now = datetime.now(timezone.utc)
                    if cutoff is not None and exp_date > cutoff:
                        continue  # Not expiring soon
                elif is_expired:
                    if perm_name in active_or_pending:
                        continue  # Already has an active or pending version
                    exp_date = _parse_date_from_text(row_text)
                else:
                    continue  # Unknown status, skip

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
                    url_before = page.url
                    row.click()
                    page.wait_for_load_state("networkidle")
                    if page.url == url_before:
                        print("[convoy]   Row click did not navigate. Skipping.")
                        results.append({"success": False, "row": row_text[:80], "error": "row not navigable"})
                        continue
                    # Wait for the action button to render
                    btn_selector = "button:has-text('Extend Access'), button:has-text('Re-request'), a:has-text('Extend Access'), a:has-text('Re-request')"
                    try:
                        page.wait_for_selector(btn_selector, timeout=8000)
                    except PlaywrightTimeout:
                        pass
                    for label in ["Extend Access", "Re-request", "Rerequest", "Renew"]:
                        candidate = page.locator(f"button, a", has_text=label)
                        if candidate.count() > 0:
                            btn = candidate.first
                            print(f"[convoy]   Clicking '{label}' on detail page...")
                            break

                if btn is None:
                    print("[convoy]   Could not find Extend/Re-request button. Skipping.")
                    results.append({"success": False, "row": row_text[:80], "error": "button not found"})
                    page.goto(CONVOY_MY_REQUESTS, timeout=20000)
                    page.wait_for_selector("tr.clickable-row", timeout=30000)
                    continue

                btn.click()
                # Wait for the form to appear (select dropdown with duration options)
                try:
                    page.wait_for_selector(
                        f"select:has(option:has-text('{DURATION_PREFERENCE[0]}'))",
                        timeout=8000
                    )
                except PlaywrightTimeout:
                    pass

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


def _select_combobox_option(page, combobox, option_text: str) -> bool:
    """Open a downshift combobox and click the matching option. Returns True on success."""
    try:
        combobox.click()
        page.wait_for_selector('[role="option"]', timeout=5000)
        option = page.locator('[role="option"]').filter(has_text=option_text).first
        if option.count() > 0:
            option.click()
            return True
        # Close the dropdown if option not found
        combobox.click()
    except Exception:
        pass
    return False


def _fill_renewal_form(page):
    """Fill in the renewal form using downshift combobox dropdowns."""
    comboboxes = page.locator('[role="combobox"]').all()
    print(f"[convoy]   Found {len(comboboxes)} combobox(es) on form.")

    # First combobox — expiration duration
    if len(comboboxes) >= 1:
        for duration in DURATION_PREFERENCE:
            if _select_combobox_option(page, comboboxes[0], duration):
                print(f"[convoy]   Set expiration: {duration}")
                break
        else:
            print("[convoy]   Could not set expiration.")
    else:
        print("[convoy]   No comboboxes found — form may not have loaded.")
        return

    # Reason field — combobox, checkbox, or text input
    reason_set = False

    # Try second combobox
    if len(comboboxes) >= 2:
        if _select_combobox_option(page, comboboxes[1], REASON_TEXT):
            print(f"[convoy]   Set reason (combobox): {REASON_TEXT}")
            reason_set = True

    # Try checkbox with value="provide_financial_services"
    if not reason_set:
        try:
            checkbox = page.locator("input[type='checkbox'][value='provide_financial_services']").first
            if checkbox.count() > 0:
                if not checkbox.is_checked():
                    checkbox.click()
                print(f"[convoy]   Set reason (checkbox): provide_financial_services")
                reason_set = True
        except Exception:
            pass

    # Try textarea[name="reason"]
    if not reason_set:
        try:
            text_input = page.locator("textarea[name='reason']").first
            if text_input.count() > 0:
                text_input.fill(REASON_TEXT)
                print(f"[convoy]   Set reason (textarea): {REASON_TEXT}")
                reason_set = True
        except Exception:
            pass

    if not reason_set:
        print("[convoy]   Could not set reason.")

    # Submit
    submit = page.locator("button[type='submit'], button").filter(
        has_text=re.compile("submit|confirm|request|extend", re.IGNORECASE)
    ).first
    if submit.count() == 0:
        all_btns = [b.inner_text().strip() for b in page.locator("button").all() if b.inner_text().strip()]
        print(f"[convoy]   Could not find submit button. Buttons visible: {all_btns}")
        return
    print(f"[convoy]   Clicking submit: '{submit.inner_text().strip()}'")
    try:
        submit.click()
        page.wait_for_load_state("networkidle")
    except Exception as e:
        print(f"[convoy]   Submit error: {e}")


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
