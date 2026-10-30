from __future__ import annotations

from pathlib import Path

from app.engines.base import EngineJob
from app.engines.hfspace import HFSpaceEngine, _clamp_size


def _job(tmp_path: Path, **overrides) -> EngineJob:
    data = {
        "generation_id": "gen_test",
        "project_id": "proj_test",
        "type": "text2video",
        "prompt": "a lighthouse in a storm, cinematic",
        "negative_prompt": "",
        "params": {},
        "width": 832,
        "height": 480,
        "fps": 24,
        "frames": 48,
        "seed": 42,
        "output_dir": tmp_path,
    }
    data.update(overrides)
    return EngineJob(**data)


def test_text_to_video_args(tmp_path: Path) -> None:
    engine = HFSpaceEngine("Lightricks/ltx-video-distilled", "/text_to_video")
    args = engine._predict_args(_job(tmp_path))

    assert args["mode"] == "text-to-video"
    assert args["prompt"].startswith("a lighthouse")
    assert args["negative_prompt"]  # sensible default when empty
    assert args["duration_ui"] == 2.0
    assert args["seed_ui"] == 42
    assert args["randomize_seed"] is False
    assert args["input_image_filepath"] is None
    assert args["width_ui"] % 32 == 0
    assert args["height_ui"] % 32 == 0


def test_image_to_video_passes_image_path(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"not-a-real-png")
    engine = HFSpaceEngine("Lightricks/ltx-video-distilled")
    args = engine._predict_args(
        _job(tmp_path, type="image2video", image_path=image)
    )

    assert args["mode"] == "image-to-video"
    assert args["input_image_filepath"] == str(image)


def test_duration_is_clamped_to_space_limits(tmp_path: Path) -> None:
    engine = HFSpaceEngine("Lightricks/ltx-video-distilled")
    short = engine._predict_args(_job(tmp_path, frames=8, fps=24))
    long = engine._predict_args(_job(tmp_path, frames=24 * 40, fps=24))

    assert short["duration_ui"] == 1.0
    assert long["duration_ui"] == 8.0


def test_clamp_size_rounds_and_bounds() -> None:
    assert _clamp_size(50) == 256
    assert _clamp_size(5000) == 1280
    assert _clamp_size(850) % 32 == 0
    assert 256 <= _clamp_size(850) <= 1280


def test_first_video_extraction(tmp_path: Path) -> None:
    video = tmp_path / "out.mp4"
    video.write_bytes(b"fake-mp4")

    assert HFSpaceEngine._first_video({"video": str(video), "subtitles": None}) == video
    assert HFSpaceEngine._first_video({"result": [{"path": str(video)}]}) == video
    assert HFSpaceEngine._first_video({"video": str(tmp_path / "missing.mp4")}) is None
    assert HFSpaceEngine._first_video("no-file") is None
