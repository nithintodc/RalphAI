"""Static file serving with dev-friendly cache headers (avoid stale SPA bundles)."""

from __future__ import annotations

from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class DevFriendlyStaticFiles(StaticFiles):
    """
    HTML entrypoints: never cache (browser must revalidate index.html).
    Hashed Vite assets: long cache (filename changes when content changes).
    Everything else: short/no cache for local dev.
    """

    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        normalized = (path or "").lstrip("/").lower()
        is_html = normalized.endswith(".html") or normalized == "" or normalized.endswith("/")
        is_hashed_asset = "/assets/" in f"/{normalized}" or (
            "." in normalized
            and any(
                part.count("-") >= 1 and part.rsplit(".", 1)[-1] in ("js", "css", "mjs")
                for part in normalized.split("/")
            )
        )

        if is_html:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        elif is_hashed_asset:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response
