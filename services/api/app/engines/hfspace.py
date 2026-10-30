from __future__ import annotations

import asyncio
import os
import re
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .base import EngineArtifact, EngineHealth, EngineJob, EngineProgress

DEFAULT_SPACE = "Lightricks/ltx-video-distilled"
DEFAULT_API = "/text_to_video"
DEFAULT_NEGATIVE = "worst quality, inconsistent motion, blurry, jittery, distorted"

_ENDPOINT_BY_TYPE = {
    "text2video": "/text_to_video",
    "image2video": "/image_to_video",
    "video2video": "/video_to_video",
}
_MODE_BY_ENDPOINT = {
    "/text_to_video": "text-to-video",
    "/image_to_video": "image-to-video",
    "/video_to_video": "video-to-video",
}

# Hugging Face only hands an anonymous ZeroGPU quota to traffic that looks like
# a same-origin browser call. Without these the Space answers instantly with
# "404: Not Found" / "Session not found" instead of generating anything.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
}

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


@dataclass
class _HFJob:
    job: EngineJob
    state: str = "running"
    progress: float = 0.05
    message: str = "تحضير الطلب…"
    error: str | None = None
    result: Path | None = None
    started: float = field(default_factory=time.time)
    cancel: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None


def _clamp_size(value: int) -> int:
    """LTX wants multiples of 32 within 256..1280."""
    return max(256, min(1280, int(round(value / 32.0)) * 32))


_QUOTA_HINT = (
    "انتهت حصة ZeroGPU المجانية لهذه الشبكة: دقيقتان يومياً بلا حساب، "
    "و5 دقائق مع حساب Hugging Face مجاني"
)


def _humanize_error(exc: Exception) -> str:
    """Turn Gradio/ZeroGPU errors into an actionable Arabic message."""
    detail = str(exc).strip()
    low = detail.lower()

    if "zerogpu quota" in low or "exceeded your gpu quota" in low:
        wait = ""
        match = re.search(r"try again in ([0-9:]+)", detail, re.I)
        if match and match.group(1) not in {"0:00:00", "00:00:00"}:
            wait = f"، وتعود بعد {match.group(1)}"
        return (
            f"{_QUOTA_HINT}{wait}. أضف رمز Hugging Face مجانياً من الإعدادات "
            "لمضاعفة الحصة، أو استخدم دفتر Colab لتوليد أكثر."
        )

    if "session not found" in low or "404: not found" in low:
        return (
            "رفض فضاء Hugging Face الطلب — أعد المحاولة بعد قليل، "
            "أو اختر فضاءً آخر من الإعدادات."
        )

    if "401" in low or "unauthorized" in low or "invalid token" in low:
        return (
            "رمز Hugging Face غير صالح — حدّثه من الإعدادات أو أفرغه "
            "للتوليد بلا رمز."
        )

    if not detail or type(exc).__name__ in {"CancelledError", "TimeoutError"}:
        return (
            "لم يصل ردّ من فضاء Hugging Face. قد تكون حصة ZeroGPU المجانية "
            "انتهت (دقيقتان يومياً بلا حساب، 5 دقائق برمز مجاني) أو حدث انقطاع — "
            "أعد المحاولة لاحقاً."
        )

    return detail


