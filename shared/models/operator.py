"""Operator registry shape — used by orchestrator and Slack commands."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OperatorProfile(BaseModel):
    operator_id: str
    operator_name: str = ""
    store_ids: list[str] = Field(default_factory=list)
    region: str = ""
    tier: str = ""
    store_count: int = 0
