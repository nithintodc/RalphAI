#!/usr/bin/env python3
"""
Optional: Run DoorDash report download using browser-use (AI-driven control).
Uses an LLM to interpret the page and perform login, navigation, and download.

Set GEMINI_API_KEY in .env to use Google Gemini as the LLM provider.
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_date_range() -> tuple[str, str]:
    """
    Return (start_date, end_date) as MM/DD/YYYY.
    Reads REPORT_START_DATE / REPORT_END_DATE from env if set,
    otherwise computes the last 3 full months automatically.
    """
    start = os.getenv("REPORT_START_DATE", "").strip()
    end = os.getenv("REPORT_END_DATE", "").strip()
    if start and end:
        return start, end
    today = datetime.now().date()
    first_this_month = today.replace(day=1)
    last_prev_month = first_this_month - timedelta(days=1)
    y, m = first_this_month.year, first_this_month.month
    m -= 3
    if m <= 0:
        m += 12
        y -= 1
    first_three_months_ago = datetime(y, m, 1).date()
    return first_three_months_ago.strftime("%m/%d/%Y"), last_prev_month.strftime("%m/%d/%Y")

DOWNLOAD_DIR = Path(__file__).resolve().parent / "downloads"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _get_llm():
    """Use Google Gemini API (GEMINI_API_KEY) with gemini-3-flash-preview."""
    try:
        from browser_use import ChatGoogle
    except ImportError:
        raise SystemExit("Install browser-use: pip install browser-use")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not api_key.strip():
        raise SystemExit("Set GEMINI_API_KEY in .env.")
    return ChatGoogle(model="gemini-3-flash-preview", api_key=api_key)


def _get_browser():
    """Browser with download path set to project downloads/ (CDP or local Chrome)."""
    from shared.browser_use_factory import create_browser_use_browser

    return create_browser_use_browser(DOWNLOAD_DIR)


async def main():
    email = os.getenv("DOORDASH_EMAIL", "").strip()
    password = os.getenv("DOORDASH_PASSWORD", "").strip()
    if not email or not password:
        raise SystemExit("Set DOORDASH_EMAIL and DOORDASH_PASSWORD in .env")

    start_date, end_date = _get_date_range()

    task = (
        "Log in to the DoorDash Merchant Portal at https://merchant-portal.doordash.com/merchant/ "
        f"using this email: {email} and this password: {password}. "
        "Then open the Reports section, create a new report, select Financial report, "
        f"set the date range from {start_date} to {end_date}, create the report, "
        "wait for it to finish generating, then click Download. "
        f"Ensure the file is saved to this folder: {DOWNLOAD_DIR.resolve()}."
    )

    from browser_use import Agent

    llm = _get_llm()
    browser = _get_browser()
    agent = Agent(task=task, llm=llm, browser=browser)
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
