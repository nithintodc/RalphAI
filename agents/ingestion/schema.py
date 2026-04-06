"""Typed shapes aligned with contracts/ingestion.json (runtime validation optional)."""

from __future__ import annotations

from typing import Any, TypedDict


class IngestionInput(TypedDict):
    operator_id: str
    source: str
    days: int


class IngestionData(TypedDict):
    orders: list[dict[str, Any]]
    revenue: list[dict[str, Any]]
    ads: list[dict[str, Any]]
    menu: list[dict[str, Any]]


class IngestionOutput(TypedDict):
    operator_id: str
    data: IngestionData
