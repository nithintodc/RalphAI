import pandas as pd

from shared.order_time_columns import (
    FINANCIAL_ORDER_TIME_COL,
    SALES_BY_ORDER_TIME_COL,
    drop_rows_without_order_time,
    find_financial_order_time_column,
    find_sales_by_order_time_column,
)


def test_find_financial_order_time_column_exact_match():
    df = pd.DataFrame({FINANCIAL_ORDER_TIME_COL: ["08:15"], "Other": [1]})
    assert find_financial_order_time_column(df) == FINANCIAL_ORDER_TIME_COL


def test_find_financial_order_time_column_ignores_timestamp_local_time():
    df = pd.DataFrame({"Timestamp local time": ["08:15"], FINANCIAL_ORDER_TIME_COL: ["09:00"]})
    assert find_financial_order_time_column(df) == FINANCIAL_ORDER_TIME_COL


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
