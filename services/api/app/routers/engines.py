from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..deps import registry
from ..schemas import EngineTestRequest

router = APIRouter(prefix="/api/engines", tags=["engines"])


@router.get("")
def list_engines() -> list[dict]:
    return registry.list()


@router.get("/hfspace/account")
async def hfspace_account() -> dict:
    engine = registry.get("hfspace")
    account = getattr(engine, "account", None)
    if account is None:
        raise HTTPException(404, "محرّك Hugging Face غير مُفعَّل")
    return await account()


@router.get("/status")
async def engines_status() -> list[dict]:
    return await registry.health_all()


@router.post("/test")
async def test_engine(body: EngineTestRequest) -> dict:
    engine = registry.get(body.engine_id)
    if not engine:
        raise HTTPException(404, "المحرّك غير معروف")
    health = await engine.health()
    return {
        "id": engine.id,
        "ready": health.ready,
        "detail": health.detail,
        "latency_ms": health.latency_ms,
    }
