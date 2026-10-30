from __future__ import annotations

from .db import init_db
from .engines.registry import EngineRegistry
from .services.jobs import JobQueue

init_db()

registry = EngineRegistry()
queue = JobQueue(registry)
