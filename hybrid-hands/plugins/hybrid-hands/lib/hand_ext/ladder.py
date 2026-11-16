"""Two-tier ladder log for native subagent runs: tier 1 fails -> one retry at tier 2."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from .constants import EXIT_OK, EXIT_USAGE, STATE_DIR_DEFAULT, STATE_DIR_ENV

LADDER_FILE_ENV = "HYBRID_HANDS_LADDER_FILE"
LADDER_FILE_NAME = "ladder.jsonl"
ROLES = ("collect", "chrome")
TIER_FIRST, TIER_SECOND = 1, 2
RESULT_OK, RESULT_FAIL = "ok", "fail"
ID_HEX_LEN = 10  # 40 random bits: collision-free for a local log of this size
SECONDS_PER_DAY = 86400
NO_DATA = "chưa có dữ liệu"


def ladder_path() -> Path:
    """Machine-wide state dir (same as Go ledger), never output/llm or a tracked dir."""
    override = os.environ.get(LADDER_FILE_ENV)
    if override:
        return Path(override).expanduser()
    base = os.environ.get(STATE_DIR_ENV) or STATE_DIR_DEFAULT
    return Path(base).expanduser() / LADDER_FILE_NAME


@dataclass
class Records:
    rows: list = field(default_factory=list)
    skipped: int = 0


def read_records(path: Path) -> Records:
    out = Records()
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            out.skipped += 1
            continue
        if not isinstance(row, dict) or row.get("role") not in ROLES or row.get("tier") not in (TIER_FIRST, TIER_SECOND):
            out.skipped += 1
            continue
        out.rows.append(row)
    return out


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, data)
    finally:
        os.close(fd)  # closing releases the lock


def _profile(cfg: Optional[dict]) -> str:
    if cfg is None:
        try:
            from .config import load_config
            cfg = load_config()
        except Exception:  # config is optional metadata here; a broken file must not block logging
            return ""
    value = cfg.get("profile") if isinstance(cfg, dict) else None
    return value if isinstance(value, str) else ""


def _escalation_error(rows: Iterable[dict], args: argparse.Namespace) -> str:
    source = args.escalated_from
    if source is None:
        return ""
    if args.tier != TIER_SECOND:
        return "--escalated-from chỉ dùng với --tier 2"
    match = next((r for r in rows if r.get("id") == source), None)
    if match is None:
        return f"không có lượt id={source}"
    if match.get("tier") != TIER_FIRST or match.get("result") != RESULT_FAIL:
        return f"lượt {source} không phải bậc 1 hỏng"
    return ""


def cmd_log(args: argparse.Namespace, cfg: Optional[dict]) -> int:
    path = ladder_path()
    error = _escalation_error(read_records(path).rows, args)
    if error:
        print(f"ladder: {error}", file=sys.stderr)
        return EXIT_USAGE
    row = {"id": uuid.uuid4().hex[:ID_HEX_LEN], "ts": time.time(), "role": args.role,
           "tier": args.tier, "result": args.result, "escalated_from": args.escalated_from,
           "model": args.model, "effort": args.effort, "note": args.note,
           "profile": _profile(cfg)}
    _append(path, row)
    print(row["id"])
    return EXIT_OK


def _ratio(part: int, whole: int) -> Optional[float]:
    return part / whole if whole else None


def compute_stats(rows: list, since_ts: Optional[float] = None) -> dict:
    stats = {}
    for role in ROLES:
        mine = [r for r in rows if r["role"] == role and (since_ts is None or r.get("ts", 0) >= since_ts)]
        first = [r for r in mine if r["tier"] == TIER_FIRST]
        escalated = [r for r in mine if r["tier"] == TIER_SECOND and r.get("escalated_from")]
        second = [r for r in mine if r["tier"] == TIER_SECOND]
        first_ok = sum(r.get("result") == RESULT_OK for r in first)
        stats[role] = {"tier1_runs": len(first), "tier1_ok": first_ok,
                       "tier1_ok_rate": _ratio(first_ok, len(first)),
                       "escalations": len(escalated),
                       "escalations_ok": sum(r.get("result") == RESULT_OK for r in escalated),
                       "tier2_fail": sum(r.get("result") == RESULT_FAIL for r in second)}
    return stats


def cmd_stats(args: argparse.Namespace) -> int:
    records = read_records(ladder_path())
    since = time.time() - args.since_days * SECONDS_PER_DAY if args.since_days is not None else None
    stats = compute_stats(records.rows, since)
    if args.json:
        print(json.dumps({"roles": stats, "skipped": records.skipped}, ensure_ascii=False))
        return EXIT_OK
    if not any(s["tier1_runs"] or s["escalations"] or s["tier2_fail"] for s in stats.values()):
        print(NO_DATA)
    for role, s in stats.items():
        rate = "?" if s["tier1_ok_rate"] is None else f"{s['tier1_ok_rate']:.0%}"
        print(f"{role}: bậc1 {s['tier1_ok']}/{s['tier1_runs']} ({rate}), nâng {s['escalations']} "
              f"(đạt {s['escalations_ok']}), bậc2 hỏng {s['tier2_fail']}")
    if records.skipped:
        print(f"bỏ qua {records.skipped} dòng hỏng")
    return EXIT_OK


def add_parser(subparsers) -> None:
    parser = subparsers.add_parser("ladder", help="ghi/thống kê thang 2 bậc của subagent native")
    sub = parser.add_subparsers(dest="ladder_command", required=True)
    log = sub.add_parser("log", help="ghi một lượt")
    log.add_argument("--role", required=True, choices=ROLES)
    log.add_argument("--tier", required=True, type=int, choices=(TIER_FIRST, TIER_SECOND))
    log.add_argument("--result", required=True, choices=(RESULT_OK, RESULT_FAIL))
    log.add_argument("--escalated-from", default=None)
    log.add_argument("--model", default="")
    log.add_argument("--effort", default="")
    log.add_argument("--note", default="")
    stats = sub.add_parser("stats", help="thống kê theo vai")
    stats.add_argument("--json", action="store_true")
    stats.add_argument("--since-days", type=float, default=None)


def run(args: argparse.Namespace, cfg: Optional[dict] = None) -> int:
    if args.ladder_command == "log":
        return cmd_log(args, cfg)
    return cmd_stats(args)
