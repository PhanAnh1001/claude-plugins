"""So sánh prompt cache giai đoạn TRƯỚC và SAU một mốc thời gian (mặc định: cài policy 2.1.0).

Ported from session scratchpad 2026-11-02.
Với hai nhóm subagent và main, tính: số request, tỉ lệ cache hit, chi phí quy đổi trung
bình mỗi request (bội số giá input), số resume và tỉ lệ resume <=5 phút, miss RESUME và
miss TOOL DÀI (Bash) 5-60 phút cùng token write, phân bố ngữ cảnh lúc resume, số hand
tạo mới mỗi phiên. Xuất bảng Markdown; chỉ số liệu, không in nội dung hội thoại.
Một request thuộc giai đoạn theo timestamp của nó; một hand thuộc giai đoạn theo request
đầu tiên của hand.
Chạy: python3 -I compare_periods.py [--cutoff 2026-11-02T12:00] [--projects-dir DIR] [--out FILE]
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

# python3 -I bỏ PYTHONPATH và thư mục hiện hành, nhưng sys.path[0] vẫn là thư mục chứa
# script; thêm tường minh để import chắc chắn cả khi được nạp theo cách khác.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from resume_miss import (DEFAULT_PROJECTS, RESUME, TOOL, TTL_5M, Req,  # noqa: E402
                         Transition, is_subagent, iter_transcripts, scan_file)

DEFAULT_CUTOFF = "2026-11-02T12:00"      # giờ local lúc cài policy 2.1.0
SMALL_SAMPLE_SUBAGENT_REQ = 2_000        # dưới ngưỡng này kết quả SAU chưa đủ tin cậy
LONG_TOOL_NAME = "Bash"
PRICE = {"input": 1.0, "w5m": 1.25, "w1h": 2.0, "output": 5.0}
DEFAULT_READ_MULT = 0.1
READ_MULT = {"claude-opus-5-5": 0.05, "claude-fable-5-1": 0.025}
RESUME_CTX_BUCKETS = [(0, 80_000, "<80k"), (80_000, 200_000, "80-200k"), (200_000, 10**12, ">200k")]
BEFORE, AFTER = "TRƯỚC", "SAU"
GROUPS = ("subagent", "main")


def read_mult(model: str) -> float:
    return next((v for k, v in READ_MULT.items() if model.startswith(k)), DEFAULT_READ_MULT)


def cost(r: Req) -> float:
    return (r.inp * PRICE["input"] + r.w5 * PRICE["w5m"] + r.w1 * PRICE["w1h"]
            + r.rd * read_mult(r.model) + r.out * PRICE["output"])


@dataclass
class Stats:
    reqs: int = 0
    read: int = 0
    ctx: int = 0
    cost: float = 0.0
    resumes: int = 0
    warm_resumes: int = 0
    resume_miss: int = 0
    resume_miss_write: int = 0
    tool_miss: int = 0
    tool_miss_write: int = 0
    resume_ctx: Counter = field(default_factory=Counter)
    hands: int = 0
    hand_sessions: set[str] = field(default_factory=set)

    def add_req(self, r: Req) -> None:
        self.reqs += 1
        self.read += r.rd
        self.ctx += r.ctx
        self.cost += cost(r)

    def add_transition(self, t: Transition) -> None:
        if t.kind == RESUME:
            self.resumes += 1
            self.warm_resumes += t.gap <= TTL_5M
            self.resume_ctx[bucket_name(t.cur.ctx)] += 1
        if not t.is_big_mid_miss:
            return
        if t.kind == RESUME:
            self.resume_miss += 1
            self.resume_miss_write += t.cur.write
        elif t.kind == TOOL and t.detail == LONG_TOOL_NAME:
            self.tool_miss += 1
            self.tool_miss_write += t.cur.write


def bucket_name(ctx: int) -> str:
    return next(n for lo, hi, n in RESUME_CTX_BUCKETS if lo <= ctx < hi)


def parse_cutoff(text: str) -> datetime:
    """Giờ không kèm múi giờ được hiểu là giờ local của máy."""
    dt = datetime.fromisoformat(text)
    return dt.astimezone() if dt.tzinfo is None else dt


def session_of(path: str) -> str:
    """Thư mục phiên cha của transcript hand: <project>/<session>/subagents/agent-*.jsonl."""
    return os.path.dirname(os.path.dirname(path))


def collect(root: str, cutoff: datetime) -> dict[tuple[str, str], Stats]:
    stats = {(g, p): Stats() for g in GROUPS for p in (BEFORE, AFTER)}
    period = lambda ts: BEFORE if ts < cutoff else AFTER  # noqa: E731
    for path in iter_transcripts(root):
        scan = scan_file(path)
        if not scan.reqs:
            continue
        group = "subagent" if is_subagent(path) else "main"
        for r in scan.reqs:
            stats[(group, period(r.ts))].add_req(r)
        for t in scan.transitions:
            stats[(group, period(t.cur.ts))].add_transition(t)
        if group == "subagent":
            s = stats[(group, period(scan.reqs[0].ts))]
            s.hands += 1
            s.hand_sessions.add(session_of(path))
    return stats


def ratio(a: float, b: float, fmt: str) -> str:
    return format(a / b, fmt) if b else "-"


def rows(s: Stats) -> list[str]:
    ctx_total = sum(s.resume_ctx.values())
    dist = " / ".join(f"{n} {ratio(s.resume_ctx[n], ctx_total, '.0%')}" for _, _, n in RESUME_CTX_BUCKETS)
    return [
        f"{s.reqs:,}",
        ratio(s.read, s.ctx, ".3f"),
        ratio(s.cost, s.reqs, ",.0f"),
        f"{s.resumes:,}",
        ratio(s.warm_resumes, s.resumes, ".1%"),
        f"{s.resume_miss:,} / {s.resume_miss_write:,}",
        f"{s.tool_miss:,} / {s.tool_miss_write:,}",
        dist if ctx_total else "-",
        f"{s.hands:,} / {len(s.hand_sessions):,} = {ratio(s.hands, len(s.hand_sessions), '.1f')}",
    ]


LABELS = [
    "Số request",
    "Tỉ lệ cache hit (read / ngữ cảnh)",
    "Chi phí quy đổi TB mỗi request (token input tương đương)",
    "Số resume",
    "Tỉ lệ resume <=5 phút",
    "Miss RESUME 5-60 phút (số / token write)",
    f"Miss TOOL DÀI {LONG_TOOL_NAME} 5-60 phút (số / token write)",
    "Ngữ cảnh lúc resume",
    "Hand tạo mới / phiên có hand = hand mỗi phiên",
]


def render(stats: dict[tuple[str, str], Stats], cutoff: datetime) -> str:
    out = [f"# So sánh cache trước/sau mốc {cutoff.isoformat(timespec='minutes')}", "",
           f"Tạo lúc {datetime.now().astimezone().isoformat(timespec='minutes')}. "
           "Hệ số chi phí (bội số giá input): read 0,05 opus-5-5 / 0,025 fable-5-1 / 0,1 model khác; "
           "write 5m 1,25; write 1h 2; output 5. Miss = request ghi cache >20k token sau khoảng nghỉ 5-60 phút.", ""]
    after_sub = stats[("subagent", AFTER)].reqs
    if after_sub < SMALL_SAMPLE_SUBAGENT_REQ:
        out += [f"> CẢNH BÁO: mẫu SAU nhỏ ({after_sub:,} request subagent < {SMALL_SAMPLE_SUBAGENT_REQ:,}); "
                "chưa đủ để kết luận.", ""]
    for g in GROUPS:
        before, after = rows(stats[(g, BEFORE)]), rows(stats[(g, AFTER)])
        out += [f"## {g}", "", f"| Chỉ số | {BEFORE} | {AFTER} |", "|---|---:|---:|"]
        labels = LABELS if g == "subagent" else LABELS[:-1]   # dòng hand chỉ có nghĩa với subagent
        out += [f"| {lab} | {b} | {a} |" for lab, b, a in zip(labels, before, after)]
        out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--projects-dir", default=DEFAULT_PROJECTS)
    ap.add_argument("--cutoff", default=DEFAULT_CUTOFF, help="ISO 8601; không có múi giờ = giờ local")
    ap.add_argument("--out", help="ghi bảng Markdown ra file (mặc định chỉ in stdout)")
    args = ap.parse_args()
    cutoff = parse_cutoff(args.cutoff)
    text = render(collect(args.projects_dir, cutoff), cutoff)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
