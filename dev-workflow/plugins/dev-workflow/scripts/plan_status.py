#!/usr/bin/env python3
"""Build a phone-friendly project status page from the repo's Markdown plans.

Usage:
    python3 plan_status.py --repo PATH [--out DIR] [--html] [--days 14]

Writes <out>/plan-status.md (+ .html). Out: --out, `[plan_status] out_dir`, else docs/status.
Plans: Markdown files with task checkboxes under `paths.plans` or the fallback globs, minus
`handoffs`, hidden dirs, node_modules and `[plan_status] exclude`. Manual block survives re-runs.
Exit codes: 0 ok, 2 bad arguments or no plan found.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11: config is optional here
    tomllib = None  # type: ignore[assignment]

EXIT_OK, EXIT_ERROR = 0, 2
CONFIG_RELATIVE = Path(".claude") / "dev-workflow.toml"
CONFIG_SECTION, CONFIG_OUT_KEY, CONFIG_EXCLUDE_KEY = "plan_status", "out_dir", "exclude"
DEFAULT_OUT = "docs/status"
DEFAULT_DAYS = 14
MD_NAME, HTML_NAME = "plan-status.md", "plan-status.html"
FALLBACK_GLOBS = ("docs/plans/**/*.md", "docs/**/*plan*.md", "docs/**/*roadmap*.md",
                  "docs/**/*milestone*.md", "docs/work-in-progress/**/*.md")
MANUAL_START = "<!-- plan-status:manual:start -->"
MANUAL_END = "<!-- plan-status:manual:end -->"
MANUAL_PLACEHOLDER = "_Ghi chú, rủi ro, quyết định cần người (giữ nguyên khi chạy lại)._"
BAR_WIDTH = 10
BAR_FULL, BAR_EMPTY = "▓", "░"
MAX_OPEN_TASKS, MAX_COMMITS = 10, 5
MAX_TASK_CHARS, MAX_TITLE_CHARS, MAX_ITEM_TITLE_CHARS = 90, 40, 30
DEFAULT_EXCLUDE_PARTS = frozenset({"handoffs", "node_modules"})
PLAN_MARKER = "plan"
GIT_TIMEOUT_SECONDS = 20
DONE_STATUSES = frozenset({"completed", "done", "closed", "xong"})
STATUS_LABELS = {"done": "✅ Xong", "active": "🔄 Đang làm", "todo": "⏳ Chưa bắt đầu", "empty": "— Không có task"}

CHECKBOX_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\[([ xX~-])\]\s+(.*)$")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
H1_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
MILESTONE_RE = re.compile(r"\bM(\d+)\b")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
START_KEYS, END_KEYS = ("start", "started"), ("due", "end", "deadline", "target")


@dataclass
class Plan:
    path: str
    title: str
    status: str
    done: int = 0
    skipped: int = 0
    open_tasks: list[str] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)

    @property
    def open(self) -> int:
        return len(self.open_tasks)

    @property
    def percent(self) -> int:
        total = self.done + self.open
        return round(100 * self.done / total) if total else 0

    @property
    def milestone(self) -> int | None:
        match = MILESTONE_RE.search(f"{self.title} {Path(self.path).stem}")
        return int(match.group(1)) if match else None


def parse_frontmatter(text: str) -> dict[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and not line.startswith((" ", "\t")):
            meta[key.strip().lower()] = value.strip().strip("\"'")
    return meta


def shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def clean_task(text: str) -> str:
    return shorten(re.sub(r"\s+", " ", text.replace("**", "").replace("`", "")).strip(), MAX_TASK_CHARS)


def derive_status(meta_status: str, done: int, open_count: int) -> str:
    if meta_status.lower() in DONE_STATUSES or (open_count == 0 and done > 0):
        return "done"
    if done + open_count == 0:
        return "empty"
    return "active" if done else "todo"


def parse_plan(path: Path, repo: Path) -> Plan | None:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = parse_frontmatter(text)
    done = skipped = 0
    open_tasks: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        match = None if in_fence else CHECKBOX_RE.match(line)
        if not match:
            continue
        mark, body = match.group(1), match.group(2)
        if mark in "-~" or body.lstrip().startswith("~~"):
            skipped += 1
        elif mark in "xX":
            done += 1
        else:
            open_tasks.append(clean_task(body))
    if done + skipped + len(open_tasks) == 0:
        return None
    h1 = H1_RE.search(text)
    title = meta.get("title") or (h1.group(1).strip() if h1 else path.stem)
    status = derive_status(meta.get("status", ""), done, len(open_tasks))
    return Plan(path.relative_to(repo).as_posix(), title, status, done, skipped, open_tasks, meta)


def load_config(repo: Path) -> dict:
    path = repo / CONFIG_RELATIVE
    if tomllib is None or not path.is_file():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def find_plan_files(repo: Path, config: dict, out_dir: Path) -> list[Path]:
    plans_dir = config.get("paths", {}).get("plans")
    globs = [f"{plans_dir.rstrip('/')}/**/*.md"] if isinstance(plans_dir, str) and plans_dir else []
    globs += list(FALLBACK_GLOBS)
    extra = config.get(CONFIG_SECTION, {}).get(CONFIG_EXCLUDE_KEY, [])
    excluded = DEFAULT_EXCLUDE_PARTS | ({str(x) for x in extra} if isinstance(extra, list) else set())
    found = {p.resolve() for pattern in globs for p in repo.glob(pattern) if p.is_file()}
    out, root = out_dir.resolve(), repo.resolve()

    def keep(p: Path) -> bool:  # skip handoffs, hidden dirs, node_modules and [plan_status] exclude
        dirs = p.relative_to(root).parts[:-1]
        return out not in p.parents and not any(d in excluded or d.startswith(".") for d in dirs)
    return sorted((p for p in found if keep(p)), key=lambda p: p.as_posix())


def git_lines(repo: Path, *args: str) -> list[str]:
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                                timeout=GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return result.stdout.splitlines() if result.returncode == 0 else []


def progress_bar(percent: int) -> str:
    filled = round(percent * BAR_WIDTH / 100)
    return BAR_FULL * filled + BAR_EMPTY * (BAR_WIDTH - filled) + f" {percent}%"


def md_cell(text: str) -> str:
    return text.replace("|", "\\|")


def sort_key(plan: Plan) -> tuple:
    order = {"active": 0, "todo": 1, "done": 2, "empty": 3}
    milestone = plan.milestone if plan.milestone is not None else 1_000_000
    return (order[plan.status], milestone, plan.path)


@dataclass
class Report:
    plans: list[Plan]
    head: str
    commits: list[str]
    days: int
    today: str
    done: int = field(init=False)
    open: int = field(init=False)
    skipped: int = field(init=False)

    def __post_init__(self) -> None:
        self.done, self.skipped = sum(p.done for p in self.plans), sum(p.skipped for p in self.plans)
        self.open = sum(p.open for p in self.plans)

    @property
    def percent(self) -> int:
        total = self.done + self.open
        return round(100 * self.done / total) if total else 0

    def by_status(self, status: str) -> list[Plan]:
        return [p for p in self.plans if p.status == status]

    def open_items(self) -> list[tuple[Plan, str]]:
        ordered = sorted(self.plans, key=lambda p: (not is_real_plan(p), p.path))
        return [(p, t) for p in ordered if p.status != "done" for t in p.open_tasks][:MAX_OPEN_TASKS]


def is_real_plan(plan: Plan) -> bool:
    return PLAN_MARKER in Path(plan.path).stem.lower() or plan.meta.get("type", "").lower() == PLAN_MARKER


def link(plan: Plan, out_rel: Path | None) -> str:
    """Relative to the output dir when it is inside the repo, else the repo-relative path."""
    return plan.path if out_rel is None else Path(os.path.relpath(plan.path, out_rel)).as_posix()


def summary_lines(report: Report) -> list[str]:
    active = report.by_status("active")
    lines = [
        f"- **Tổng tiến độ:** {report.percent}% ({report.done}/{report.done + report.open} task xong, {report.skipped} bỏ).",
        f"- **Plan:** {len(active) + len(report.by_status('todo'))} đang mở, {len(report.by_status('done'))} xong / {len(report.plans)} plan.",
    ]
    if active:
        lines.append("- **Đang chạy:** " + ", ".join(f"{p.title} ({p.percent}%)" for p in active[:3]) + ".")
    items = report.open_items()
    if items:
        lines.append(f"- **Việc kế tiếp:** {items[0][1]} — _{shorten(items[0][0].title, MAX_ITEM_TITLE_CHARS)}_.")
    lines.append(f"- **Hoạt động {report.days} ngày:** {len(report.commits)} commit.")
    return lines


def milestone_chart(plans: list[Plan]) -> list[str]:
    dated = [p for p in plans if any(DATE_RE.match(p.meta.get(k, "")) for k in START_KEYS)
             and any(DATE_RE.match(p.meta.get(k, "")) for k in END_KEYS)]
    if dated:
        out = ["```mermaid", "gantt", "  dateFormat YYYY-MM-DD", "  title Lịch plan"]
        for i, p in enumerate(sorted(dated, key=lambda p: p.path)):
            start = next(p.meta[k] for k in START_KEYS if DATE_RE.match(p.meta.get(k, "")))
            end = next(p.meta[k] for k in END_KEYS if DATE_RE.match(p.meta.get(k, "")))
            tag = "done" if p.status == "done" else ("active" if p.status == "active" else "")
            name = p.title.replace(":", " ")
            out.append(f"  {name} :{tag + ', ' if tag else ''}p{i}, {start}, {end}")
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
    out += ["  classDef done fill:#2e7d32,color:#fff", "  classDef active fill:#1565c0,color:#fff",
            "  classDef todo fill:#9e9e9e,color:#fff", "  classDef empty fill:#eeeeee", "```"]
    return out


def render_md(report: Report, out_rel: Path, manual: str) -> str:
    lines = [f"# Tình hình plan dự án", "",
             f"Cập nhật {report.today} · commit `{report.head or '?'}`", "", "## Tóm tắt", ""]
    lines += summary_lines(report)
    lines += ["", "## Ghi chú (giữ tay)", "", MANUAL_START, manual, MANUAL_END, "",
              "## Các plan", "", "| Plan | Trạng thái | Tiến độ | Còn |", "|---|---|---|---|"]
    for p in sorted(report.plans, key=sort_key):
        lines.append(f"| [{md_cell(shorten(p.title, MAX_TITLE_CHARS))}]({link(p, out_rel)}) | {STATUS_LABELS[p.status]} "
                     f"| {progress_bar(p.percent)} | {p.open} |")
    lines += ["", "## Phân bố task", "", "```mermaid", "pie showData",
              f'  "Xong" : {report.done}', f'  "Còn" : {report.open}', f'  "Bỏ" : {report.skipped}', "```"]
    chart = milestone_chart(report.plans)
    if chart:
        lines += ["", "## Milestone", ""] + chart
    lines += ["", f"## Việc đang mở (tối đa {MAX_OPEN_TASKS})", ""]
    items = report.open_items()
    lines += [f"- [ ] {md_cell(t)} — [{md_cell(shorten(p.title, MAX_ITEM_TITLE_CHARS))}]({link(p, out_rel)})" for p, t in items] or ["_Không còn việc mở._"]
    lines += ["", f"## Hoạt động {report.days} ngày qua", "", f"{len(report.commits)} commit."]
    if report.commits:
        lines += [""] + [f"- {c}" for c in report.commits[:MAX_COMMITS]]
    return "\n".join(lines) + "\n"


HTML_CSS = """body{font:15px/1.45 -apple-system,system-ui,sans-serif;margin:0;padding:12px;max-width:720px;
color:#1b1f24;background:#fff}h1{font-size:20px}h2{font-size:17px;margin-top:22px}
.card{border:1px solid #d0d7de;border-radius:8px;padding:8px 10px;margin:6px 0}
.bar{background:#e5e7eb;border-radius:4px;height:8px;margin:4px 0}.bar>div{background:#2e7d32;height:8px;border-radius:4px}
.muted{color:#6b7280;font-size:13px}a{color:#0969da}ul{padding-left:20px}
@media(prefers-color-scheme:dark){body{background:#0d1117;color:#e6edf3}.card{border-color:#30363d}a{color:#58a6ff}}"""


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


def render_html(report: Report, out_rel: Path, manual: str) -> str:
    esc = html.escape
    body = [f"<h1>Tình hình plan dự án</h1><p class=muted>Cập nhật {esc(report.today)} · commit {esc(report.head or '?')}</p>",
            "<h2>Tóm tắt</h2><ul>"]
    body += [f"<li>{esc(line[2:].replace('**', ''))}</li>" for line in summary_lines(report)]
    body.append(f"</ul><h2>Ghi chú</h2><div class=card><pre style='white-space:pre-wrap;margin:0'>{esc(manual.strip())}</pre></div>")
    body.append("<h2>Các plan</h2>")
    for p in sorted(report.plans, key=sort_key):
        body.append(f"<div class=card><a href='{esc(link(p, out_rel))}'>{esc(shorten(p.title, MAX_TITLE_CHARS))}</a><div class=bar>"
                    f"<div style='width:{p.percent}%'></div></div><span class=muted>{STATUS_LABELS[p.status]} · "
                    f"{p.percent}% · còn {p.open}</span></div>")
    body.append("<h2>Phân bố task</h2>" + pie_svg([("Xong", report.done, "#2e7d32"),
                                                    ("Còn", report.open, "#1565c0"), ("Bỏ", report.skipped, "#9e9e9e")]))
    body.append("<h2>Việc đang mở</h2><ul>")
    body += [f"<li>{esc(t)} <span class=muted>— {esc(shorten(p.title, MAX_ITEM_TITLE_CHARS))}</span></li>" for p, t in report.open_items()]
    body.append(f"</ul><h2>Hoạt động {report.days} ngày qua</h2><p>{len(report.commits)} commit.</p><ul>")
    body += [f"<li>{esc(c)}</li>" for c in report.commits[:MAX_COMMITS]]
    body.append("</ul>")
    return ("<!doctype html><html lang=vi><head><meta charset=utf-8><meta name=viewport "
            "content='width=device-width,initial-scale=1'><title>Tình hình plan</title>"
            f"<style>{HTML_CSS}</style></head><body>{''.join(body)}</body></html>\n")


def read_manual(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""
    start, end = text.find(MANUAL_START), text.find(MANUAL_END)
    if start < 0 or end < start:
        return MANUAL_PLACEHOLDER
    return text[start + len(MANUAL_START): end].strip("\n")


def resolve_out(repo: Path, config: dict, out_arg: str | None) -> Path:
    if out_arg:
        return Path(out_arg).expanduser().resolve()
    configured = config.get(CONFIG_SECTION, {}).get(CONFIG_OUT_KEY)
    return (repo / (configured if isinstance(configured, str) and configured else DEFAULT_OUT)).resolve()


def build_report(repo: Path, out_dir: Path, days: int, today: str) -> Report:
    config = load_config(repo)
    plans = [p for f in find_plan_files(repo, config, out_dir) if (p := parse_plan(f, repo))]
    head = next(iter(git_lines(repo, "rev-parse", "--short", "HEAD")), "")
    commits = git_lines(repo, "log", f"--since={days} days ago", "--date=short", "--pretty=%ad %h %s")
    return Report(plans, head, commits, days, today)


def generate(repo: Path, out_dir: Path, days: int, with_html: bool, today: str) -> list[Path]:
    report = build_report(repo, out_dir, days, today)
    if not report.plans:
        raise ValueError(f"no plan with task checkboxes found under {repo}")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_abs, root = out_dir.resolve(), repo.resolve()
    out_rel = out_abs.relative_to(root) if out_abs == root or root in out_abs.parents else None
    md_path = out_dir / MD_NAME
    manual = read_manual(md_path)
    md_path.write_text(render_md(report, out_rel, manual), encoding="utf-8")
    written = [md_path]
    if with_html:
        html_path = out_dir / HTML_NAME
        html_path.write_text(render_html(report, out_rel, manual), encoding="utf-8")
        written.append(html_path)
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a phone-friendly plan status page.")
    parser.add_argument("--repo", required=True, help="repository root to scan")
    parser.add_argument("--out", help=f"output dir (default: [{CONFIG_SECTION}] {CONFIG_OUT_KEY} or {DEFAULT_OUT})")
    parser.add_argument("--html", action="store_true", help=f"also write {HTML_NAME}")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help="git activity window in days")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir() or args.days < 1:
        print("plan_status: --repo must be a directory and --days >= 1", file=sys.stderr)
        return EXIT_ERROR
    try:
        config = load_config(repo)
        out_dir = resolve_out(repo, config, args.out)
        written = generate(repo, out_dir, args.days, args.html, dt.date.today().isoformat())
    except (ValueError, OSError) as exc:
        print(f"plan_status: {exc}", file=sys.stderr)
        return EXIT_ERROR
    for path in written:
        print(path)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
