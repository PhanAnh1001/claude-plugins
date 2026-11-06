"""USD cost of this machine's Claude API calls, read incrementally from local transcripts.

Ported from live-tiktok-games sessions/ops/runs/local-usage.sh: the USD/MTok price table, the
"keep the LAST record per (message.id, requestId)" dedupe and the skipped "<synthetic>" model.
Differences: incremental scan by (inode, offset) into a JSON ledger, cache writes split into the
1-hour and 5-minute kinds, model-family fallback prices, session id and cwd kept per message.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

# v3 adds session names and aliases: older ledgers are rescanned from scratch.
LEDGER_VERSION = 3
LEDGER_NAME = ".statusline-local-usage.json"
DAY_SECONDS = 86400
# Keep a little more than one 7-day window of history (window plus slack for late renders).
RETENTION_SECONDS = 9 * DAY_SECONDS
PER_TOKENS = 1_000_000
SYNTHETIC_MODEL = "<synthetic>"
USAGE_MARKER = b'"usage"'
SUBAGENTS_DIR = "subagents"
# Title records of a main transcript: (type, value key, ledger session key). Later records win.
TITLE_RECORDS = (("custom-title", "customTitle", "custom_title"),
                 ("agent-name", "agentName", "agent_name"),
                 ("ai-title", "aiTitle", "alias"))
TITLE_MARKERS = tuple((f'"type":"{kind}"'.encode(), kind, key, field)
                      for kind, key, field in TITLE_RECORDS)


@dataclass(frozen=True)
class ModelPrice:
    input: float   # USD per million input tokens
    output: float  # USD per million output tokens


# Anthropic first-party API list prices, USD per million tokens (data of 10/2026):
#   https://platform.claude.com/docs/en/about-claude/pricing (cached table in the claude-api skill)
# Haiku 5.5 is priced for prompts <= 100K tokens (0.50 / 2.50 above), so its cost can be low.
PRICES = {
    "claude-opus-5-5": ModelPrice(4.00, 20.00),
    "claude-sonnet-5-5": ModelPrice(2.00, 10.00),
    "claude-haiku-5-5": ModelPrice(0.10, 0.50),
}
# Unknown model ids fall back to the 5.5 price of their family.
FAMILY_FALLBACK = (("opus", "claude-opus-5-5"), ("sonnet", "claude-sonnet-5-5"),
                   ("haiku", "claude-haiku-5-5"))
# Cache multipliers on the input price (Anthropic prompt-caching pricing).
CACHE_WRITE_1H_FACTOR = 2.0
CACHE_WRITE_5M_FACTOR = 1.25
CACHE_READ_FACTOR = 0.1


@dataclass(frozen=True)
class UsageRecord:
    key: str
    ts: float
    usd: float
    sid: str
    cwd: str
    model: str
    priced: bool


def price_for(model: str) -> Optional[ModelPrice]:
    if model in PRICES:
        return PRICES[model]
    name = model.lower()
    for family, model_id in FAMILY_FALLBACK:
        if family in name:
            return PRICES[model_id]
    return None


def _num(mapping: object, key: str) -> float:
    if not isinstance(mapping, dict):
        return 0.0
    value = mapping.get(key) or 0
    return float(value) if isinstance(value, (int, float)) else 0.0


def cache_write_input_units(usage: dict) -> float:
    """Cache-write tokens expressed in input-price units, split by cache lifetime when known."""
    detail = usage.get("cache_creation")
    if isinstance(detail, dict) and ("ephemeral_1h_input_tokens" in detail
                                     or "ephemeral_5m_input_tokens" in detail):
        return (CACHE_WRITE_1H_FACTOR * _num(detail, "ephemeral_1h_input_tokens")
                + CACHE_WRITE_5M_FACTOR * _num(detail, "ephemeral_5m_input_tokens"))
    return CACHE_WRITE_5M_FACTOR * _num(usage, "cache_creation_input_tokens")


def usage_usd(price: ModelPrice, usage: dict) -> float:
    input_units = (_num(usage, "input_tokens") + cache_write_input_units(usage)
                   + CACHE_READ_FACTOR * _num(usage, "cache_read_input_tokens"))
    return (input_units * price.input + _num(usage, "output_tokens") * price.output) / PER_TOKENS


def parse_timestamp(value: object) -> Optional[float]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def session_id_for(path: Path) -> str:
    """Main transcript <sid>.jsonl -> sid; subagent <sid>/subagents/agent-*.jsonl -> sid."""
    if path.parent.name == SUBAGENTS_DIR:
        return path.parent.parent.name
    return path.stem


def usage_record(line: bytes, sid: str) -> Optional[UsageRecord]:
    """One transcript line as a priced usage record, or None when it carries no API usage."""
    if USAGE_MARKER not in line:
        return None
    try:
        record = json.loads(line)
    except ValueError:
        return None
    if not isinstance(record, dict) or record.get("type") != "assistant":
        return None
    message = record.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
        return None
    model = str(message.get("model") or "")
    if model == SYNTHETIC_MODEL:
        return None
    msg_id, request_id = message.get("id"), record.get("requestId")
    ts = parse_timestamp(record.get("timestamp"))
    if (not msg_id and not request_id) or ts is None:
        return None
    price = price_for(model)
    usd = usage_usd(price, message["usage"]) if price else 0.0
    cwd = record.get("cwd")
    return UsageRecord(f"{msg_id}|{request_id}", ts, usd, sid,
                       cwd if isinstance(cwd, str) else "", model, price is not None)


def title_update(line: bytes) -> Optional[tuple[str, str]]:
    """(ledger session field, value) for a custom-title / agent-name / ai-title record."""
    for marker, kind, key, field in TITLE_MARKERS:
        if marker not in line:
            continue
        try:
            record = json.loads(line)
        except ValueError:
            return None
        value = record.get(key) if isinstance(record, dict) else None
        if isinstance(value, str) and record.get("type") == kind:
            return field, value
        return None
    return None


def session_name(entry: dict) -> tuple[str, str]:
    """(name, alias) of a ledger session: custom title first, then agent name."""
    name = entry.get("custom_title") or entry.get("agent_name") or ""
    return str(name), str(entry.get("alias") or "")


# --- Ledger ---
def empty_ledger() -> dict:
    return {"version": LEDGER_VERSION, "files": {}, "messages": {}, "sessions": {}, "unpriced": {}}


def load_ledger(path: Path) -> dict:
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty_ledger()
    if not isinstance(ledger, dict) or ledger.get("version") != LEDGER_VERSION:
        return empty_ledger()  # v1 ledgers hold relative units: rescan from scratch
    base = empty_ledger()
    for key in ("files", "messages", "sessions", "unpriced"):
        if not isinstance(ledger.get(key, base[key]), dict):
            return empty_ledger()
        base[key] = ledger.get(key, base[key])
    return base


def add_record(ledger: dict, record: UsageRecord) -> None:
    # A later record of the same response overwrites the earlier one (its usage is cumulative).
    ledger["messages"][record.key] = [record.ts, round(record.usd, 6), record.sid]
    session = ledger["sessions"].setdefault(record.sid, {"cwd": "", "last_ts": 0})
    if record.cwd:
        session["cwd"] = record.cwd
    session["last_ts"] = max(session.get("last_ts") or 0, record.ts)
    if not record.priced:
        ledger["unpriced"][record.model] = max(ledger["unpriced"].get(record.model, 0), record.ts)


def scan_file(path: Path, entry: Optional[dict], ledger: dict) -> dict:
    """Read new complete lines of one transcript into the ledger; return its new file entry."""
    stat = path.stat()
    offset = 0
    if isinstance(entry, dict) and entry.get("ino") == stat.st_ino:
        previous = entry.get("offset")
        if isinstance(previous, int) and 0 <= previous <= stat.st_size:
            offset = previous
    with path.open("rb") as handle:
        handle.seek(offset)
        chunk = handle.read()
    end = chunk.rfind(b"\n")
    if end < 0:
        return {"ino": stat.st_ino, "offset": offset}
    sid = session_id_for(path)
    is_main = path.parent.name != SUBAGENTS_DIR
    for line in chunk[:end].split(b"\n"):
        record = usage_record(line, sid)
        if record is not None:
            add_record(ledger, record)
        elif is_main:
            update = title_update(line)
            if update is not None:
                ledger["sessions"].setdefault(sid, {"cwd": "", "last_ts": 0})[update[0]] = update[1]
    return {"ino": stat.st_ino, "offset": offset + end + 1}


def transcript_paths(projects: Path) -> Iterable[Path]:
    if not projects.is_dir():
        return []
    return projects.rglob("*.jsonl")


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def prune(ledger: dict, cutoff: float) -> None:
    ledger["files"] = {name: e for name, e in ledger["files"].items() if Path(name).exists()}
    ledger["messages"] = {k: m for k, m in ledger["messages"].items() if m[0] >= cutoff}
    ledger["sessions"] = {s: v for s, v in ledger["sessions"].items()
                          if (v.get("last_ts") or 0) >= cutoff}
    ledger["unpriced"] = {m: ts for m, ts in ledger["unpriced"].items() if ts >= cutoff}


def update_ledger(home: Path, now: float) -> dict:
    path = home / LEDGER_NAME
    ledger = load_ledger(path)
    cutoff = now - RETENTION_SECONDS
    files: dict = ledger["files"]
    for transcript in transcript_paths(home / "projects"):
        try:
            if transcript.stat().st_mtime < cutoff:
                continue
            files[str(transcript)] = scan_file(transcript, files.get(str(transcript)), ledger)
        except OSError:
            continue
    prune(ledger, cutoff)
    write_atomic(path, json.dumps(ledger))
    return ledger
