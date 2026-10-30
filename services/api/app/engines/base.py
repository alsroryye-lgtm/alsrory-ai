from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

EngineState = Literal["running", "completed", "failed", "canceled"]


@dataclass(slots=True)
class EngineJob:
    generation_id: str
    project_id: str
    type: str
    prompt: str
    negative_prompt: str
    params: dict[str, Any]
    width: int
    height: int
    fps: int
    frames: int
    seed: int
    output_dir: Path
    image_path: Path | None = None
    video_path: Path | None = None
    audio_path: Path | None = None


@dataclass(slots=True)
class EngineProgress:
    state: EngineState
    progress: float = 0.0
    message: str = ""
    error: str | None = None


@dataclass(slots=True)
class EngineArtifact:
    kind: str
    filename: str
    mime: str = "video/mp4"
    data: bytes | None = None
    path: Path | None = None
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EngineHealth:
    ready: bool
    detail: str = ""
    latency_ms: int | None = None


@runtime_checkable
class Engine(Protocol):
    id: str
    label: str
    capabilities: set[str]

    async def health(self) -> EngineHealth: ...
    async def submit(self, job: EngineJob) -> str: ...
    async def poll(self, engine_job_id: str) -> EngineProgress: ...
    async def fetch(self, engine_job_id: str) -> list[EngineArtifact]: ...
    async def cancel(self, engine_job_id: str) -> None: ...


VIDEO_TYPES = {
    "text2video",
    "image2video",
    "video2video",
    "avatar",
    "upscale",
    "interpolate",
    "subtitles",
    "audio",
}

ASPECT_SIZES = {
    "16:9": (832, 480),
    "9:16": (480, 832),
    "1:1": (640, 640),
    "4:3": (704, 528),
    "3:4": (528, 704),
}
