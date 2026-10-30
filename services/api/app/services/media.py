from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any

from ..config import settings
from ..engines.base import ASPECT_SIZES

ASPECTS = ASPECT_SIZES


def _run(cmd: list[str], timeout: int = 900) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        cmd,
        capture_output=True,
        timeout=timeout,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


async def probe(path: Path) -> dict[str, Any]:
    if not settings.ffprobe:
        return {}

    def _probe() -> dict[str, Any]:
        result = _run(
            [
                settings.ffprobe,  # type: ignore[list-item]
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            timeout=60,
        )
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout.decode("utf-8", "ignore"))

    try:
        return await asyncio.to_thread(_probe)
    except Exception:
        return {}


async def make_thumbnail(video: Path, out: Path, width: int = 640) -> bool:
    if not settings.ffmpeg:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)

    def _thumb() -> bool:
        result = _run(
            [
                settings.ffmpeg,  # type: ignore[list-item]
                "-y",
                "-ss",
                "0.4",
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                f"scale={width}:-2",
                "-q:v",
                "3",
                str(out),
            ],
            timeout=120,
        )
        return result.returncode == 0 and out.exists()

    try:
        return await asyncio.to_thread(_thumb)
    except Exception:
        return False


async def concat_videos(
    inputs: list[Path], out: Path, aspect_ratio: str = "16:9", fps: int = 30
) -> Path:
    if not settings.ffmpeg:
        raise RuntimeError("FFmpeg غير متاح — لا يمكن التصدير")
    if not inputs:
        raise ValueError("لا توجد مقاطع للتصدير")

    width, height = ASPECT_SIZES.get(aspect_ratio, ASPECT_SIZES["16:9"])

    def _concat() -> None:
        cmd: list[str] = [settings.ffmpeg]  # type: ignore[list-item]
        for path in inputs:
            cmd += ["-i", str(path)]

        filters: list[str] = []
        labels: list[str] = []
        for index in range(len(inputs)):
            filters.append(
                f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},"
                f"format=yuv420p[v{index}]"
            )
            labels.append(f"[v{index}]")
        filters.append("".join(labels) + f"concat=n={len(inputs)}:v=1:a=0[v]")

        out.parent.mkdir(parents=True, exist_ok=True)
        cmd += [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-y",
            str(out),
        ]
        result = _run(cmd, timeout=1800)
        if result.returncode != 0:
            tail = result.stderr.decode("utf-8", "ignore")[-800:]
            raise RuntimeError(f"فشل FFmpeg: {tail}")

    await asyncio.to_thread(_concat)
    return out
