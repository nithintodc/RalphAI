"""DoorDash data access — loads from operator's export zip directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from agents.deepdive.data_loader import load_ssm_zips
from shared.config.settings import deepdive_operator_zip_dir
from shared.logger import get_logger

log = get_logger("ingestion.doordash_client")


def fetch_operator_window(operator_id: str, days: int) -> dict[str, Any]:
    """Load DoorDash export zips from the operator's data directory.

    Looks in ``data/operators/<operator_id>/raw/`` first, then falls back to
    ``data/TriArch/`` (legacy shared directory).  The ``days`` parameter is
    informational — filtering is applied downstream in DeepDive because the
    exports are already date-bounded at download time.

    Returns a dict mapping dataset category keys to ``pd.DataFrame`` objects.
    Returns empty DataFrames for every expected key when no zips are found.
    """
    _ = days  # date-range filtering happens at download / DeepDive level

    zip_dir: Path = deepdive_operator_zip_dir(operator_id)

    if not zip_dir.is_dir():
        log.warning(
            "No zip directory for operator %s (tried %s) — returning empty datasets",
            operator_id,
            zip_dir,
        )
        return _empty_datasets()

    datasets = load_ssm_zips(zip_dir)

    if not datasets:
        log.warning(
            "No zip files found in %s for operator %s — returning empty datasets",
            zip_dir,
            operator_id,
        )
        return _empty_datasets()

    log.info(
        "Loaded %d dataset(s) for operator %s from %s: %s",
        len(datasets),
        operator_id,
        zip_dir,
        sorted(k for k in datasets if not k.startswith("store_id")),
    )
    return datasets


def _empty_datasets() -> dict[str, Any]:
    """Return empty DataFrames for all expected export categories."""
    keys = [
        "financial_detailed",
        "financial_simplified",
        "financial_errors",
        "financial_payouts",
        "marketing_promotions",
        "marketing_sponsored",
        "sales_by_order",
        "sales_by_time",
        "product_mix",
        "operations_quality",
    ]
    return {k: pd.DataFrame() for k in keys}
