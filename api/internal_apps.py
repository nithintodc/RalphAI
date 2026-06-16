"""Serve bundled agent UIs from RalphAI (same origin) instead of separate localhost ports."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from api.static_cache import DevFriendlyStaticFiles

ROOT = Path(__file__).resolve().parent.parent

INTERNAL_APPS: dict[str, Path] = {
    "markup-app": ROOT / "agents" / "markup_app",
    "the-super-app": ROOT / "agents" / "the_super_app" / "app" / "dist",
}

# Repo-root scan for Super App marketing breakdown fallback (formerly standalone agent).
_DEFAULT_DATASET_ROOT = ROOT


def _walk_csv_matches(base: Path, prefix: str) -> list[Path]:
    if not base.is_dir():
        return []
    matches: list[Path] = []
    for path in base.rglob("*.csv"):
        if "node_modules" in path.parts:
            continue
        if path.name.startswith(prefix):
            matches.append(path)
    return matches


def _choose_best_csv_match(matches: list[Path]) -> Path | None:
    if not matches:
        return None
    return sorted(matches, key=lambda p: (len(p.parts), str(p)))[0]


def _read_default_dataset(base: Path, prefix: str, label: str) -> dict:
    matches = _walk_csv_matches(base, prefix)
    if not matches:
        return {
            "error": f"No {prefix}*.csv file was found under the project (upload DoorDash exports to enable breakdown).",
            "label": label,
        }
    selected = _choose_best_csv_match(matches)
    assert selected is not None
    return {
        "csvText": selected.read_text(encoding="utf-8", errors="replace"),
        "fileName": selected.name,
        "relativePath": str(selected.relative_to(base)),
        "mode": "root-scan",
        "totalMatches": len(matches),
        "label": label,
    }


def _missing_app_html(slug: str, directory: Path) -> HTMLResponse:
    return HTMLResponse(
        f"""<!DOCTYPE html><html><head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
        <link href="https://fonts.googleapis.com/css2?family=Google+Sans:ital,opsz,wght@0,17..18,400..700;1,17..18,400..700&display=swap" rel="stylesheet" />
        </head><body style="font-family:'Google Sans',system-ui,sans-serif;padding:2rem">
        <h2>{slug.replace("-", " ").title()} is not built yet</h2>
        <p>Expected files at: <code>{directory}</code></p>
        <p>For The Super App, run:<br>
        <code>cd agents/the_super_app/app && npm ci && npm run build</code></p>
        </body></html>""",
        status_code=503,
    )


def register_internal_apps(app: FastAPI) -> None:
    """Mount static agent bundles and shared APIs on the RalphAI server."""

    @app.get("/api/default-dataset")
    def super_app_default_dd_exports() -> dict:
        """Sample DoorDash CSVs for Super App marketing breakdown when uploads are incomplete."""
        base = _DEFAULT_DATASET_ROOT
        return {
            "financialDetailed": _read_default_dataset(base, "FINANCIAL_DETAILED", "financialDetailed"),
            "marketingPromotion": _read_default_dataset(base, "MARKETING_PROMO", "marketingPromotion"),
            "salesByTimeProductPerformance": _read_default_dataset(
                base,
                "SALES_viewByTime_byStoreProductPerformance",
                "salesByTimeProductPerformance",
            ),
        }

    @app.get("/internal-apps/{slug}/health", include_in_schema=False)
    def internal_app_health(slug: str) -> dict:
        directory = INTERNAL_APPS.get(slug)
        if not directory:
            raise HTTPException(404, "Unknown internal app")
        index = directory / "index.html"
        build_version = int(index.stat().st_mtime) if index.is_file() else 0
        return {
            "slug": slug,
            "ready": directory.is_dir(),
            "path": str(directory),
            "buildVersion": build_version,
        }

    for slug, directory in INTERNAL_APPS.items():
        mount_path = f"/internal-apps/{slug}"
        if directory.is_dir():
            app.mount(
                mount_path,
                DevFriendlyStaticFiles(directory=str(directory), html=True),
                name=f"internal-app-{slug}",
            )
        else:

            def _make_missing_handler(app_slug: str, app_dir: Path, path: str):
                @app.get(path, include_in_schema=False)
                @app.get(f"{path}/{{rest:path}}", include_in_schema=False)
                def missing_internal_app(rest: str = "") -> HTMLResponse:
                    del rest
                    return _missing_app_html(app_slug, app_dir)

                return missing_internal_app

            _make_missing_handler(slug, directory, mount_path)
