"""Incremental JSONL tailing and small JSON source caching."""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence

from . import db

LINE_END = b"\n"
ParseLine = Callable[[str, int, int, int], Iterable[tuple[str, dict]]]

_lib = Path(__file__).resolve().parent.parent
if str(_lib) not in sys.path:
    sys.path.insert(0, str(_lib))
from shared_config import file_stamp  # noqa: E402


def _file_row(conn: sqlite3.Connection, path: str) -> Optional[tuple]:
    return conn.execute("SELECT file_id, dev, inode, generation, offset FROM files WHERE path=?",
                        (path,)).fetchone()


def _clear_rows(conn: sqlite3.Connection, file_id: int, tables: Sequence[str]) -> None:
    for table in tables:
        if table not in db.DATA_TABLES:
            raise ValueError(f"unknown data table: {table}")
        conn.execute(f"DELETE FROM {table} WHERE file_id=?", (file_id,))


def _insert(conn: sqlite3.Connection, table: str, row: dict) -> None:
    if table not in db.DATA_TABLES:
        raise ValueError(f"unknown data table: {table}")
    cols = list(row)
    conn.execute(f"INSERT OR REPLACE INTO {table}({','.join(cols)}) "
                 f"VALUES({','.join('?' * len(cols))})", [row[c] for c in cols])


def _ensure_file(conn: sqlite3.Connection, path: str, scope: str) -> tuple:
    row = _file_row(conn, path)
    if row is None:
        conn.execute("INSERT INTO files(path, scope) VALUES(?, ?)", (path, scope))
        row = _file_row(conn, path)
    return row


def _complete_chunk(path: str, offset: int) -> bytes:
    with open(path, "rb") as fh:
        fh.seek(offset)
        data = fh.read()
    end = data.rfind(LINE_END)
    return data[: end + 1] if end >= 0 else b""


def read_appended(conn: sqlite3.Connection, path: str | os.PathLike, scope: str,
                  parse_line: ParseLine, tables: Sequence[str] = db.DATA_TABLES) -> int:
    """Ingest newly appended complete lines of `path`; returns lines processed.

    Rotation (new dev/inode) or truncation bumps generation, clears the file's rows
    in `tables` and rereads from 0. Rows and the new offset commit together.
    """
    path = str(path)
    st = os.stat(path)
    with conn:
        file_id, dev, inode, generation, offset = _ensure_file(conn, path, scope)
        if (dev, inode) != (st.st_dev, st.st_ino) or st.st_size < offset:
            if dev is not None:
                generation += 1
            offset = 0
            _clear_rows(conn, file_id, tables)
        chunk = _complete_chunk(path, offset)
        lines = 0
        pos = offset
        for raw in chunk.splitlines(keepends=True):
            for table, row in parse_line(raw.decode("utf-8", errors="replace"),
                                         pos, file_id, generation):
                _insert(conn, table, row)
            pos += len(raw)
            lines += 1
        conn.execute("UPDATE files SET dev=?, inode=?, generation=?, offset=?, size=?,"
                     " mtime_ns=?, parser_version=?, scope=? WHERE file_id=?",
                     (st.st_dev, st.st_ino, generation, pos, st.st_size, st.st_mtime_ns,
                      db.PARSER_VERSION, scope, file_id))
    return lines


def forget_missing(conn: sqlite3.Connection, scope: str, seen_paths: Iterable[str],
                   tables: Sequence[str] = db.DATA_TABLES) -> int:
    """Drop files of `scope` not in seen_paths, with their rows; returns count."""
    seen = {str(p) for p in seen_paths}
    with conn:
        gone = [(fid, p) for fid, p in conn.execute(
            "SELECT file_id, path FROM files WHERE scope=?", (scope,)) if p not in seen]
        for file_id, _ in gone:
            _clear_rows(conn, file_id, tables)
            conn.execute("DELETE FROM files WHERE file_id=?", (file_id,))
    return len(gone)


def read_json_source(conn: sqlite3.Connection, path: str | os.PathLike,
                     filter_fn: Callable[[Any], Any]) -> Any:
    """Return allowlist-filtered JSON payload, re-reading only when the stamp changes.

    Returns None when the file is missing or unparsable; never raises for those.
    """
    path_s = str(path)
    stamp = json.dumps(list(file_stamp(Path(path_s))))
    row = conn.execute("SELECT stamp, payload_json FROM json_sources WHERE path=?",
                       (path_s,)).fetchone()
    if row and row[0] == stamp:
        return json.loads(row[1]) if row[1] is not None else None
    try:
        payload = filter_fn(json.loads(Path(path_s).read_text(encoding="utf-8")))
        payload_json = json.dumps(payload)
    except (OSError, ValueError, TypeError):
        payload, payload_json = None, None
    with conn:
        conn.execute("INSERT OR REPLACE INTO json_sources(path, stamp, payload_json)"
                     " VALUES(?, ?, ?)", (path_s, stamp, payload_json))
    return payload


def read_tail(conn: sqlite3.Connection, path: str | os.PathLike) -> str:
    """Uncommitted bytes after the stored offset when the file lacks a final newline."""
    path_s = str(path)
    row = conn.execute("SELECT offset FROM files WHERE path=?", (path_s,)).fetchone()
    try:
        with open(path_s, "rb") as fh:
            fh.seek(row[0] if row else 0)
            data = fh.read()
    except OSError:
        return ""
    if not data or data.endswith(LINE_END):
        return ""
    return data[data.rfind(LINE_END) + 1:].decode("utf-8", errors="replace")
