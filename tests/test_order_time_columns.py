import pandas as pd

from shared.order_time_columns import (
    DD_SLOT_TIME_RESOLVED_COL,
    FINANCIAL_ORDER_TIME_COL,
    FINANCIAL_ORDER_TIME_FALLBACK_COL,
    SALES_BY_ORDER_TIME_COL,
    attach_dd_slot_time_column,
    drop_rows_without_order_time,
    drop_rows_without_resolved_dd_slot_time,
    find_financial_order_time_column,
    find_financial_order_time_fallback_column,
    find_sales_by_order_time_column,
    has_dd_slot_time_source_columns,
    resolve_dd_slot_time_series,
)


def test_find_financial_order_time_column_exact_match():
    df = pd.DataFrame({FINANCIAL_ORDER_TIME_COL: ["08:15"], "Other": [1]})
    assert find_financial_order_time_column(df) == FINANCIAL_ORDER_TIME_COL


def test_find_financial_order_time_column_ignores_timestamp_local_time():
    df = pd.DataFrame({"Timestamp local time": ["08:15"], FINANCIAL_ORDER_TIME_COL: ["09:00"]})
    assert find_financial_order_time_column(df) == FINANCIAL_ORDER_TIME_COL


def test_find_financial_order_time_fallback_column():
    df = pd.DataFrame({"Timestamp local time": ["08:15"]})
    assert find_financial_order_time_fallback_column(df) == "Timestamp local time"


def test_has_dd_slot_time_source_columns():
    assert has_dd_slot_time_source_columns(pd.DataFrame({FINANCIAL_ORDER_TIME_COL: ["x"]}))
    assert has_dd_slot_time_source_columns(pd.DataFrame({"Timestamp local time": ["x"]}))
    assert not has_dd_slot_time_source_columns(pd.DataFrame({"Other": [1]}))


def test_resolve_dd_slot_time_series_prefers_received():
    df = pd.DataFrame(
        {
            FINANCIAL_ORDER_TIME_COL: ["08:00", None, ""],
            FINANCIAL_ORDER_TIME_FALLBACK_COL: ["09:00", "10:00", "11:00"],
        }
    )
    out = resolve_dd_slot_time_series(df)
    assert list(out) == ["08:00", "10:00", "11:00"]


def test_attach_and_drop_resolved_dd_slot_time():
    df = pd.DataFrame(
        {
            FINANCIAL_ORDER_TIME_COL: ["08:00", None, ""],
            FINANCIAL_ORDER_TIME_FALLBACK_COL: ["09:00", "10:00", "null"],
            "id": [1, 2, 3],
        }
    )
    out = drop_rows_without_resolved_dd_slot_time(attach_dd_slot_time_column(df))
    assert DD_SLOT_TIME_RESOLVED_COL in out.columns
    assert list(out["id"]) == [1, 2]


def test_find_sales_by_order_time_column_exact_match():
    df = pd.DataFrame({SALES_BY_ORDER_TIME_COL: ["10:30"]})
    assert find_sales_by_order_time_column(df) == SALES_BY_ORDER_TIME_COL


def test_drop_rows_without_order_time_removes_null_and_blank():
    df = pd.DataFrame(
        {
            FINANCIAL_ORDER_TIME_COL: ["08:00", None, "", "null", "09:00"],
            "id": [1, 2, 3, 4, 5],
        }
    )
    out = drop_rows_without_order_time(df, FINANCIAL_ORDER_TIME_COL)
    assert list(out["id"]) == [1, 5]


def test_drop_rows_without_order_time_missing_column_returns_empty():
    df = pd.DataFrame({"id": [1, 2]})
    out = drop_rows_without_order_time(df, FINANCIAL_ORDER_TIME_COL)
    assert out.empty
