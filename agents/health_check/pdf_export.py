"""Convert self-contained HTML reports to PDF (Playwright)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def html_to_pdf(html_path: Path, pdf_path: Path) -> Optional[Path]:
    """Render local HTML file to PDF. Returns pdf path or None on failure."""
    html_path = Path(html_path).resolve()
    pdf_path = Path(pdf_path)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if not html_path.is_file():
        logger.warning("html_to_pdf: missing %s", html_path)
        return None
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("html_to_pdf: playwright not installed")
        return None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(html_path.as_uri(), wait_until="networkidle")
            page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={"top": "16px", "bottom": "16px", "left": "16px", "right": "16px"},
            )
            browser.close()
        logger.info("PDF written: %s", pdf_path)
        return pdf_path
    except Exception as e:
        logger.warning("html_to_pdf failed: %s", e)
        return None
