from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from ..config import settings
from ..db import new_id, now_iso, storage_rel
from ..engines.base import EngineArtifact

_EXT_BY_MIME = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
}


def project_dir(project_id: str) -> Path:
    return settings.assets_dir / "projects" / project_id


def generation_dir(project_id: str, generation_id: str) -> Path:
    path = project_dir(project_id) / generation_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def asset_path(relative: str) -> Path:
    candidate = (settings.data_dir / relative).resolve()
    root = settings.data_dir.resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("مسار أصل غير صالح")
    return candidate


def save_artifact(
    project_id: str,
    generation_id: str,
    artifact: EngineArtifact,
) -> dict[str, Any]:
    folder = generation_dir(project_id, generation_id)
    suffix = Path(artifact.filename).suffix or _EXT_BY_MIME.get(artifact.mime, ".bin")
    filename = f"{artifact.kind}-{new_id('a')[2:]}{suffix}"
    target = folder / filename

    if artifact.data is not None:
        target.write_bytes(artifact.data)
    elif artifact.path is not None:
        source = artifact.path.resolve()
        # Engines that write straight into the generation folder: move instead of
        # duplicating the file (videos can be hundreds of MB).
        if source.parent == folder.resolve() and source != target:
            shutil.move(str(source), str(target))
        else:
            shutil.copyfile(source, target)
    else:
        raise ValueError("الأصل لا يحتوي بيانات")

    asset_id = new_id("asset")
    record = {
        "id": asset_id,
        "project_id": project_id,
        "generation_id": generation_id,
        "kind": artifact.kind,
        "path": storage_rel(target),
        "mime": artifact.mime,
        "width": artifact.width,
        "height": artifact.height,
        "duration_s": artifact.duration_s,
        "size_bytes": target.stat().st_size,
        "meta_json": __import__("json").dumps(artifact.meta, ensure_ascii=False),
        "created_at": now_iso(),
    }
    from ..db import execute

    execute(
        """INSERT INTO assets(id, project_id, generation_id, kind, path, mime,
           width, height, duration_s, size_bytes, meta_json, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            record["id"],
            record["project_id"],
            record["generation_id"],
            record["kind"],
            record["path"],
            record["mime"],
            record["width"],
            record["height"],
            record["duration_s"],
            record["size_bytes"],
            record["meta_json"],
            record["created_at"],
        ),
    )
    return record


def remove_project_files(project_id: str) -> None:
    path = project_dir(project_id)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def remove_asset_file(relative: str) -> None:
    try:
        path = asset_path(relative)
    except ValueError:
        return
    if path.exists():
        path.unlink(missing_ok=True)
