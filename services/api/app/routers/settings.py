from __future__ import annotations

from fastapi import APIRouter

from ..db import get_setting, put_setting
from ..deps import registry
from ..schemas import EngineConfigUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])

_MASK = "••••••••"


def _public_config() -> dict:
    config = registry.config()
    token = config.get("comfy_token") or ""
    return {
        "default_engine": config["default_engine"],
        "comfy_url": config["comfy_url"],
        "comfy_token_set": bool(token),
        "comfy_token": _MASK if token else "",
        "comfy_workflow": config["comfy_workflow"],
        "hf_space_id": config["hf_space_id"] or "",
        "hf_api_name": config["hf_api_name"],
        "available_engines": registry.list(),
    }


@router.get("")
def read_settings() -> dict:
    return _public_config()


@router.put("")
def update_settings(body: EngineConfigUpdate) -> dict:
    current = get_setting("engine_config", {}) or {}
    incoming = body.model_dump(exclude_unset=True)

    if "comfy_token" in incoming:
        value = incoming.pop("comfy_token")
        if value == _MASK:
            pass
        else:
            current["comfy_token"] = value or ""

    for key, value in incoming.items():
        if value is None:
            continue
        current[key] = value

    put_setting("engine_config", current)
    registry.refresh()
    return _public_config()
