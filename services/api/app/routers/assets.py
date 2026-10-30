from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from ..config import settings
from ..db import execute, new_id, now_iso, query, query_one
from ..schemas import ApiMessage
from ..serializers import asset_public
from ..services.storage import asset_path, remove_asset_file, storage_rel

router = APIRouter(prefix="/api/assets", tags=["assets"])

_ALLOWED = {
    ".mp4": "video",
    ".webm": "video",
    ".mov": "video",
    ".mkv": "video",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".mp3": "audio",
    ".wav": "audio",
    ".m4a": "audio",
    ".flac": "audio",
}
_MAX_BYTES = 512 * 1024 * 1024


@router.get("")
def list_assets(
    project_id: str | None = None,
    kind: str | None = None,
    limit: int = Query(default=60, ge=1, le=300),
) -> list[dict]:
    clauses: list[str] = []
    values: list[object] = []
    if project_id:
        clauses.append("project_id = ?")
        values.append(project_id)
    if kind:
        clauses.append("kind = ?")
        values.append(kind)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    values.append(limit)
    rows = query(
        f"SELECT * FROM assets {where} ORDER BY created_at DESC LIMIT ?", tuple(values)
    )
    return [asset_public(row) for row in rows]


@router.post("/upload", status_code=201)
async def upload_asset(
    project_id: str = Form(...),
    kind: str = Form("image"),
    file: UploadFile = File(...),
) -> dict:
    if not query_one("SELECT id FROM projects WHERE id = ?", (project_id,)):
        raise HTTPException(404, "المشروع غير موجود")

    original = Path(file.filename or "upload.bin")
    suffix = original.suffix.lower()
    if suffix not in _ALLOWED:
        raise HTTPException(400, "نوع الملف غير مدعوم")

    folder = settings.assets_dir / "projects" / project_id / "uploads"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{uuid.uuid4().hex[:12]}{suffix}"

    total = 0
    try:
        with target.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > _MAX_BYTES:
                    raise HTTPException(413, "الملف أكبر من الحد (512MB)")
                out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    guessed = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    asset_id = new_id("asset")
    resolved_kind = kind if kind in {"image", "video", "audio"} else _ALLOWED[suffix]
    execute(
        """INSERT INTO assets(id, project_id, generation_id, kind, path, mime,
           width, height, duration_s, size_bytes, meta_json, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            asset_id,
            project_id,
            None,
            resolved_kind,
            storage_rel(target),
            guessed,
            None,
            None,
            None,
            total,
            '{"source":"upload","original_name":"' + original.name.replace('"', "") + '"}',
            now_iso(),
        ),
    )
    row = query_one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    return asset_public(row or {})


@router.get("/{asset_id}")
def get_asset(asset_id: str) -> dict:
    row = query_one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    if not row:
        raise HTTPException(404, "الأصل غير موجود")
    return asset_public(row)


@router.get("/{asset_id}/file")
def get_asset_file(asset_id: str, download: bool = False) -> FileResponse:
    row = query_one("SELECT * FROM assets WHERE id = ?", (asset_id,))
    if not row:
        raise HTTPException(404, "الأصل غير موجود")
    try:
        path = asset_path(row["path"])
    except ValueError:
        raise HTTPException(400, "مسار غير صالح")
    if not path.exists():
        raise HTTPException(404, "الملف مفقود من القرص")
    return FileResponse(
        path,
        media_type=row["mime"] or "application/octet-stream",
        filename=f"{row['id']}{path.suffix}" if download else None,
    )


@router.get("/{asset_id}/download")
def download_asset(asset_id: str) -> FileResponse:
    return get_asset_file(asset_id, download=True)


@router.delete("/{asset_id}")
def delete_asset(asset_id: str) -> ApiMessage:
    row = query_one("SELECT path FROM assets WHERE id = ?", (asset_id,))
    if not row:
        raise HTTPException(404, "الأصل غير موجود")
    remove_asset_file(row["path"])
    execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    return ApiMessage(message="حُذف الأصل")
