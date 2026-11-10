"""Incremental Codex rollout records in `codex_records` (allowlisted metadata only).

The caller supplies `classify(line) -> Optional[dict]`, the exact header/literal
filter of the legacy reader; only its allowlisted result is stored. Rows come back
in file order, including the uncommitted tail (parsed, never stored), so a reader
sees the same records as `for line in handle`.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from . import db, ingest, runtime

TABLE = "codex_records"
SCOPE_SESSIONS = "codex_sessions"
SCOPE_ARCHIVED = "codex_archived"
ARCHIVED_DIR = "archived_sessions"
# Bytes before the committed offset hashed to detect an in-place rewrite that kept
# the inode and did not shrink the file (append-only logs never change them).
FINGERPRINT_BYTES = 256
FINGERPRINT_KEY = "codex_fp:"

Classify = Callable[[str], Optional[dict]]


@dataclass(frozen=True)
class CodexRecord:
    """One classified rollout line: kind/observed_at plus allowlisted flags/payload."""
    kind: str
    observed_at: Optional[float]
    data: dict


_memo: Dict[str, Tuple[tuple, List[CodexRecord]]] = {}
_memo_conn: List[object] = [None]


def scope_for(path: Path) -> str:
    return SCOPE_ARCHIVED if ARCHIVED_DIR in Path(path).parts else SCOPE_SESSIONS


def _record(row: dict) -> CodexRecord:
    return CodexRecord(str(row.get("kind") or ""), row.get("observed_at"), row["data"])


def _parser(classify: Classify):
    def parse_line(text: str, pos: int, file_id: int, generation: int):
        row = classify(text)
        if row is None:
            return ()
        return ((TABLE, {"file_id": file_id, "generation": generation, "byte_offset": pos,
                         "kind": row.get("kind"), "observed_at": row.get("observed_at"),
                         "thread_id": row.get("thread_id"),
                         "payload_json": json.dumps(row["data"])}),)
    return parse_line


def _fingerprint(path: str, offset: int) -> str:
    with open(path, "rb") as fh:
        start = max(0, offset - FINGERPRINT_BYTES)
        fh.seek(start)
        return f"{offset}:{hashlib.sha1(fh.read(offset - start)).hexdigest()}"


def _drop_if_rewritten(conn: sqlite3.Connection, path: str) -> None:
    row = conn.execute("SELECT file_id, offset FROM files WHERE path=?", (path,)).fetchone()
    if row is None or not row[1]:
        return
    stored = conn.execute("SELECT value FROM meta WHERE key=?",
                          (FINGERPRINT_KEY + path,)).fetchone()
    if stored and stored[0] == _fingerprint(path, row[1]):
        return
    with conn:
        conn.execute(f"DELETE FROM {TABLE} WHERE file_id=?", (row[0],))
        conn.execute("DELETE FROM files WHERE file_id=?", (row[0],))


def _unchanged(conn: sqlite3.Connection, path: str, st: os.stat_result,
               scope: str) -> Optional[Tuple[int, int]]:
    """(file_id, generation) when the stored stat stamp equals `st`, else None.

    Same dev/inode/size/mtime_ns/parser/scope as the last ingest means the bytes the
    fingerprint covered are unchanged, so drop/read/fingerprint/meta writes are skipped.
    """
    row = conn.execute(
        "SELECT f.file_id, f.generation FROM files f JOIN meta m ON m.key=?"
        " WHERE f.path=? AND f.dev=? AND f.inode=? AND f.size=? AND f.mtime_ns=?"
        " AND f.parser_version=? AND f.scope=?",
        (FINGERPRINT_KEY + path, path, st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns,
         db.PARSER_VERSION, scope)).fetchone()
    return (row[0], row[1]) if row else None


def _ingest(conn: sqlite3.Connection, path: str, classify: Classify,
            st: os.stat_result) -> List[CodexRecord]:
    scope = scope_for(Path(path))
    known = _unchanged(conn, path, st, scope)
    if known is None:
        _drop_if_rewritten(conn, path)
        ingest.read_appended(conn, path, scope, _parser(classify), (TABLE,))
        file_id, generation, offset = conn.execute(
            "SELECT file_id, generation, offset FROM files WHERE path=?", (path,)).fetchone()
        with conn:
            conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
                         (FINGERPRINT_KEY + path, _fingerprint(path, offset)))
    else:
        file_id, generation = known
    found = [CodexRecord(kind or "", at, json.loads(payload)) for kind, at, payload in conn.execute(
        f"SELECT kind, observed_at, payload_json FROM {TABLE} WHERE file_id=? AND generation=?"
        " ORDER BY byte_offset", (file_id, generation))]
    tail = ingest.read_tail(conn, path)
    if tail:
        row = classify(tail)
        if row is not None:
            found.append(_record(row))
    return found


def records(path: Path, classify: Classify) -> Optional[List[CodexRecord]]:
    """Stored records of `path`, or None -> caller reads the file itself.

    Raises OSError when the file cannot be read (callers keep their strict rule).
    Each file is ingested once per process while its stat stamp is unchanged.
    """
    conn = runtime.connection()
    if conn is None:
        return None
    if _memo_conn[0] is not conn:
        _memo.clear()
        _memo_conn[0] = conn
    key = str(path)
    st = os.stat(key)
    stamp = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
    cached = _memo.get(key)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    try:
        found = _ingest(conn, key, classify, st)
    except sqlite3.Error as exc:
        runtime.disable_after_error(exc)
        _memo.clear()
        return None
    _memo[key] = (stamp, found)
    return found


def forget(scope: str, seen_paths: Iterable[Path]) -> None:
    """Drop stored files of `scope` that a full listing no longer contains."""
    conn = runtime.connection()
    if conn is None:
        return
    seen = {str(p) for p in seen_paths}
    try:
        ingest.forget_missing(conn, scope, seen, (TABLE,))
        with conn:
            conn.executemany("DELETE FROM meta WHERE key=?", [
                (FINGERPRINT_KEY + p,) for (p,) in conn.execute(
                    "SELECT substr(key, ?) FROM meta WHERE key LIKE ?",
                    (len(FINGERPRINT_KEY) + 1, FINGERPRINT_KEY + "%")).fetchall()
                if scope_for(Path(p)) == scope and p not in seen])
    except sqlite3.Error as exc:
        runtime.disable_after_error(exc)
