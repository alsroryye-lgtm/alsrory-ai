from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import settings
from ..db import execute, new_id, now_iso, query_one
from ..schemas import ExportRequest
from ..serializers import asset_public
from ..services import media, storage

router = APIRouter(prefix="/api/exports", tags=["exports"])


@router.post("", status_code=201)
async def export_project(body: ExportRequest) -> dict:
    rows = []
    for asset_id in body.asset_ids:
        row = query_one("SELECT * FROM assets WHERE id = ?", (asset_id,))
        if not row:
            raise HTTPException(404, f"الأصل {asset_id} غير موجود")
        if row["kind"] not in {"video", "export"}:
            raise HTTPException(400, "التصدير يدعم مقاطع الفيديو فقط")
        rows.append(row)

    project_ids = {row["project_id"] for row in rows}
    if len(project_ids) != 1:
        raise HTTPException(400, "كل المقاطع يجب أن تكون من مشروع واحد")
    project_id = rows[0]["project_id"]

    inputs: list[Path] = []
    for row in rows:
        try:
            path = storage.asset_path(row["path"])
        except ValueError:
            raise HTTPException(400, "مسار غير صالح")
        if not path.exists():
            raise HTTPException(404, "ملف المقطع مفقود من القرص")
        inputs.append(path)

    export_id = new_id("exp")
    out_dir = settings.data_dir / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c for c in body.filename if c.isalnum() or c in "._- ").strip()
    out = out_dir / f"{export_id}-{safe_name or 'final.mp4'}"
    if out.suffix.lower() != ".mp4":
        out = out.with_suffix(".mp4")

    try:
        await media.concat_videos(inputs, out, body.aspect_ratio)
    except Exception as exc:
        raise HTTPException(500, str(exc))

    # Record real output metadata so the UI can show duration and dimensions.
    fallback_w, fallback_h = media.ASPECTS.get(
        body.aspect_ratio, media.ASPECTS["16:9"]
    )
    duration = sum(float(row["duration_s"] or 0) for row in rows) or None
    width, height = fallback_w, fallback_h
    probed = await media.probe(out)
    if probed:
        try:
            duration = float(probed["format"]["duration"])
        except (KeyError, TypeError, ValueError):
            pass
        for stream in probed.get("streams", []):
            if stream.get("codec_type") == "video":
                width = stream.get("width") or width
                height = stream.get("height") or height
                break

    asset_id = new_id("asset")
    execute(
        """INSERT INTO assets(id, project_id, generation_id, kind, path, mime,
           width, height, duration_s, size_bytes, meta_json, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            asset_id,
            project_id,
            None,
            "export",
            storage.storage_rel(out),
            "video/mp4",
            width,
            height,
            round(duration, 3) if duration else None,
            out.stat().st_size,
            '{"source":"timeline","items":' + str(len(inputs)) + "}",
            now_iso(),
        ),
    )
    row = query_one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    return asset_public(row or {})
