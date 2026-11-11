"""Page rendering for plan_status.py: Markdown (GitHub, Mermaid) and self-contained HTML
(inline CSS/SVG, no JS, no external URL)."""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import plan_status as ps

HTML_CSS = """body{font:15px/1.45 -apple-system,system-ui,sans-serif;margin:0;padding:12px;max-width:720px;
color:#1b1f24;background:#fff}h1{font-size:20px}h2{font-size:17px;margin-top:22px}
.card{border:1px solid #d0d7de;border-radius:8px;padding:8px 10px;margin:6px 0}
.bar{background:#e5e7eb;border-radius:4px;height:8px;margin:4px 0}.bar>div{background:#2e7d32;height:8px;border-radius:4px}
.muted{color:#6b7280;font-size:13px}a{color:#0969da}ul{padding-left:20px}
@media(prefers-color-scheme:dark){body{background:#0d1117;color:#e6edf3}.card{border-color:#30363d}a{color:#58a6ff}}"""
COLOR_DONE, COLOR_OPEN, COLOR_SKIPPED = "#2e7d32", "#1565c0", "#9e9e9e"
MD_EMPHASIS_RE = re.compile(r"\*\*|(?<!\w)_|_(?!\w)")


def strip_md(text: str) -> str:
    """Drop Markdown emphasis markup (`**`, `_..._`) so it does not show up literally in HTML."""
    return MD_EMPHASIS_RE.sub("", text)


def pie_svg(parts: list[tuple[str, int, str]]) -> str:
    total = sum(v for _, v, _ in parts) or 1
    radius, circ, offset = 15.9155, 100.0, 0.0
    segs = []
    for _, value, color in parts:
        share = 100 * value / total
        segs.append(f'<circle r="{radius}" cx="21" cy="21" fill="none" stroke="{color}" stroke-width="8" '
                    f'stroke-dasharray="{share:.2f} {circ - share:.2f}" stroke-dashoffset="{-offset + 25:.2f}"/>')
        offset += share
    legend = " · ".join(f'<span style="color:{c}">■</span> {html.escape(n)} {v}' for n, v, c in parts)
    return f'<svg viewBox="0 0 42 42" width="140" height="140">{"".join(segs)}</svg><div class="muted">{legend}</div>'


def milestone_chart(plans: list[Any]) -> list[str]:
    def first_date(p: Any, keys: tuple[str, ...]) -> str:
        return next((p.meta[k] for k in keys if ps.DATE_RE.match(p.meta.get(k, ""))), "")

    dated = [p for p in plans if first_date(p, ps.START_KEYS) and first_date(p, ps.END_KEYS)]
    if dated:
        out = ["```mermaid", "gantt", "  dateFormat YYYY-MM-DD", "  title Lịch plan"]
        for i, p in enumerate(sorted(dated, key=lambda p: p.path)):
            tag = p.status if p.status in ("done", "active") else ""
            name = p.title.replace(":", " ")
            out.append(f"  {name} :{tag + ', ' if tag else ''}p{i}, {first_date(p, ps.START_KEYS)}, "
                       f"{first_date(p, ps.END_KEYS)}")
        return out + ["```"]
    stones = sorted((p for p in plans if p.milestone is not None), key=lambda p: (p.milestone, p.path))
    if len(stones) < 2:
        return []
    out = ["```mermaid", "flowchart LR"]
    for i, p in enumerate(stones):
        label = f"M{p.milestone} {p.percent}%".replace('"', "'")
        out.append(f'  n{i}["{label}"]:::{p.status}')
        if i:
            out.append(f"  n{i - 1} --> n{i}")
    out += [f"  classDef done fill:{COLOR_DONE},color:#fff", f"  classDef active fill:{COLOR_OPEN},color:#fff",
            f"  classDef todo fill:{COLOR_SKIPPED},color:#fff", "  classDef empty fill:#eeeeee", "```"]
    return out


