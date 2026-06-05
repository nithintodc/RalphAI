"""Typed shapes aligned with contracts/ingestion.json (runtime validation optional)."""

from __future__ import annotations

from typing import Any, TypedDict


class IngestionInput(TypedDict):
    operator_id: str
    source: str
    days: int


class IngestionData(TypedDict, total=False):
    """DoorDash export datasets keyed by category.

    Values are ``pd.DataFrame`` objects (or empty DataFrames when a category is
    absent from the export).  The ``total=False`` flag means all keys are
    optional — callers must use ``.get()`` or check presence before access.

    Category keys match ``agents/deepdive/data_loader._CATEGORY_PATTERNS``:

    Financial
    ---------
    financial_detailed    FINANCIAL_DETAILED_TRANSACTIONS
    financial_simplified  FINANCIAL_SIMPLIFIED_TRANSACTIONS
    financial_errors      FINANCIAL_ERROR_CHARGES_AND_ADJUSTMENTS
    financial_payouts     FINANCIAL_PAYOUT_SUMMARY

    Marketing
    ---------
    marketing_promotions  MARKETING_PROMOTION
    marketing_sponsored   MARKETING_SPONSORED_LISTING

    Sales
    -----
    sales_by_order        SALES_viewByOrder
    sales_by_time         SALES_viewByTime_* (time-series views)
    product_mix           PRODUCT_MIX / SALES_viewByStore_productPerformance

    Operations
    ----------
    operations_quality    OPERATIONS_QUALITY / ops_avoidable_wait / ops_cancelled / ops_missing_incorrect

    Derived
    -------
    store_id_mapping      DD ↔ National store-ID cross-reference (built by data_loader)
    """

    # Financial
    financial_detailed: Any
    financial_simplified: Any
    financial_errors: Any
    financial_payouts: Any
    # Marketing
    marketing_promotions: Any
    marketing_sponsored: Any
    # Sales
    sales_by_order: Any
    sales_by_time: Any
    product_mix: Any
    # Operations
    operations_quality: Any
    # Derived
    store_id_mapping: Any


class IngestionOutput(TypedDict):
    operator_id: str
    data: IngestionData