class HFSpaceEngine:
    """Keyless adapter for public Hugging Face Spaces (Gradio API).

    The default Space runs LTX-Video (distilled) on ZeroGPU: it needs no API
    key, but the prompt/image leaves your machine and anonymous GPU quotas
    apply. Swap ``hf_space_id`` / ``hf_api_name`` for any Space exposing a
    compatible signature.
    """

    id = "hfspace"
    label = "Hugging Face — مجاني بلا مفتاح"
    capabilities = {"text2video", "image2video"}

    def __init__(
        self,
        space_id: str = DEFAULT_SPACE,
        api_name: str = DEFAULT_API,
        token: str = "",
    ) -> None:
        self.space_id = (space_id or DEFAULT_SPACE).strip()
        self.api_name = (api_name or DEFAULT_API).strip()
        self.token = (token or os.getenv("HF_TOKEN", "")).strip()
        self._jobs: dict[str, _HFJob] = {}
        self._lock = threading.Lock()
        self._health: tuple[float, EngineHealth] | None = None

    # ------------------------------------------------------------------ helpers
    def _client(self):
        try:
            from gradio_client import Client  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "مكتبة gradio_client غير مثبتة. شغّل: pip install -r services/api/requirements.txt"
            ) from exc
        return Client(
            self.space_id,
            token=self.token or None,
            verbose=False,
            headers=dict(_BROWSER_HEADERS),
        )

    def _resolve_api(self, job: EngineJob) -> str:
        """Pick the Space endpoint that matches the job type."""
        extra = job.params.get("extra", {}) or {}
        explicit = str(extra.get("hf_api_name") or "").strip()
        if explicit:
            return explicit
        return _ENDPOINT_BY_TYPE.get(job.type, self.api_name or DEFAULT_API)

    def _predict_args(
        self, job: EngineJob, api_name: str = DEFAULT_API
    ) -> dict[str, Any]:
        mode = _MODE_BY_ENDPOINT.get(api_name)
        if mode is None:
            mode = "image-to-video" if job.type == "image2video" else "text-to-video"
        duration = job.frames / max(1, job.fps)

        input_image: Any = None
        if job.type == "image2video" and job.image_path:
            # Gradio expects an uploaded file handle, not a local path string:
            # a bare string is resolved on the Space machine and fails there.
            try:
                from gradio_client import handle_file

                input_image = handle_file(str(job.image_path))
            except Exception:
                input_image = str(job.image_path)

        return {
            "prompt": job.prompt or "a cinematic shot",
            "negative_prompt": job.negative_prompt or DEFAULT_NEGATIVE,
            "input_image_filepath": input_image,
            "input_video_filepath": None,
            "height_ui": _clamp_size(job.height),
            "width_ui": _clamp_size(job.width),
            "mode": mode,
            "duration_ui": max(1.0, min(8.0, round(duration, 2))),
            "ui_frames_to_use": 9,
            "seed_ui": int(job.seed),
            "randomize_seed": False,
            "ui_guidance_scale": 1,
            "improve_texture_flag": True,
        }

    def _predict(self, job: EngineJob) -> Any:
        client = self._client()
        extra = job.params.get("extra", {}) or {}
        api_name = self._resolve_api(job)

        if api_name in _MODE_BY_ENDPOINT:
            return client.predict(api_name=api_name, **self._predict_args(job, api_name))

        args = extra.get("hf_args") or [job.prompt, job.negative_prompt, job.seed]
        return client.predict(*args, api_name=api_name)

    @staticmethod
    def _first_video(value: Any) -> Path | None:
        if isinstance(value, str):
            path = Path(value)
            return path if path.exists() and path.is_file() else None
        if isinstance(value, dict):
            for key in ("video", "path", "name", "file"):
                if key in value:
                    found = HFSpaceEngine._first_video(value[key])
                    if found:
                        return found
            for item in value.values():
                found = HFSpaceEngine._first_video(item)
                if found:
                    return found
        if isinstance(value, (list, tuple)):
            for item in value:
                found = HFSpaceEngine._first_video(item)
                if found:
                    return found
        return None

    def _run(self, state: _HFJob) -> None:
        job = state.job
        try:
            if job.type == "image2video" and (
                not job.image_path or not Path(job.image_path).exists()
            ):
                raise RuntimeError("اختر صورة موجودة أولاً لتوليد فيديو من صورة")

            state.message = "الاتصال بفضاء Hugging Face…"
            state.progress = 0.12
            result = self._predict(job)
            state.progress = 0.92
            state.message = "تنزيل الناتج…"

            produced = self._first_video(result)
            if produced is None:
                raise RuntimeError(
                    "أعاد الفضاء نتيجة بلا ملف فيديو — تحقّق من نوع المهمة أو الـ API"
                )

            job.output_dir.mkdir(parents=True, exist_ok=True)
            suffix = produced.suffix or ".mp4"
            target = job.output_dir / f"hf{suffix}"
            if produced.resolve() != target.resolve():
                if produced.parent.resolve() == job.output_dir.resolve():
                    target = produced
                else:
                    shutil.move(str(produced), str(target))

            state.result = target
            state.progress = 1.0
            state.state = "completed"
            state.message = "اكتمل التوليد"
        except Exception as exc:
            state.state = "failed"
            state.error = _humanize_error(exc)
            state.message = "فشل التوليد"

    # ------------------------------------------------------------------- engine
    async def health(self) -> EngineHealth:
        if not self.space_id:
            return EngineHealth(ready=False, detail="لم يُضبط فضاء Hugging Face")

        now = time.time()
        if self._health and now - self._health[0] < 120:
            return self._health[1]

        started = time.perf_counter()

        def _probe() -> None:
            self._client().view_api(print_info=False, return_format="dict")

        try:
            await asyncio.wait_for(asyncio.to_thread(_probe), timeout=45)
            latency = int((time.perf_counter() - started) * 1000)
            health = EngineHealth(
                ready=True, detail=f"الفضاء جاهز: {self.space_id}", latency_ms=latency
            )
        except Exception as exc:
            health = EngineHealth(
                ready=False, detail=f"تعذّر الوصول إلى الفضاء: {exc}"
            )
        self._health = (now, health)
        return health

    async def submit(self, job: EngineJob) -> str:
        engine_job_id = f"hf_{uuid.uuid4().hex[:10]}"
        state = _HFJob(job=job)
        with self._lock:
            self._jobs[engine_job_id] = state
        state.thread = threading.Thread(
            target=self._run,
            args=(state,),
            name=f"hfspace-{engine_job_id}",
            daemon=True,
        )
        state.thread.start()
        return engine_job_id

    async def poll(self, engine_job_id: str) -> EngineProgress:
        state = self._jobs.get(engine_job_id)
        if not state:
            return EngineProgress(state="failed", error="مهمة غير معروفة")
        if state.state == "running":
            elapsed = time.time() - state.started
            state.progress = max(state.progress, min(0.9, 0.12 + elapsed / 240 * 0.78))
        return EngineProgress(
            state=state.state,  # type: ignore[arg-type]
            progress=round(min(1.0, max(0.0, state.progress)), 3),
            message=state.message,
            error=state.error,
        )

    async def fetch(self, engine_job_id: str) -> list[EngineArtifact]:
        state = self._jobs.get(engine_job_id)
        if not state:
            raise KeyError(engine_job_id)
        if state.thread:
            state.thread.join(timeout=300)
        if not state.result or not state.result.exists():
            raise FileNotFoundError(state.error or "لم يُنتج الفضاء ملفاً")

        width: int | None = None
        height: int | None = None
        duration: float | None = None
        try:
            import imageio_ffmpeg

            reader = imageio_ffmpeg.read_frames(str(state.result))
            meta = next(reader)
            reader.close()
            size = meta.get("size")
            if size:
                width, height = int(size[0]), int(size[1])
            if meta.get("duration"):
                duration = float(meta["duration"])
        except Exception:
            duration = min(8.0, state.job.frames / max(1, state.job.fps))

        return [
            EngineArtifact(
                kind="video",
                filename=f"{state.job.generation_id}{state.result.suffix or '.mp4'}",
                path=state.result,
                mime=_MIME.get(state.result.suffix.lower(), "video/mp4"),
                width=width,
                height=height,
                duration_s=duration,
                meta={
                    "engine": "hfspace",
                    "space": self.space_id,
                    "seed": state.job.seed,
                },
            )
        ]

    async def cancel(self, engine_job_id: str) -> None:
        state = self._jobs.get(engine_job_id)
        if state:
            state.cancel.set()
            state.state = "canceled"
            state.message = "أُلغيت المهمة"
