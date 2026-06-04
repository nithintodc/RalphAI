"""Campaign Killer agent — ends active DoorDash marketing campaigns named TODC-*.

Flow per operator: Merchant login → Marketing → Campaigns → All statuses → Active → Apply →
for each visible row whose name starts with ``TODC-``: ⋮ → End campaign → Yes, end →
reason *Technical issue — I have trouble…* → End campaign.

Usage:
    # Kill TODC-* campaigns for ALL operators in the CSV:
    python -m agents.campaign_killer.agent

    # Kill for specific operators (by business name):
    python -m agents.campaign_killer.agent "Goodman Group Restaurants" "Another Operator"

    # Optional: skip typing "TODC" in the campaigns table search (default is to search):
    python -m agents.campaign_killer.agent --no-todc-table-search

    # Run headless (no visible browser):
    python -m agents.campaign_killer.agent --headless

    # Dry-run: list operators without actually running:
    python -m agents.campaign_killer.agent --dry-run
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from shared.utils.account_directory import load_account_operators
from shared.utils.slack_client import post_message, slack_notification_channel

from .killer import KillResult, kill_campaigns_for_operator

log = logging.getLogger(__name__)


def _emit_campaign_killer_line(
    *,
    email: str,
    business_name: str,
    campaigns_ended: list[str],
    status: str,
    errors: list[str],
) -> None:
    """
    Log to terminal (stdout + logger) and optionally Slack when ``SLACK_CHANNEL`` is set
    (same channel as other agents; see ``slack_notification_channel``).
    """
    n = len(campaigns_ended)
    names = ", ".join(campaigns_ended) if campaigns_ended else ""
    err_tail = ""
    if errors:
        err_tail = f" Details: {'; '.join(errors)}"

    if n > 0:
        line = (
            f"Campaign Killer | For {email} ({business_name}), "
            f"{n} campaign(s) removed: {names}"
        )
    else:
        if status in ("login_failed", "error", "skipped_2fa"):
            line = (
                f"Campaign Killer | For {email} ({business_name}), "
                f"no campaigns removed — status={status}.{err_tail}"
            )
        else:
            line = (
                f"Campaign Killer | For {email} ({business_name}), "
                f"no active matching campaigns removed.{err_tail}"
            )

    log.info(line)
    print(line, flush=True)

    channel = slack_notification_channel()
    if channel:
        if status == "skipped_2fa":
            emoji = ":warning:"
            body = "Skipped — *2FA required*, cannot proceed automatically."
        elif n > 0:
            emoji = ":skull_and_crossbones:"
            body = f"Removed *{n}* campaign(s): {names}"
        elif status == "login_failed":
            emoji = ":x:"
            body = f"Login failed — no campaigns removed.{err_tail}"
        elif status == "error":
            emoji = ":x:"
            body = f"Error — no campaigns removed.{err_tail}"
        elif status == "success":
            emoji = ":white_check_mark:"
            body = "No active ad campaigns found."
        else:
            emoji = ":information_source:"
            body = f"No campaigns removed (status: `{status}`).{err_tail}"

        slack_text = f"{emoji} *Campaign Killer* | `{email}` — *{business_name}*\n{body}"
        post_message(channel, slack_text)


@dataclass
class Operator:
    operator_id: str
    business_name: str
    email: str
    password: str


def _load_operators(selected_ids: list[str] | None = None) -> list[Operator]:
    """Load operators from Airtable. If selected_ids given, filter to those only."""
    try:
        rows, warning = load_account_operators()
    except Exception as exc:
        log.error("Account directory error: %s", exc)
        return []
    if warning:
        log.warning("Account directory: %s", warning)
    if not rows:
        log.error("No operators in Airtable account directory.")
        return []

    operators: list[Operator] = []
    for row in rows:
        email = str(row.get("doordash_email", "")).strip()
        password = str(row.get("doordash_password", "")).strip()
        if not email or not password:
            continue
        operators.append(
            Operator(
                operator_id=row["operator_id"],
                business_name=row["business_name"],
                email=email,
                password=password,
            )
        )

    if selected_ids:
        lookup = {s.strip().lower() for s in selected_ids if s.strip()}
        operators = [
            op for op in operators
            if op.operator_id.lower() in lookup or op.business_name.lower() in lookup
        ]

    # De-duplicate by email so we don't login to the same account twice.
    seen_emails: set[str] = set()
    unique: list[Operator] = []
    for op in operators:
        key = op.email.lower()
        if key not in seen_emails:
            seen_emails.add(key)
            unique.append(op)

    return unique


async def run_async(
    *,
    operator_ids: list[str] | None = None,
    headless: bool = False,
    search_todc: bool = True,
) -> dict[str, Any]:
    """
    Main entry point: iterate operators sequentially, end active **TODC-*** campaigns.
    Each operator gets its own browser instance (launched and closed).
    """
    operators = _load_operators(operator_ids)
    if not operators:
        return {"status": "no_operators", "results": []}

    log.info("Campaign Killer starting for %d operator(s).", len(operators))

    results: list[dict[str, Any]] = []
    for i, op in enumerate(operators, 1):
        log.info(
            "--- [%d/%d] Operator: %s (%s) ---",
            i, len(operators), op.business_name, op.email,
        )
        result: KillResult = await kill_campaigns_for_operator(
            email=op.email,
            password=op.password,
            operator_id=op.operator_id,
            headless=headless,
            search_todc=search_todc,
        )
        results.append({
            "operator_id": result.operator_id,
            "email": result.email,
            "status": result.status,
            "campaigns_ended": result.campaigns_ended,
            "campaigns_ended_count": len(result.campaigns_ended),
            "errors": result.errors,
        })

        _emit_campaign_killer_line(
            email=result.email,
            business_name=op.business_name,
            campaigns_ended=result.campaigns_ended,
            status=result.status,
            errors=result.errors,
        )

    total_ended = sum(r["campaigns_ended_count"] for r in results)
    count_success = sum(1 for r in results if r["status"] == "success")
    count_partial = sum(1 for r in results if r["status"] == "partial")
    count_2fa = sum(1 for r in results if r["status"] == "skipped_2fa")
    count_login_failed = sum(1 for r in results if r["status"] == "login_failed")
    count_error = sum(1 for r in results if r["status"] == "error")

    summary = {
        # "success" keeps the run index consistent with every other agent's status vocab.
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "total_operators": len(operators),
        "total_campaigns_ended": total_ended,
        "operators_success": count_success + count_partial,
        "operators_skipped_2fa": count_2fa,
        "operators_failed": count_login_failed + count_error,
        "results": results,
    }

    report_dir = Path(__file__).resolve().parents[2] / "data" / "runs" / "campaign_killer"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"kill-run-{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    log.info("Report saved to %s", report_path)

    done_line = (
        f"Campaign Killer | Finished: {len(operators)} operator(s), "
        f"{total_ended} campaign(s) removed in total."
    )
    log.info(done_line)
    print(done_line, flush=True)
    ch = slack_notification_channel()
    if ch:
        breakdown_parts = []
        if count_success + count_partial > 0:
            breakdown_parts.append(f":white_check_mark: {count_success + count_partial} processed")
        if count_2fa > 0:
            breakdown_parts.append(f":warning: {count_2fa} skipped (2FA)")
        if count_login_failed > 0:
            breakdown_parts.append(f":x: {count_login_failed} login failed")
        if count_error > 0:
            breakdown_parts.append(f":x: {count_error} errored")
        breakdown = "\n".join(breakdown_parts) if breakdown_parts else "No operators processed."

        skipped_names = [
            r["operator_id"] for r in results if r["status"] == "skipped_2fa"
        ]
        skipped_section = ""
        if skipped_names:
            skipped_section = (
                "\n\n*Skipped (2FA required):*\n"
                + "\n".join(f"• `{n}`" for n in skipped_names)
            )

        post_message(
            ch,
            f":skull: *Campaign Killer — run complete*\n"
            f"*{len(operators)}* operator(s) | *{total_ended}* campaign(s) ended\n\n"
            f"{breakdown}{skipped_section}",
        )

    return summary


def run(
    *,
    operator_ids: list[str] | None = None,
    headless: bool = False,
    search_todc: bool = True,
) -> dict[str, Any]:
    """Sync wrapper around the async entry point."""
    return asyncio.run(
        run_async(operator_ids=operator_ids, headless=headless, search_todc=search_todc)
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    args = sys.argv[1:]
    headless = "--headless" in args
    dry_run = "--dry-run" in args
    skip_todc_search = "--no-todc-table-search" in args or "--skip-todc-search" in args
    operator_names = [a for a in args if not a.startswith("--")]

    operators = _load_operators(operator_names or None)
    if dry_run:
        print(f"Would process {len(operators)} operator(s):")
        for op in operators:
            print(f"  • {op.business_name} — {op.email}")
        sys.exit(0)

    print(f"Starting Campaign Killer for {len(operators)} operator(s)…")
    result = run(
        operator_ids=operator_names or None,
        headless=headless,
        search_todc=not skip_todc_search,
    )
    print(json.dumps(result, indent=2))
