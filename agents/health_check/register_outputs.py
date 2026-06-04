"""
Health Check register bundle: week1/2 DD+UE registers, WoW registers, HTML, PDF, Drive, Slack.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

from agents.health_check.drive_upload import upload_file_to_drive
from agents.health_check.pdf_export import html_to_pdf
from agents.health_check.campaign_wow import build_campaign_slack_summary, campaign_wow_for_html
from agents.health_check.wow_viz import build_register_wow_report_html, build_wow_slack_message
from shared.register_build import (
    build_wow_register_csv,
    empty_ue_register_df,
    register_df_to_analysis_rows,
    weekly_csv_to_register_df,
    write_register_csv,
)
from shared.register_wow import build_slack_summary, compare_register_slots
from shared.utils.slack_client import notify as slack_notify

logger = logging.getLogger(__name__)

def resolve_healthcheck_html_url(html_path: Path, *, operator_name: str) -> str | None:
    """
    Public URL for the WoW HTML report: Google Drive when configured, else API base URL.
    """
    html_path = Path(html_path)
    if not html_path.is_file():
        return None

    upload = upload_file_to_drive(
        html_path,
        subfolder_name=f"healthcheck_{operator_name[:40]}",
        file_name=f"{operator_name}_register_wow.html",
        mimetype="text/html",
    )
    if upload and upload.get("webViewLink"):
        return str(upload["webViewLink"])

    base = (
        os.getenv("RALPHAI_PUBLIC_BASE_URL")
        or os.getenv("RALPHAI_API_BASE_URL")
        or ""
    ).strip().rstrip("/")
    if base:
        return f"{base}/api/healthcheck/wow-viz?path={quote(str(html_path.resolve()))}"
    return None


REGISTER_FILES = {
    "week1_dd": "week1-dd-register.csv",
    "week2_dd": "week2-dd-register.csv",
    "week1_ue": "week1-ue-register.csv",
    "week2_ue": "week2-ue-register.csv",
    "wow_dd": "WoW-dd-register.csv",
    "wow_ue": "WoW-ue-register.csv",
    "html": "register_wow_report.html",
    "html_legacy": "wow_buckets.html",
    "pdf": "register_wow_report.pdf",
    "wow_campaigns_promo": "wow_campaigns_promo.csv",
    "wow_campaigns_ads": "wow_campaigns_ads.csv",
}


def build_operator_register_bundle(
    *,
    week1_weekly_csv: Path,
    week2_weekly_csv: Path,
    output_dir: Path,
    week1_label: str,
    week2_label: str,
    operator_name: str,
    ue_week1_csv: Path | None = None,
    ue_week2_csv: Path | None = None,
    campaign_wow_files: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """
    Write register CSVs, HTML report, PDF, upload to Drive, post Slack summary.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {"register_files": {}, "platform": "dd"}

    # DoorDash registers from weekly health-check CSVs
    dd_w1_df = weekly_csv_to_register_df(week1_weekly_csv, week_label=week1_label)
    dd_w2_df = weekly_csv_to_register_df(week2_weekly_csv, week_label=week2_label)
    store_ids = sorted(dd_w1_df["Merchant Store ID"].astype(str).unique().tolist())

    w1_dd = output_dir / REGISTER_FILES["week1_dd"]
    w2_dd = output_dir / REGISTER_FILES["week2_dd"]
    wow_dd = output_dir / REGISTER_FILES["wow_dd"]
    write_register_csv(dd_w1_df, w1_dd)
    write_register_csv(dd_w2_df, w2_dd)
    build_wow_register_csv(w1_dd, w2_dd, wow_dd)

    result["register_files"].update(
        {
            "week1_dd_register": str(w1_dd),
            "week2_dd_register": str(w2_dd),
            "wow_dd_register": str(wow_dd),
        }
    )

    # Uber Eats — from UE weekly CSVs when provided, else zero grid (DD store IDs)
    if ue_week1_csv and ue_week1_csv.is_file() and ue_week2_csv and ue_week2_csv.is_file():
        ue_w1_df = weekly_csv_to_register_df(ue_week1_csv, week_label=week1_label)
        ue_w2_df = weekly_csv_to_register_df(ue_week2_csv, week_label=week2_label)
        result["platform"] = "dd+ue"
    else:
        ue_w1_df = empty_ue_register_df(store_ids, week_label=week1_label)
        ue_w2_df = empty_ue_register_df(store_ids, week_label=week2_label)

    w1_ue = output_dir / REGISTER_FILES["week1_ue"]
    w2_ue = output_dir / REGISTER_FILES["week2_ue"]
    wow_ue = output_dir / REGISTER_FILES["wow_ue"]
    write_register_csv(ue_w1_df, w1_ue)
    write_register_csv(ue_w2_df, w2_ue)
    build_wow_register_csv(w1_ue, w2_ue, wow_ue)

    result["register_files"].update(
        {
            "week1_ue_register": str(w1_ue),
            "week2_ue_register": str(w2_ue),
            "wow_ue_register": str(wow_ue),
        }
    )

    labels = {"week1": week1_label, "week2": week2_label}
    dd_analysis = compare_register_slots(
        register_df_to_analysis_rows(dd_w1_df),
        register_df_to_analysis_rows(dd_w2_df),
        labels=labels,
    )
    ue_analysis = compare_register_slots(
        register_df_to_analysis_rows(ue_w1_df),
        register_df_to_analysis_rows(ue_w2_df),
        labels=labels,
    )

    campaign_wow = campaign_wow_files or {}
    promo_wow = campaign_wow.get("wow_campaigns_promo")
    ads_wow = campaign_wow.get("wow_campaigns_ads")
    if promo_wow:
        result["register_files"]["wow_campaigns_promo"] = promo_wow
    if ads_wow:
        result["register_files"]["wow_campaigns_ads"] = ads_wow
    if campaign_wow.get("wow_campaigns"):
        result["register_files"]["wow_campaigns"] = campaign_wow["wow_campaigns"]
    if campaign_wow.get("wow_campaigns_by_name"):
        result["register_files"]["wow_campaigns_by_name"] = campaign_wow["wow_campaigns_by_name"]

    campaigns_html = campaign_wow_for_html(
        Path(promo_wow) if promo_wow else None,
        Path(ads_wow) if ads_wow else None,
    )

    html_path = build_register_wow_report_html(
        dd_analysis,
        ue_analysis=ue_analysis,
        output_path=output_dir / REGISTER_FILES["html"],
        title_suffix=operator_name,
        ue_has_data=result["platform"] == "dd+ue",
        campaigns_analysis=campaigns_html if campaigns_html.get("promo") or campaigns_html.get("ads") else None,
    )
    if html_path:
        legacy = output_dir / REGISTER_FILES["html_legacy"]
        legacy.write_text(Path(html_path).read_text(encoding="utf-8"), encoding="utf-8")
        result["wow_viz_html"] = str(legacy)
        result["register_wow_html"] = str(html_path)

    html_url: Optional[str] = None
    if html_path:
        html_url = resolve_healthcheck_html_url(Path(html_path), operator_name=operator_name)
        if html_url:
            result["html_report_url"] = html_url

    pdf_path: Optional[Path] = None
    pdf_url: Optional[str] = None
    if html_path:
        pdf_path = html_to_pdf(Path(html_path), output_dir / REGISTER_FILES["pdf"])
        if pdf_path:
            result["register_files"]["pdf"] = str(pdf_path)
            upload = upload_file_to_drive(
                pdf_path,
                subfolder_name=f"healthcheck_{operator_name[:40]}",
                file_name=f"{operator_name}_register_wow.pdf",
                mimetype="application/pdf",
            )
            if upload:
                pdf_url = upload.get("webViewLink") or None
                result["pdf_drive_url"] = pdf_url
                result["pdf_drive_file_id"] = upload.get("file_id")

    slack_text = build_slack_summary(
        dd_analysis,
        title=operator_name,
        pdf_url=pdf_url,
        html_url=html_url,
    )
    if ue_analysis.get("slotCount") and result["platform"] == "dd+ue":
        slack_text += "\n\n*Uber Eats*\n" + build_slack_summary(
            ue_analysis,
            title=operator_name,
            html_url=html_url,
        )
    elif not slack_text:
        slack_text = build_wow_slack_message(
            week1_weekly_csv,
            week2_weekly_csv,
            week1_label=week1_label,
            week2_label=week2_label,
            title=operator_name,
        )
    campaign_slack = build_campaign_slack_summary(
        promo_wow_csv=Path(promo_wow) if promo_wow else None,
        ads_wow_csv=Path(ads_wow) if ads_wow else None,
        week1_label=week1_label,
        week2_label=week2_label,
        operator_name=operator_name,
    )
    if campaign_slack and (promo_wow or ads_wow):
        slack_notify(campaign_slack)
        result["campaign_slack_sent"] = True

    if slack_text:
        slack_notify(slack_text)
        result["wow_slack_sent"] = True

    return result
