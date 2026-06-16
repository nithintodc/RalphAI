"""Employee-friendly Slack copy for Ralph agents (no run IDs, no internal clutter)."""

from __future__ import annotations

_AGENT_DISPLAY: dict[str, str] = {
    "offers": "Ralph Offers",
    "ads": "Ralph Ads",
    "strategist": "Strategist",
    "health_check": "Health Check",
    "data_run": "Data Run",
    "deepdive": "DeepDive",
    "campaign_analyser": "Campaign Analyser",
    "monthly_reporter": "Monthly Reporter",
}


def agent_display_name(agent: str) -> str:
    key = (agent or "").strip().lower().replace(" ", "_")
    if key in _AGENT_DISPLAY:
        return _AGENT_DISPLAY[key]
    cleaned = (agent or "Agent").strip()
    if cleaned.lower().startswith("ralphai"):
        return cleaned.replace("RalphAI", "Ralph", 1).strip()
    return cleaned


def ralph_campaign_product(label: str) -> str:
    """Map Offers/Ads sheet labels to Ralph Offers / Ralph Ads."""
    key = (label or "").strip().lower()
    if key in ("offers", "offer"):
        return "Ralph Offers"
    if key in ("ads", "ad"):
        return "Ralph Ads"
    return agent_display_name(label)


def _status_emoji(status: str) -> str:
    s = (status or "").strip().lower()
    if s in ("success", "completed", "ok"):
        return "✅"
    if s in ("failed", "error"):
        return "❌"
    if s in ("running", "pending", "queued"):
        return "⏳"
    if s in ("skipped", "interrupted", "cancelled"):
        return "⚠️"
    return "ℹ️"


def _status_phrase(status: str) -> str:
    s = (status or "").strip().lower()
    if s in ("success", "completed"):
        return "complete"
    if s in ("failed", "error"):
        return "failed"
    if s == "queued":
        return "queued"
    if s == "running":
        return "in progress"
    return s or "updated"


def run_finished(
    *,
    agent: str,
    operator: str,
    status: str,
    duration: str = "",
    error: str = "",
) -> str:
    name = agent_display_name(agent)
    lines = [f"{_status_emoji(status)} *{name}* — {_status_phrase(status)}"]
    op = (operator or "").strip()
    if op and op != "—":
        lines.append(op)
    dur = (duration or "").strip()
    if dur:
        lines.append(f"_{dur}_")
    err = (error or "").strip()
    if err:
        lines.append(f"_{err[:240]}_")
    return "\n".join(lines)


def export_ready(*, kind: str, filename: str) -> str:
    title = (kind or "Export").strip()
    name = (filename or "file").strip()
    return f"📤 *{title}*\n`{name}`"


def campaigns_starting(*, product: str, count: int) -> str:
    label = ralph_campaign_product(product)
    noun = "campaign" if count == 1 else "campaigns"
    return f"🚀 *{label}* — starting {count} {noun}"


def campaigns_phase_started(*, product: str, count: int) -> str:
    label = ralph_campaign_product(product)
    noun = "campaign" if count == 1 else "campaigns"
    return f"▶️ *{label}* — creating {count} {noun}"


def portal_logged_in() -> str:
    return "🔐 Logged into DoorDash"


def portal_login_failed(*, detail: str = "") -> str:
    text = (detail or "").strip()
    if text:
        return f"❌ DoorDash login failed\n_{text[:200]}_"
    return "❌ DoorDash login failed"


def campaign_item_result(*, index: int, total: int, name: str, outcome: str) -> str:
    """outcome: done | skipped | failed | timed out"""
    key = (outcome or "").strip().lower()
    icons = {
        "done": "✅",
        "skipped": "⏭️",
        "failed": "❌",
        "timed out": "⏱️",
    }
    icon = icons.get(key, "•")
    return f"{icon} [{index}/{total}] {name}"


def campaigns_progress(
    *,
    product: str,
    index: int,
    total: int,
    ok: int,
    failed: int,
    skipped: int,
) -> str:
    label = ralph_campaign_product(product)
    return f"*{label}* — {index}/{total} · {ok} ok · {failed} failed · {skipped} skipped"


def campaigns_complete(
    *,
    product: str,
    ok: int,
    failed: int,
    skipped: int,
    minutes: float,
) -> str:
    label = ralph_campaign_product(product)
    return (
        f"✅ *{label}* — done\n"
        f"{ok} ok · {failed} failed · {skipped} skipped · {minutes:.0f} min"
    )


def campaigns_aborted(*, index: int, total: int, ok: int, failed: int, skipped: int) -> str:
    return (
        f"⚠️ *Campaign run stopped* at {index}/{total}\n"
        f"{ok} ok · {failed} failed · {skipped} skipped"
    )


def reports_phase_started(*, date_range: str = "") -> str:
    lines = ["📥 *Reports* — downloading"]
    if (date_range or "").strip():
        lines.append(f"_{date_range.strip()}_")
    return "\n".join(lines)


def reports_ready() -> str:
    return "📥 Reports downloaded"


def analysis_started() -> str:
    return "📊 *Analysis* — processing reports"


def analysis_ready(*, seconds: float | None = None) -> str:
    if seconds is not None and seconds > 0:
        return f"📊 Combined analysis ready _({seconds:.0f}s)_"
    return "📊 Combined analysis ready"


def analysis_missing() -> str:
    return "⚠️ Combined analysis not created — check report files"


def campaigns_resume(*, skipped: int, remaining: int) -> str:
    return f"↩️ Resuming — {skipped} already done, {remaining} remaining"


def browser_restarted(*, index: int, total: int) -> str:
    return f"🔄 Browser refreshed before campaign {index}/{total}"


def report_missing_retry(*, names: list[str]) -> str:
    joined = ", ".join(names)
    return f"⚠️ Missing {joined} — retrying download"
