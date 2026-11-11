#!/usr/bin/env python3
"""Build a phone-friendly project status page from the repo's Markdown plans.

Usage:
    dw plan-status --repo PATH [--page NAME] [--out DIR] [--html] [--days 14]

Config: `.claude/plan-status.toml` (`[defaults]` + `[[page]]`), else `[plan_status]` in
`.claude/dev-workflow.toml`. No `[[page]]` -> one page <out>/plan-status.md (+ .html); with pages
each page writes its own `out`, and >= 2 pages also write <out_dir>/README.md (index).
Plans: Markdown files with task checkboxes (page `include` globs, or `paths.plans` + fallback globs),
minus `handoffs`, hidden dirs, node_modules, `exclude` dirs and `exclude_files` globs.
Manual block survives re-runs. Exit codes: 0 ok, 2 bad arguments, bad config or no plan found.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from plan_status_git import RefSource, git_lines

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11: config is optional here
    tomllib = None  # type: ignore[assignment]

EXIT_OK, EXIT_ERROR = 0, 2
CONFIG_RELATIVE = Path(".claude") / "dev-workflow.toml"
PAGES_CONFIG_RELATIVE = Path(".claude") / "plan-status.toml"
CONFIG_SECTION, CONFIG_OUT_KEY, CONFIG_EXCLUDE_KEY = "plan_status", "out_dir", "exclude"
DEFAULTS_SECTION, PAGE_SECTION = "defaults", "page"
DEFAULT_OUT = "docs/status"
DEFAULT_DAYS = 14
DEFAULT_TITLE = "Tình hình plan dự án"
MD_NAME, HTML_SUFFIX, INDEX_NAME = "plan-status.md", ".html", "README.md"
MIN_PAGES_FOR_INDEX = 2
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
    url: str = ""

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
    return parse_text(path.read_text(encoding="utf-8", errors="replace"), path.relative_to(repo).as_posix())


def parse_text(text: str, rel: str) -> Plan | None:
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
    title = meta.get("title") or (h1.group(1).strip() if h1 else Path(rel).stem)
    status = derive_status(meta.get("status", ""), done, len(open_tasks))
    return Plan(rel, title, status, done, skipped, open_tasks, meta)


@dataclass
class Page:
    name: str
    title: str
    md_path: Path
    include: list[str]
    exclude_dirs: frozenset[str]
    exclude_files: list[str] = field(default_factory=list)
    git_paths: list[str] = field(default_factory=list)
    ref: str = ""
    link_base: str = ""


@dataclass
class Settings:
    days: int
    html: bool
    out_dir: Path
    pages: list[Page]
    multi: bool


def read_toml(path: Path) -> dict:
    if tomllib is None or not path.is_file():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def str_list(table: dict, key: str) -> list[str]:
    value = table.get(key, [])
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise ValueError(f"'{key}' must be a list of strings")
    return value


def load_settings(repo: Path) -> Settings:
    pages_cfg = read_toml(repo / PAGES_CONFIG_RELATIVE)
    dw_cfg = {} if pages_cfg else read_toml(repo / CONFIG_RELATIVE)
    defaults = pages_cfg.get(DEFAULTS_SECTION, {}) if pages_cfg else dw_cfg.get(CONFIG_SECTION, {})
    if not isinstance(defaults, dict):
        raise ValueError("config defaults must be a table")
    out_name = defaults.get(CONFIG_OUT_KEY) or DEFAULT_OUT
    out_dir = (repo / str(out_name)).resolve()
    excluded = DEFAULT_EXCLUDE_PARTS | frozenset(str_list(defaults, CONFIG_EXCLUDE_KEY))
    days, with_html = defaults.get("days", DEFAULT_DAYS), defaults.get("html", False)
    if not isinstance(days, int) or isinstance(days, bool) or not isinstance(with_html, bool):
        raise ValueError("'days' must be an integer and 'html' a boolean")
    raw_pages = pages_cfg.get(PAGE_SECTION, [])
    if not isinstance(raw_pages, list) or not all(isinstance(p, dict) for p in raw_pages):
        raise ValueError("[[page]] must be an array of tables")
    if not raw_pages:
        plans_dir = dw_cfg.get("paths", {}).get("plans")
        globs = [f"{plans_dir.rstrip('/')}/**/*.md"] if isinstance(plans_dir, str) and plans_dir else []
        page = Page("", DEFAULT_TITLE, out_dir / MD_NAME, globs + list(FALLBACK_GLOBS), excluded)
        return Settings(days, with_html, out_dir, [page], multi=False)
    pages = []
    for raw in raw_pages:
        name, out = raw.get("name"), raw.get("out")
        if not isinstance(name, str) or not name or not isinstance(out, str) or not out:
            raise ValueError("every [[page]] needs a non-empty 'name' and 'out'")
        pages.append(Page(name, str(raw.get("title") or name), (repo / out).resolve(),
                          str_list(raw, "include") or list(FALLBACK_GLOBS), excluded,
                          str_list(raw, "exclude_files"), str_list(raw, "git_paths"),
                          str(raw.get("ref") or ""), str(raw.get("link_base") or "")))
    if len({p.name for p in pages}) != len(pages):
        raise ValueError("[[page]] names must be unique")
    return Settings(days, with_html, out_dir, pages, multi=True)


def find_plan_files(repo: Path, page: Page) -> list[Path]:
    root = repo.resolve()
    found = {p.resolve() for pattern in page.include for p in root.glob(pattern) if p.is_file()}
    out = page.md_path.parent

    def keep(p: Path) -> bool:  # skip output dir, handoffs, hidden dirs, node_modules, excludes
        rel = p.relative_to(root)
        if out in p.parents or any(fnmatch.fnmatch(rel.as_posix(), g) for g in page.exclude_files):
            return False
        return not any(d in page.exclude_dirs or d.startswith(".") for d in rel.parts[:-1])
    return sorted((p for p in found if keep(p)), key=lambda p: p.as_posix())


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
    source: str = ""
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
    """Web URL for ref plans, else relative to the output dir (inside the repo) or repo-relative."""
    if plan.url:
        return plan.url
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
    return lines + ([report.source] if report.source else [])


def read_manual(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8") if md_path.is_file() else ""
    start, end = text.find(MANUAL_START), text.find(MANUAL_END)
    if start < 0 or end < start:
        return MANUAL_PLACEHOLDER
    return text[start + len(MANUAL_START): end].strip("\n")


def rel_to_repo(repo: Path, out_dir: Path) -> Path | None:
    root = repo.resolve()
    return out_dir.relative_to(root) if out_dir == root or root in out_dir.parents else None


def write_page(repo: Path, page: Page, days: int, with_html: bool, today: str) -> tuple[list[Path], Report]:
    src = RefSource(repo, page.ref, page.link_base) if page.ref else None
    out_rel, manual = rel_to_repo(repo, page.md_path.parent), read_manual(page.md_path)
    plans = src.plans(page, parse_text, out_rel) if src else [
        p for f in find_plan_files(repo, page) if (p := parse_plan(f, repo.resolve()))]
    if not plans:
        raise ValueError(f"no plan with task checkboxes found for page '{page.name or 'default'}' under {repo}")
    head = src.sha if src else next(iter(git_lines(repo, "rev-parse", "--short", "HEAD")), "")
    pathspec = ["--", *page.git_paths] if page.git_paths else []
    commits = git_lines(repo, "log", *([page.ref] if src else []), f"--since={days} days ago",
                        "--date=short", "--pretty=%ad %h %s", *pathspec)
    report = Report(plans, head, commits, days, today, src.source_line(repo) if src else "")
    from plan_status_html import render_html, render_md  # lazy: that module imports this one
    page.md_path.parent.mkdir(parents=True, exist_ok=True)
    page.md_path.write_text(render_md(report, out_rel, manual, page.title), encoding="utf-8")
    written = [page.md_path]
    if with_html:
        html_path = page.md_path.with_suffix(HTML_SUFFIX)
        html_path.write_text(render_html(report, out_rel, manual, page.title), encoding="utf-8")
        written.append(html_path)
    return written, report


def write_index(out_dir: Path, done: list[tuple[Page, Report]]) -> Path:
    lines = [f"# {DEFAULT_TITLE}", "", "## Tóm tắt", "", f"{len(done)} trang; mở từng trang để xem chi tiết.", "",
             "| Trang | Tiến độ | Còn |", "|---|---|---|"]
    for page, report in done:
        href = Path(os.path.relpath(page.md_path, out_dir)).as_posix()
        lines.append(f"| [{md_cell(page.title)}]({href}) | {progress_bar(report.percent)} | {report.open} |")
    out_dir.mkdir(parents=True, exist_ok=True)
    index = out_dir / INDEX_NAME
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return index


def run(repo: Path, args: argparse.Namespace, today: str) -> list[Path]:
    settings = load_settings(repo)
    pages = [p for p in settings.pages if args.page in (None, p.name)]
    if not pages:
        raise ValueError(f"unknown page '{args.page}'; known: {', '.join(p.name for p in settings.pages)}")
    if args.out:
        if len(pages) != 1:
            raise ValueError("--out needs a single page; add --page NAME")
        pages[0].md_path = Path(args.out).expanduser().resolve() / pages[0].md_path.name
    days = args.days if args.days is not None else settings.days
    if days < 1:
        raise ValueError("--days must be >= 1")
    written, done = [], []
    for page in pages:
        files, report = write_page(repo, page, days, args.html or settings.html, today)
        written += files
        done.append((page, report))
    if settings.multi and args.page is None and len(done) >= MIN_PAGES_FOR_INDEX:
        written.append(write_index(settings.out_dir, done))
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate phone-friendly plan status pages.")
    parser.add_argument("--repo", required=True, help="repository root to scan")
    parser.add_argument("--page", help="only this [[page]] name (default: every page)")
    parser.add_argument("--out", help=f"output dir for a single page (default: config or {DEFAULT_OUT})")
    parser.add_argument("--html", action="store_true", help="also write the .html page")
    parser.add_argument("--days", type=int, default=None, help=f"git activity window (default {DEFAULT_DAYS})")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).expanduser().resolve()
    if not repo.is_dir():
        print("plan_status: --repo must be a directory", file=sys.stderr)
        return EXIT_ERROR
    try:
        written = run(repo, args, dt.date.today().isoformat())
    except (ValueError, OSError) as exc:  # tomllib.TOMLDecodeError is a ValueError
        print(f"plan_status: {exc}", file=sys.stderr)
        return EXIT_ERROR
    for path in written:
        print(path)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
