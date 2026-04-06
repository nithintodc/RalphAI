"""Operator lifecycle state machine."""

from __future__ import annotations

from enum import Enum
from typing import Literal

Transition = Literal[
    "start_deepdive",
    "deepdive_complete",
    "submit_reco",
    "approve_reco",
    "reject_reco",
    "modify_reco",
    "start_campaign_setup",
    "campaigns_live",
    "schedule_review",
    "submit_review",
    "approve_review",
]


class OperatorState(str, Enum):
    NEW = "NEW"
    DEEPDIVE_RUNNING = "DEEPDIVE_RUNNING"
    DEEPDIVE_DONE = "DEEPDIVE_DONE"
    RECO_PENDING_APPROVAL = "RECO_PENDING_APPROVAL"
    RECO_APPROVED = "RECO_APPROVED"
    CAMPAIGNS_SETTING_UP = "CAMPAIGNS_SETTING_UP"
    CAMPAIGNS_LIVE = "CAMPAIGNS_LIVE"
    REVIEW_PENDING = "REVIEW_PENDING"
    REVIEW_APPROVED = "REVIEW_APPROVED"


def transition(state: OperatorState, event: Transition) -> OperatorState:
    """Deterministic next state; extend with a table or Redis-backed FSM in production."""
    table: dict[tuple[OperatorState, Transition], OperatorState] = {
        (OperatorState.NEW, "start_deepdive"): OperatorState.DEEPDIVE_RUNNING,
        (OperatorState.DEEPDIVE_RUNNING, "deepdive_complete"): OperatorState.DEEPDIVE_DONE,
        (OperatorState.DEEPDIVE_DONE, "submit_reco"): OperatorState.RECO_PENDING_APPROVAL,
        (OperatorState.RECO_PENDING_APPROVAL, "approve_reco"): OperatorState.RECO_APPROVED,
        (OperatorState.RECO_PENDING_APPROVAL, "reject_reco"): OperatorState.DEEPDIVE_DONE,
        (OperatorState.RECO_PENDING_APPROVAL, "modify_reco"): OperatorState.RECO_PENDING_APPROVAL,
        (OperatorState.RECO_APPROVED, "start_campaign_setup"): OperatorState.CAMPAIGNS_SETTING_UP,
        (OperatorState.CAMPAIGNS_SETTING_UP, "campaigns_live"): OperatorState.CAMPAIGNS_LIVE,
        (OperatorState.CAMPAIGNS_LIVE, "schedule_review"): OperatorState.REVIEW_PENDING,
        (OperatorState.REVIEW_PENDING, "submit_review"): OperatorState.REVIEW_PENDING,
        (OperatorState.REVIEW_PENDING, "approve_review"): OperatorState.REVIEW_APPROVED,
        (OperatorState.REVIEW_APPROVED, "campaigns_live"): OperatorState.CAMPAIGNS_LIVE,
    }
    key = (state, event)
    if key not in table:
        raise ValueError(f"invalid transition: {state!r} + {event!r}")
    return table[key]
