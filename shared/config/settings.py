"""Environment-based settings + legacy `Settings` for `flow_manager` / JSON contracts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from shared.config.constants import REVIEW_DELAY_DAYS


@dataclass(frozen=True)
class Settings:
    """Orchestrator control defaults (original micro-agent pipeline)."""

    log_level: str
    contracts_dir: str
    require_human_approval_default: bool
    min_confidence_default: float
    max_budget_cents_default: int | None

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            contracts_dir=os.environ.get(
                "CONTRACTS_DIR",
                os.path.join(
                    os.path.dirname(__file__), "..", "..", "contracts"
                ),
            ),
            require_human_approval_default=os.environ.get(
                "REQUIRE_HUMAN_APPROVAL", ""
            ).lower()
            in ("1", "true", "yes"),
            min_confidence_default=float(os.environ.get("MIN_CONFIDENCE", "0.0")),
            max_budget_cents_default=(
                int(os.environ["MAX_BUDGET_CENTS"])
                if os.environ.get("MAX_BUDGET_CENTS")
                else None
            ),
        )


def data_root() -> Path:
    raw = os.environ.get("TODC_DATA_DIR")
    if raw:
        return Path(raw).resolve()
    return Path(__file__).resolve().parents[2] / "data"


def deepdive_default_zip_dir() -> Path:
    """Directory of DoorDash export `.zip` files when DeepDive runs without `data_dir` / `data_files`."""
    return data_root() / "TriArch"


def deepdive_operator_zip_dir(operator_id: str) -> Path:
    """Per-operator directory for DoorDash export `.zip` files.

    Resolution order:
    1. ``data/operators/<operator_id>/raw/``  — written by health-check / onboarding downloads.
    2. ``deepdive_default_zip_dir()``         — legacy shared directory (TriArch).

    Returns whichever path exists first, or the per-operator path as a creation target
    when neither exists yet.
    """
    per_operator = data_root() / "operators" / operator_id / "raw"
    if per_operator.is_dir():
        return per_operator
    default = deepdive_default_zip_dir()
    if default.is_dir():
        return default
    return per_operator


def redis_url() -> str | None:
    return os.environ.get("REDIS_URL")


def review_delay_days() -> int:
    return int(os.environ.get("REVIEW_DELAY_DAYS", REVIEW_DELAY_DAYS))


def reporting_browser_use_root() -> Path:
    """
    Repo directory for the browser-use DoorDash workflow (``main.py`` and nested ``agents/``).
    """
    return Path(__file__).resolve().parents[2] / "agents" / "reporting_browser_use"


def marketingreco_reporting_root() -> Path:
    """
    Reporting workflow root used by MarketingReco manual/auto and Offers/Ads automation.
    """
    raw = os.environ.get("MARKETINGRECO_REPORTING_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return reporting_browser_use_root()


def deepdive_include_metric_hierarchy() -> bool:
    """
    Feature flag for DeepDive hierarchy rollups in responses/reports.
    """
    return os.environ.get("DEEPDIVE_INCLUDE_METRIC_HIERARCHY", "1").lower() in ("1", "true", "yes")


def account_information_csv_path() -> Path:
    """
    Legacy CSV path (``ACCOUNT_INFORMATION_CSV``). Operator pickers and agents use
    Airtable via ``shared.utils.account_directory.load_account_operators`` instead.
    """
    raw = os.environ.get("ACCOUNT_INFORMATION_CSV", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "accounts.csv"
