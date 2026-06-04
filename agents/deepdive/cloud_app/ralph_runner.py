"""
Headless runner for App2.0 analytics (ported Streamlit app) — used by RalphAI API + dashboard.
Installs a dummy `streamlit` module before importing cloud_app modules (Streamlit UI depends on `st` at import time).
"""

from __future__ import annotations

import importlib
import math
import re
import sys
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

_STREAMLIT_DUMMY: Any | None = None
_REPORT_LOCK = threading.RLock()


def _parse_date_range(date_range: str) -> tuple[str, str]:
    if not date_range or not str(date_range).strip():
        raise ValueError("Invalid date range format. Expected MM/DD/YYYY-MM/DD/YYYY")
    s = str(date_range).strip()
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


def _parse_excluded_dates(excluded_dates_text: str) -> list:
    if not excluded_dates_text or not excluded_dates_text.strip():
        return []
    dates = []
    for p in [x.strip() for x in excluded_dates_text.split(",") if x.strip()]:
        dt = datetime.strptime(p, "%m/%d/%Y")
        dates.append(dt.date())
    return dates


def _parse_store_ids(store_ids_text: str) -> list[str]:
    if not store_ids_text or not store_ids_text.strip():
        return []
    return [s.strip() for s in store_ids_text.split(",") if s.strip()]


def _marketing_subdirs(p: Path) -> list[Path]:
    if not p.is_dir():
        return []
    return sorted(x for x in p.iterdir() if x.is_dir() and x.name.startswith("marketing_"))


def _resolve_marketing_folder(base: Path) -> Path:
    if _marketing_subdirs(base):
        return base
    for child in sorted(base.iterdir()):
        if child.is_dir() and _marketing_subdirs(child):
            return child
    return base


class _SessionState(dict):
    def __getattr__(self, item: str) -> Any:
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item) from None

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


def _build_dummy_streamlit_module() -> Any:
    import types
    from contextlib import contextmanager

    dummy = types.SimpleNamespace()
    dummy.session_state = _SessionState()
    dummy.secrets = {}

    def _no_op(*_a: Any, **_k: Any) -> None:
        return None

    dummy.error = _no_op
    dummy.warning = _no_op
    dummy.success = _no_op
    dummy.info = _no_op
    dummy.markdown = _no_op
    dummy.write = _no_op
    dummy.code = _no_op

    def cache_data_decorator(func=None, **_kwargs):  # type: ignore[no-untyped-def]
        if func is None:
            return lambda f: f
        return func

    dummy.cache_data = cache_data_decorator

    @contextmanager
    def spinner(_text: str):  # type: ignore[no-untyped-def]
        yield

    dummy.spinner = spinner
    dummy.set_page_config = _no_op
    dummy.sidebar = types.SimpleNamespace()
    dummy.expander = lambda *_a, **_k: types.SimpleNamespace(
        __enter__=lambda s: s, __exit__=lambda *_: False
    )
    dummy.multiselect = lambda *_a, **_k: []
    dummy.button = lambda *_a, **_k: False
    dummy.rerun = _no_op
    return dummy


