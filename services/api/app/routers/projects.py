from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import execute, new_id, now_iso, query, query_one
from ..schemas import ApiMessage, ProjectCreate, ProjectUpdate
from ..serializers import asset_public, generation_public, project_public
from ..services import storage

router = APIRouter(prefix="/api/projects", tags=["projects"])

_LIST_SQL = """
SELECT p.*,
  (SELECT COUNT(*) FROM generations g WHERE g.project_id = p.id) AS generation_count,
  (SELECT COUNT(*) FROM assets a WHERE a.project_id = p.id AND a.kind = 'video') AS asset_count,
  (SELECT a.id FROM assets a
     WHERE a.project_id = p.id AND a.kind IN ('thumbnail','image')
     ORDER BY a.created_at DESC LIMIT 1) AS cover_asset_id
FROM projects p
ORDER BY p.updated_at DESC
"""


@router.get("")
def list_projects() -> list[dict]:
    return [project_public(row) for row in query(_LIST_SQL)]


@router.post("", status_code=201)
def create_project(body: ProjectCreate) -> dict:
    project_id = new_id("proj")
    stamp = now_iso()
    execute(
        """INSERT INTO projects(id, name, description, aspect_ratio, style_preset,
           created_at, updated_at) VALUES(?,?,?,?,?,?,?)""",
        (
            project_id,
            body.name.strip(),
            body.description.strip(),
            body.aspect_ratio,
            body.style_preset,
            stamp,
            stamp,
        ),
    )
    row = query_one(
        "SELECT * FROM projects WHERE id = ?",
        (project_id,),
    )
    return project_public(row or {})


@router.get("/{project_id}")
def get_project(project_id: str) -> dict:
    row = query_one(
        _LIST_SQL.replace("ORDER BY p.updated_at DESC", "WHERE p.id = ?"),
        (project_id,),
    )
    if not row:
        raise HTTPException(404, "المشروع غير موجود")
    generations = query(
        "SELECT * FROM generations WHERE project_id = ? ORDER BY created_at DESC LIMIT 60",
        (project_id,),
    )
    assets = query(
        "SELECT * FROM assets WHERE project_id = ? ORDER BY created_at DESC LIMIT 200",
        (project_id,),
    )
    payload = project_public(row)
    payload["generations"] = [generation_public(g) for g in generations]
    payload["assets"] = [asset_public(a) for a in assets]
    return payload


@router.patch("/{project_id}")
def update_project(project_id: str, body: ProjectUpdate) -> dict:
    row = query_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if not row:
        raise HTTPException(404, "المشروع غير موجود")

    fields = body.model_dump(exclude_unset=True)
    if not fields:
        return project_public(row)

    allowed = {"name", "description", "aspect_ratio", "style_preset"}
    assignments = [f"{key} = ?" for key in fields if key in allowed]
    values = [fields[key] for key in fields if key in allowed]
    if not assignments:
        return project_public(row)
    assignments.append("updated_at = ?")
    values.extend([now_iso(), project_id])
    execute(
        f"UPDATE projects SET {', '.join(assignments)} WHERE id = ?", tuple(values)
    )
    updated = query_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    return project_public(updated or {})


@router.delete("/{project_id}")
def delete_project(project_id: str) -> ApiMessage:
    row = query_one("SELECT id FROM projects WHERE id = ?", (project_id,))
    if not row:
        raise HTTPException(404, "المشروع غير موجود")
    storage.remove_project_files(project_id)
    execute("DELETE FROM assets WHERE project_id = ?", (project_id,))
    execute("DELETE FROM generations WHERE project_id = ?", (project_id,))
    execute("DELETE FROM scenes WHERE project_id = ?", (project_id,))
    execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return ApiMessage(message="حُذف المشروع")
