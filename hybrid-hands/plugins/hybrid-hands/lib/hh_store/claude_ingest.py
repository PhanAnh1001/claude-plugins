"""Incremental ingest of Claude transcript/subagent JSONL into hh-store.

Only allowlisted metadata and token counts are stored (never message text). The
account comes from the Claude config home that contains the file, matched against
the effective ``ext_hand.claude_accounts``; unmatched homes get ``""`` (unknown).
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from . import ingest, runtime

USAGE_TABLE = "claude_usage_lines"
INFO_TABLE = "claude_file_info"
CLAUDE_TABLES = (USAGE_TABLE, INFO_TABLE)
UNKNOWN_ACCOUNT = ""
# Depth of the config home above each file: H/projects/<slug>/<sid>.jsonl and
# H/projects/<slug>/<sid>/subagents/agent-<id>.jsonl.
HOME_DEPTH = {"claude_transcript": 2, "claude_subagent": 4}
USAGE_KEYS = ("input_tokens", "output_tokens", "cache_read_input_tokens",
              "cache_creation_input_tokens")
CACHE_DETAIL_KEY = "cache_creation"
CACHE_DETAIL_KEYS = ("ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens")
SCALAR_TYPES = (int, float, str, bool, type(None))


def _expand(raw: str, root: Path) -> Path:
    if raw == "~" or raw.startswith("~/"):
        path = Path.home() / raw[2:] if raw != "~" else Path.home()
    else:
        path = Path(raw)
    return (path if path.is_absolute() else root / path).resolve()


@lru_cache(maxsize=8)
def _account_homes(home_key: str, config_key: str, cwd: str) -> Dict[str, Path]:
    from hand_ext.constants import DEFAULTS
    accounts: Any = DEFAULTS["claude_accounts"]
    try:
        from shared_config import load_config
        accounts = load_config(known_root=Path(cwd)).effective["ext_hand"]["claude_accounts"]
    except Exception:  # noqa: BLE001 - any config failure keeps the plugin defaults
        pass
    found: Dict[str, Path] = {}
    for name, entry in (accounts.items() if isinstance(accounts, dict) else ()):
        raw = entry.get("config_dir") if isinstance(entry, dict) else None
        if isinstance(raw, str) and raw.strip():
            try:
                found[str(name)] = _expand(raw.strip(), Path(cwd))
            except (OSError, RuntimeError):
                continue
    return found


def account_homes() -> Dict[str, Path]:
    """Effective Claude account name -> resolved config home."""
    return dict(_account_homes(str(Path.home()), os.environ.get("HYBRID_HANDS_CONFIG", ""),
                               str(Path.cwd())))


def account_for_home(home: Path) -> str:
    try:
        resolved = Path(home).resolve()
    except (OSError, RuntimeError):
        return UNKNOWN_ACCOUNT
    matches = [name for name, path in account_homes().items() if path == resolved]
    return matches[0] if len(matches) == 1 else UNKNOWN_ACCOUNT


def _account_for_file(path: Path, scope: str) -> str:
    parents = Path(path).parents
    depth = HOME_DEPTH.get(scope)
    if depth is None or depth >= len(parents):
        return UNKNOWN_ACCOUNT
    return account_for_home(parents[depth])


def _filtered_usage(usage: dict) -> dict:
    kept = {k: usage[k] for k in USAGE_KEYS if k in usage and isinstance(usage[k], SCALAR_TYPES)}
    detail = usage.get(CACHE_DETAIL_KEY)
    if isinstance(detail, dict):
        kept[CACHE_DETAIL_KEY] = {k: detail[k] for k in CACHE_DETAIL_KEYS
                                  if k in detail and isinstance(detail[k], SCALAR_TYPES)}
    return kept


def _count(usage: dict, key: str, source: Optional[dict] = None) -> int:
    try:
        return max(0, int((source if source is not None else usage).get(key) or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _id_text(value: Any) -> str:
    return str(value) if value else ""


def _usage_row(item: dict, record: Any, scope: str, account: str, offset: int,
               file_id: int, generation: int) -> dict:
    message = item.get("message") or {}
    usage = _filtered_usage(record.usage)
    detail = usage.get(CACHE_DETAIL_KEY) or {}
    return dict(file_id=file_id, generation=generation, byte_offset=offset,
                account=account, scope=scope,
                message_id=_id_text(message.get("id")),
                request_id=_id_text(item.get("requestId")),
                at=record.at, model=record.model,
                input=_count(usage, "input_tokens"),
                cached_input=_count(usage, "cache_read_input_tokens"),
                output=_count(usage, "output_tokens"),
                cache_write_5m=_count(usage, CACHE_DETAIL_KEYS[0], detail),
                cache_write_1h=_count(usage, CACHE_DETAIL_KEYS[1], detail),
                usage_json=json.dumps(usage))


def _stored_fold(conn: sqlite3.Connection, path: str) -> tuple:
    row = conn.execute(
        "SELECT i.generation, i.payload_json FROM claude_file_info i JOIN files f"
        " ON f.file_id=i.file_id WHERE f.path=?", (path,)).fetchone()
    return (row[0], json.loads(row[1])) if row else (None, None)


def _ingest(conn: sqlite3.Connection, path: Path, scope: str, account: str) -> None:
    from hh_ps.transcript_source import FileFold, is_usage_line, parse_object, usage_record

    generation, payload = _stored_fold(conn, str(path))
    state = {"generation": generation, "fold": FileFold(**payload) if payload else FileFold()}

    def parse_line(text: str, offset: int, file_id: int, gen: int) -> Iterable[tuple]:
        if state["generation"] != gen:
            state["generation"], state["fold"] = gen, FileFold()
        item = parse_object(text)
        if item is None:
            return ()
        state["fold"].add(item)
        rows = [(INFO_TABLE, dict(file_id=file_id, generation=gen, account=account,
                                  payload_json=json.dumps(asdict(state["fold"]))))]
        record = usage_record(item) if is_usage_line(item) else None
        if record is not None:
            rows.append((USAGE_TABLE, _usage_row(item, record, scope, account, offset,
                                                 file_id, gen)))
        return rows

    ingest.read_appended(conn, path, f"{scope}@{account or 'unknown'}", parse_line,
                         CLAUDE_TABLES)


def _load(conn: sqlite3.Connection, path: Path) -> Any:
    from hh_ps.transcript_source import (
        FileFold, FileScan, UsageRecord, is_usage_line, parse_object, usage_record)

    _, payload = _stored_fold(conn, str(path))
    scan = FileScan(FileFold(**payload) if payload else FileFold(), [])
    rows = conn.execute(
        "SELECT u.at, u.message_id, u.request_id, u.usage_json, u.model FROM claude_usage_lines u"
        " JOIN files f ON f.file_id=u.file_id WHERE f.path=? ORDER BY u.byte_offset",
        (str(path),))
    for at, message_id, request_id, usage_json, model in rows:
        key = f"{message_id}|{request_id}" if message_id or request_id else None
        scan.records.append(UsageRecord(at=at, key=key, usage=json.loads(usage_json),
                                        model=model or ""))
    item = parse_object(ingest.read_tail(conn, path))  # unterminated last line: not stored
    if item is not None:
        scan.fold.add(item)
        record = usage_record(item) if is_usage_line(item) else None
        if record is not None:
            scan.records.append(record)
    return scan


def scan_stored(path: Path, scope: str) -> Optional[Any]:
    """FileScan built from the store, or None -> caller reads the file (legacy path)."""
    conn = runtime.connection()
    if conn is None:
        return None
    try:
        _ingest(conn, path, scope, _account_for_file(path, scope))
        return _load(conn, path)
    except sqlite3.Error as exc:
        runtime.disable_after_error(exc)
        return None
    except OSError:
        return None


def sync(path: Path, scope: str) -> None:
    """Ingest `path` without building a FileScan (the indexer needs no rows)."""
    conn = runtime.connection()
    if conn is None:
        return
    try:
        _ingest(conn, path, scope, _account_for_file(path, scope))
    except sqlite3.Error as exc:
        runtime.disable_after_error(exc)
    except OSError:
        return


def account_rows(conn: sqlite3.Connection, account: str) -> List[sqlite3.Row]:
    """Stored usage lines of one account (for tests/diagnostics)."""
    return conn.execute("SELECT scope, message_id, request_id, at, model, input, output"
                        " FROM claude_usage_lines WHERE account=? ORDER BY file_id, byte_offset",
                        (account,)).fetchall()
