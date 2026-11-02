"""Phân loại nguyên nhân cache miss lớn của subagent (khoảng cách 5-60 phút).

Ported from session scratchpad 2026-11-02.
Với mỗi cặp request liên tiếp trong một transcript, xác định nguyên nhân request sau:
- RESUME: có bản ghi user không phải tool_result đến sau end_turn (kể cả isMeta có
  origin - tin tiếp việc SendMessage) hoặc có tin người dùng thật;
- TOOL DÀI: chỉ có tool_result (tên tool lấy từ tool_use của request trước);
- KHÁC: còn lại.
Chỉ in số liệu và vị trí file tương đối so với --projects-dir, không in nội dung hội thoại.
Module cũng cung cấp scan_file()/iter_transcripts() cho compare_periods.py.
Chạy: python3 -I resume_miss.py [--projects-dir DIR] [--out FILE]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics as st
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

DEFAULT_PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")
SUBAGENT_DIR_MARK = f"{os.sep}subagents{os.sep}"
BIG_WRITE = 20_000      # cùng ngưỡng với compact_cache.py
TTL_5M = 300            # giây
TTL_1H = 3600
GAP_BUCKETS = [(300, 600, "5-10m"), (600, 1200, "10-20m"), (1200, 3600, "20-60m")]
CTX_BUCKETS = [(0, 50_000, "<50k"), (50_000, 100_000, "50-100k"),
               (100_000, 200_000, "100-200k"), (200_000, 10**12, ">200k")]
RESUME, TOOL, OTHER = "a_RESUME", "b_TOOL_DAI", "c_KHAC"
END_TURN = "end_turn"
SYNTHETIC_MODEL = "<synthetic>"


@dataclass
class Req:
    key: str
    ts: datetime
    line: int
    model: str
    inp: int
    w5: int
    w1: int
    rd: int
    out: int
    stop: str | None
    tools: dict[str, str] = field(default_factory=dict)   # tool_use id -> name

    @property
    def write(self) -> int:
        return self.w5 + self.w1

    @property
    def ctx(self) -> int:
        return self.inp + self.rd + self.write


@dataclass
class Transition:
    """Request `cur` cùng nguyên nhân tính từ request liền trước `prev`."""
    prev: Req
    cur: Req
    kind: str
    detail: str
    tool_dur: float | None

    @property
    def gap(self) -> float:
        return (self.cur.ts - self.prev.ts).total_seconds()

    @property
    def is_big_mid_miss(self) -> bool:
        """Miss lớn trong khoảng 5-60 phút (cache 5m đã hết, 1h còn)."""
        return self.cur.write > BIG_WRITE and TTL_5M < self.gap <= TTL_1H


@dataclass
class FileScan:
    path: str
    reqs: list[Req]
    transitions: list[Transition]


def ts_of(o: dict) -> datetime:
    return datetime.fromisoformat(o["timestamp"].replace("Z", "+00:00"))


def make_req(o: dict, ln: int) -> Req:
    m = o["message"]
    u = m["usage"]
    cc = u.get("cache_creation") or {}
    w5, w1 = cc.get("ephemeral_5m_input_tokens"), cc.get("ephemeral_1h_input_tokens")
    if w5 is None and w1 is None:
        w5, w1 = u.get("cache_creation_input_tokens") or 0, 0
    key = o.get("requestId") or m.get("id") or f"{ln}"
    return Req(key, ts_of(o), ln, m.get("model", "?"), u.get("input_tokens") or 0, w5 or 0, w1 or 0,
               u.get("cache_read_input_tokens") or 0, u.get("output_tokens") or 0, m.get("stop_reason"))


def user_kind(o: dict) -> str:
    """'tool_result' | 'human' | 'meta' cho một bản ghi user."""
    if o.get("isMeta") or o.get("isCompactSummary"):
        return "meta"
    c = (o.get("message") or {}).get("content")
    if isinstance(c, list) and c and all(isinstance(b, dict) and b.get("type") == "tool_result" for b in c):
        return "tool_result"
    return "human"


def origin_label(o: dict) -> str:
    org = o.get("origin")
    return json.dumps(org, sort_keys=True)[:60] if isinstance(org, (dict, list)) else str(org)


def bucket(v: float, buckets: list) -> str:
    return next((n for lo, hi, n in buckets if lo <= v < hi), "?")


def classify(prev: Req, between: list[dict]) -> tuple[str, str, float | None]:
    kinds = [(user_kind(o), o) for o in between if o.get("type") == "user"]
    # Tin tiếp việc (SendMessage) được ghi là user isMeta=True có "origin", đến sau end_turn.
    new_msgs = [o for k, o in kinds if k != "tool_result"]
    if new_msgs and (prev.stop == END_TURN or any(k == "human" for k, _ in kinds)):
        return RESUME, origin_label(new_msgs[-1]), None
    results = [o for k, o in kinds if k == "tool_result"]
    if results:
        last = results[-1]
        ids = [b.get("tool_use_id") for b in last["message"]["content"]]
        name = next((prev.tools[i] for i in ids if i in prev.tools), "?")
        return TOOL, name, (ts_of(last) - prev.ts).total_seconds()
    desc = ",".join(sorted({f'{o.get("type")}/{o.get("subtype", "")}' for o in between})) or "không có bản ghi"
    return OTHER, desc, None


def scan_file(path: str) -> FileScan:
    """Đọc một transcript: danh sách request (khử dòng trùng) và các chuyển tiếp đã phân loại."""
    reqs: list[Req] = []
    transitions: list[Transition] = []
    cur: Req | None = None
    between: list[dict] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln, raw in enumerate(fh, 1):
            try:
                o = json.loads(raw)
            except json.JSONDecodeError:
                continue
            m = o.get("message") or {}
            if o.get("type") != "assistant" or not m.get("usage") or m.get("model") == SYNTHETIC_MODEL:
                if "timestamp" in o:
                    between.append(o)
                continue
            new = make_req(o, ln)
            if cur is not None and new.key == cur.key:     # dòng trùng của cùng request: giữ usage cuối
                new.ts, new.line, new.tools = cur.ts, cur.line, cur.tools
                new.stop = new.stop or cur.stop
                reqs[-1] = new
                if transitions and transitions[-1].cur is cur:
                    transitions[-1].cur = new
                cur = new
            else:
                if cur is not None:
                    transitions.append(Transition(cur, new, *classify(cur, between)))
                reqs.append(new)
                cur = new
                between = []
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    cur.tools[b.get("id")] = b.get("name", "?")
    return FileScan(path, reqs, transitions)


def is_subagent(path: str) -> bool:
    return SUBAGENT_DIR_MARK in path


def iter_transcripts(root: str) -> list[str]:
    return sorted(glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True))


def report(scans: list[FileScan], root: str) -> str:
    trans = [t for s in scans for t in s.transitions]
    where = {id(t): os.path.relpath(s.path, root) for s in scans for t in s.transitions}
    miss = [t for t in trans if t.is_big_mid_miss]
    lines: list[str] = []
    p = lines.append
    p(f"Tổng miss subagent >20k write, gap 5-60m: {len(miss)}")
    by: dict[str, list[Transition]] = defaultdict(list)
    for t in miss:
        by[t.kind].append(t)
    for kind in (RESUME, TOOL, OTHER):
        ms = by[kind]
        if not ms:
            p(f"{kind}: 0")
            continue
        p(f"{kind}: n={len(ms)} write={sum(t.cur.write for t in ms):,} "
          f"gap_median={st.median(t.gap for t in ms) / 60:.1f}m ctx_median={st.median(t.cur.ctx for t in ms):,.0f}")
    ra = by[RESUME]
    p("  (a) gap: " + str(Counter(bucket(t.gap, GAP_BUCKETS) for t in ra)))
    p("  (a) ctx lúc resume: " + str(Counter(bucket(t.cur.ctx, CTX_BUCKETS) for t in ra)))
    p("  (a) origin: " + str(Counter(t.detail for t in ra).most_common(4)))
    tb = by[TOOL]
    p("  (b) top tool: " + str(Counter(t.detail for t in tb).most_common(8)))
    if tb:
        p(f"  (b) thời lượng tool median={st.median(t.tool_dur for t in tb) / 60:.1f}m")
    p("  (c) mô tả: " + str(Counter(t.detail for t in by[OTHER]).most_common(5)))
    rg = [t.gap for t in trans if t.kind == RESUME]
    warm = sum(g <= TTL_5M for g in rg)
    p(f"Resume subagent mọi khoảng cách: {len(rg)}, <=5m: {warm} ({warm / max(1, len(rg)):.1%}), "
      f"5-60m: {sum(TTL_5M < g <= TTL_1H for g in rg)}, >1h: {sum(g > TTL_1H for g in rg)}")
    for kind in (RESUME, TOOL, OTHER):
        for t in by[kind][:1]:
            p(f"Ví dụ {kind}: miss @{where[id(t)]}:{t.cur.line} (request trước dòng {t.prev.line}) "
              f"gap={t.gap / 60:.1f}m write={t.cur.write:,} ctx={t.cur.ctx:,} {t.detail}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--projects-dir", default=DEFAULT_PROJECTS)
    ap.add_argument("--out", help="ghi kết quả ra file (mặc định chỉ in stdout)")
    args = ap.parse_args()
    scans = [scan_file(f) for f in iter_transcripts(args.projects_dir) if is_subagent(f)]
    text = report(scans, args.projects_dir)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
