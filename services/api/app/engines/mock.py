from __future__ import annotations

import hashlib
import math
import random
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .base import EngineArtifact, EngineHealth, EngineJob, EngineProgress

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _font(size: int) -> ImageFont.ImageFont:
    for path in _FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _palette(seed_text: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    digest = hashlib.sha256(seed_text.encode("utf-8")).digest()
    a = (60 + digest[0] % 120, 40 + digest[1] % 100, 120 + digest[2] % 120)
    b = (20 + digest[3] % 60, 90 + digest[4] % 120, 90 + digest[5] % 120)
    return a, b


@dataclass
class _MockJob:
    job: EngineJob
    path: Path
    state: str = "running"
    progress: float = 0.0
    message: str = "جارٍ تحضير المشهد…"
    error: str | None = None
    started: float = field(default_factory=time.time)
    cancel: threading.Event = field(default_factory=threading.Event)
    thread: threading.Thread | None = None


class MockEngine:
    """Deterministic procedural renderer used for demos and automated tests.

    It produces a real MP4 (H.264) with Pillow + FFmpeg, so the whole pipeline
    (queue, progress, assets, library, editor) is exercised without a GPU.
    """

    id = "mock"
    label = "المحرّك التجريبي (بلا GPU)"
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

    def __init__(self) -> None:
        self._jobs: dict[str, _MockJob] = {}
        self._lock = threading.Lock()

    async def health(self) -> EngineHealth:
        from ..config import settings

        if not settings.ffmpeg:
            return EngineHealth(
                ready=False, detail="FFmpeg غير متاح — ثبّت imageio-ffmpeg أو FFmpeg"
            )
        return EngineHealth(ready=True, detail="جاهز • توليد إجرائي سريع")

    async def submit(self, job: EngineJob) -> str:
        engine_job_id = f"mock_{uuid.uuid4().hex[:10]}"
        job.output_dir.mkdir(parents=True, exist_ok=True)
        path = job.output_dir / "mock.mp4"
        state = _MockJob(job=job, path=path)
        with self._lock:
            self._jobs[engine_job_id] = state
        state.thread = threading.Thread(
            target=self._render, args=(state,), name=f"mock-{engine_job_id}", daemon=True
        )
        state.thread.start()
        return engine_job_id

    def _render(self, state: _MockJob) -> None:
        from ..config import settings

        job = state.job
        try:
            import imageio_ffmpeg

            fps = job.fps
            total_frames = max(8, min(job.frames, 8 * fps))
            width = max(256, job.width - job.width % 8)
            height = max(256, job.height - job.height % 8)
            color_a, color_b = _palette(job.prompt or job.generation_id)
            rng = random.Random(job.seed or 1)
            blobs = [
                (
                    rng.uniform(0, width),
                    rng.uniform(0, height),
                    rng.uniform(0.4, 1.6),
                    rng.uniform(0, math.tau),
                    rng.uniform(40, 140),
                )
                for _ in range(9)
            ]

            writer = imageio_ffmpeg.write_frames(
                str(state.path),
                (width, height),
                fps=fps,
                codec="libx264",
                pix_fmt_in="rgb24",
                pix_fmt_out="yuv420p",
                output_params=["-movflags", "+faststart"],
                macro_block_size=1,
                ffmpeg_log_level="error",
            )
            writer.send(None)

            base = Image.new("RGB", (48, 27))
            pixels = []
            for y in range(27):
                for x in range(48):
                    t = (x / 47 + y / 26) / 2
                    pixels.append(
                        tuple(
                            int(color_a[i] * (1 - t) + color_b[i] * t) for i in range(3)
                        )
                    )
            base.putdata(pixels)
            backdrop = base.resize((width, height), Image.BICUBIC).filter(
                ImageFilter.GaussianBlur(2)
            )

            title_font = _font(max(16, width // 34))
            small_font = _font(max(11, width // 64))
            frame_seconds = 1.0 / fps

            for i in range(total_frames):
                if state.cancel.is_set():
                    state.state = "canceled"
                    state.message = "أُلغيت المهمة"
                    try:
                        writer.close()
                    except Exception:
                        pass
                    return

                frame = backdrop.copy()
                overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                od = ImageDraw.Draw(overlay)
                phase = i / total_frames
                for bx, by, speed, offset, radius in blobs:
                    cx = (bx + math.cos(phase * math.tau * speed + offset) * width * 0.18) % width
                    cy = (by + math.sin(phase * math.tau * speed * 0.7 + offset) * height * 0.16) % height
                    r = radius * (1 + 0.25 * math.sin(phase * math.tau + offset))
                    alpha = int(38 + 42 * (0.5 + 0.5 * math.sin(phase * math.tau * 2 + offset)))
                    od.ellipse(
                        (cx - r, cy - r, cx + r, cy + r),
                        fill=(255, 255, 255, alpha),
                    )
                frame = Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB")

                d = ImageDraw.Draw(frame)
                pad = width // 22
                accent = tuple(min(255, c + 70) for c in color_a)
                d.rectangle(
                    (pad, height - pad - 46, pad + 118, height - pad - 20),
                    fill=accent,
                )
                d.text(
                    (pad + 14, height - pad - 44),
                    "alsrory.AI",
                    font=small_font,
                    fill=(10, 10, 16),
                )
                d.text(
                    (pad, height - pad - 4),
                    f"MOCK ENGINE · {i + 1}/{total_frames}",
                    font=small_font,
                    fill=(235, 235, 245),
                )

                caption = (job.prompt or "مشهد تجريبي").replace("\n", " ").strip()
                if caption:
                    d.text(
                        (pad, pad),
                        caption[:64],
                        font=title_font,
                        fill=(255, 255, 255),
                    )

                writer.send(frame.tobytes())
                state.progress = (i + 1) / total_frames * 0.92
                state.message = f"رسم الإطار {i + 1} من {total_frames}"
                time.sleep(min(0.02, frame_seconds * 0.5))

            writer.close()
            state.progress = 0.97
            state.message = "إنهاء الترميز…"

            poster = Path(job.output_dir) / "mock.jpg"
            base_frame = None
            try:
                import imageio_ffmpeg as _f

                reader = _f.read_frames(str(state.path), pix_fmt="rgb24")
                meta = next(reader)
                raw = next(reader)
                base_frame = Image.frombytes("RGB", (meta["size"][0], meta["size"][1]), raw)
                reader.close()
            except Exception:
                base_frame = backdrop
            base_frame.save(poster, "JPEG", quality=88)

            state.progress = 1.0
            state.state = "completed"
            state.message = "اكتمل التوليد"
        except Exception as exc:  # pragma: no cover - defensive
            state.state = "failed"
            state.error = str(exc)
            state.message = "فشل التوليد"

    async def poll(self, engine_job_id: str) -> EngineProgress:
        state = self._jobs.get(engine_job_id)
        if not state:
            return EngineProgress(state="failed", error="مهمة غير معروفة")
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
            state.thread.join(timeout=120)
        if not state.path.exists():
            raise FileNotFoundError("لم يُنتج المحرّك ملفاً")

        artifacts = [
            EngineArtifact(
                kind="video",
                filename="mock.mp4",
                path=state.path,
                mime="video/mp4",
                width=state.job.width,
                height=state.job.height,
                duration_s=min(state.job.frames / max(1, state.job.fps), 8),
                meta={"engine": "mock", "seed": state.job.seed},
            )
        ]
        poster = Path(state.job.output_dir) / "mock.jpg"
        if poster.exists():
            artifacts.append(
                EngineArtifact(
                    kind="thumbnail",
                    filename="mock.jpg",
                    path=poster,
                    mime="image/jpeg",
                )
            )
        return artifacts

    async def cancel(self, engine_job_id: str) -> None:
        state = self._jobs.get(engine_job_id)
        if state:
            state.cancel.set()
