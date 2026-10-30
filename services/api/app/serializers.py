from __future__ import annotations

import json
from typing import Any


def _json(value: Any, default: Any) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def project_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row.get("description", ""),
        "aspect_ratio": row.get("aspect_ratio", "16:9"),
        "style_preset": row.get("style_preset", ""),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "generation_count": row.get("generation_count"),
        "asset_count": row.get("asset_count"),
        "cover_asset_id": row.get("cover_asset_id"),
    }


def generation_public(row: dict[str, Any], assets: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "project_id": row["project_id"],
        "scene_id": row.get("scene_id"),
        "type": row["type"],
        "status": row["status"],
        "progress": row.get("progress", 0),
        "prompt": row.get("prompt", ""),
        "negative_prompt": row.get("negative_prompt", ""),
        "params": _json(row.get("params_json"), {}),
        "engine_id": row.get("engine_id", "mock"),
        "seed": row.get("seed"),
        "error_stage": row.get("error_stage"),
        "error_detail": row.get("error_detail"),
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
    }
    if assets is not None:
        payload["assets"] = [asset_public(a) for a in assets]
    return payload


def asset_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "generation_id": row.get("generation_id"),
        "kind": row["kind"],
        "mime": row.get("mime", ""),
        "width": row.get("width"),
        "height": row.get("height"),
        "duration_s": row.get("duration_s"),
        "size_bytes": row.get("size_bytes", 0),
        "meta": _json(row.get("meta_json"), {}),
        "created_at": row.get("created_at"),
        "url": f"/api/assets/{row['id']}/file",
        "download_url": f"/api/assets/{row['id']}/download",
    }
