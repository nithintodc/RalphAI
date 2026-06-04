"""Convert self-contained HTML reports to PDF (Playwright)."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def _ensure_playwright_chromium() -> bool:
    """Install Chromium for Playwright if the browser binary is missing."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("html_to_pdf: playwright package not installed (pip install playwright)")
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        return True
    except Exception:
        pass

    logger.info("html_to_pdf: installing Playwright Chromium (one-time)...")
    try:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.warning("html_to_pdf: playwright install chromium failed: %s", e.stderr or e)
        return False


def html_to_pdf(html_path: Path, pdf_path: Path) -> Optional[Path]:
    """Render local HTML file to PDF with styles/backgrounds. Returns pdf path or None."""
    html_path = Path(html_path).resolve()
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if not html_path.is_file():
        logger.warning("html_to_pdf: missing %s", html_path)
        return None

    if not _ensure_playwright_chromium():
        return None

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            try:
                page.goto(html_path.as_uri(), wait_until="networkidle", timeout=120_000)
            except Exception as nav_err:
                logger.warning("html_to_pdf: networkidle %s — using domcontentloaded", nav_err)
                page.goto(html_path.as_uri(), wait_until="domcontentloaded", timeout=120_000)
            try:
                page.wait_for_function(
                    "() => { const el = document.querySelector('#platforms'); "
                    "return el && el.innerHTML && el.innerHTML.length > 200; }",
                    timeout=60_000,
                )
            except Exception:
                page.wait_for_timeout(2500)
            page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={"top": "16px", "bottom": "16px", "left": "16px", "right": "16px"},
            )
            browser.close()
        if pdf_path.is_file() and pdf_path.stat().st_size > 0:
            logger.info("PDF written: %s (%d bytes)", pdf_path, pdf_path.stat().st_size)
            return pdf_path
        logger.warning("html_to_pdf: empty PDF at %s", pdf_path)
        return None
    except Exception as e:
        logger.warning("html_to_pdf failed: %s", e)
        if shutil.which("playwright"):
            logger.warning("html_to_pdf: try: python -m playwright install chromium")
        return None
