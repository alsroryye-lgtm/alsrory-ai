from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ..db import execute, new_id, now_iso, query, query_one
from ..deps import queue, registry
from ..engines.base import ASPECT_SIZES
from ..schemas import ApiMessage, GenerationCreate
from ..serializers import asset_public, generation_public

router = APIRouter(prefix="/api/generations", tags=["generations"])

TERMINAL = {"completed", "failed", "canceled"}


def _assets_for(generation_id: str) -> list[dict]:
    return query(
        "SELECT * FROM assets WHERE generation_id = ? ORDER BY created_at ASC",
        (generation_id,),
    )


@router.get("")
def list_generations(
    project_id: str | None = None,
    status: str | None = None,
    limit: int = Query(default=30, ge=1, le=200),
) -> list[dict]:
    clauses: list[str] = []
    values: list[object] = []
    if project_id:
        clauses.append("project_id = ?")
        values.append(project_id)
    if status:
        clauses.append("status = ?")
        values.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    values.append(limit)
    rows = query(
        f"SELECT * FROM generations {where} ORDER BY created_at DESC LIMIT ?",
        tuple(values),
    )
    return [generation_public(row) for row in rows]


@router.post("", status_code=202)
async def create_generation(body: GenerationCreate) -> dict:
    if not query_one("SELECT id FROM projects WHERE id = ?", (body.project_id,)):
        raise HTTPException(404, "المشروع غير موجود")

    params = body.params.model_dump()
    width = params.get("width", 832)
    height = params.get("height", 480)
    if (width, height) == (832, 480):
        width, height = ASPECT_SIZES.get(params.get("aspect_ratio", "16:9"), (832, 480))
        params["width"], params["height"] = width, height

    engine = registry.resolve(body.type, body.engine_id)
    generation_id = new_id("gen")
    execute(
        """INSERT INTO generations(id, project_id, scene_id, type, status, progress,
           prompt, negative_prompt, params_json, engine_id, seed, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            generation_id,
            body.project_id,
            body.scene_id,
            body.type,
            "queued",
            0.0,
            body.prompt.strip(),
            body.negative_prompt.strip(),
            json.dumps(params, ensure_ascii=False),
            engine.id,
            params.get("seed"),
            now_iso(),
        ),
    )
    execute(
        "UPDATE projects SET updated_at = ? WHERE id = ?",
        (now_iso(), body.project_id),
    )
    await queue.enqueue(generation_id)
    row = query_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    return generation_public(row or {}, assets=[])


@router.get("/{generation_id}")
def get_generation(generation_id: str) -> dict:
    row = query_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    if not row:
        raise HTTPException(404, "المهمة غير موجودة")
    return generation_public(row, assets=_assets_for(generation_id))


@router.post("/{generation_id}/cancel")
async def cancel_generation(generation_id: str) -> ApiMessage:
    row = query_one("SELECT status FROM generations WHERE id = ?", (generation_id,))
    if not row:
        raise HTTPException(404, "المهمة غير موجودة")
    if row["status"] in TERMINAL:
        return ApiMessage(ok=False, message="المهمة منتهية بالفعل")
    await queue.cancel(generation_id)
    return ApiMessage(message="أُلغيت المهمة")


@router.post("/{generation_id}/retry", status_code=202)
async def retry_generation(generation_id: str) -> dict:
    row = query_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
    if not row:
        raise HTTPException(404, "المهمة غير موجودة")

    new_generation_id = new_id("gen")
    execute(
        """INSERT INTO generations(id, project_id, scene_id, type, status, progress,
           prompt, negative_prompt, params_json, engine_id, seed, created_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            new_generation_id,
            row["project_id"],
            row["scene_id"],
            row["type"],
            "queued",
            0.0,
            row["prompt"],
            row["negative_prompt"],
            row["params_json"],
            row["engine_id"],
            None,
            now_iso(),
        ),
    )
    await queue.enqueue(new_generation_id)
    created = query_one("SELECT * FROM generations WHERE id = ?", (new_generation_id,))
    return generation_public(created or {}, assets=[])


@router.get("/{generation_id}/events")
async def generation_events(generation_id: str, request: Request) -> StreamingResponse:
    if not query_one("SELECT id FROM generations WHERE id = ?", (generation_id,)):
        raise HTTPException(404, "المهمة غير موجودة")

    async def stream():
        last = ""
        ticks = 0
        yield "retry: 2000\n\n"
        while True:
            if await request.is_disconnected():
                break
            row = query_one(
                "SELECT * FROM generations WHERE id = ?", (generation_id,)
            )
            if not row:
                yield 'event: gone\ndata: {"status":"deleted"}\n\n'
                break
            payload = generation_public(row, assets=_assets_for(generation_id))
            body = json.dumps(payload, ensure_ascii=False)
            if body != last:
                yield f"event: progress\ndata: {body}\n\n"
                last = body
            ticks += 1
            if ticks % 20 == 0:
                yield ": keep-alive\n\n"
            if row["status"] in TERMINAL:
                yield "event: done\ndata: {}\n\n"
                break
            await asyncio.sleep(0.6)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
