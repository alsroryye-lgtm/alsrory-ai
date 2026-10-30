from __future__ import annotations

import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .config import settings

_write_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    aspect_ratio  TEXT NOT NULL DEFAULT '16:9',
    style_preset  TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scenes (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title           TEXT NOT NULL DEFAULT '',
    prompt          TEXT NOT NULL DEFAULT '',
    negative_prompt TEXT NOT NULL DEFAULT '',
    order_index     INTEGER NOT NULL DEFAULT 0,
    duration_s      REAL NOT NULL DEFAULT 5,
    engine          TEXT NOT NULL DEFAULT '',
    settings_json   TEXT NOT NULL DEFAULT '{}',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS generations (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    scene_id        TEXT,
    type            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'queued',
    progress        REAL NOT NULL DEFAULT 0,
    prompt          TEXT NOT NULL DEFAULT '',
    negative_prompt TEXT NOT NULL DEFAULT '',
    params_json     TEXT NOT NULL DEFAULT '{}',
    engine_id       TEXT NOT NULL DEFAULT 'mock',
    engine_job_id   TEXT,
    error_stage     TEXT,
    error_detail    TEXT,
    seed            INTEGER,
    created_at      TEXT NOT NULL,
    started_at      TEXT,
    finished_at     TEXT
);

CREATE TABLE IF NOT EXISTS assets (
    id            TEXT PRIMARY KEY,
    project_id    TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    generation_id TEXT,
    kind          TEXT NOT NULL DEFAULT 'video',
    path          TEXT NOT NULL,
    mime          TEXT NOT NULL DEFAULT '',
    width         INTEGER,
    height        INTEGER,
    duration_s    REAL,
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    meta_json     TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_generations_project ON generations(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_assets_project ON assets(project_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scenes_project ON scenes(project_id, order_index);
"""


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:14]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)


def query(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def query_one(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple[Any, ...] = ()) -> None:
    with _write_lock, connect() as conn:
        conn.execute(sql, params)


def execute_rowcount(sql: str, params: tuple[Any, ...] = ()) -> int:
    with _write_lock, connect() as conn:
        cur = conn.execute(sql, params)
        return cur.rowcount


def get_setting(key: str, default: Any = None) -> Any:
    import json

    row = query_one("SELECT value_json FROM settings WHERE key = ?", (key,))
    if not row:
        return default
    try:
        return json.loads(row["value_json"])
    except Exception:
        return default


def put_setting(key: str, value: Any) -> None:
    import json

    execute(
        """INSERT INTO settings(key, value_json, updated_at) VALUES(?,?,?)
           ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json,
                                          updated_at=excluded.updated_at""",
        (key, json.dumps(value, ensure_ascii=False), now_iso()),
    )


def storage_rel(path: Path) -> str:
    """Store asset paths relative to the data dir so the folder stays portable."""
    try:
        return path.resolve().relative_to(settings.data_dir.resolve()).as_posix()
    except ValueError:
        return str(path)
