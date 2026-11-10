"""Visit the deployed app in a real browser so Streamlit Community Cloud
does not put it to sleep, and wake it if it already has.

A plain HTTP request is not enough: the app only counts as visited once a
browser has loaded it. Run by .github/workflows/keep-awake.yml.

    APP_URL=https://rto-calculate.streamlit.app/ python scripts/keep_awake.py
"""

from __future__ import annotations

import os
import re
import sys
import time

from playwright.sync_api import sync_playwright

APP_URL = os.environ.get("APP_URL", "https://rto-calculate.streamlit.app/")
CHANNEL = os.environ.get("BROWSER_CHANNEL") or None  # e.g. "chrome" to use an installed browser
WAIT_SECONDS = int(os.environ.get("WAIT_SECONDS", "240"))
WAKE_BUTTON = re.compile(r"get this app back up", re.I)


def app_is_up(page) -> bool:
    """The app runs in a frame of the page; it is up once Streamlit has drawn it."""
    for frame in page.frames:
        try:
            if frame.locator('[data-testid="stApp"]').count():
                return True
        except Exception:  # a frame that is navigating
            continue
    return False


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(channel=CHANNEL)
        page = browser.new_page()
        page.goto(APP_URL, wait_until="domcontentloaded", timeout=60_000)
        woke = False
        deadline = time.monotonic() + WAIT_SECONDS
        while time.monotonic() < deadline:
            if app_is_up(page):
                print(f"{APP_URL} is up" + (" (it was asleep and has been woken)" if woke else ""))
                browser.close()
                return 0
            button = page.get_by_role("button", name=WAKE_BUTTON)
            if not woke and button.count():
                button.first.click()
                woke = True
                print("The app was asleep. Asked Streamlit to wake it.")
            page.wait_for_timeout(3_000)
        print(f"{APP_URL} did not come up within {WAIT_SECONDS} seconds.", file=sys.stderr)
        browser.close()
        return 1


if __name__ == "__main__":
    sys.exit(main())
