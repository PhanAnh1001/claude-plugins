"""Text output: estimate cost table, run summary, ledger report."""
from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Optional

from .constants import PRICING_SOURCE_URL, REPORT_PREVIEW_LINES


def _usd(value: float) -> str:
    return f"{value:.4f}"


def estimate_table(*, model: str, tier: str, effort: str, label: str, max_usd: float,
                   approval_usd: float, brief_tokens: int, spent_usd: float,
                   prices: Dict[str, float]) -> str:
    p = prices
    unit = (f"input {p['input']} / cached {p['cached_input']} / output {p['output']} USD mỗi 1M token"
            f" (prompt ≤{int(p['long_threshold'])}); >{int(p['long_threshold'])}: "
            f"{p['long_input']} / {p['long_cached_input']} / {p['long_output']}"
            f" ([nguồn]({PRICING_SOURCE_URL}))")
    rows = [
        ("Model / tầng / effort", f"{model} / {tier} / {effort}"),
        ("Việc", label),
        ("Số request tối đa", "1 lượt `codex exec` (nhiều lần gọi model bên trong, tính chung trần)"),
        ("Trần USD của lượt", _usd(max_usd)),
        ("Đơn giá", unit),
        ("Ước token đầu vào brief+preamble", f"~{brief_tokens}"),
        ("Đã chi trong sổ", _usd(spent_usd)),
    ]
    lines = ["| Mục | Giá trị |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows]
    if max_usd >= approval_usd:
        lines.append("")
        lines.append(f"**Cần duyệt:** trần {_usd(max_usd)} USD ≥ ngưỡng {_usd(approval_usd)} USD;"
                     " chạy với `--approved` sau khi người dùng đồng ý.")
    return "\n".join(lines)


def run_summary(*, status: str, usd: float, tokens: Dict[str, int], seconds: float,
                report_path: Optional[str], report_text: str, errors: List[str]) -> str:
    lines = [
        f"status: {status}",
        f"usd: {_usd(usd)}",
        f"tokens: input={tokens['input']} cached={tokens['cached_input']} output={tokens['output']}",
        f"seconds: {seconds:.1f}",
        f"report: {report_path or '(không có)'}",
    ]
    for err in errors[:3]:
        lines.append(f"error: {err[:300]}")
    if report_text:
        lines.append("---")
        lines += report_text.splitlines()[:REPORT_PREVIEW_LINES]
    return "\n".join(lines)


def ledger_report(entries: Iterable[Dict]) -> str:
    by_label: Dict[str, List[float]] = defaultdict(lambda: [0, 0, 0, 0, 0.0])
    by_day: Dict[str, List[float]] = defaultdict(lambda: [0, 0, 0, 0, 0.0])
    for e in entries:
        tok = e.get("tokens") or {}
        vals = [1, tok.get("input", 0), tok.get("cached_input", 0), tok.get("output", 0),
                float(e.get("usd", 0) or 0)]
        for bucket, key in ((by_label, e.get("label", "")), (by_day, str(e.get("started", ""))[:10])):
            bucket[key] = [a + b for a, b in zip(bucket[key], vals)]
    out: List[str] = []
    for title, data in (("label", by_label), ("ngày", by_day)):
        out += [f"| {title} | lượt | input | cached | output | USD |", "|---|---|---|---|---|---|"]
        for key in sorted(data):
            n, i, c, o, u = data[key]
            out.append(f"| {key} | {int(n)} | {int(i)} | {int(c)} | {int(o)} | {_usd(u)} |")
        out.append("")
    total = sum(v[4] for v in by_label.values())
    out.append(f"Tổng: {sum(int(v[0]) for v in by_label.values())} lượt, {_usd(total)} USD")
    return "\n".join(out)
