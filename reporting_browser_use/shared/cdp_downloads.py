"""Configure CDP-attached Chrome to save downloads into the agent folder."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


async def configure_browser_download_dir(browser: Any, download_dir: Path) -> None:
    """
    Set Browser.setDownloadBehavior on an attached browser-use session.

    Required when using LOCAL_BROWSER_CDP_URL — without this, DoorDash report zips
    often land in ~/Downloads instead of the per-run download directory.
    """
    target = Path(download_dir).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)

    try:
        await browser.start()
    except Exception:
        pass

    cdp_client = getattr(browser, "cdp_client", None)
    if cdp_client is None:
        logger.warning("No CDP client on browser — cannot set download path")
        return

    try:
        await cdp_client.send.Browser.setDownloadBehavior(
            params={
                "behavior": "allow",
                "downloadPath": str(target),
                "eventsEnabled": True,
            }
        )
        logger.info("CDP download path set to %s", target)
    except Exception as exc:
        logger.warning("Could not set CDP download path to %s: %s", target, exc)
