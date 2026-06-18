"""
Campaign memory: learns from past run outcomes to improve future browser agent runs.

Stores per-operator history in a JSON file alongside the campaign workbook.
Before each campaign the agent receives a PRIOR EXPERIENCE block with:
  - success/failure counts and last run date
  - the last error or agent statement when a run failed
  - a slow-store warning when average time exceeds 400s
  - a duplicate alert when the last run was a duplicate

After each campaign, outcomes are recorded and the file is saved atomically.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MEMORY_FILENAME = "campaign_memory.json"
_MAX_OUTCOMES_PER_STORE = 20  # rolling window kept per store


class CampaignMemory:
    def __init__(self, memory_path: Path):
        self.memory_path = Path(memory_path)
        self.data: dict[str, Any] = self._load()
        self._dirty = False

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if self.memory_path.is_file():
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.info("campaign_memory: loaded %d store(s) from %s", len(data.get("stores", {})), self.memory_path)
                return data
            except Exception as e:
                logger.warning("campaign_memory: could not load %s (%s) — starting fresh", self.memory_path, e)
        return {"version": 1, "stores": {}}

    def save(self) -> None:
        """Atomically write memory to disk (only if changed)."""
        if not self._dirty:
            return
        try:
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.memory_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, default=str)
            tmp.replace(self.memory_path)
            self._dirty = False
            logger.debug("campaign_memory: saved to %s", self.memory_path)
        except Exception as e:
            logger.warning("campaign_memory: could not save %s: %s", self.memory_path, e)

    # ------------------------------------------------------------------
    # Record outcome
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        *,
        store_id: str,
        store_name: str = "",
        campaign_name: str = "",
        status: str,
        elapsed_s: float,
        final_text: str = "",
        error_text: str = "",
    ) -> None:
        """Record the result of one campaign attempt."""
        store_id = str(store_id).strip()
        if not store_id or store_id.lower() in ("nan", "none", ""):
            return

        stores = self.data.setdefault("stores", {})
        entry = stores.setdefault(store_id, {
            "store_name": store_name,
            "success_count": 0,
            "failure_count": 0,
            "timeout_count": 0,
            "duplicate_count": 0,
            "outcomes": [],
        })

        if store_name and not entry.get("store_name"):
            entry["store_name"] = store_name

        s = status.lower()
        if "successful" in s or s == "success":
            entry["success_count"] = entry.get("success_count", 0) + 1
        elif "duplicate" in s:
            entry["duplicate_count"] = entry.get("duplicate_count", 0) + 1
        else:
            entry["failure_count"] = entry.get("failure_count", 0) + 1
            if "timeout" in error_text.lower() or "timed out" in error_text.lower():
                entry["timeout_count"] = entry.get("timeout_count", 0) + 1

        outcome: dict[str, Any] = {
            "date": str(date.today()),
            "campaign": campaign_name,
            "status": status,
            "elapsed_s": round(elapsed_s, 1),
        }
        if final_text:
            outcome["final_text"] = final_text[:300]
        if error_text:
            outcome["error"] = error_text[:200]

        outcomes: list = entry.setdefault("outcomes", [])
        outcomes.append(outcome)
        entry["outcomes"] = outcomes[-_MAX_OUTCOMES_PER_STORE:]
        entry["last_status"] = status
        entry["last_run_date"] = str(date.today())
        self._dirty = True

    # ------------------------------------------------------------------
    # Generate hints for prompt injection
    # ------------------------------------------------------------------

    def get_store_hints(self, store_id: str) -> str:
        """
        Return a PRIOR EXPERIENCE block to prepend to the task description.
        Returns empty string when there is no prior data for this store.
        """
        store_id = str(store_id).strip()
        entry = self.data.get("stores", {}).get(store_id)
        if not entry:
            return ""

        success = entry.get("success_count", 0)
        failure = entry.get("failure_count", 0)
        duplicate = entry.get("duplicate_count", 0)
        timeout = entry.get("timeout_count", 0)
        last_status = entry.get("last_status", "")
        last_date = entry.get("last_run_date", "")
        total = success + failure + duplicate
        if total == 0:
            return ""

        lines: list[str] = []

        # Summary
        parts = []
        if success:
            parts.append(f"{success} successful")
        if failure:
            parts.append(f"{failure} failed" + (f" ({timeout} timed out)" if timeout else ""))
        if duplicate:
            parts.append(f"{duplicate} duplicates")
        lines.append(f"History: {', '.join(parts)}. Last run: {last_status} on {last_date}.")

        # Warn about recent failures
        recent = (entry.get("outcomes") or [])[-3:]
        recent_failures = [o for o in recent if "fail" in o.get("status", "").lower()]
        if recent_failures:
            lines.append(
                f"WARNING: {len(recent_failures)} of the last {len(recent)} run(s) FAILED for this store."
            )
            last_fail = recent_failures[-1]
            if last_fail.get("error"):
                lines.append(f"  Last error: {last_fail['error']}")
            if last_fail.get("final_text"):
                lines.append(f"  Agent last reported: {last_fail['final_text'][:150]}")

        # Duplicate alert
        if last_status and "duplicate" in last_status.lower():
            lines.append(
                "NOTE: The last run was a DUPLICATE — verify this campaign is not already live "
                "before attempting to create it again."
            )

        # Slow-store warning
        elapsed_vals = [
            o["elapsed_s"] for o in (entry.get("outcomes") or []) if o.get("elapsed_s")
        ]
        if elapsed_vals:
            avg = sum(elapsed_vals) / len(elapsed_vals)
            if avg > 400:
                lines.append(
                    f"NOTE: This store averages {avg:.0f}s per campaign — modals may load slowly, "
                    f"allow extra time before retrying clicks."
                )

        if not lines:
            return ""

        block = "\n".join(f"- {ln}" for ln in lines)
        return f"PRIOR EXPERIENCE FOR THIS STORE:\n{block}"

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_run_dir(cls, run_dir: Path) -> "CampaignMemory":
        """Load memory stored one level above run_dir (shared across all runs for this operator)."""
        return cls(Path(run_dir).parent / _MEMORY_FILENAME)
