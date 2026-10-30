from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from .base import EngineArtifact, EngineHealth, EngineJob, EngineProgress

_MIME = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".gif": "image/gif",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
}


class HFSpaceEngine:
    """Experimental adapter for public Hugging Face Spaces (Gradio API).

    Space signatures differ, so the caller supplies positional arguments in
    ``params.extra.hf_args`` (or the sensible default below). Expect queues and
    quotas; this is a fallback, not the primary engine.
    """

    id = "hfspace"
    label = "Hugging Face Space (تجريبي)"
    capabilities = set({"text2video", "image2video"})

    def __init__(self, space_id: str, api_name: str = "/generate") -> None:
        self.space_id = space_id.strip()
        self.api_name = api_name.strip() or "/generate"
        self._results: dict[str, Any] = {}
        self._errors: dict[str, str] = {}

    def _client(self):
        try:
            from gradio_client import Client  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "حزمة gradio_client غير مثبّتة. نفّذ: pip install gradio_client"
            ) from exc
        return Client(self.space_id)

    async def health(self) -> EngineHealth:
        if not self.space_id:
            return EngineHealth(
                ready=False, detail="أضف معرّف Space في الإعدادات (user/space-name)"
            )
        try:
            await asyncio.wait_for(
                asyncio.to_thread(lambda: self._client().view_api()), timeout=25
            )
            return EngineHealth(ready=True, detail=f"Space متاح: {self.space_id}")
        except Exception as exc:
            return EngineHealth(ready=False, detail=f"تعذّر الاتصال: {exc}")

    async def submit(self, job: EngineJob) -> str:
        engine_job_id = f"hf_{uuid.uuid4().hex[:10]}"
        extra = job.params.get("extra", {}) or {}
        args = extra.get("hf_args") or [
            job.prompt,
            job.negative_prompt,
            job.seed,
        ]
        api_name = extra.get("hf_api_name") or self.api_name

        def _run() -> Any:
            client = self._client()
            return client.predict(*args, api_name=api_name)

        try:
            self._results[engine_job_id] = await asyncio.to_thread(_run)
        except Exception as exc:
            self._errors[engine_job_id] = str(exc)
        return engine_job_id

    async def poll(self, engine_job_id: str) -> EngineProgress:
        if engine_job_id in self._errors:
            return EngineProgress(
                state="failed", progress=1.0, error=self._errors.pop(engine_job_id)
            )
        if engine_job_id in self._results:
            return EngineProgress(
                state="completed", progress=1.0, message="اكتمل التوليد"
            )
        return EngineProgress(state="running", progress=0.35, message="يعمل على Space…")

    async def fetch(self, engine_job_id: str) -> list[EngineArtifact]:
        result = self._results.get(engine_job_id)
        if result is None:
            raise RuntimeError("لا توجد نتيجة من Space")

        paths: list[Path] = []

        def _collect(value: Any) -> None:
            if isinstance(value, str):
                p = Path(value)
                if p.exists() and p.is_file():
                    paths.append(p)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    _collect(item)
            elif isinstance(value, dict):
                for item in value.values():
                    _collect(item)

        _collect(result)
        if not paths:
            raise RuntimeError("أعاد Space نتيجة غير قابلة للقراءة")

        artifacts: list[EngineArtifact] = []
        for path in paths[:8]:
            suffix = path.suffix.lower()
            kind = "video" if suffix in {".mp4", ".webm", ".gif"} else (
                "audio" if suffix in {".wav", ".mp3"} else "image"
            )
            artifacts.append(
                EngineArtifact(
                    kind=kind,
                    filename=path.name,
                    data=path.read_bytes(),
                    mime=_MIME.get(suffix, "application/octet-stream"),
                    meta={"engine": "hfspace", "space": self.space_id},
                )
            )
        return artifacts

    async def cancel(self, engine_job_id: str) -> None:
        self._results.pop(engine_job_id, None)
        self._errors.pop(engine_job_id, None)
