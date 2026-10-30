from __future__ import annotations

import asyncio
import copy
import json
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from ..config import PROJECT_ROOT
from .base import EngineArtifact, EngineHealth, EngineJob, EngineProgress

WORKFLOWS_DIR = PROJECT_ROOT / "workers" / "comfy" / "workflows"

_MIME = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".gif": "image/gif",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".flac": "audio/flac",
}


class ComfyEngine:
    """Talks to a ComfyUI instance (local or a Colab/Kaggle tunnel).

    The workflow is user-supplied (exported with *Export (API)*) and filled with
    placeholders, so the adapter stays valid across ComfyUI/model upgrades.
    """

    id = "comfy"
    label = "ComfyUI"
    capabilities = set(
        {
            "text2video",
            "image2video",
            "video2video",
            "avatar",
            "upscale",
            "interpolate",
            "subtitles",
            "audio",
        }
    )

    def __init__(self, url: str, token: str = "", workflow: str = "") -> None:
        self.url = (url or "http://127.0.0.1:8188").rstrip("/")
        self.token = token.strip()
        self.default_workflow = workflow or "workers/comfy/workflows/text2video.json"
        self._started: dict[str, float] = {}

    # ------------------------------------------------------------------ helpers
    def _headers(self) -> dict[str, str]:
        return {"X-Alsrory-Token": self.token} if self.token else {}

    def _client(self, timeout: float = 30) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.url, headers=self._headers(), timeout=timeout
        )

    def _workflow_path(self, job_type: str) -> Path:
        candidate = WORKFLOWS_DIR / f"{job_type}.json"
        if candidate.exists():
            return candidate
        configured = Path(self.default_workflow)
        if not configured.is_absolute():
            configured = PROJECT_ROOT / configured
        # Refuse to silently run a text2video workflow for another task type.
        if job_type != "text2video" and configured.name == "text2video.json":
            raise FileNotFoundError(
                f"لا يوجد Workflow للنوع «{job_type}». صدّر ملفاً من ComfyUI "
                f"(Export API) واحفظه باسم workers/comfy/workflows/{job_type}.json"
            )
        return configured

    def _fill(self, node: Any, values: dict[str, Any]) -> Any:
        if isinstance(node, dict):
            return {k: self._fill(v, values) for k, v in node.items()}
        if isinstance(node, list):
            return [self._fill(v, values) for v in node]
        if isinstance(node, str):
            stripped = node.strip()
            for key, value in values.items():
                token = "{{" + key + "}}"
                if stripped == token:
                    return value
                if token in node:
                    node = node.replace(token, str(value))
            return node
        return node

    async def _upload_image(self, client: httpx.AsyncClient, path: Path) -> str:
        with path.open("rb") as fh:
            resp = await client.post(
                "/upload/image",
                files={"image": (path.name, fh, "application/octet-stream")},
                data={"overwrite": "true"},
            )
        resp.raise_for_status()
        payload = resp.json()
        name = payload.get("name", path.name)
        subfolder = payload.get("subfolder", "")
        return f"{subfolder}/{name}" if subfolder else name

    # ------------------------------------------------------------------ protocol
    async def health(self) -> EngineHealth:
        started = time.perf_counter()
        try:
            async with self._client(timeout=6) as client:
                resp = await client.get("/system_stats")
                resp.raise_for_status()
            return EngineHealth(
                ready=True,
                detail=f"متصل بـ {self.url}",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return EngineHealth(
                ready=False,
                detail=f"تعذّر الوصول إلى {self.url}: {exc.__class__.__name__}",
            )

    async def submit(self, job: EngineJob) -> str:
        workflow_path = self._workflow_path(job.type)
        if not workflow_path.exists():
            raise FileNotFoundError(
                f"لا يوجد Workflow في {workflow_path}. صدّر واحداً من ComfyUI (Export API)."
            )
        template = json.loads(workflow_path.read_text(encoding="utf-8"))

        client_id = uuid.uuid4().hex
        async with self._client() as client:
            image_ref = ""
            if job.image_path and job.image_path.exists():
                image_ref = await self._upload_image(client, job.image_path)

            values = {
                "prompt": job.prompt,
                "negative": job.negative_prompt,
                "negative_prompt": job.negative_prompt,
                "width": job.width,
                "height": job.height,
                "frames": job.frames,
                "fps": job.fps,
                "seed": job.seed,
                "seconds": job.params.get("seconds", 4),
                "image": image_ref,
                "motion_strength": job.params.get("motion_strength", 0.5),
                "generation_id": job.generation_id,
            }
            workflow = self._fill(copy.deepcopy(template), values)

            resp = await client.post(
                "/prompt", json={"prompt": workflow, "client_id": client_id}
            )
            if resp.status_code >= 400:
                raise RuntimeError(f"ComfyUI رفض الـ workflow: {resp.text[:500]}")
            prompt_id = resp.json().get("prompt_id")
            if not prompt_id:
                raise RuntimeError("ComfyUI لم يُرجع prompt_id")

        self._started[prompt_id] = time.time()
        return prompt_id

    async def poll(self, engine_job_id: str) -> EngineProgress:
        elapsed = time.time() - self._started.get(engine_job_id, time.time())
        try:
            async with self._client(timeout=15) as client:
                hist = await client.get(f"/history/{engine_job_id}")
                if hist.status_code == 200:
                    data = hist.json().get(engine_job_id)
                    if data:
                        status = data.get("status", {})
                        if status.get("status_str") == "error":
                            messages = status.get("messages", [])
                            detail = "فشل تنفيذ الـ workflow داخل ComfyUI"
                            for item in messages:
                                if isinstance(item, list) and item and item[0] == "execution_error":
                                    detail = str(item[1].get("exception_message", detail))
                            return EngineProgress(
                                state="failed", progress=1.0, error=detail
                            )
                        return EngineProgress(
                            state="completed", progress=1.0, message="اكتمل التوليد"
                        )

                queue = await client.get("/queue")
                if queue.status_code == 200:
                    body = queue.json()
                    running = [row[1] for row in body.get("queue_running", []) if len(row) > 1]
                    pending = [row[1] for row in body.get("queue_pending", []) if len(row) > 1]
                    if engine_job_id in running:
                        # ComfyUI exposes no percentage; use a gentle time-based estimate.
                        progress = min(0.9, 0.08 + elapsed / 240)
                        return EngineProgress(
                            state="running",
                            progress=round(progress, 3),
                            message=f"قيد التنفيذ داخل ComfyUI · {int(elapsed)} ث",
                        )
                    if engine_job_id in pending:
                        return EngineProgress(
                            state="running", progress=0.04, message="في طابور ComfyUI"
                        )
        except Exception as exc:
            return EngineProgress(
                state="running",
                progress=min(0.9, 0.08 + elapsed / 240),
                message=f"تعذّر قراءة الحالة ({exc.__class__.__name__}) — إعادة المحاولة",
            )

        return EngineProgress(
            state="running", progress=0.02, message="بانتظار بدء التنفيذ…"
        )

    async def fetch(self, engine_job_id: str) -> list[EngineArtifact]:
        async with self._client(timeout=30) as client:
            hist = await client.get(f"/history/{engine_job_id}")
            hist.raise_for_status()
            entry = hist.json().get(engine_job_id)
            if not entry:
                raise RuntimeError("لا يوجد سجل للمهمة في ComfyUI")

            files: list[dict[str, Any]] = []
            for node_output in entry.get("outputs", {}).values():
                for key in ("gifs", "videos", "images", "audio", "files"):
                    for item in node_output.get(key, []) or []:
                        if isinstance(item, dict) and item.get("filename"):
                            files.append(item)

            if not files:
                raise RuntimeError("انتهت المهمة لكن ComfyUI لم يُرجع أي ملف")

            artifacts: list[EngineArtifact] = []
            for item in files:
                resp = await client.get(
                    "/view",
                    params={
                        "filename": item["filename"],
                        "subfolder": item.get("subfolder", ""),
                        "type": item.get("type", "output"),
                    },
                )
                resp.raise_for_status()
                suffix = Path(item["filename"]).suffix.lower()
                kind = "video" if suffix in {".mp4", ".webm", ".mov", ".gif"} else (
                    "audio" if suffix in {".wav", ".mp3", ".flac"} else "image"
                )
                artifacts.append(
                    EngineArtifact(
                        kind=kind,
                        filename=item["filename"],
                        data=resp.content,
                        mime=_MIME.get(suffix, "application/octet-stream"),
                        meta={"node": item.get("type", "")},
                    )
                )
            return artifacts

    async def cancel(self, engine_job_id: str) -> None:
        try:
            async with self._client(timeout=10) as client:
                await client.post("/queue", json={"delete": [engine_job_id]})
                await client.post("/interrupt", json={"prompt_id": engine_job_id})
        except Exception:
            pass
