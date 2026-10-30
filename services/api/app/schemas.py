from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

GenerationType = Literal[
    "text2video",
    "image2video",
    "video2video",
    "avatar",
    "upscale",
    "interpolate",
    "subtitles",
    "audio",
    "export",
]

JobStatus = Literal[
    "queued", "running", "postprocessing", "completed", "failed", "canceled"
]

AssetKind = Literal["video", "image", "audio", "subtitle", "thumbnail", "export"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    aspect_ratio: str = Field(default="16:9", pattern=r"^(16:9|9:16|1:1|4:3|3:4)$")
    style_preset: str = Field(default="", max_length=80)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    aspect_ratio: str | None = Field(
        default=None, pattern=r"^(16:9|9:16|1:1|4:3|3:4)$"
    )
    style_preset: str | None = Field(default=None, max_length=80)


class GenerationParams(BaseModel):
    width: int = Field(default=832, ge=256, le=4096)
    height: int = Field(default=480, ge=256, le=4096)
    seconds: float = Field(default=4.0, ge=0.5, le=60)
    fps: int = Field(default=24, ge=8, le=60)
    seed: int | None = Field(default=None, ge=0, le=2**31 - 1)
    aspect_ratio: str = Field(default="16:9", pattern=r"^(16:9|9:16|1:1|4:3|3:4)$")
    image_asset_id: str | None = None
    video_asset_id: str | None = None
    audio_asset_id: str | None = None
    motion_strength: float = Field(default=0.5, ge=0, le=1)
    style_preset: str = Field(default="", max_length=80)
    camera_motion: str = Field(default="none", max_length=40)
    extra: dict[str, Any] = Field(default_factory=dict)

    @field_validator("width", "height")
    @classmethod
    def _even(cls, v: int) -> int:
        return v - (v % 8) if v % 8 else v


class GenerationCreate(BaseModel):
    project_id: str
    type: GenerationType = "text2video"
    prompt: str = Field(default="", max_length=4000)
    negative_prompt: str = Field(default="", max_length=2000)
    engine_id: str | None = None
    scene_id: str | None = None
    params: GenerationParams = Field(default_factory=GenerationParams)


class EngineTestRequest(BaseModel):
    engine_id: str


class EngineConfigUpdate(BaseModel):
    default_engine: str | None = None
    comfy_url: str | None = None
    comfy_token: str | None = None
    comfy_workflow: str | None = None
    hf_space_id: str | None = None
    hf_api_name: str | None = None
    hf_token: str | None = None


class PromptEnhanceRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=2000)
    style: str = Field(default="cinematic", max_length=40)


class ExportRequest(BaseModel):
    asset_ids: list[str] = Field(min_length=1, max_length=50)
    aspect_ratio: str = Field(default="16:9", pattern=r"^(16:9|9:16|1:1|4:3|3:4)$")
    filename: str = Field(default="final.mp4", max_length=80)


class ApiMessage(BaseModel):
    ok: bool = True
    message: str = ""
