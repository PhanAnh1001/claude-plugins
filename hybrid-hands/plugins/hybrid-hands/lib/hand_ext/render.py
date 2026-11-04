"""Plain-text/Markdown output for hand-ext commands."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .backends.base import Check
from .constants import REPORT_PREVIEW_LINES

TOKEN_KEYS = ("input", "cached_input", "output")


def mark(ok: bool) -> str:
    return "đạt" if ok else "thiếu"


def doctor_table(rows: Iterable[Tuple[str, List[Check]]]) -> str:
    out = ["| backend | kiểm | kết quả | chi tiết |", "|---|---|---|---|"]
    for name, checks in rows:
        for c in checks:
            out.append(f"| {name} | {c.name} | {mark(c.ok)} | {c.detail} |")
    return "\n".join(out)


def run_summary(entry: Dict[str, Any], seconds: float, report_path: Optional[str],
                report_text: str, errors: List[str]) -> str:
    tok = entry.get("tokens", {})
    quota = entry.get("quota", {})
    lines = [
        f"backend: {entry['backend']}  model: {entry['model']}  status: {entry['status']}",
        "token: " + ", ".join(f"{k}={tok.get(k, 0)}" for k in TOKEN_KEYS),
        f"hạn mức: used_percent={quota.get('used_percent')} resets_at={quota.get('resets_at')}",
        f"thời gian: {seconds:.1f} s",
        f"report: {report_path or '(không có)'}",
    ]
    lines += [f"lỗi: {e}" for e in errors[:REPORT_PREVIEW_LINES]]
    if report_text:
        lines += ["", "--- report.md ---"] + report_text.splitlines()[:REPORT_PREVIEW_LINES]
    return "\n".join(lines)


def _sum(entries: Iterable[Dict[str, Any]], key) -> Dict[str, Dict[str, int]]:
    agg: Dict[str, Dict[str, int]] = defaultdict(lambda: {"runs": 0, **{k: 0 for k in TOKEN_KEYS}})
    for e in entries:
        row = agg[key(e)]
        row["runs"] += 1
        for k in TOKEN_KEYS:
            row[k] += int((e.get("tokens") or {}).get(k, 0) or 0)
    return dict(agg)


def ledger_report(entries: List[Dict[str, Any]]) -> str:
    out = [f"Tổng lượt: {len(entries)}"]
    groups = (("backend", lambda e: str(e.get("backend"))),
              ("label", lambda e: str(e.get("label"))),
              ("ngày", lambda e: str(e.get("started", ""))[:10]))
    for title, key in groups:
        out += ["", f"| {title} | lượt | input | cached_input | output |", "|---|---|---|---|---|"]
        for name, row in sorted(_sum(entries, key).items()):
            out.append(f"| {name} | {row['runs']} | " + " | ".join(str(row[k]) for k in TOKEN_KEYS) + " |")
    return "\n".join(out)
