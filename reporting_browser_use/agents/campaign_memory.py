"""
Campaign memory: learns from past run outcomes to improve future browser agent runs.

Storage design — fixed-size record per store, no raw history:
  Each store entry is ~150 bytes regardless of how many campaigns have run.
  1,000 stores ≈ 150 KB. The file does not grow over time.

Per-store fields (short keys to minimise JSON overhead):
  n       store name (truncated to 40 chars)
  ok      cumulative success count
  fail    cumulative failure count
  dup     cumulative duplicate count
  to      cumulative timeout count
  avg_s   rolling-average elapsed seconds (updated incrementally)
  last    last outcome code: "ok" | "fail" | "dup"
  last_d  last run date (YYYY-MM-DD)
  warn    synthesised failure reason from most recent failure (≤120 chars)
  tip     learned actionable insight written when a pattern is detected (≤120 chars)

Synthesis rules (applied in record_outcome):
  - warn: overwritten on every failure with a ≤120-char distillation of
    error_text or final_text — never accumulated.
  - tip: written/updated when a pattern is first detected, then left stable:
      • avg_s > 400 after ≥3 runs  → slow-modal tip
      • fail rate > 50% after ≥4 runs → high-failure-rate tip
      • all failures are timeouts   → connectivity tip
  - avg_s: rolling mean via  new = (old * (n-1) + val) / n  — O(1), no history.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_MEMORY_FILENAME = "campaign_memory.json"
_NAME_MAX = 40       # store name truncation
_WARN_MAX = 120      # warn/tip field length cap


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
                n = len(data.get("stores", {}))
                logger.info("campaign_memory: loaded %d store(s) from %s", n, self.memory_path)
                return data
            except Exception as e:
                logger.warning(
                    "campaign_memory: could not load %s (%s) — starting fresh",
                    self.memory_path, e,
                )
        return {"v": 2, "stores": {}}

    def save(self) -> None:
        """Atomically flush to disk (only if changed). Uses tmp+rename for crash safety."""
        if not self._dirty:
            return
        try:
            self.memory_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.memory_path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                # Compact JSON — no indent, saves ~40% vs indent=2
                json.dump(self.data, f, separators=(",", ":"), default=str)
            tmp.replace(self.memory_path)
            self._dirty = False
            logger.debug("campaign_memory: saved to %s", self.memory_path)
        except Exception as e:
            logger.warning("campaign_memory: could not save %s: %s", self.memory_path, e)

    # ------------------------------------------------------------------
    # Record outcome  (the only write path)
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        *,
        store_id: str,
        store_name: str = "",
        campaign_name: str = "",  # unused in storage but kept for API compat
        status: str,
        elapsed_s: float,
        final_text: str = "",
        error_text: str = "",
    ) -> None:
        """Synthesise and persist one campaign outcome."""
        store_id = str(store_id).strip()
        if not store_id or store_id.lower() in ("nan", "none", ""):
            return

        stores = self.data.setdefault("stores", {})
        e = stores.setdefault(store_id, {
            "n": "", "ok": 0, "fail": 0, "dup": 0, "to": 0,
            "avg_s": 0.0, "last": "", "last_d": "",
            "warn": None, "tip": None,
        })

        # Migrate v1 entries (long-key format) on first touch
        if "success_count" in e:
            e = self._migrate_v1(store_id, e)
            stores[store_id] = e

        # Store name (keep the longer/better one)
        if store_name and len(store_name) > len(e.get("n") or ""):
            e["n"] = store_name[:_NAME_MAX]

        # Classify outcome
        s = status.lower()
        is_ok = "successful" in s or s == "success"
        is_dup = "duplicate" in s
        is_fail = not is_ok and not is_dup

        # Update counters
        if is_ok:
            e["ok"] += 1
            e["last"] = "ok"
            e["warn"] = None          # clear last warning on success
        elif is_dup:
            e["dup"] += 1
            e["last"] = "dup"
        else:
            e["fail"] += 1
            e["last"] = "fail"
            is_timeout = "timeout" in error_text.lower() or "timed out" in error_text.lower()
            if is_timeout:
                e["to"] += 1
            # Synthesise warn: prefer error_text, fall back to final_text
            raw = (error_text or final_text or "").strip()
            if raw:
                e["warn"] = _truncate(raw, _WARN_MAX)

        # Rolling average elapsed (incremental — no history needed)
        n_total = e["ok"] + e["fail"] + e["dup"]
        if n_total == 1:
            e["avg_s"] = round(elapsed_s, 1)
        else:
            e["avg_s"] = round(((e["avg_s"] * (n_total - 1)) + elapsed_s) / n_total, 1)

        e["last_d"] = str(date.today())

        # Pattern detection → tip (written once, stable thereafter)
        self._maybe_write_tip(e)

        self._dirty = True

    # ------------------------------------------------------------------
    # Hint generation  (read-only, called per campaign before task build)
    # ------------------------------------------------------------------

    def get_store_hints(self, store_id: str) -> str:
        """
        Return a compact PRIOR EXPERIENCE block for injection into the task prompt.
        Returns "" when no data exists for this store.
        """
        store_id = str(store_id).strip()
        e = self.data.get("stores", {}).get(store_id)
        if not e:
            return ""

        ok, fail, dup, to_ = e.get("ok", 0), e.get("fail", 0), e.get("dup", 0), e.get("to", 0)
        total = ok + fail + dup
        if total == 0:
            return ""

        last = e.get("last", "")
        last_d = e.get("last_d", "")
        warn = e.get("warn")
        tip = e.get("tip")
        avg_s = e.get("avg_s", 0)

        lines: list[str] = []

        # One-line summary
        parts: list[str] = []
        if ok:
            parts.append(f"{ok} ok")
        if fail:
            parts.append(f"{fail} failed" + (f" ({to_} timeout)" if to_ else ""))
        if dup:
            parts.append(f"{dup} dup")
        last_label = {"ok": "Success", "fail": "FAILED", "dup": "Duplicate"}.get(last, last)
        lines.append(f"History ({total} runs): {', '.join(parts)}. Last: {last_label} on {last_d}.")

        # Failure warning + reason
        if last == "fail" and warn:
            lines.append(f"WARNING: Last run FAILED — {warn}")
        elif fail > 0 and fail >= ok and total >= 3:
            lines.append(f"WARNING: This store fails more often than it succeeds ({fail}/{total} runs).")

        # Duplicate alert
        if last == "dup":
            lines.append("NOTE: Last run was a DUPLICATE — verify the campaign is not already live before creating.")

        # Slow-modal tip
        if tip:
            lines.append(f"TIP: {tip}")
        elif avg_s > 400:
            lines.append(f"NOTE: Avg {avg_s:.0f}s/campaign — modals load slowly, allow extra time before retrying clicks.")

        block = "\n".join(f"- {ln}" for ln in lines)
        return f"PRIOR EXPERIENCE FOR THIS STORE:\n{block}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _maybe_write_tip(self, e: dict) -> None:
        """Detect patterns and write a stable tip. Does not overwrite an existing tip."""
        if e.get("tip"):
            return
        ok, fail, to_ = e.get("ok", 0), e.get("fail", 0), e.get("to", 0)
        total = ok + fail
        avg_s = e.get("avg_s", 0)

        if total >= 3 and avg_s > 400:
            e["tip"] = f"Modals load slowly (~{avg_s:.0f}s avg) — wait before retrying any click."
        elif total >= 4 and fail > ok:
            e["tip"] = f"High failure rate ({fail}/{total} runs) — proceed carefully and verify each step."
        elif fail >= 2 and to_ == fail:
            e["tip"] = "All failures were timeouts — check portal connectivity before starting."

    @staticmethod
    def _migrate_v1(store_id: str, old: dict) -> dict:
        """Convert a v1 (long-key) entry to compact v2 format."""
        outcomes = old.get("outcomes") or []
        elapsed_vals = [o.get("elapsed_s", 0) for o in outcomes if o.get("elapsed_s")]
        avg_s = round(sum(elapsed_vals) / len(elapsed_vals), 1) if elapsed_vals else 0.0
        last_fail = next(
            (o for o in reversed(outcomes) if "fail" in o.get("status", "").lower()), None
        )
        warn = None
        if last_fail:
            raw = last_fail.get("error") or last_fail.get("final_text") or ""
            warn = _truncate(raw, _WARN_MAX) if raw else None
        last_s = (old.get("last_status") or "").lower()
        last_code = "ok" if "success" in last_s else ("dup" if "dup" in last_s else "fail")
        return {
            "n": (old.get("store_name") or "")[:_NAME_MAX],
            "ok": old.get("success_count", 0),
            "fail": old.get("failure_count", 0),
            "dup": old.get("duplicate_count", 0),
            "to": old.get("timeout_count", 0),
            "avg_s": avg_s,
            "last": last_code,
            "last_d": old.get("last_run_date", ""),
            "warn": warn,
            "tip": None,
        }

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_run_dir(cls, run_dir: Path) -> "CampaignMemory":
        """Load memory one level above run_dir — shared across all runs for this operator."""
        return cls(Path(run_dir).parent / _MEMORY_FILENAME)


# ------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------

def _truncate(text: str, max_len: int) -> str:
    """Truncate to max_len chars, cutting at a word boundary where possible."""
    text = " ".join(text.split())  # collapse whitespace
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)
    return (cut[0] if len(cut) > 1 else text[:max_len]) + "…"
