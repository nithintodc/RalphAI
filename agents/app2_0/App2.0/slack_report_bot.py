#!/usr/bin/env python3
"""
Slack /report bot for App2.0-cloud-app.

Flow:
1) User runs /report → modal asks Pre period, Post period, optional operator name.
2) On submit, bot posts instructions to upload in the channel:
   - dd-data.csv
   - ue-data.csv
   - marketing.zip (contains marketing_* folders with marketing CSVs)
3) When all three are received, bot runs the App2.0 report and uploads the Excel to the channel.

Slack app: enable Socket Mode; subscribe to the `file_shared` event; scopes need files:read (and chat:write, files:write).
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

try:
    # Fix SSL verification issues in Python environments that don't have a proper CA bundle configured.
    import certifi  # type: ignore

    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except Exception:
    pass

try:
    # Optional dependency; if not installed, we can still rely on environment variables.
    from dotenv import load_dotenv  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]


def _parse_date_range(date_range: str) -> tuple[str, str]:
    """
    Accept a range like "MM/DD/YYYY-MM/DD/YYYY" (extra whitespace/characters tolerated).
    Returns normalized ("MM/DD/YYYY", "MM/DD/YYYY").
    """
    if not date_range or not str(date_range).strip():
        raise ValueError("Invalid date range format. Expected MM/DD/YYYY-MM/DD/YYYY")
    s = str(date_range).strip()
    # Extract two dates; avoids stray trailing characters from Slack/mobile clients.
    m = re.search(
        r"(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})",
        s,
    )
    if not m:
        raise ValueError("Invalid date range format. Expected MM/DD/YYYY-MM/DD/YYYY")
    start, end = m.group(1).strip(), m.group(2).strip()
    start_dt = datetime.strptime(start, "%m/%d/%Y")
    end_dt = datetime.strptime(end, "%m/%d/%Y")
    if start_dt > end_dt:
        raise ValueError("Start date must be <= end date")

    return start_dt.strftime("%m/%d/%Y"), end_dt.strftime("%m/%d/%Y")


def _parse_excluded_dates(excluded_dates_text: str) -> list[datetime.date]:
    """
    Accept "MM/DD/YYYY, MM/DD/YYYY" and return list[date].
    """
    if not excluded_dates_text or not excluded_dates_text.strip():
        return []

    dates: list[datetime.date] = []
    parts = [p.strip() for p in excluded_dates_text.split(",") if p.strip()]
    for p in parts:
        dt = datetime.strptime(p, "%m/%d/%Y")
        dates.append(dt.date())
    return dates


def _parse_store_ids(store_ids_text: str) -> list[str]:
    if not store_ids_text or not store_ids_text.strip():
        return []
    # Treat store ids as strings to avoid numeric vs string mismatches.
    return [s.strip() for s in store_ids_text.split(",") if s.strip()]


def _marketing_subdirs(p: Path) -> list[Path]:
    if not p.is_dir():
        return []
    return sorted(
        x for x in p.iterdir() if x.is_dir() and x.name.startswith("marketing_")
    )


def _resolve_marketing_folder(base: Path) -> Path:
    """
    Prefer `base` if it contains marketing_* dirs; else a direct child subfolder that does
    (supports zips that wrap files one level deep).
    """
    if _marketing_subdirs(base):
        return base
    for child in sorted(base.iterdir()):
        if child.is_dir() and _marketing_subdirs(child):
            return child
    return base


def _download_slack_file_to_path(url: str, dest: Path) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN missing for file download")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310 — Slack private URL
        dest.write_bytes(resp.read())


_pending_lock = threading.Lock()
# user_id -> pending upload session (see main() for keys)
_pending_uploads: dict[str, dict[str, Any]] = {}


class _SessionState(dict):
    """
    A minimal replacement for Streamlit's session_state that supports:
    - dict style access (get, in, ...)
    - attribute style access (st.session_state.foo = ...)
    """

    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item) from None

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


def _build_dummy_streamlit_module() -> Any:
    """
    Build a lightweight dummy `streamlit` module so the App2.0 functions can run outside `streamlit run app.py`.
    """
    import types
    from contextlib import contextmanager

    dummy = types.SimpleNamespace()

    dummy.session_state = _SessionState()
    dummy.secrets = {}

    def _no_op(*_args: Any, **_kwargs: Any) -> None:
        return None

    dummy.error = _no_op
    dummy.warning = _no_op
    dummy.success = _no_op
    dummy.info = _no_op
    dummy.markdown = _no_op
    dummy.write = _no_op

    def cache_data_decorator(func=None, **_kwargs):  # type: ignore[no-untyped-def]
        """
        Streamlit's `@st.cache_data` becomes a no-op when running outside Streamlit.
        """
        if func is None:
            return lambda f: f
        return func

    dummy.cache_data = cache_data_decorator

    @contextmanager
    def spinner(_text: str):  # type: ignore[no-untyped-def]
        yield

    dummy.spinner = spinner

    # Provide placeholders if any code path calls these.
    dummy.set_page_config = _no_op
    dummy.sidebar = types.SimpleNamespace()  # not used by our runner
    dummy.expander = lambda *_args, **_kwargs: types.SimpleNamespace(__enter__=lambda s: s, __exit__=lambda *_: False)  # type: ignore[attr-defined]
    dummy.multiselect = lambda *_args, **_kwargs: []  # type: ignore[attr-defined]
    dummy.button = lambda *_args, **_kwargs: False  # type: ignore[attr-defined]
    dummy.rerun = _no_op

    return dummy


# IMPORTANT: Keep one dummy `streamlit` instance across multiple report runs.
# The App2.0 modules cache `import streamlit as st` at import time, so if we swap the dummy object
# after the first import, App2.0 code may keep using the old instance.
_STREAMLIT_DUMMY: Optional[Any] = None


def _unique_sorted_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        s = "" if v is None else str(v)
        if not s:
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return sorted(out)


@dataclass(frozen=True)
class ReportInputs:
    pre_range: str
    post_range: str
    excluded_dates_text: str
    operator_name: str
    dd_store_ids_text: str
    ue_store_ids_text: str


def generate_app2_report_excel(
    app_dir: Path,
    inputs: ReportInputs,
    *,
    data_root: Optional[Path] = None,
) -> tuple[bytes, str, str]:
    """
    Returns: (file_bytes, filename, short_summary_text)
    """
    global _STREAMLIT_DUMMY

    # Step 1: install dummy streamlit before importing App2.0 modules.
    # We keep the same dummy object for the lifetime of this process.
    if _STREAMLIT_DUMMY is None:
        _STREAMLIT_DUMMY = _build_dummy_streamlit_module()
    dummy_streamlit = _STREAMLIT_DUMMY

    # Reset state for each report run.
    dummy_streamlit.session_state = _SessionState()
    sys.modules["streamlit"] = dummy_streamlit  # type: ignore[assignment]

    # Ensure App2.0 modules are importable by their plain module names.
    sys.path.insert(0, str(app_dir))

    try:
        import importlib

        config = importlib.import_module("config")
        data_loading = importlib.import_module("data_loading")
        data_processing = importlib.import_module("data_processing")
        marketing_analysis = importlib.import_module("marketing_analysis")
        table_generation = importlib.import_module("table_generation")
        export_functions = importlib.import_module("export_functions")

        slot_analysis = None
        try:
            slot_analysis = importlib.import_module("slot_analysis")
        except Exception:
            slot_analysis = None

        export_to_excel = getattr(export_functions, "export_to_excel")

        # Step 2: parse inputs.
        pre_start, pre_end = _parse_date_range(inputs.pre_range)
        post_start, post_end = _parse_date_range(inputs.post_range)
        excluded_dates = _parse_excluded_dates(inputs.excluded_dates_text)
        operator_name = inputs.operator_name.strip() or None

        root = data_root if data_root is not None else Path(config.ROOT_DIR)
        dd_data_path = root / "dd-data.csv"
        ue_data_path = root / "ue-data.csv"

        if not dd_data_path.exists():
            raise FileNotFoundError(f"Missing DoorDash master file: {dd_data_path}")
        if not ue_data_path.exists():
            raise FileNotFoundError(f"Missing UberEats master file: {ue_data_path}")

        marketing_folder_path = _resolve_marketing_folder(root)

        # Step 3: load + aggregate data (DoorDash + UberEats).
        (
            ue_pre_24_sales,
            ue_pre_24_payouts,
            ue_pre_24_orders,
            ue_post_24_sales,
            ue_post_24_payouts,
            ue_post_24_orders,
            ue_pre_25_sales,
            ue_pre_25_payouts,
            ue_pre_25_orders,
            ue_post_25_sales,
            ue_post_25_payouts,
            ue_post_25_orders,
        ) = data_processing.load_and_aggregate_ue_data(
            excluded_dates=excluded_dates,
            pre_start_date=pre_start,
            pre_end_date=pre_end,
            post_start_date=post_start,
            post_end_date=post_end,
            ue_data_path=ue_data_path,
        )

        ue_sales_df, ue_payouts_df, ue_orders_df = data_processing.process_data(
            ue_pre_24_sales,
            ue_pre_24_payouts,
            ue_pre_24_orders,
            ue_post_24_sales,
            ue_post_24_payouts,
            ue_post_24_orders,
            ue_pre_25_sales,
            ue_pre_25_payouts,
            ue_pre_25_orders,
            ue_post_25_sales,
            ue_post_25_payouts,
            ue_post_25_orders,
        )

        (
            dd_pre_24_sales,
            dd_pre_24_payouts,
            dd_pre_24_orders,
            dd_post_24_sales,
            dd_post_24_payouts,
            dd_post_24_orders,
            dd_pre_25_sales,
            dd_pre_25_payouts,
            dd_pre_25_orders,
            dd_post_25_sales,
            dd_post_25_payouts,
            dd_post_25_orders,
        ) = data_processing.load_and_aggregate_dd_data(
            excluded_dates=excluded_dates,
            pre_start_date=pre_start,
            pre_end_date=pre_end,
            post_start_date=post_start,
            post_end_date=post_end,
            dd_data_path=dd_data_path,
        )

        dd_sales_df, dd_payouts_df, dd_orders_df = data_processing.process_data(
            dd_pre_24_sales,
            dd_pre_24_payouts,
            dd_pre_24_orders,
            dd_post_24_sales,
            dd_post_24_payouts,
            dd_post_24_orders,
            dd_pre_25_sales,
            dd_pre_25_payouts,
            dd_pre_25_orders,
            dd_post_25_sales,
            dd_post_25_payouts,
            dd_post_25_orders,
        )

        # Step 4: new customers (DoorDash derived from marketing promotion files).
        (
            dd_pre_24_nc,
            dd_post_24_nc,
            dd_pre_25_nc,
            dd_post_25_nc,
            ue_pre_24_total,
            ue_post_24_total,
            ue_pre_25_total,
            ue_post_25_total,
        ) = data_processing.load_and_aggregate_new_customers(
            excluded_dates=excluded_dates,
            pre_start_date=pre_start,
            pre_end_date=pre_end,
            post_start_date=post_start,
            post_end_date=post_end,
            marketing_folder_path=marketing_folder_path,
        )

        dd_new_customers_df = data_processing.process_new_customers_data(
            dd_pre_24_nc,
            dd_post_24_nc,
            dd_pre_25_nc,
            dd_post_25_nc,
            is_ue=False,
        )

        ue_new_customers_df = data_processing.pd.DataFrame(  # type: ignore[attr-defined]
            columns=["Store ID", "pre_24", "post_24", "pre_25", "post_25", "PrevsPost", "LastYear_Pre_vs_Post", "YoY"]
        )

        # Streamlit session state values required by create_summary_tables for UE new customers.
        dummy_streamlit.session_state["ue_new_customers_totals"] = {
            "pre_24": ue_pre_24_total,
            "post_24": ue_post_24_total,
            "pre_25": ue_pre_25_total,
            "post_25": ue_post_25_total,
        }

        # Step 5: normalize Store IDs to strings (prevents numeric vs string mismatches).
        for df in (dd_sales_df, dd_payouts_df, dd_orders_df, dd_new_customers_df, ue_sales_df, ue_payouts_df, ue_orders_df):
            if df is not None and not df.empty and "Store ID" in df.columns:
                df["Store ID"] = df["Store ID"].astype(str)

        # Step 6: determine which stores to include.
        dd_selected_stores = _parse_store_ids(inputs.dd_store_ids_text)
        ue_selected_stores = _parse_store_ids(inputs.ue_store_ids_text)
        if not dd_selected_stores:
            dd_selected_stores = _unique_sorted_strings(dd_sales_df["Store ID"].unique().tolist()) if not dd_sales_df.empty else []
        if not ue_selected_stores:
            ue_selected_stores = _unique_sorted_strings(ue_sales_df["Store ID"].unique().tolist()) if not ue_sales_df.empty else []

        dummy_streamlit.session_state["selected_stores_DoorDash"] = dd_selected_stores
        dummy_streamlit.session_state["selected_stores_UberEats"] = ue_selected_stores

        # Step 7: build tables required by export_to_excel.
        dd_table1, dd_table2 = (
            table_generation.get_platform_store_tables(dd_sales_df, "selected_stores_DoorDash")
            if not dd_sales_df.empty
            else (None, None)
        )
        ue_table1, ue_table2 = (
            table_generation.get_platform_store_tables(ue_sales_df, "selected_stores_UberEats")
            if not ue_sales_df.empty
            else (None, None)
        )

        dd_summary1, dd_summary2 = (
            table_generation.get_platform_summary_tables(
                dd_sales_df, dd_payouts_df, dd_orders_df, dd_new_customers_df, "selected_stores_DoorDash", is_ue=False
            )
            if not dd_sales_df.empty
            else (None, None)
        )
        ue_summary1, ue_summary2 = (
            table_generation.get_platform_summary_tables(
                ue_sales_df, ue_payouts_df, ue_orders_df, ue_new_customers_df, "selected_stores_UberEats", is_ue=True
            )
            if not ue_sales_df.empty
            else (None, None)
        )

        combined_summary1, combined_summary2 = table_generation.create_combined_summary_tables(
            dd_sales_df,
            dd_payouts_df,
            dd_orders_df,
            dd_new_customers_df,
            ue_sales_df,
            ue_payouts_df,
            ue_orders_df,
            ue_new_customers_df,
            dd_selected_stores,
            ue_selected_stores,
        )
        combined_store_table1, combined_store_table2 = table_generation.create_combined_store_tables(
            dd_table1, dd_table2, ue_table1, ue_table2
        )

        # Corporate vs TODC marketing tables (optional but supported).
        promotion_table, sponsored_table, corporate_todc_table = marketing_analysis.create_corporate_vs_todc_table(
            excluded_dates=excluded_dates,
            pre_start_date=pre_start,
            pre_end_date=pre_end,
            post_start_date=post_start,
            post_end_date=post_end,
            marketing_folder_path=marketing_folder_path,
        )

        # Step 8: optional slot analysis. If it fails, we proceed without it.
        sales_pre_post_table = None
        sales_yoy_table = None
        payouts_pre_post_table = None
        payouts_yoy_table = None
        if slot_analysis is not None:
            try:
                (
                    sales_pre_post_table,
                    sales_yoy_table,
                    payouts_pre_post_table,
                    payouts_yoy_table,
                ) = slot_analysis.process_slot_analysis(
                    dd_data_path,
                    pre_start_date=pre_start,
                    pre_end_date=pre_end,
                    post_start_date=post_start,
                    post_end_date=post_end,
                    excluded_dates=excluded_dates,
                )
            except Exception:
                # Slot analysis is non-critical; keep report generation resilient.
                sales_pre_post_table = None
                sales_yoy_table = None
                payouts_pre_post_table = None
                payouts_yoy_table = None

        file_bytes, filename = export_to_excel(
            dd_table1,
            dd_table2,
            ue_table1,
            ue_table2,
            dd_sales_df,
            dd_payouts_df,
            dd_orders_df,
            dd_new_customers_df,
            ue_sales_df,
            ue_payouts_df,
            ue_orders_df,
            ue_new_customers_df,
            dd_selected_stores,
            ue_selected_stores,
            combined_summary1,
            combined_summary2,
            combined_store_table1,
            combined_store_table2,
            corporate_todc_table=corporate_todc_table,
            promotion_table=promotion_table,
            sponsored_table=sponsored_table,
            summary_metrics_table=None,
            store_ids_markups_table=None,
            operator_name=operator_name,
            sales_pre_post_table=sales_pre_post_table,
            sales_yoy_table=sales_yoy_table,
            payouts_pre_post_table=payouts_pre_post_table,
            payouts_yoy_table=payouts_yoy_table,
        )

        # Step 9: generate a short summary for the Slack message (not the full spreadsheet).
        try:
            sales_pre = combined_summary1.loc["Sales", "Pre"] if combined_summary1 is not None else None
            sales_post = combined_summary1.loc["Sales", "Post"] if combined_summary1 is not None else None
            growth_pct = combined_summary1.loc["Sales", "Growth%"] if combined_summary1 is not None else None
            summary_text = (
                f"TODC report ready for operator: {operator_name or 'default'} | "
                f"Sales Pre: {sales_pre} | Sales Post: {sales_post} | Growth: {growth_pct}%"
            )
        except Exception:
            summary_text = "TODC report ready."

        return file_bytes, filename, summary_text
    finally:
        # Remove the inserted app_dir from sys.path.
        try:
            sys.path.remove(str(app_dir))
        except ValueError:
            pass


def _start_background_report_job(
    client: Any,
    channel_id: str,
    user_id: str,
    app_dir: Path,
    inputs: ReportInputs,
    *,
    data_root: Optional[Path] = None,
    cleanup_dir: Optional[Path] = None,
) -> None:
    def _work() -> None:
        try:
            file_bytes, filename, summary_text = generate_app2_report_excel(
                app_dir=app_dir,
                inputs=inputs,
                data_root=data_root,
            )

            # Upload Excel to Slack.
            file_io = io.BytesIO(file_bytes)
            file_io.name = filename

            client.files_upload(
                channels=channel_id,
                file=file_io,
                filename=filename,
                title=filename,
                initial_comment=summary_text,
            )
        except Exception as e:
            msg = str(e)
            if "Missing DoorDash master file" in msg or "Missing UberEats master file" in msg:
                msg = (
                    "Missing required data files. "
                    "Upload `dd-data.csv` and `ue-data.csv` (and `marketing.zip`) after submitting the form."
                )
            client.chat_postMessage(
                channel=channel_id,
                text=f"Failed to generate report for <@{user_id}>: {msg}",
            )
        finally:
            if cleanup_dir is not None:
                try:
                    shutil.rmtree(cleanup_dir, ignore_errors=True)
                except Exception:
                    pass

    threading.Thread(target=_work, daemon=True).start()


def create_slack_app() -> App:
    if load_dotenv is not None:
        load_dotenv()
    bot_token = os.environ.get("SLACK_BOT_TOKEN")
    app_token = os.environ.get("SLACK_APP_TOKEN")
    if not bot_token:
        raise RuntimeError("Missing SLACK_BOT_TOKEN in environment/.env")
    if not app_token:
        raise RuntimeError("Missing SLACK_APP_TOKEN in environment/.env")

    # Socket Mode does not require SLACK_SIGNING_SECRET.
    slack_app = App(token=bot_token)
    return slack_app


def main() -> None:
    slack_app = create_slack_app()

    app_dir = Path(os.environ.get("TODC_APP2_DIR", Path(__file__).resolve().parent)).resolve()
    app_token = os.environ.get("SLACK_APP_TOKEN", "").strip()

    @slack_app.command("/report")
    def report_command(ack, body, client, respond, logger):  # type: ignore[no-untyped-def]
        ack()

        trigger_id = body.get("trigger_id")
        channel_id = body.get("channel_id")
        user_id = body.get("user_id")
        if not trigger_id or not channel_id:
            respond("Missing required Slack fields for /report.")
            return

        modal_view = {
            "type": "modal",
            "callback_id": "todc_report_view",
            "private_metadata": json.dumps({"channel_id": channel_id, "user_id": user_id}),
            "title": {"type": "plain_text", "text": "TODC Report"},
            "submit": {"type": "plain_text", "text": "Next"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": [
                {
                    "type": "input",
                    "block_id": "pre",
                    "label": {"type": "plain_text", "text": "Pre Period (MM/DD/YYYY-MM/DD/YYYY)"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value",
                        "placeholder": {"type": "plain_text", "text": "11/1/2025-11/30/2025"},
                    },
                },
                {
                    "type": "input",
                    "block_id": "post",
                    "label": {"type": "plain_text", "text": "Post Period (MM/DD/YYYY-MM/DD/YYYY)"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value",
                        "placeholder": {"type": "plain_text", "text": "12/1/2025-12/31/2025"},
                    },
                },
                {
                    "type": "input",
                    "block_id": "operator",
                    "optional": True,
                    "label": {"type": "plain_text", "text": "Operator Name (optional)"},
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "value",
                        "placeholder": {"type": "plain_text", "text": "alpha"},
                    },
                },
            ],
        }

        client.views_open(trigger_id=trigger_id, view=modal_view)

    @slack_app.view("todc_report_view")
    def report_view_submission(ack, body, client, logger):  # type: ignore[no-untyped-def]
        ack()

        private_metadata_raw = body.get("view", {}).get("private_metadata", "{}")
        try:
            private_metadata = json.loads(private_metadata_raw)
        except json.JSONDecodeError:
            private_metadata = {}

        channel_id = private_metadata.get("channel_id")
        user_id = private_metadata.get("user_id", "")
        if not channel_id:
            return

        state_values = body.get("view", {}).get("state", {}).get("values", {})

        def _get(block_id: str) -> str:
            return (
                state_values.get(block_id, {})
                .get("value", {})
                .get("value", "")
            )

        inputs = ReportInputs(
            pre_range=_get("pre"),
            post_range=_get("post"),
            excluded_dates_text="",
            operator_name=_get("operator"),
            dd_store_ids_text="",
            ue_store_ids_text="",
        )

        try:
            _parse_date_range(inputs.pre_range)
            _parse_date_range(inputs.post_range)
        except ValueError as e:
            client.chat_postMessage(
                channel=channel_id,
                text=f"<@{user_id}> Invalid date range: {e}",
            )
            return

        work_dir = Path(tempfile.mkdtemp(prefix="todc_slack_"))

        with _pending_lock:
            prev = _pending_uploads.get(user_id)
            if prev:
                try:
                    shutil.rmtree(prev["work_dir"], ignore_errors=True)
                except Exception:
                    pass
            _pending_uploads[user_id] = {
                "channel_id": channel_id,
                "inputs": inputs,
                "work_dir": work_dir,
                "has_dd": False,
                "has_ue": False,
                "has_mkt": False,
            }

        client.chat_postMessage(
            channel=channel_id,
            text=(
                f"<@{user_id}> Step 2: Upload in this channel with these exact filenames:\n"
                "• dd-data.csv\n"
                "• ue-data.csv\n"
                "• marketing.zip (zip containing marketing_* folders with the marketing CSVs)\n\n"
                "When all three are received, the bot runs the report and posts the Excel here."
            ),
        )

    @slack_app.event("file_shared")
    def on_file_shared(event, client, logger):  # type: ignore[no-untyped-def]
        user_id = event.get("user_id")
        file_id = event.get("file_id")
        if not user_id or not file_id:
            return

        with _pending_lock:
            sess = _pending_uploads.get(user_id)
            if not sess:
                return
            channel_id = sess["channel_id"]
            work_dir: Path = sess["work_dir"]

        name_raw = ""
        name = ""
        try:
            info = client.files_info(file=file_id)
            file_obj = info.get("file") or {}
            name_raw = (file_obj.get("name") or "").strip()
            name = name_raw.lower()
            if name not in ("dd-data.csv", "ue-data.csv", "marketing.zip"):
                return

            url = file_obj.get("url_private_download") or file_obj.get("url_private")
            if not url:
                client.chat_postMessage(
                    channel=channel_id,
                    text=f"<@{user_id}> Could not get a download URL for `{name_raw}`. Check bot scopes (`files:read`).",
                )
                return

            if name == "marketing.zip":
                zip_path = work_dir / "marketing.upload.zip"
                _download_slack_file_to_path(url, zip_path)
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(work_dir)
                zip_path.unlink(missing_ok=True)
            else:
                dest = work_dir / name
                _download_slack_file_to_path(url, dest)

        except Exception as e:
            logger.exception("file_shared handling failed")
            client.chat_postMessage(
                channel=channel_id,
                text=f"<@{user_id}> Error receiving `{name_raw or 'file'}`: {e}",
            )
            return

        msgs: list[str] = []
        ready = False
        data_to_run: Optional[dict[str, Any]] = None

        with _pending_lock:
            sess = _pending_uploads.get(user_id)
            if not sess:
                return
            wdir: Path = sess["work_dir"]
            if wdir != work_dir:
                return

            if name == "dd-data.csv":
                sess["has_dd"] = True
            elif name == "ue-data.csv":
                sess["has_ue"] = True
            elif name == "marketing.zip":
                sess["has_mkt"] = bool(_marketing_subdirs(_resolve_marketing_folder(wdir)))

            label = {"dd-data.csv": "dd-data.csv", "ue-data.csv": "ue-data.csv", "marketing.zip": "marketing.zip"}[name]

            if name == "marketing.zip" and not sess["has_mkt"]:
                msgs.append(
                    f"<@{user_id}> `{label}` was unpacked but no `marketing_*` folders were found. "
                    "Put `marketing_*` folders at the top level of the zip (or one folder deep). "
                    "Upload a fixed `marketing.zip` again."
                )
            else:
                got = int(sess["has_dd"]) + int(sess["has_ue"]) + int(sess["has_mkt"])
                msgs.append(f"<@{user_id}> Received `{label}` ({got}/3).")

            if sess["has_dd"] and sess["has_ue"] and sess["has_mkt"]:
                data_to_run = _pending_uploads.pop(user_id, None)
                ready = data_to_run is not None

        for m in msgs:
            client.chat_postMessage(channel=channel_id, text=m)

        if ready and data_to_run:
            client.chat_postMessage(
                channel=channel_id,
                text=f"<@{user_id}> All files received. Running report (may take a few minutes)...",
            )
            _start_background_report_job(
                client=client,
                channel_id=data_to_run["channel_id"],
                user_id=user_id,
                app_dir=app_dir,
                inputs=data_to_run["inputs"],
                data_root=data_to_run["work_dir"],
                cleanup_dir=data_to_run["work_dir"],
            )

    print(f"Slack TODC report bot running in Socket Mode (App dir: {app_dir})")
    SocketModeHandler(slack_app, app_token).start()


if __name__ == "__main__":
    main()