def _unique_sorted_strings(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        s = "" if v is None else str(v)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return sorted(out)


def _df_to_records(df: Any, max_rows: int = 400) -> dict[str, Any]:
    import pandas as pd

    if df is None or (hasattr(df, "empty") and df.empty):
        return {"columns": [], "rows": []}
    d = df.reset_index()
    if len(d) > max_rows:
        d = d.head(max_rows)
    cols = [str(c) for c in d.columns]
    rows: list[dict[str, Any]] = []
    for _, row in d.iterrows():
        rec: dict[str, Any] = {}
        for c in d.columns:
            v = row[c]
            if pd.isna(v):
                rec[str(c)] = None
            elif isinstance(v, (float, int)) and isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                rec[str(c)] = None
            else:
                rec[str(c)] = v.item() if hasattr(v, "item") else v
        rows.append(rec)
    return {"columns": cols, "rows": rows}


@dataclass(frozen=True)
class ReportInputs:
    pre_range: str
    post_range: str
    excluded_dates_text: str
    operator_name: str
    dd_store_ids_text: str
    ue_store_ids_text: str


def cloud_app_dir() -> Path:
    return Path(__file__).resolve().parent


def generate_monthly_report_bundle(
    inputs: ReportInputs,
    *,
    data_root: Path,
) -> dict[str, Any]:
    with _REPORT_LOCK:
        return _generate_monthly_report_bundle_unlocked(inputs, data_root=data_root)


def _generate_monthly_report_bundle_unlocked(
    inputs: ReportInputs,
    *,
    data_root: Path,
) -> dict[str, Any]:
    """
    Run full App2.0 Excel export + optional date export + JSON-serializable table previews.

    Returns keys: excel_bytes, filename, summary_text, tables, date_export_bytes, date_export_filename (optional).
    """
    global _STREAMLIT_DUMMY

    if _STREAMLIT_DUMMY is None:
        _STREAMLIT_DUMMY = _build_dummy_streamlit_module()
    dummy_streamlit = _STREAMLIT_DUMMY
    dummy_streamlit.session_state = _SessionState()
    sys.modules["streamlit"] = dummy_streamlit  # type: ignore[assignment]

    app_dir = cloud_app_dir()
    sys.path.insert(0, str(app_dir))

    try:
        config = importlib.import_module("config")
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
        create_date_export_from_master_files = getattr(
            export_functions, "create_date_export_from_master_files", None
        )
        build_financial_summary_table = getattr(
            export_functions, "build_financial_summary_table", None
        )
        create_bucketing_export = getattr(
            export_functions, "create_bucketing_export", None
        )

        pre_start, pre_end = _parse_date_range(inputs.pre_range)
        post_start, post_end = _parse_date_range(inputs.post_range)
        excluded_dates = _parse_excluded_dates(inputs.excluded_dates_text)
        operator_name = inputs.operator_name.strip() or None

        root = data_root
        # Standard names under work dir; missing files behave like Streamlit (empty aggregates).
        dd_data_path = root / "dd-data.csv"
        ue_data_path = root / "ue-data.csv"

        marketing_folder_path = _resolve_marketing_folder(root)

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

        ue_new_customers_df = data_processing.pd.DataFrame(
            columns=[
                "Store ID",
                "pre_24",
                "post_24",
                "pre_25",
                "post_25",
                "PrevsPost",
                "LastYear_Pre_vs_Post",
                "YoY",
            ]
        )

        dummy_streamlit.session_state["ue_new_customers_totals"] = {
            "pre_24": ue_pre_24_total,
            "post_24": ue_post_24_total,
            "pre_25": ue_pre_25_total,
            "post_25": ue_post_25_total,
        }

        for df in (
            dd_sales_df,
            dd_payouts_df,
            dd_orders_df,
            dd_new_customers_df,
            ue_sales_df,
            ue_payouts_df,
            ue_orders_df,
        ):
            if df is not None and not df.empty and "Store ID" in df.columns:
                df["Store ID"] = df["Store ID"].astype(str)

        dd_selected_stores = _parse_store_ids(inputs.dd_store_ids_text)
        ue_selected_stores = _parse_store_ids(inputs.ue_store_ids_text)
        if not dd_selected_stores:
            dd_selected_stores = (
                _unique_sorted_strings(dd_sales_df["Store ID"].unique().tolist())
                if not dd_sales_df.empty
                else []
            )
        if not ue_selected_stores:
            ue_selected_stores = (
                _unique_sorted_strings(ue_sales_df["Store ID"].unique().tolist())
                if not ue_sales_df.empty
                else []
            )

        dummy_streamlit.session_state["selected_stores_DoorDash"] = dd_selected_stores
        dummy_streamlit.session_state["selected_stores_UberEats"] = ue_selected_stores

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
                dd_sales_df,
                dd_payouts_df,
                dd_orders_df,
                dd_new_customers_df,
                "selected_stores_DoorDash",
                is_ue=False,
            )
            if not dd_sales_df.empty
            else (None, None)
        )
        ue_summary1, ue_summary2 = (
            table_generation.get_platform_summary_tables(
                ue_sales_df,
                ue_payouts_df,
                ue_orders_df,
                ue_new_customers_df,
                "selected_stores_UberEats",
                is_ue=True,
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

        financial_summary_table = None
        if build_financial_summary_table is not None:
            try:
                financial_summary_table = build_financial_summary_table(
                    dd_data_path,
                    ue_data_path,
                    pre_start,
                    pre_end,
                    post_start,
                    post_end,
                    excluded_dates,
                )
            except Exception:
                financial_summary_table = None

        promotion_table, sponsored_table, corporate_todc_table = (
            marketing_analysis.create_corporate_vs_todc_table(
                excluded_dates=excluded_dates,
                pre_start_date=pre_start,
                pre_end_date=pre_end,
                post_start_date=post_start,
                post_end_date=post_end,
                marketing_folder_path=marketing_folder_path,
            )
        )

        sales_pre_post_table = None
        sales_yoy_table = None
        payouts_pre_post_table = None
        payouts_yoy_table = None
        ue_sales_pre_post_table = None
        ue_sales_yoy_table = None
        ue_payouts_pre_post_table = None
        ue_payouts_yoy_table = None
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
                pass
            try:
                (
                    ue_sales_pre_post_table,
                    ue_sales_yoy_table,
                    ue_payouts_pre_post_table,
                    ue_payouts_yoy_table,
                ) = slot_analysis.process_ue_slot_analysis(
                    ue_data_path,
                    pre_start_date=pre_start,
                    pre_end_date=pre_end,
                    post_start_date=post_start,
                    post_end_date=post_end,
                    excluded_dates=excluded_dates,
                )
            except Exception:
                pass

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
            ue_sales_pre_post_table=ue_sales_pre_post_table,
            ue_sales_yoy_table=ue_sales_yoy_table,
            ue_payouts_pre_post_table=ue_payouts_pre_post_table,
            ue_payouts_yoy_table=ue_payouts_yoy_table,
            dd_data_path=dd_data_path,
            ue_data_path=ue_data_path,
            pre_start_date=pre_start,
            pre_end_date=pre_end,
            post_start_date=post_start,
            post_end_date=post_end,
            excluded_dates=excluded_dates,
            financial_summary_table=financial_summary_table,
        )

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

        tables = {
            "combined_summary_pre_post": _df_to_records(combined_summary1),
            "combined_summary_yoy": _df_to_records(combined_summary2),
            "combined_store_pre_post": _df_to_records(combined_store_table1, max_rows=200),
            "combined_store_yoy": _df_to_records(combined_store_table2, max_rows=200),
            "dd_summary_pre_post": _df_to_records(dd_summary1),
            "dd_summary_yoy": _df_to_records(dd_summary2),
            "dd_store_pre_post": _df_to_records(dd_table1, max_rows=200),
            "dd_store_yoy": _df_to_records(dd_table2, max_rows=200),
            "ue_summary_pre_post": _df_to_records(ue_summary1),
            "ue_summary_yoy": _df_to_records(ue_summary2),
            "ue_store_pre_post": _df_to_records(ue_table1, max_rows=200),
            "ue_store_yoy": _df_to_records(ue_table2, max_rows=200),
            "promotion_corporate_vs_todc": _df_to_records(promotion_table, max_rows=200),
            "sponsored_corporate_vs_todc": _df_to_records(sponsored_table, max_rows=200),
            "corporate_vs_todc": _df_to_records(corporate_todc_table, max_rows=200),
            "financial_summary": _df_to_records(financial_summary_table, max_rows=200),
            "dd_slot_sales_pre_post": _df_to_records(sales_pre_post_table, max_rows=200),
            "dd_slot_sales_yoy": _df_to_records(sales_yoy_table, max_rows=200),
            "dd_slot_payouts_pre_post": _df_to_records(payouts_pre_post_table, max_rows=200),
            "dd_slot_payouts_yoy": _df_to_records(payouts_yoy_table, max_rows=200),
            "ue_slot_sales_pre_post": _df_to_records(ue_sales_pre_post_table, max_rows=200),
            "ue_slot_sales_yoy": _df_to_records(ue_sales_yoy_table, max_rows=200),
            "ue_slot_payouts_pre_post": _df_to_records(ue_payouts_pre_post_table, max_rows=200),
            "ue_slot_payouts_yoy": _df_to_records(ue_payouts_yoy_table, max_rows=200),
        }

        date_export_bytes: bytes | None = None
        date_export_filename: str | None = None
        bucketing_export_bytes: bytes | None = None
        bucketing_export_filename: str | None = None
        if create_date_export_from_master_files is not None:
            try:
                de, dn = create_date_export_from_master_files(
                    dd_data_path,
                    ue_data_path,
                    pre_start,
                    pre_end,
                    post_start,
                    post_end,
                    excluded_dates=excluded_dates,
                    operator_name=operator_name,
                )
                if de and dn:
                    date_export_bytes = de
                    date_export_filename = dn
            except Exception:
                pass
        if create_bucketing_export is not None and dd_data_path.is_file():
            try:
                be, bn = create_bucketing_export(
                    dd_data_path,
                    operator_name=operator_name,
                    pre_start_date=pre_start,
                    pre_end_date=pre_end,
                    post_start_date=post_start,
                    post_end_date=post_end,
                    excluded_dates=excluded_dates,
                )
                if be and bn:
                    bucketing_export_bytes = be
                    bucketing_export_filename = bn
            except Exception:
                pass

        _ = config  # silence unused in some envs
        return {
            "excel_bytes": file_bytes,
            "filename": filename,
            "summary_text": summary_text,
            "tables": tables,
            "date_export_bytes": date_export_bytes,
            "date_export_filename": date_export_filename,
            "bucketing_export_bytes": bucketing_export_bytes,
            "bucketing_export_filename": bucketing_export_filename,
        }
    finally:
        try:
            sys.path.remove(str(app_dir))
        except ValueError:
            pass


def generate_app2_report_excel(
    app_dir: Path,
    inputs: ReportInputs,
    *,
    data_root: Optional[Path] = None,
) -> tuple[bytes, str, str]:
    """Backward-compatible tuple return (used by tests / scripts)."""
    root = data_root if data_root is not None else app_dir
    b = generate_monthly_report_bundle(inputs, data_root=root)
    return b["excel_bytes"], b["filename"], b["summary_text"]