def render_md(report: Any, out_rel: Path | None, manual: str, title: str) -> str:
    cell, short = ps.md_cell, ps.shorten
    lines = [f"# {title}", "", f"Cập nhật {report.today} · commit `{report.head or '?'}`", "", "## Tóm tắt", ""]
    lines += ps.summary_lines(report)
    lines += ["", "## Ghi chú (giữ tay)", "", ps.MANUAL_START, manual, ps.MANUAL_END, "",
              "## Các plan", "", "| Plan | Trạng thái | Tiến độ | Còn |", "|---|---|---|---|"]
    for p in sorted(report.plans, key=ps.sort_key):
        lines.append(f"| [{cell(short(p.title, ps.MAX_TITLE_CHARS))}]({ps.link(p, out_rel)}) | "
                     f"{ps.STATUS_LABELS[p.status]} | {ps.progress_bar(p.percent)} | {p.open} |")
    lines += ["", "## Phân bố task", "", "```mermaid", "pie showData",
              f'  "Xong" : {report.done}', f'  "Còn" : {report.open}', f'  "Bỏ" : {report.skipped}', "```"]
    chart = milestone_chart(report.plans)
    if chart:
        lines += ["", "## Milestone", ""] + chart
    lines += ["", f"## Việc đang mở (tối đa {ps.MAX_OPEN_TASKS})", ""]
    lines += [f"- [ ] {cell(t)} — [{cell(short(p.title, ps.MAX_ITEM_TITLE_CHARS))}]({ps.link(p, out_rel)})"
              for p, t in report.open_items()] or ["_Không còn việc mở._"]
    lines += ["", f"## Hoạt động {report.days} ngày qua", "", f"{len(report.commits)} commit."]
    if report.commits:
        lines += [""] + [f"- {c}" for c in report.commits[:ps.MAX_COMMITS]]
    return "\n".join(lines) + "\n"


def render_html(report: Any, out_rel: Path | None, manual: str, title: str) -> str:
    esc = html.escape
    body = [f"<h1>{esc(title)}</h1><p class=muted>Cập nhật {esc(report.today)} · commit {esc(report.head or '?')}</p>",
            "<h2>Tóm tắt</h2><ul>"]
    body += [f"<li>{esc(strip_md(line[2:]))}</li>" for line in ps.summary_lines(report)]
    body.append(f"</ul><h2>Ghi chú</h2><div class=card><pre style='white-space:pre-wrap;margin:0'>{esc(manual.strip())}</pre></div>")
    body.append("<h2>Các plan</h2>")
    for p in sorted(report.plans, key=ps.sort_key):
        body.append(f"<div class=card><a href='{esc(ps.link(p, out_rel))}'>{esc(ps.shorten(p.title, ps.MAX_TITLE_CHARS))}</a>"
                    f"<div class=bar><div style='width:{p.percent}%'></div></div><span class=muted>"
                    f"{ps.STATUS_LABELS[p.status]} · {p.percent}% · còn {p.open}</span></div>")
    body.append("<h2>Phân bố task</h2>" + pie_svg([("Xong", report.done, COLOR_DONE),
                                                    ("Còn", report.open, COLOR_OPEN), ("Bỏ", report.skipped, COLOR_SKIPPED)]))
    body.append("<h2>Việc đang mở</h2><ul>")
    body += [f"<li>{esc(t)} <span class=muted>— {esc(ps.shorten(p.title, ps.MAX_ITEM_TITLE_CHARS))}</span></li>"
             for p, t in report.open_items()]
    body.append(f"</ul><h2>Hoạt động {report.days} ngày qua</h2><p>{len(report.commits)} commit.</p><ul>")
    body += [f"<li>{esc(c)}</li>" for c in report.commits[:ps.MAX_COMMITS]]
    body.append("</ul>")
    return ("<!doctype html><html lang=vi><head><meta charset=utf-8><meta name=viewport "
            f"content='width=device-width,initial-scale=1'><title>{esc(title)}</title>"
            f"<style>{HTML_CSS}</style></head><body>{''.join(body)}</body></html>\n")
