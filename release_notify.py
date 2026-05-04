import argparse
import asyncio
import os
import re
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
JIRA_HOST = os.environ["JIRA_HOST"]
JIRA_BASE = f"https://{JIRA_HOST}/browse"

BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
TELEGRAM_PROXY = os.environ.get("TELEGRAM_PROXY")

USERDATA_DIR = Path("./browser_session/userdata")

# CSS selectors for Jira Server/DC issue title (tried in order)
TITLE_SELECTORS = [
    "#summary-val",
    "h1#summary-val",
    "[data-test-id='issue.views.issue-base.foundation.summary.heading']",
    "h1.issue-header-summary",
    "h1[class*='summary']",
    ".issue-summary h1",
    "#issue-content h1",
]

LOGIN_INDICATORS = ["login", "signin", "sign-in", "log-in", "authenticate"]


# ── Helpers ──────────────────────────────────────────────────────────────────
def extract_jira_tickets(commits: list[str]) -> list[str]:
    pattern = re.compile(r'[A-Z]+-\d+')
    tickets, seen = [], set()
    for commit in commits:
        for match in pattern.findall(commit):
            if match not in seen:
                seen.add(match)
                tickets.append(match)
    return tickets


def is_login_page(url: str) -> bool:
    return any(ind in url.lower() for ind in LOGIN_INDICATORS)


# ── Scrape titles ────────────────────────────────────────────────────────────
async def scrape_titles(ctx, tickets: list[str]) -> dict[str, str]:
    """
    Uses a single page for all tickets to preserve the session across navigations.
    Opens a visible browser — user must log in if session is missing.
    """
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    ticket_titles: dict[str, str] = {}

    for ticket in tickets:
        url = f"{JIRA_BASE}/{ticket}"
        print(f"  Fetching: {url}")

        await page.goto(url, wait_until="domcontentloaded", timeout=15000)

        # If redirected to login — wait for user to log in (once)
        if not page.url.startswith(f"https://{JIRA_HOST}/browse/"):
            print("  Not logged in. Please log in to Jira (up to 5 minutes)...")
            try:
                await page.wait_for_url(
                    lambda u: u.startswith(f"https://{JIRA_HOST}/browse/"),
                    timeout=300_000,
                )
                await page.wait_for_load_state("networkidle", timeout=15000)
                print(f"  Logged in! Current URL: {page.url}")
            except Exception:
                print("  Login timeout — skipping remaining tickets.")
                ticket_titles[ticket] = "Login required"
                break

        print(f"    URL before scrape: {page.url}")
        if not page.url.startswith(f"https://{JIRA_HOST}/browse/"):
            ticket_titles[ticket] = "Login required"
            continue

        await page.wait_for_load_state("load", timeout=10000)

        title = None
        for selector in TITLE_SELECTORS:
            try:
                el = await page.wait_for_selector(selector, timeout=500)
                if el:
                    title = (await el.inner_text()).strip()
                    if title:
                        break
            except Exception:
                continue

        if not title:
            page_title = await page.title()
            title = re.sub(r'\s*[-–|].*$', '', page_title).strip()

        print(f"    -> {title or 'Unknown'}")
        ticket_titles[ticket] = title or "Unknown"

    return ticket_titles


# ── Telegram ─────────────────────────────────────────────────────────────────
def send_telegram(message: str) -> None:
    try:
        proxies = {"https": TELEGRAM_PROXY} if TELEGRAM_PROXY else None
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            proxies=proxies,
            timeout=15,
        )
        if resp.ok:
            print("Message sent to Telegram successfully.")
        else:
            print(f"Telegram error: {resp.status_code} {resp.text}")
    except requests.exceptions.ConnectionError:
        print("Cannot reach api.telegram.org (network/proxy issue).")
        print("Message that would be sent:")
        print(message)
    except requests.exceptions.Timeout:
        print("Telegram request timed out.")
        print("Message that would be sent:")
        print(message)


# ── Main ─────────────────────────────────────────────────────────────────────
async def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Send release notification to Telegram")
    parser.add_argument("environment", help="Уnvironment, e.g. QA")
    parser.add_argument("release", help="Release version, e.g. 26.1.0")
    parser.add_argument("rc", help="RC number, e.g. 7")
    parser.add_argument("commits", nargs="+", help='Commit strings, e.g. "abc123(BugFix DEV-123 Fix something)"')
    args = parser.parse_args()

    ENVIRONMENT = args.environment
    RELEASE = args.release
    RC = args.rc
    COMMITS = args.commits

    print(f"Release: {RELEASE}-rc{RC}")

    tickets = extract_jira_tickets(COMMITS)
    if not tickets:
        print("No Jira tickets found in commits.")
        return
    print(f"Tickets found: {tickets}")

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        USERDATA_DIR.mkdir(parents=True, exist_ok=True)
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir=str(USERDATA_DIR),
            headless=False,
            args=["--start-maximized"],
        )
        print("\nScraping titles...")
        ticket_titles = await scrape_titles(ctx, tickets)
        await ctx.close()

    lines = [f"\U0001f4cb На {ENVIRONMENT} {RELEASE}-rc{RC}:"]
    for ticket, title in ticket_titles.items():
        url = f"{JIRA_BASE}/{ticket}"
        safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        lines.append(f'<a href="{url}">{ticket} - {safe_title}</a>')
    message = "\n\n".join(lines)

    print("\n--- Telegram message ---")
    print(message)
    print("-----------------------\n")

    send_telegram(message)


if __name__ == "__main__":
    asyncio.run(main())
