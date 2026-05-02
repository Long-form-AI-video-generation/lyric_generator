"""Built-in background preset endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from backend.models.schemas import PresetList
from backend.services.presets import preset_service

router = APIRouter(tags=["presets"])


@router.get("/presets", response_model=PresetList)
async def presets() -> PresetList:
    preset_service.ensure_assets(include_full=False)
    return PresetList(presets=preset_service.list_presets())
