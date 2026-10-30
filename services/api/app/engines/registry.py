from __future__ import annotations

import asyncio
from typing import Any

from ..config import settings
from ..db import get_setting
from .base import Engine
from .comfy import ComfyEngine
from .hfspace import HFSpaceEngine
from .mock import MockEngine


class EngineRegistry:
    def __init__(self) -> None:
        self._mock = MockEngine()
        self._engines: dict[str, Engine] = {"mock": self._mock}
        self.default_id = "mock"
        self.refresh()

    # ------------------------------------------------------------------ config
    def config(self) -> dict[str, Any]:
        stored = get_setting("engine_config", {}) or {}
        return {
            "default_engine": stored.get("default_engine") or settings.default_engine,
            "comfy_url": stored.get("comfy_url") or settings.comfy_url,
            "comfy_token": (
                stored.get("comfy_token")
                if stored.get("comfy_token") is not None
                else settings.comfy_token
            ),
            "comfy_workflow": stored.get("comfy_workflow")
            or settings.comfy_workflow,
            "hf_space_id": (
                stored.get("hf_space_id")
                if stored.get("hf_space_id") is not None
                else settings.hf_space_id
            ),
            "hf_api_name": stored.get("hf_api_name") or settings.hf_api_name,
        }

    def refresh(self) -> None:
        cfg = self.config()
        self._engines = {
            "mock": self._mock,
            "comfy": ComfyEngine(
                url=cfg["comfy_url"],
                token=cfg["comfy_token"] or "",
                workflow=cfg["comfy_workflow"] or "",
            ),
        }
        if cfg["hf_space_id"]:
            self._engines["hfspace"] = HFSpaceEngine(
                cfg["hf_space_id"], cfg["hf_api_name"] or "/generate"
            )
        self.default_id = cfg["default_engine"]
        if self.default_id not in self._engines:
            self.default_id = "mock"

    # ------------------------------------------------------------------ access
    def get(self, engine_id: str | None) -> Engine | None:
        if not engine_id:
            return self._engines.get(self.default_id)
        return self._engines.get(engine_id)

    def resolve(self, generation_type: str, preferred: str | None) -> Engine:
        engine = self.get(preferred)
        if engine and generation_type in engine.capabilities:
            return engine
        fallback = self._engines.get(self.default_id)
        if fallback and generation_type in fallback.capabilities:
            return fallback
        for candidate in self._engines.values():
            if generation_type in candidate.capabilities:
                return candidate
        return self._mock

    def list(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for engine in self._engines.values():
            items.append(
                {
                    "id": engine.id,
                    "label": engine.label,
                    "capabilities": sorted(engine.capabilities),
                    "is_default": engine.id == self.default_id,
                    "configured": engine.id != "hfspace" or bool(
                        self.config()["hf_space_id"]
                    ),
                }
            )
        return items

    async def health_all(self) -> list[dict[str, Any]]:
        async def _one(engine: Engine) -> dict[str, Any]:
            try:
                health = await asyncio.wait_for(engine.health(), timeout=20)
                return {
                    "id": engine.id,
                    "ready": health.ready,
                    "detail": health.detail,
                    "latency_ms": health.latency_ms,
                }
            except Exception as exc:
                return {
                    "id": engine.id,
                    "ready": False,
                    "detail": f"{exc.__class__.__name__}: {exc}",
                }

        results = await asyncio.gather(*(_one(e) for e in self._engines.values()))
        return list(results)
