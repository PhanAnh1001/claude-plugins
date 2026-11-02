"""Phân tích ảnh hưởng auto-compact lên prompt cache từ transcript Claude Code.

Ported from session scratchpad 2026-11-02.
In tổng quan cache theo nhóm main/subagent, sự kiện compact, tham số mô hình B/S/g,
phân bố ngữ cảnh và so sánh A/B theo ngày. Chỉ in số liệu và vị trí file (tương đối
so với --projects-dir), không in nội dung hội thoại.
Chạy: python3 -I compact_cache.py [--projects-dir DIR] [--out FILE]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics as st
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

DEFAULT_PROJECTS = os.path.join(os.path.expanduser("~"), ".claude", "projects")
BIG_WRITE = 20_000          # ngưỡng cache_write "lớn" (brief)
TTL_5M = 300                # giây
TTL_1H = 3600
POST_N = 3                  # số request sau compact cần ghi
PRICE = {"input": 1.0, "w5m": 1.25, "w1h": 2.0, "read": 0.1, "output": 5.0}
# Hệ số cache read theo model (bội số giá input; model khác dùng PRICE["read"])
READ_MULT = {"claude-opus-5-5": 0.05, "claude-fable-5-1": 0.025}


def read_mult(model: str) -> float:
    for k, v in READ_MULT.items():
        if model.startswith(k) or k.replace("-", "") in model.replace("-", "").replace(".", ""):
            return v
    return PRICE["read"]


# Mốc đổi autoCompactWindow 400k -> 300k (coordinator cung cấp từ lịch sử config)
PERIOD_A_END = "2026-10-28T11:10:00Z"
PERIOD_B_START = "2026-10-29T04:39:00Z"

BUCKETS = [(0, 50_000, "0-50k"), (50_000, 100_000, "50-100k"), (100_000, 150_000, "100-150k"),
           (150_000, 200_000, "150-200k"), (200_000, 10**12, ">200k")]


@dataclass
class Req:
    ts: datetime
    model: str
    inp: int
    w5: int
    w1: int
    rd: int
    out: int
    file: str
    line: int

    @property
    def write(self) -> int:
        return self.w5 + self.w1

    @property
    def ctx(self) -> int:
        return self.inp + self.rd + self.write

    def cost(self) -> float:
        return (self.inp * PRICE["input"] + self.w5 * PRICE["w5m"] + self.w1 * PRICE["w1h"]
                + self.rd * read_mult(self.model) + self.out * PRICE["output"])


@dataclass
class Compact:
    ts: datetime
    trigger: str
    pre: int
    file: str
    line: int
    before: Req | None = None
    after: list[Req] = field(default_factory=list)


def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def to_req(o: dict, path: str, ln: int) -> Req | None:
    m = o.get("message") or {}
    u = m.get("usage")
    if not u or m.get("model") == "<synthetic>":
        return None
    cw = u.get("cache_creation_input_tokens") or 0
    cc = u.get("cache_creation") or {}
    w5, w1 = cc.get("ephemeral_5m_input_tokens"), cc.get("ephemeral_1h_input_tokens")
    if w5 is None and w1 is None:
        w5, w1 = cw, 0
    return Req(parse_ts(o["timestamp"]), m.get("model", "?"), u.get("input_tokens") or 0,
               w5 or 0, w1 or 0, u.get("cache_read_input_tokens") or 0,
               u.get("output_tokens") or 0, path, ln)


def read_file(path: str) -> list[tuple[str, object]]:
    """Trả về chuỗi sự kiện ('req', Req) / ('compact', Compact) theo thứ tự dòng, đã khử trùng."""
    events: list[tuple[str, object]] = []
    idx: dict[str, int] = {}
    with open(path, encoding="utf-8", errors="replace") as fh:
        for ln, raw in enumerate(fh, 1):
            try:
                o = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if o.get("type") == "system" and o.get("subtype") == "compact_boundary":
                md = o.get("compactMetadata") or {}
                events.append(("compact", Compact(parse_ts(o["timestamp"]), md.get("trigger", "?"),
                                                  md.get("preTokens") or 0, path, ln)))
            elif o.get("type") == "assistant":
                r = to_req(o, path, ln)
                if r is None:
                    continue
                key = o.get("requestId") or (o.get("message") or {}).get("id") or f"{path}:{ln}"
                if key in idx:  # dòng trùng: giữ bản cuối (usage đầy đủ nhất)
                    events[idx[key]] = ("req", r)
                else:
                    idx[key] = len(events)
                    events.append(("req", r))
    return events


def is_sub(path: str) -> bool:
    return "/subagents/" in path


def pct(xs: list[float], q: float) -> float:
    if not xs:
        return float("nan")
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def tri(xs: list[float]) -> str:
    return f"n={len(xs)} p25={pct(xs,.25):,.0f} median={pct(xs,.5):,.0f} p75={pct(xs,.75):,.0f}"


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--projects-dir", default=DEFAULT_PROJECTS)
    ap.add_argument("--out", help="ghi kết quả ra file (mặc định chỉ in stdout)")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    root = args.projects_dir
    files = glob.glob(os.path.join(root, "**", "*.jsonl"), recursive=True)
    groups = {"main": [], "subagent": []}
    seen_keys: set = set()
    compacts: list[Compact] = []
    growth: list[int] = []
    cycle_len: list[int] = []
    gaps_miss = defaultdict(lambda: [0, 0])
    after_flag: set[int] = set()
    sessions = {"main": set(), "subagent": set()}

    for f in files:
        g = "subagent" if is_sub(f) else "main"
        ev = read_file(f)
        reqs_seq: list[Req] = []
        pending: Compact | None = None
        last: Req | None = None
        since = 0
        for kind, x in ev:
            if kind == "compact":
                x.before = last
                if g == "main":
                    compacts.append(x)
                    if since:
                        cycle_len.append(since)
                pending, since = x, 0
                continue
            r: Req = x
            k = (r.file, r.line)
            if k in seen_keys:
                continue
            seen_keys.add(k)
            groups[g].append(r)
            sessions[g].add(f)
            since += 1
            just_after = pending is not None and len(pending.after) == 0
            if pending is not None:
                pending.after.append(r)
                if len(pending.after) >= POST_N:
                    pending = None
            if last is not None and not just_after:
                growth.append(r.ctx - last.ctx)
            if r.write > BIG_WRITE and not just_after:
                gap = (r.ts - last.ts).total_seconds() if last else None
                cat = ("đầu file/phiên" if gap is None else ">1h" if gap > TTL_1H
                       else "5m-1h" if gap > TTL_5M else "<=5m")
                gaps_miss[(g, cat)][0] += 1
                gaps_miss[(g, cat)][1] += r.write
            last = r

    out = []
    p = out.append
    p("# 1. Tổng quan")
    for g, rs in groups.items():
        T = lambda a: sum(getattr(r, a) for r in rs)
        inp, w5, w1, rd, o = T("inp"), T("w5"), T("w1"), T("rd"), T("out")
        hit = rd / max(1, rd + w5 + w1 + inp)
        cost = sum(r.cost() for r in rs)
        p(f"[{g}] files={len(sessions[g])} requests={len(rs)} input={inp:,} w5m={w5:,} w1h={w1:,} "
          f"read={rd:,} output={o:,} hit={hit:.3f} cost_eq_input={cost:,.0f} "
          f"(read {sum(r.rd*read_mult(r.model) for r in rs)/cost:.1%}, write {(w5*1.25+w1*2)/cost:.1%}, out {o*5/cost:.1%}, in {inp/cost:.1%})")
        p(f"  tỉ lệ write 1h/(5m+1h)={w1/max(1,w1+w5):.3f}")
        bm = defaultdict(lambda: [0, 0.0, 0, 0])
        for r in rs:
            x = bm[r.model]; x[0] += 1; x[1] += r.cost(); x[2] += r.w5; x[3] += r.w1
        for mdl, (n, c, a5, a1) in sorted(bm.items(), key=lambda kv: -kv[1][0]):
            p(f"  model {mdl}: req={n} ({n/len(rs):.1%}) cost_eq={c:,.0f} read_mult={read_mult(mdl)} w1h_share={a1/max(1,a5+a1):.3f}")
        by = defaultdict(lambda: [0] * 6)
        for r in rs:
            b = by[r.ts.strftime("%Y-%m")]
            b[0] += 1; b[1] += r.inp; b[2] += r.w5; b[3] += r.w1; b[4] += r.rd; b[5] += r.out
        for mth in sorted(by):
            n, i, a5, a1, d, oo = by[mth]
            p(f"  {g} {mth}: req={n} in={i:,} w5m={a5:,} w1h={a1:,} read={d:,} out={oo:,} "
              f"hit={d/max(1,d+a5+a1+i):.3f}")

    p("\n# 2. Sự kiện compact (main)")
    trig = defaultdict(int)
    for c in compacts:
        trig[c.trigger] += 1
    p(f"tổng={len(compacts)} theo trigger={dict(trig)}")
    for c in sorted(compacts, key=lambda c: c.ts):
        b = c.before
        bs = f"before(read={b.rd:,} write={b.write:,} ctx={b.ctx:,})" if b else "before=None"
        a = " | ".join(f"a{i+1}(read={r.rd:,} w={r.write:,} in={r.inp:,} out={r.out:,})" for i, r in enumerate(c.after))
        p(f"{c.ts:%Y-%m-%d %H:%M} {c.trigger:6} pre={c.pre:,} {bs} {a} @{os.path.relpath(c.file, root)}:{c.line}")
    a1 = [c.after[0] for c in compacts if c.after]
    p(f"a1 cache_read: {tri([r.rd for r in a1])}")
    p(f"a1 cache_write: {tri([r.write for r in a1])}")
    p(f"a1 ctx: {tri([r.ctx for r in a1])}")
    p(f"before ctx: {tri([c.before.ctx for c in compacts if c.before])}")
    p("Ghi chú: request sinh tóm tắt không ghi vào transcript dưới dạng assistant message có usage riêng "
      "(được kiểm tra: không có dòng assistant nào giữa before và boundary) -> S lấy từ cache_write a1.")

    p("\n# 3. preTokens auto-compact theo tháng")
    bym = defaultdict(list)
    for c in compacts:
        if c.trigger == "auto":
            bym[c.ts.strftime("%Y-%m")].append(c.pre)
    for m in sorted(bym):
        xs = bym[m]
        p(f"{m}: n={len(xs)} min={min(xs):,} median={st.median(xs):,.0f} max={max(xs):,}")

    p("\n# 4. Tham số mô hình")
    p(f"B (read a1): {tri([r.rd for r in a1])}")
    p(f"S (write a1): {tri([r.write for r in a1])}")
    p(f"g (Δctx liên tiếp, mọi nhóm, không qua compact): {tri(growth)}  mean={st.mean(growth):,.0f}")
    p(f"g dương: {tri([x for x in growth if x > 0])}")
    p(f"request mỗi chu kỳ compact (giữa 2 compact cùng file): {tri(cycle_len)}")

    p("\n# 5. Cache miss lớn (>20k write) không ngay sau compact")
    for (g, cat), (n, tok) in sorted(gaps_miss.items()):
        p(f"{g:8} {cat:15} n={n} write_tokens={tok:,}")

    p("\n# 6. Phân bố ctx mỗi request")
    for g, rs in groups.items():
        cnt = defaultdict(int)
        for r in rs:
            for lo, hi, name in BUCKETS:
                if lo <= r.ctx < hi:
                    cnt[name] += 1
        p(f"{g}: " + " ".join(f"{n}={cnt[n]} ({cnt[n]/max(1,len(rs)):.1%})" for _, _, n in BUCKETS))

    p("\n# 7. Giai đoạn A/B (main, claude-opus-5-5)")
    a_end, b_start = parse_ts(PERIOD_A_END), parse_ts(PERIOD_B_START)
    post = {(c.after[0].file, c.after[0].line) for c in compacts if c.after}
    for name, ok in (("A", lambda t: t < a_end), ("B", lambda t: t >= b_start)):
        rs = [r for r in groups["main"] if r.model.startswith("claude-opus-5-5") and ok(r.ts)]
        cs = [c for c in compacts if ok(c.ts)]
        cost = sum(r.cost() for r in rs)
        pc = sum(r.w5 * PRICE["w5m"] + r.w1 * PRICE["w1h"] for r in rs if (r.file, r.line) in post)
        rd = sum(r.rd for r in rs); den = sum(r.ctx for r in rs)
        p(f"{name}: req={len(rs)} compact={len(cs)} (auto={sum(c.trigger=='auto' for c in cs)}) "
          f"req/chu_ky={len(rs)/max(1,len(cs)):.1f} ctx_tb={den/max(1,len(rs)):,.0f} hit={rd/max(1,den):.3f} "
          f"cost_tb/req={cost/max(1,len(rs)):,.0f} write_sau_compact={pc:,.0f} ({pc/max(1,cost):.1%} tổng cost) "
          f"preTokens_median={st.median([c.pre for c in cs]) if cs else 0:,.0f}")

    text = "\n".join(out)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
