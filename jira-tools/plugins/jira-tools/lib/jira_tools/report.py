"""Lệnh ``report``: thu việc đã làm / sẽ làm trong tuần từ Jira + git và in báo cáo.

- Không cờ hiển thị: in bản nháp máy tạo (4 báo cáo khi ``--kind all``).
- ``--json``: in dữ liệu thu được để Claude soạn nội dung (skill ``weekly-report``).
- ``--input FILE``: chỉ render JSON đã soạn, không gọi Jira (không cần PAT).

Chỉ đọc, nên không có ``--dry-run``.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any, Final

from jira_tools import report_data
from jira_tools.client import JiraClient
from jira_tools.errors import EXIT_OK, ConfigError
from jira_tools.output import print_json
from jira_tools.report_period import Period, done_period, parse_day, plan_period
from jira_tools.report_render import render_draft, render_input

KIND_DONE: Final = "done"
KIND_PLAN: Final = "plan"
KIND_ALL: Final = "all"
KINDS: Final = (KIND_DONE, KIND_PLAN, KIND_ALL)
DEFAULT_PAGE_SIZE: Final = 100


def _periods(args: argparse.Namespace) -> dict[str, Period]:
    """Khoảng ngày của từng kind; ``--from``/``--to`` chỉ ghi đè khi kind là done hoặc plan."""
    anchor = parse_day(args.anchor, "--anchor") if args.anchor else date.today()
    periods = {KIND_DONE: done_period(anchor), KIND_PLAN: plan_period(anchor)}
    if args.date_from is None and args.date_to is None:
        return periods if args.kind == KIND_ALL else {args.kind: periods[args.kind]}
    if args.kind == KIND_ALL:
        raise ConfigError("--from/--to chỉ dùng với --kind done hoặc --kind plan")
    base = periods[args.kind]
    start = parse_day(args.date_from, "--from") if args.date_from else base.start
    end = parse_day(args.date_to, "--to") if args.date_to else base.end
    if end < start:
        raise ConfigError("--to phải không trước --from")
    return {args.kind: Period(start, end)}


def _repos(args: argparse.Namespace) -> list[str]:
    return list(args.repo) if args.repo else [os.getcwd()]


def _git_lines(args: argparse.Namespace, period: Period) -> list[str]:
    lines: list[str] = []
    for repo in _repos(args):
        lines.extend(report_data.read_git_log(repo, args.git_author, period))
    return lines


def collect(client: JiraClient, args: argparse.Namespace) -> dict[str, Any]:
    """Dữ liệu ``--json``: ``project``, ``title`` và phần ``done``/``plan`` theo kind."""
    periods = _periods(args)
    if not args.project:
        raise ConfigError(
            "Không xác định được dự án: truyền --project hoặc chạy trong repo đã khai"
        )
    project_config = args.project_config
    fields = project_config.fields if project_config else {}
    report_config = project_config.report if project_config else {}
    ctx = report_data.ReportContext(
        client=client,
        project=args.project,
        user=args.user,
        limit=args.limit,
        epic_field=report_data.resolve_epic_field(client, fields),
        exclude_epics=tuple(args.exclude_epic or ()),
    )
    data: dict[str, Any] = {
        "project": args.project,
        "title": report_data.resolve_title(client, args.project, report_config),
    }
    if KIND_DONE in periods:
        period = periods[KIND_DONE]
        issues = report_data.collect_done(ctx, period, _git_lines(args, period))
        data[KIND_DONE] = {**period.as_dict(), "issues": issues}
    if KIND_PLAN in periods:
        period = periods[KIND_PLAN]
        issues = report_data.collect_plan(ctx)
        hours = report_data.remaining_hours(issues)
        data[KIND_PLAN] = {**period.as_dict(), "issues": issues, "remaining_hours": hours}
    return data


def _read_input(path: str) -> Any:
    try:
        return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"Không thấy file --input {path}") from None
    except (OSError, ValueError) as error:
        raise ConfigError(f"Không đọc được --input {path}: {type(error).__name__}") from None


def cmd_report(client: JiraClient, args: argparse.Namespace) -> int:
    if args.input:
        print(render_input(_read_input(args.input)))
        return EXIT_OK
    data = collect(client, args)
    if args.json:
        print_json(data)
    else:
        print(render_draft(data))
    return EXIT_OK


def add_report_parser(
    subparsers: Any, parents: Sequence[argparse.ArgumentParser]
) -> argparse.ArgumentParser:
    """Đăng ký subcommand ``report`` vào parser của ``cli``."""
    parser = subparsers.add_parser(
        "report", parents=list(parents), help="báo cáo tuần: việc đã làm / sẽ làm"
    )
    parser.add_argument("--project", help="key dự án (mặc định theo repo git hiện tại)")
    parser.add_argument("--kind", choices=KINDS, default=KIND_ALL)
    parser.add_argument("--anchor", help="ngày neo YYYY-MM-DD (mặc định hôm nay)")
    parser.add_argument("--from", dest="date_from", help="ghi đè ngày đầu (kind done/plan)")
    parser.add_argument("--to", dest="date_to", help="ghi đè ngày cuối (kind done/plan)")
    parser.add_argument("--user", help="username Jira (mặc định currentUser())")
    parser.add_argument(
        "--repo", action="append", help="repo git để đọc commit; lặp lại được (mặc định cwd)"
    )
    parser.add_argument("--git-author", help="tác giả commit (mặc định git config user.name)")
    parser.add_argument(
        "--exclude-epic", action="append", help="bỏ issue thuộc epic này khỏi plan; lặp lại được"
    )
    parser.add_argument("--input", help="file JSON báo cáo đã soạn; chỉ render, không gọi Jira")
    parser.add_argument("--limit", type=int, default=DEFAULT_PAGE_SIZE, help="cỡ trang search")
    parser.set_defaults(handler=cmd_report)
    return parser
