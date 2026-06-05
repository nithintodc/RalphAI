"""API routes for operator ↔ Multilogin profile mapping (settings UI)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["operator-profile-mapping"])


class MappingSaveBody(BaseModel):
    operators: list[dict[str, Any]] = Field(default_factory=list)
    unmatched_profiles: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/operator-profile-mapping")
def get_operator_profile_mapping() -> dict[str, Any]:
    from shared.operator_profile_mapping import (
        all_known_profiles,
        build_venn_view,
        load_mapping,
        mapping_path,
    )

    mapping = load_mapping(force_reload=True)
    return {
        "path": str(mapping_path()),
        "mapping": mapping,
        "venn": build_venn_view(mapping),
        "profiles": all_known_profiles(mapping),
    }


@router.post("/operator-profile-mapping/sync")
def sync_operator_profile_mapping(offline: bool = False) -> dict[str, Any]:
    from multilogin.sync_operator_mapping import sync_and_write
    from shared.operator_profile_mapping import (
        all_known_profiles,
        build_venn_view,
        load_mapping,
        mapping_path,
    )

    try:
        sync_and_write(offline=offline)
    except Exception as exc:
        raise HTTPException(503, f"Sync failed: {exc}") from exc

    mapping = load_mapping(force_reload=True)
    return {
        "path": str(mapping_path()),
        "mapping": mapping,
        "venn": build_venn_view(mapping),
        "profiles": all_known_profiles(mapping),
    }


@router.put("/operator-profile-mapping")
def put_operator_profile_mapping(body: MappingSaveBody) -> dict[str, Any]:
    from shared.operator_profile_mapping import (
        all_known_profiles,
        mapping_csv_path,
        mapping_path,
        save_mapping_payload,
    )

    try:
        result = save_mapping_payload(body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, str(exc)) from exc

    mapping = result["mapping"]
    return {
        "path": str(mapping_path()),
        "json_path": result.get("json_path") or str(mapping_path()),
        "csv_path": result.get("csv_path") or str(mapping_csv_path()),
        **result,
        "profiles": all_known_profiles(mapping),
    }
