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


def redis_url() -> str | None:
    return os.environ.get("REDIS_URL")


def review_delay_days() -> int:
    return int(os.environ.get("REVIEW_DELAY_DAYS", REVIEW_DELAY_DAYS))
