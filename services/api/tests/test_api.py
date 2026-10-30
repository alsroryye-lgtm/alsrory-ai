from __future__ import annotations

import os
import tempfile
import time

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="alsrory-test-")
os.environ["DEFAULT_ENGINE"] = "mock"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def _wait(client: TestClient, generation_id: str, timeout: float = 90) -> dict:
    deadline = time.time() + timeout
    data: dict = {}
    while time.time() < deadline:
        data = client.get(f"/api/generations/{generation_id}").json()
        if data["status"] in {"completed", "failed", "canceled"}:
            return data
        time.sleep(0.5)
    return data


def test_health_and_ffmpeg() -> None:
    with TestClient(app) as client:
        health = client.get("/api/health").json()
        assert health["ok"] is True
        assert health["ffmpeg"] is True
        assert "mock" in health["engines"]


def test_full_generation_flow() -> None:
    with TestClient(app) as client:
        project = client.post(
            "/api/projects",
            json={
                "name": "اختبار عربي",
                "description": "مشروع للتحقق من الترميز",
                "aspect_ratio": "16:9",
                "style_preset": "cinematic",
            },
        ).json()
        assert project["name"] == "اختبار عربي"
        assert project["aspect_ratio"] == "16:9"

        created = client.post(
            "/api/generations",
            json={
                "project_id": project["id"],
                "type": "text2video",
                "prompt": "مدينة عربية قديمة عند الغروب",
                "params": {
                    "width": 832,
                    "height": 480,
                    "seconds": 2,
                    "fps": 24,
                    "aspect_ratio": "16:9",
                },
            },
        )
        assert created.status_code == 202, created.text
        generation = created.json()
        assert generation["engine_id"] == "mock"

        final = _wait(client, generation["id"])
        assert final["status"] == "completed", final.get("error_detail")
        assert final["progress"] == 1
        kinds = {asset["kind"] for asset in final["assets"]}
        assert "video" in kinds

        video = next(a for a in final["assets"] if a["kind"] == "video")
        file_response = client.get(video["url"])
        assert file_response.status_code == 200
        assert len(file_response.content) > 10_000
        assert file_response.headers["content-type"].startswith("video/")

        project_after = client.get(f"/api/projects/{project['id']}").json()
        assert project_after["generation_count"] == 1
        assert len(project_after["assets"]) >= 2

        export = client.post(
            "/api/exports",
            json={
                "asset_ids": [video["id"]],
                "aspect_ratio": "16:9",
                "filename": "smoke.mp4",
            },
        )
        assert export.status_code == 201, export.text
        exported = export.json()
        assert exported["kind"] == "export"
        assert client.get(exported["url"]).status_code == 200


def test_prompt_enhance_and_settings() -> None:
    with TestClient(app) as client:
        result = client.post(
            "/api/prompts/enhance",
            json={"prompt": "قطة تجلس على النافذة", "style": "cinematic"},
        ).json()
        assert "قطة" in result["prompt"]
        assert result["negative_prompt"]
        assert isinstance(result["tips"], list)

        settings = client.get("/api/settings").json()
        assert "available_engines" in settings
        updated = client.put(
            "/api/settings", json={"default_engine": "mock"}
        ).json()
        assert updated["default_engine"] == "mock"
