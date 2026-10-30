from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from .config import settings
from .db import execute, init_db, query_one
from .deps import queue, registry
from .routers import assets, engines, exports, generations, projects, prompts
from .routers import settings as settings_router

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    execute(
        """UPDATE generations
           SET status='failed', error_stage='startup',
               error_detail='أُعيد تشغيل الخادم أثناء تنفيذ المهمة. أعد المحاولة.',
               finished_at=strftime('%Y-%m-%dT%H:%M:%S+00:00','now')
           WHERE status IN ('running','postprocessing')"""
    )
    await queue.start()
    try:
        yield
    finally:
        await queue.stop()


app = FastAPI(
    title="alsrory.AI API",
    description="استوديو فيديو محلي بالذكاء الاصطناعي — محرّكات قابلة للتبديل.",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (projects, generations, assets, engines, settings_router, prompts, exports):
    app.include_router(module.router)


@app.get("/api/health", tags=["system"])
def health() -> dict:
    return {
        "ok": True,
        "version": VERSION,
        "default_engine": registry.default_id,
        "engines": [item["id"] for item in registry.list()],
        "ffmpeg": bool(settings.ffmpeg),
        "data_dir": str(settings.data_dir),
        "projects": (query_one("SELECT COUNT(*) AS n FROM projects") or {}).get("n", 0),
        "pending_jobs": (
            query_one(
                "SELECT COUNT(*) AS n FROM generations WHERE status IN ('queued','running','postprocessing')"
            )
            or {}
        ).get("n", 0),
    }


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/docs")
