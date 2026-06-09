"""API routes for global browser automation mode (Settings UI)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["browser-settings"])


class BrowserModeBody(BaseModel):
    mode: str = Field(..., description="multilogin | native")


@router.get("/browser-settings")
def get_browser_settings() -> dict:
    from shared.browser_settings import browser_mode_summary

    return browser_mode_summary()


@router.put("/browser-settings")
def put_browser_settings(body: BrowserModeBody) -> dict:
    from shared.browser_settings import save_browser_mode

    try:
        return save_browser_mode(body.mode)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
