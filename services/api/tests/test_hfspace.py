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


def test_image_to_video_uses_image_endpoint(tmp_path: Path) -> None:
    image = tmp_path / "frame.png"
    image.write_bytes(b"not-a-real-png")
    job = _job(tmp_path, type="image2video", image_path=image)
    engine = HFSpaceEngine("Lightricks/ltx-video-distilled")

    assert engine._resolve_api(job) == "/image_to_video"
    args = engine._predict_args(job, engine._resolve_api(job))

    assert args["mode"] == "image-to-video"
    value = args["input_image_filepath"]
    resolved = value.get("path") if isinstance(value, dict) else value
    assert Path(resolved) == image


def test_explicit_api_name_overrides_task_type(tmp_path: Path) -> None:
    engine = HFSpaceEngine("Lightricks/ltx-video-distilled")
    job = _job(tmp_path, params={"extra": {"hf_api_name": "/custom"}})

    assert engine._resolve_api(job) == "/custom"
    assert engine._resolve_api(_job(tmp_path)) == "/text_to_video"


def test_client_sends_browser_headers() -> None:
    from app.engines.hfspace import _BROWSER_HEADERS

    assert _BROWSER_HEADERS["Sec-Fetch-Site"] == "same-origin"
    assert _BROWSER_HEADERS["Accept-Language"]
    assert "Mozilla" in _BROWSER_HEADERS["User-Agent"]


def test_quota_error_is_explained_in_arabic() -> None:
    from app.engines.hfspace import _humanize_error

    message = _humanize_error(
        RuntimeError(
            "You have exceeded your ZeroGPU quota (120s requested vs. -60s left). "
            "Try again in 12:30:00."
        )
    )

    assert "ZeroGPU" in message
    assert "12:30:00" in message
    assert "Colab" in message


def test_empty_error_gets_a_generic_hint() -> None:
    import concurrent.futures

    from app.engines.hfspace import _humanize_error

    assert "Hugging Face" in _humanize_error(concurrent.futures.CancelledError())
    assert _humanize_error(RuntimeError("boom")) == "boom"



def test_account_without_token_reports_anonymous(monkeypatch) -> None:
    import asyncio

    monkeypatch.delenv("HF_TOKEN", raising=False)
    engine = HFSpaceEngine("Lightricks/ltx-video-distilled", token="")
    result = asyncio.run(engine.account())

    assert result["connected"] is False
    assert "رمز" in result["detail"]


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
