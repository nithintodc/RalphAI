"""Discover DoorDash report zips in agent dir and system Downloads (CDP fallback)."""

from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def system_downloads_dirs() -> list[Path]:
    """macOS/Linux/Windows user Downloads folders (Chrome default when CDP path fails)."""
    home = Path.home()
    out: list[Path] = []
    for name in ("Downloads", "downloads"):
        path = (home / name).resolve()
        if path.is_dir() and path not in out:
            out.append(path)
    return out


def _peek_zip_type(path: Path) -> str:
    try:
        with zipfile.ZipFile(path, "r") as z:
            names_upper = " ".join(z.namelist()).upper()
        if "FINANCIAL_DETAILED" in names_upper or (
            "FINANCIAL" in names_upper and "MARKETING" not in names_upper
        ):
            return "financial"
        if (
            "MARKETING_PROMOTION" in names_upper
            or "MARKETING_SPONSORED" in names_upper
            or "MARKETING" in names_upper
        ):
            return "marketing"
    except Exception:
        pass
    return ""


def _list_candidates(
    search_dirs: list[Path],
    *,
    baseline_files: set[Path],
    min_mtime: float | None,
) -> tuple[list[tuple[float, Path, Path]], list[str]]:
    """Return (mtime, path, source_dir) sorted by mtime desc, plus filter notes."""
    all_files: list[tuple[float, Path, Path]] = []
    filtered_out: list[str] = []
    seen: set[Path] = set()

    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for ext in ("*.csv", "*.zip", "*.xlsx"):
            for f in directory.glob(ext):
                if not f.is_file():
                    continue
                resolved = f.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                st = resolved.stat()
                if resolved in baseline_files:
                    filtered_out.append(f"{resolved.name}:baseline")
                    continue
                if min_mtime is not None and st.st_mtime < min_mtime:
                    filtered_out.append(f"{resolved.name}:old")
                    continue
                all_files.append((st.st_mtime, resolved, directory))

    all_files.sort(key=lambda x: x[0], reverse=True)
    return all_files, filtered_out


def _classify_reports(
    all_files: list[tuple[float, Path, Path]],
) -> tuple[Optional[Path], Optional[Path]]:
    financial_path: Optional[Path] = None
    marketing_path: Optional[Path] = None
    unmatched: list[Path] = []

    for _mtime, path, _src in all_files:
        name_lower = path.name.lower()
        if "financial" in name_lower or "financials" in name_lower:
            if financial_path is None:
                financial_path = path
        elif "marketing" in name_lower:
            if marketing_path is None:
                marketing_path = path
        else:
            unmatched.append(path)
        if financial_path and marketing_path:
            break

    if (financial_path is None or marketing_path is None) and unmatched:
        for path in unmatched:
            if path.suffix.lower() != ".zip":
                continue
            kind = _peek_zip_type(path)
            if kind == "financial" and financial_path is None:
                financial_path = path
                logger.info("DoorDash: classified %s as financial by content", path.name)
            elif kind == "marketing" and marketing_path is None:
                marketing_path = path
                logger.info("DoorDash: classified %s as marketing by content", path.name)
            if financial_path and marketing_path:
                break

    if financial_path is None and all_files:
        for _mtime, candidate, _src in all_files:
            if candidate != marketing_path:
                financial_path = candidate
                logger.warning(
                    "DoorDash: no filename/content match; treating %s as financial",
                    financial_path.name,
                )
                break

    return financial_path, marketing_path


def _relocate_into_download_dir(path: Path, download_dir: Path) -> Path:
    download_dir = Path(download_dir).resolve()
    download_dir.mkdir(parents=True, exist_ok=True)
    if path.parent.resolve() == download_dir:
        return path
    dest = download_dir / path.name
    if dest.exists():
        dest.unlink()
    shutil.move(str(path), str(dest))
    logger.info("DoorDash: moved report %s → %s", path, dest)
    return dest


def discover_doordash_reports(
    download_dir: Path,
    *,
    baseline_files: set[Path] | None = None,
    min_mtime: float | None = None,
    relocate_external: bool = True,
) -> tuple[Optional[Path], Optional[Path], dict[str, Any]]:
    """
    Find financial + marketing reports under ``download_dir`` and system Downloads.

    When CDP attach leaves Chrome saving to ~/Downloads, files are found there and
    optionally moved into ``download_dir`` for downstream processing.
    """
    download_dir = Path(download_dir).resolve()
    download_dir.mkdir(parents=True, exist_ok=True)
    existing = baseline_files or set()
    search_dirs = [download_dir, *system_downloads_dirs()]

    all_files, filtered_out = _list_candidates(
        search_dirs,
        baseline_files=existing,
        min_mtime=min_mtime,
    )
    financial_path, marketing_path = _classify_reports(all_files)

    external_sources = {p for _m, p, src in all_files if src != download_dir}
    if relocate_external:
        if financial_path and financial_path in external_sources:
            financial_path = _relocate_into_download_dir(financial_path, download_dir)
        if marketing_path and marketing_path in external_sources:
            marketing_path = _relocate_into_download_dir(marketing_path, download_dir)

    diagnostics = {
        "considered_files": [p.name for _m, p, _s in all_files],
        "search_dirs": [str(d) for d in search_dirs],
        "filtered_out": filtered_out,
        "marketing": marketing_path.name if marketing_path else None,
        "financial": financial_path.name if financial_path else None,
    }
    return marketing_path, financial_path, diagnostics
