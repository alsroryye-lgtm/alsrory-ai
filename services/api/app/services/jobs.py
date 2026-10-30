from __future__ import annotations

import asyncio
import json
import random
from pathlib import Path
from typing import Any

from ..config import settings
from ..db import execute, new_id, now_iso, query_one
from ..engines.base import EngineJob
from . import media, storage


class JobQueue:
    def __init__(self, registry: Any) -> None:
        self.registry = registry
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._active: dict[str, str] = {}  # generation_id -> engine_job_id
        self._active_engines: dict[str, Any] = {}  # generation_id -> Engine
        self._stopping = False

    # ------------------------------------------------------------------ lifecycle
    async def start(self) -> None:
        self._stopping = False
        # A fresh queue per event loop: asyncio primitives bind to the loop that
        # first awaits them, and the test client (and uvicorn reload) can start
        # more than one loop in the same process.
        self._queue = asyncio.Queue()
        for index in range(max(1, settings.max_concurrent_jobs)):
            self._workers.append(
                asyncio.create_task(self._worker(index), name=f"job-worker-{index}")
            )

    async def stop(self) -> None:
        self._stopping = True
        workers = list(self._workers)
        self._workers.clear()
        for worker in workers:
            worker.cancel()
        for worker in workers:
            try:
                await worker
            except (asyncio.CancelledError, Exception):
                pass
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except asyncio.QueueEmpty:
                break

    async def enqueue(self, generation_id: str) -> None:
        await self._queue.put(generation_id)

    def is_active(self, generation_id: str) -> bool:
        return generation_id in self._active

    # ------------------------------------------------------------------ worker
    async def _worker(self, index: int) -> None:
        while not self._stopping:
            generation_id = await self._queue.get()
            if generation_id is None:
                self._queue.task_done()
                break
            try:
                await self._process(generation_id)
            except Exception:
                import logging

                logging.getLogger("alsrory.jobs").exception(
                    "generation failed unexpectedly: %s", generation_id
                )
            finally:
                self._queue.task_done()

    async def _process(self, generation_id: str) -> None:
        row = query_one("SELECT * FROM generations WHERE id = ?", (generation_id,))
        if not row or row["status"] != "queued":
            return

        params: dict[str, Any] = json.loads(row["params_json"] or "{}")
        engine_id = row["engine_id"] or settings.default_engine
        engine = self.registry.get(engine_id) or self.registry.get("mock")
        if engine is None:
            self._finish(generation_id, "failed", "لا يوجد محرّك متاح", "engine")
            return

        project = query_one("SELECT * FROM projects WHERE id = ?", (row["project_id"],))
        if not project:
            self._finish(generation_id, "failed", "المشروع غير موجود", "project")
            return

        seed = row["seed"]
        if seed is None:
            seed = random.randint(0, 2**31 - 1)

        width = int(params.get("width") or 832)
        height = int(params.get("height") or 480)
        fps = int(params.get("fps") or 24)
        seconds = float(params.get("seconds") or 4)
        frames = max(8, int(seconds * fps))

        output_dir = storage.generation_dir(row["project_id"], generation_id)
        job = EngineJob(
            generation_id=generation_id,
            project_id=row["project_id"],
            type=row["type"],
            prompt=row["prompt"] or "",
            negative_prompt=row["negative_prompt"] or "",
            params=params,
            width=width,
            height=height,
            fps=fps,
            frames=frames,
            seed=seed,
            output_dir=output_dir,
            image_path=self._asset_path(params.get("image_asset_id")),
            video_path=self._asset_path(params.get("video_asset_id")),
            audio_path=self._asset_path(params.get("audio_asset_id")),
        )

        execute(
            "UPDATE generations SET status='running', started_at=?, seed=?, progress=0.01 WHERE id=?",
            (now_iso(), seed, generation_id),
        )

        try:
            engine_job_id = await engine.submit(job)
            self._active[generation_id] = engine_job_id
            self._active_engines[generation_id] = engine
            execute(
                "UPDATE generations SET engine_job_id=? WHERE id=?",
                (engine_job_id, generation_id),
            )
        except Exception as exc:
            self._cleanup(generation_id)
            self._finish(generation_id, "failed", str(exc), "submit")
            return

        loop = asyncio.get_running_loop()
        deadline = loop.time() + 60 * 60
        last_progress = 0.0
        while True:
            if loop.time() > deadline:
                await engine.cancel(engine_job_id)
                self._cleanup(generation_id)
                self._finish(
                    generation_id, "failed", "تجاوزت المهمة ساعة كاملة", "timeout"
                )
                return

            current = query_one(
                "SELECT status FROM generations WHERE id = ?", (generation_id,)
            )
            if not current or current["status"] == "canceled":
                await engine.cancel(engine_job_id)
                self._cleanup(generation_id)
                return

            progress = await engine.poll(engine_job_id)
            last_progress = max(last_progress, min(1.0, progress.progress))
            execute(
                "UPDATE generations SET progress=?, status='running' WHERE id=?",
                (round(last_progress, 3), generation_id),
            )

            if progress.state == "failed":
                self._cleanup(generation_id)
                self._finish(
                    generation_id,
                    "failed",
                    progress.error or progress.message or "فشل التوليد",
                    "engine",
                )
                return
            if progress.state == "canceled":
                execute(
                    "UPDATE generations SET status='canceled' WHERE id=?",
                    (generation_id,),
                )
                self._cleanup(generation_id)
                return
            if progress.state == "completed":
                break
            await asyncio.sleep(1.0)

        execute(
            "UPDATE generations SET status='postprocessing', progress=0.99 WHERE id=?",
            (generation_id,),
        )
        try:
            artifacts = await engine.fetch(engine_job_id)
        except Exception as exc:
            self._cleanup(generation_id)
            self._finish(generation_id, "failed", str(exc), "fetch")
            return

        saved: list[dict[str, Any]] = []
        for artifact in artifacts:
            if not artifact.data and not artifact.path:
                continue
            saved.append(
                storage.save_artifact(row["project_id"], generation_id, artifact)
            )

        video_records = [a for a in saved if a["kind"] == "video"]
        if video_records and not any(a["kind"] == "thumbnail" for a in saved):
            video = storage.asset_path(video_records[0]["path"])
            thumb = settings.thumbnails_dir / f"{generation_id}.jpg"
            if await media.make_thumbnail(video, thumb):
                asset = self._register_thumbnail(row["project_id"], generation_id, thumb)
                if asset:
                    saved.append(asset)

        self._cleanup(generation_id)
        if not saved:
            self._finish(generation_id, "failed", "لم يُنتج المحرّك أي ملف", "empty")
            return

        execute(
            "UPDATE generations SET status='completed', progress=1, finished_at=? WHERE id=?",
            (now_iso(), generation_id),
        )

    def _register_thumbnail(
        self, project_id: str, generation_id: str, thumb: Path
    ) -> dict[str, Any] | None:
        try:
            relative = thumb.resolve().relative_to(settings.data_dir.resolve()).as_posix()
        except ValueError:
            return None
        asset_id = new_id("asset")
        execute(
            """INSERT INTO assets(id, project_id, generation_id, kind, path, mime,
               width, height, duration_s, size_bytes, meta_json, created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                asset_id,
                project_id,
                generation_id,
                "thumbnail",
                relative,
                "image/jpeg",
                None,
                None,
                None,
                thumb.stat().st_size,
                "{}",
                now_iso(),
            ),
        )
        return query_one("SELECT * FROM assets WHERE id = ?", (asset_id,))

    def _asset_path(self, asset_id: str | None) -> Path | None:
        if not asset_id:
            return None
        row = query_one("SELECT path FROM assets WHERE id = ?", (asset_id,))
        if not row:
            return None
        try:
            return storage.asset_path(row["path"])
        except ValueError:
            return None

    def _cleanup(self, generation_id: str) -> None:
        self._active.pop(generation_id, None)
        self._active_engines.pop(generation_id, None)

    def _finish(self, generation_id: str, status: str, detail: str, stage: str) -> None:
        execute(
            """UPDATE generations SET status=?, error_stage=?, error_detail=?,
               progress=?, finished_at=? WHERE id=?""",
            (
                status,
                stage,
                detail[:1500],
                0.0 if status == "failed" else 1.0,
                now_iso(),
                generation_id,
            ),
        )

    # ------------------------------------------------------------------ cancel
    async def cancel(self, generation_id: str) -> bool:
        row = query_one(
            "SELECT status FROM generations WHERE id = ?", (generation_id,)
        )
        if not row or row["status"] in {"completed", "failed", "canceled"}:
            return False
        execute(
            "UPDATE generations SET status='canceled', finished_at=? WHERE id=?",
            (now_iso(), generation_id),
        )
        engine = self._active_engines.get(generation_id)
        engine_job_id = self._active.get(generation_id)
        if engine is not None and engine_job_id:
            try:
                await engine.cancel(engine_job_id)
            except Exception:
                pass
        return True
