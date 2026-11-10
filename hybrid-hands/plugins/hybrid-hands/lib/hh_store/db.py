"""SQLite schema, open/rebuild policy and meta helpers."""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Optional

from .paths import FILE_MODE, state_dir

SCHEMA_VERSION = 1
PARSER_VERSION = 1
DB_NAME = "hh-store.sqlite3"
BUSY_TIMEOUT_MS = 5000
DB_SIDE_SUFFIXES = ("", "-wal", "-shm", "-journal")
# Tables whose rows belong to a files.file_id (cleared on generation change / forget).
DATA_TABLES = ("codex_records", "claude_messages")

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS files(
  file_id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, scope TEXT NOT NULL,
  dev INTEGER, inode INTEGER, generation INTEGER NOT NULL DEFAULT 0,
  offset INTEGER NOT NULL DEFAULT 0, size INTEGER, mtime_ns INTEGER,
  parser_version INTEGER, status TEXT NOT NULL DEFAULT 'ok');
CREATE INDEX IF NOT EXISTS files_scope ON files(scope);
CREATE TABLE IF NOT EXISTS codex_records(
  file_id INTEGER NOT NULL, generation INTEGER NOT NULL, byte_offset INTEGER NOT NULL,
  thread_id TEXT, kind TEXT, observed_at REAL, event_hash TEXT, payload_json TEXT,
  PRIMARY KEY(file_id, generation, byte_offset));
CREATE TABLE IF NOT EXISTS claude_messages(
  account TEXT NOT NULL, scope TEXT NOT NULL, message_id TEXT NOT NULL,
  request_id TEXT NOT NULL, file_id INTEGER, at REAL, model TEXT,
  input INTEGER, cached_input INTEGER, output INTEGER,
  cache_write_5m INTEGER, cache_write_1h INTEGER,
  PRIMARY KEY(account, scope, message_id, request_id));
CREATE TABLE IF NOT EXISTS claude_calibration(
  account TEXT PRIMARY KEY, plan TEXT, usd_per_week_pct REAL, samples INTEGER, updated_at REAL);
CREATE TABLE IF NOT EXISTS json_sources(path TEXT PRIMARY KEY, stamp TEXT, payload_json TEXT);
"""


def _connect(path: Path) -> sqlite3.Connection:
    fd = os.open(path, os.O_RDWR | os.O_CREAT, FILE_MODE)
    os.close(fd)
    os.chmod(path, FILE_MODE)
    conn = sqlite3.connect(str(path), timeout=BUSY_TIMEOUT_MS / 1000)
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _meta(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: object) -> None:
    conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)", (key, str(value)))


def _is_healthy(conn: sqlite3.Connection) -> bool:
    if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        return False
    has_meta = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone()
    if not has_meta:  # fresh file: schema will be created
        return conn.execute("SELECT count(*) FROM sqlite_master").fetchone()[0] == 0
    return (_meta(conn, "schema_version") == str(SCHEMA_VERSION)
            and _meta(conn, "parser_version") == str(PARSER_VERSION))


def _remove_db(path: Path) -> None:
    for suffix in DB_SIDE_SUFFIXES:
        try:
            os.unlink(f"{path}{suffix}")
        except FileNotFoundError:
            pass


def _init(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    with conn:
        set_meta(conn, "schema_version", SCHEMA_VERSION)
        set_meta(conn, "parser_version", PARSER_VERSION)


def open_store(path: Optional[Path] = None) -> sqlite3.Connection:
    """Open the store, rebuilding it on corruption or version mismatch."""
    db_path = Path(path) if path else state_dir() / DB_NAME
    try:
        conn = _connect(db_path)
        if _is_healthy(conn):
            _init(conn)
            return conn
        conn.close()
    except sqlite3.DatabaseError:
        pass
    _remove_db(db_path)
    conn = _connect(db_path)
    _init(conn)
    return conn


def mark_read(conn: sqlite3.Connection) -> None:
    """Record a reader heartbeat (indexer exits when it goes stale)."""
    with conn:
        set_meta(conn, "last_read_at", time.time())
