"""USD cost of this machine's Claude API calls, read incrementally from local transcripts.

Uses the shared hybrid-hands price file, exact model ids and incremental ledger scans.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

# hh-ps loads this file by absolute path, without the scripts directory on sys.path.
_prices_spec = importlib.util.spec_from_file_location(
    "_statusline_shared_prices", Path(__file__).with_name("shared_prices.py"))
if _prices_spec is None or _prices_spec.loader is None:
    raise ImportError("Cannot load sibling shared_prices.py")
_prices_module = importlib.util.module_from_spec(_prices_spec)
_prices_spec.loader.exec_module(_prices_module)
load_prices = _prices_module.load_prices

# v4 uses canonical prices and invalidates USD when the price fingerprint changes.
LEDGER_VERSION = 4
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
    cached: Optional[float] = None
    cache_write_5m: Optional[float] = None
    cache_write_1h: Optional[float] = None


def refresh_prices() -> str:
    rows = load_prices()
    PRICES.clear()
    PRICES.update({model: ModelPrice(row["input"], row["output"], row["cached"],
                                    row.get("cache_write_5m"), row.get("cache_write_1h"))
                   for model, row in rows.items()})
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


PRICES: dict[str, ModelPrice] = {}
refresh_prices()


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
    return PRICES.get(model)


def _num(mapping: object, key: str) -> float:
    if not isinstance(mapping, dict):
        return 0.0
    value = mapping.get(key) or 0
    return float(value) if isinstance(value, (int, float)) else 0.0


def usage_usd(price: ModelPrice, usage: dict) -> float:
    costs = token_costs(price, token_counts(usage))
    return sum(costs.values())


def token_costs(price: ModelPrice, tokens: dict) -> dict:
    rates = {"input": price.input, "output": price.output, "cache_read": price.cached,
             "cache_write_5m": price.cache_write_5m, "cache_write_1h": price.cache_write_1h}
    return {kind: tokens[kind] * (rate if rate is not None else 0.0) / PER_TOKENS
            for kind, rate in rates.items()}


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
    return {"version": LEDGER_VERSION, "pricing": refresh_prices(),
            "files": {}, "messages": {}, "sessions": {}, "unpriced": {}}


def load_ledger(path: Path) -> dict:
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty_ledger()
    if not isinstance(ledger, dict) or ledger.get("version") != LEDGER_VERSION:
        return empty_ledger()  # v1 ledgers hold relative units: rescan from scratch
    base = empty_ledger()
    if ledger.get("pricing") != base["pricing"]:
        return base
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


# --- One-off window report: `usage_ledger.py --since ISO [--until ISO] [--home DIR ...]` ---
TOKEN_KINDS = ("input", "output", "cache_write_5m", "cache_write_1h", "cache_read")
TOP_SESSIONS = 5
MAIN, SUBAGENT = "main", "subagent"


@dataclass(frozen=True)
class WindowMessage:
    model: str
    tokens: dict
    kind: str
    session: str


def token_counts(usage: dict) -> dict:
    detail = usage.get("cache_creation")
    if isinstance(detail, dict) and ("ephemeral_1h_input_tokens" in detail
                                     or "ephemeral_5m_input_tokens" in detail):
        write_5m, write_1h = (_num(detail, "ephemeral_5m_input_tokens"),
                              _num(detail, "ephemeral_1h_input_tokens"))
    else:
        write_5m, write_1h = _num(usage, "cache_creation_input_tokens"), 0.0
    return {"input": _num(usage, "input_tokens"), "output": _num(usage, "output_tokens"),
            "cache_write_5m": write_5m, "cache_write_1h": write_1h,
            "cache_read": _num(usage, "cache_read_input_tokens")}


def window_messages(homes: Iterable[Path], since: float, until: float) -> dict:
    """Last record per (message.id, requestId) with since <= timestamp <= until."""
    found: dict = {}
    for home in homes:
        for path in transcript_paths(home / "projects"):
            if path.stat().st_mtime < since:
                continue
            kind = SUBAGENT if path.parent.name == SUBAGENTS_DIR else MAIN
            session = f"{home.name}/{path.relative_to(home / 'projects').parts[0]}/{session_id_for(path)[:8]}"
            for line in path.read_bytes().split(b"\n"):
                rec = usage_record(line, session)
                if rec is None or not since <= rec.ts <= until:
                    continue
                usage = json.loads(line)["message"]["usage"]
                found[rec.key] = WindowMessage(rec.model, token_counts(usage), kind, session)
    return found


def model_usd(model: str, tokens: dict) -> dict:
    price = price_for(model)
    if price is None:
        return {}
    return token_costs(price, tokens)


def window_report(messages: dict) -> str:
    by_model: dict = {}
    by_kind: dict = {}
    by_session: dict = {}
    unpriced = set()
    for msg in messages.values():
        tokens = by_model.setdefault(msg.model, dict.fromkeys(TOKEN_KINDS, 0.0))
        for k in TOKEN_KINDS:
            tokens[k] += msg.tokens[k]
        usd = sum(model_usd(msg.model, msg.tokens).values())
        if price_for(msg.model) is None:
            unpriced.add(msg.model)
        by_kind[msg.kind] = by_kind.get(msg.kind, 0.0) + usd
        by_session[msg.session] = by_session.get(msg.session, 0.0) + usd
    lines = [f"messages={len(messages)} unpriced={sorted(unpriced)}",
             "model\t" + "\t".join(f"{k}_tok\t{k}_usd" for k in TOKEN_KINDS) + "\ttotal_usd"]
    for model, tokens in sorted(by_model.items()):
        usd = model_usd(model, tokens)
        cells = "\t".join(f"{int(tokens[k])}\t{usd.get(k, 0):.2f}" for k in TOKEN_KINDS)
        lines.append(f"{model}\t{cells}\t{sum(usd.values()):.2f}")
    lines.append("total_usd\t" + f"{sum(by_kind.values()):.2f}")
    lines += [f"{kind}_usd\t{usd:.2f}" for kind, usd in sorted(by_kind.items())]
    top = sorted(by_session.items(), key=lambda item: -item[1])[:TOP_SESSIONS]
    lines += [f"top\t{session}\t{usd:.2f}" for session, usd in top]
    return "\n".join(lines)


def main(argv: Optional[list] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Claude token usage and API USD in a time window")
    parser.add_argument("--since", required=True, help="ISO time with offset, e.g. 2026-11-06T20:00:00+07:00")
    parser.add_argument("--until", help="ISO time with offset (default: now)")
    parser.add_argument("--home", action="append", type=Path,
                        help="Claude config dir, repeatable (default: $CLAUDE_CONFIG_DIR or ~/.claude)")
    args = parser.parse_args(argv)
    since = datetime.fromisoformat(args.since).timestamp()
    until = datetime.fromisoformat(args.until).timestamp() if args.until else datetime.now().timestamp()
    homes = args.home or [Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")]
    print(f"window\t{datetime.fromtimestamp(since).astimezone().isoformat()}"
          f"\t{datetime.fromtimestamp(until).astimezone().isoformat()}")
    print(window_report(window_messages(homes, since, until)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
