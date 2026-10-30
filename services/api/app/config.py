from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
API_DIR = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    """Minimal .env loader (no dependency, never overrides real env vars)."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(API_DIR / ".env")


def _resolve(value: str, base: Path) -> Path:
    p = Path(value)
    return (base / p).resolve() if not p.is_absolute() else p


def _find_ffmpeg() -> str | None:
    explicit = os.getenv("FFMPEG_PATH", "").strip()
    if explicit and Path(explicit).exists():
        return explicit
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _find_ffprobe() -> str | None:
    explicit = os.getenv("FFPROBE_PATH", "").strip()
    if explicit and Path(explicit).exists():
        return explicit
    return shutil.which("ffprobe")


@dataclass(slots=True)
class Settings:
    host: str = os.getenv("API_HOST", "127.0.0.1")
    port: int = int(os.getenv("API_PORT", "8787"))
    data_dir: Path = field(
        default_factory=lambda: _resolve(os.getenv("DATA_DIR", "data"), PROJECT_ROOT)
    )
    default_engine: str = os.getenv("DEFAULT_ENGINE", "mock").strip() or "mock"
    max_concurrent_jobs: int = max(1, int(os.getenv("MAX_CONCURRENT_JOBS", "1")))
    allowed_origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in os.getenv(
                "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
            ).split(",")
            if o.strip()
        ]
    )
    comfy_url: str = os.getenv("COMFY_URL", "http://127.0.0.1:8188").rstrip("/")
    comfy_token: str = os.getenv("COMFY_TOKEN", "").strip()
    comfy_workflow: str = os.getenv(
        "COMFY_WORKFLOW", "workers/comfy/workflows/text2video.json"
    )
    hf_space_id: str = os.getenv("HF_SPACE_ID", "Lightricks/ltx-video-distilled").strip()
    hf_api_name: str = os.getenv("HF_API_NAME", "/text_to_video").strip()
    hf_token: str = os.getenv("HF_TOKEN", "").strip()

    # runtime-only
    ffmpeg: str | None = field(default_factory=_find_ffmpeg)
    ffprobe: str | None = field(default_factory=_find_ffprobe)

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def thumbnails_dir(self) -> Path:
        return self.data_dir / "thumbnails"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "alsrory.db"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
