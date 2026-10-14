"""Khai báo subcommand, hiển thị kết quả và điểm vào ``main`` của CLI Jira."""

from __future__ import annotations

import argparse
import sys
import urllib.parse
from collections.abc import Mapping
from typing import Any, Final

from jira_tools import config as jira_config
from jira_tools import createmeta, worklog
from jira_tools.client import JiraClient, build_ssl_context, resolve_token
from jira_tools.errors import (
    EXIT_API_ERROR,
    EXIT_OK,
    CommentNotStored,
    ConfigError,
    JiraCliError,
)
from jira_tools.output import dry_run as _dry_run
from jira_tools.output import print_json as _print_json
from jira_tools.payloads import (
    DEFAULT_ISSUE_TYPE,
    build_create_payload,
    build_transition_payload,
    build_update_payload,
    parse_field_assignments,
    select_transition,
    transition_label,
)

SEARCH_DEFAULT_LIMIT: Final = 50

#: Các field lấy về cho ``get`` — xin đúng phần in ra, không kéo cả issue.
#: ``description`` nằm trong danh sách vì thiếu nó thì ``get`` im lặng bỏ qua trường này và
#: người đọc kết luận nhầm là issue **không có** mô tả (đã xảy ra thật với PROJ-9).
GET_ISSUE_FIELDS: Final = (
    "summary,status,assignee,issuetype,priority,labels,timetracking,description"
)

#: Dòng ngăn giữa khối field ngắn và phần mô tả dài, để mô tả không lẫn vào phần tóm tắt.
DESCRIPTION_HEADER: Final = "--- description ---"
#: Hai trạng thái "không có nội dung" được in khác nhau: Jira phân biệt field vắng/``null``
#: với chuỗi rỗng, và gộp chúng lại chính là cách che mất lỗi mà thay đổi này đang sửa.
DESCRIPTION_ABSENT: Final = "(không có mô tả)"
DESCRIPTION_EMPTY: Final = "(mô tả rỗng)"


def _named(value: Any, key: str = "name") -> str:
    """Jira trả object lồng cho status/assignee/...; lấy nhãn, thiếu thì ``-``."""
    return str(value.get(key, "-")) if isinstance(value, dict) else "-"


def _print_issue(client: JiraClient, issue: Mapping[str, Any]) -> None:
    fields = issue.get("fields") or {}
    key = str(issue.get("key", "?"))
    print(f"key       {key}")
    print(f"summary   {fields.get('summary', '')}")
    print(f"status    {_named(fields.get('status'))}")
    print(f"assignee  {_named(fields.get('assignee'), 'displayName')}")
    print(f"issuetype {_named(fields.get('issuetype'))}")
    print(f"priority  {_named(fields.get('priority'))}")
    print(f"labels    {', '.join(fields.get('labels') or ()) or '-'}")
    print(f"url       {client.browse_url(key)}")
    print()
    print(DESCRIPTION_HEADER)
    print(render_description(fields.get("description")))


def render_description(value: Any) -> str:
    """Mô tả in nguyên văn; hai dạng "rỗng" được đánh dấu chứ không in ra khoảng trắng.

    Jira Server trả mô tả ở dạng text/wiki-markup (không phải ADF), nên không cần chuyển đổi.
    """
    if value is None:
        return DESCRIPTION_ABSENT
    text = str(value)
    return text if text.strip() else DESCRIPTION_EMPTY


def cmd_whoami(client: JiraClient, args: argparse.Namespace) -> int:
    me = client.request("GET", client.api("/myself"))
    if args.json:
        _print_json(me)
        return EXIT_OK
    print(f"name         {me.get('name', '-')}")
    print(f"displayName  {me.get('displayName', '-')}")
    print(f"emailAddress {me.get('emailAddress', '-')}")
    return EXIT_OK


def _fetch_issue_types(client: JiraClient, project_key: str) -> list[dict[str, Any]]:
    return createmeta.collect_pages(
        lambda start_at: client.request(
            "GET", createmeta.issue_types_path(project_key, start_at, client.api_prefix)
        )
    )


def _fetch_issue_type_fields(
    client: JiraClient, project_key: str, issue_type_id: str
) -> list[dict[str, Any]]:
    return createmeta.collect_pages(
        lambda start_at: client.request(
            "GET",
            createmeta.issue_type_fields_path(
                project_key, issue_type_id, start_at, client.api_prefix
            ),
        )
    )


def cmd_meta(client: JiraClient, args: argparse.Namespace) -> int:
    """Hai bước: danh sách issue type, rồi field của **từng** type (Jira 9 không gộp hai bước).

    Vì vậy lệnh phát N+1 request; ``--type`` thu về đúng một issue type khi chỉ cần kiểm một cái.
    """
    issue_types = _fetch_issue_types(client, args.project)
    if not issue_types:
        print(f"Không thấy project {args.project} (sai key, hoặc token không có quyền tạo issue).")
        return EXIT_API_ERROR
    merged = [
        createmeta.merge_issue_type(
            issue_type,
            _fetch_issue_type_fields(client, args.project, str(issue_type.get("id", ""))),
        )
        for issue_type in createmeta.select_issue_types(issue_types, args.type)
    ]
    if args.json:
        _print_json({"projectKey": args.project, "issuetypes": merged})
        return EXIT_OK
    parsed = [createmeta.parse_issue_type(issue_type) for issue_type in merged]
    for line in createmeta.render_meta(args.project, parsed):
        print(line)
    return EXIT_OK


def cmd_create(client: JiraClient, args: argparse.Namespace) -> int:
    payload = build_create_payload(
        project=args.project,
        summary=args.summary,
        issue_type=args.type,
        description=args.description,
        labels=args.label or (),
        assignee=args.assignee,
        priority=args.priority,
        parent=args.parent,
        fields=parse_field_assignments(args.field),
        create_defaults=args.project_config.create_defaults,
    )
    path = client.api("/issue")
    if args.dry_run:
        return _dry_run("POST", client.url(path), payload)
    created = client.request("POST", path, payload)
    if args.json:
        _print_json(created)
        return EXIT_OK
    key = str(created.get("key", "?"))
    print(f"{key}  {client.browse_url(key)}")
    return EXIT_OK


def cmd_update(client: JiraClient, args: argparse.Namespace) -> int:
    payload = build_update_payload(
        summary=args.summary,
        description=args.description,
        labels=args.label or (),
        assignee=args.assignee,
        priority=args.priority,
        fields=parse_field_assignments(args.field),
    )
    if not payload["fields"]:
        raise ConfigError("update cần ít nhất một field: --summary / --description / --label / ...")
    path = client.api(f"/issue/{args.key}")
    if args.dry_run:
        return _dry_run("PUT", client.url(path), payload)
    client.request("PUT", path, payload)  # 204 No Content ⇒ body rỗng, không parse JSON
    print(f"{args.key} đã cập nhật: {', '.join(sorted(payload['fields']))}")
    return EXIT_OK


def cmd_comment(client: JiraClient, args: argparse.Namespace) -> int:
    payload = {"body": args.body}
    path = client.api(f"/issue/{args.key}/comment")
    if args.dry_run:
        return _dry_run("POST", client.url(path), payload)
    created = client.request("POST", path, payload)
    if args.json:
        _print_json(created)
        return EXIT_OK
    print(f"{args.key} đã thêm comment id={created.get('id', '?')}")
    return EXIT_OK


def _fetch_transitions(client: JiraClient, key: str) -> list[dict[str, Any]]:
    data = client.request("GET", client.api(f"/issue/{key}/transitions"))
    return list(data.get("transitions") or [])


def cmd_transitions(client: JiraClient, args: argparse.Namespace) -> int:
    transitions = _fetch_transitions(client, args.key)
    if args.json:
        _print_json(transitions)
        return EXIT_OK
    for transition in transitions:
        print(transition_label(transition))
    if not transitions:
        print(f"{args.key} không có transition nào đang mở cho tài khoản này.")
    return EXIT_OK


def _comment_path(client: JiraClient, key: str) -> str:
    return client.api(f"/issue/{key}/comment")


def _comparable_body(value: Any) -> str:
    """Chỉ san xuống dòng ``\\r\\n`` và khoảng trắng hai đầu — Jira có thể trả lại như vậy."""
    return str(value or "").replace("\r\n", "\n").strip()


def _post_verified_comment(client: JiraClient, key: str, body: str) -> str:
    """Đăng comment qua endpoint riêng rồi đọc lại; trả id, hoặc ``CommentNotStored``."""
    created = client.request("POST", _comment_path(client, key), {"body": body})
    comment_id = str((created or {}).get("id") or "")
    if not comment_id:
        raise CommentNotStored(key, "Jira không trả id comment")
    stored = client.request("GET", f"{_comment_path(client, key)}/{comment_id}")
    if _comparable_body((stored or {}).get("body")) != _comparable_body(body):
        raise CommentNotStored(key, f"đọc lại comment id={comment_id} không khớp nội dung")
    return comment_id


def cmd_transition(client: JiraClient, args: argparse.Namespace) -> int:
    """Chuyển trạng thái, rồi mới đăng ``--comment`` bằng ``POST /issue/<KEY>/comment``.

    Không nhét comment vào ``update.comment`` của transition: Jira Server bỏ qua nó lặng lẽ (vẫn
    trả 204) khi transition không có screen chứa field Comment — đúng trường hợp của mọi
    transition trong project PROJ (đo 2026-09-23, ``expand=transitions.fields`` trả ``{}``).
    """
    path = client.api(f"/issue/{args.key}/transitions")
    if args.dry_run:
        # Không tra được id thật nếu không gọi mạng ⇒ nói thẳng, đừng in id giả như thật.
        print(f"(bỏ qua GET {client.url(path)} — cần mạng để tra id của {args.to!r})")
        _dry_run("POST", client.url(path), build_transition_payload("<id>"))
        if args.comment is not None:
            _dry_run("POST", client.url(_comment_path(client, args.key)), {"body": args.comment})
        return EXIT_OK
    transition = select_transition(_fetch_transitions(client, args.key), args.to)
    client.request("POST", path, build_transition_payload(str(transition["id"])))
    print(f"{args.key} → {transition_label(transition)}")
    if args.comment is not None:
        comment_id = _post_verified_comment(client, args.key, args.comment)
        print(f"{args.key} đã thêm comment id={comment_id}")
    return EXIT_OK


def cmd_get(client: JiraClient, args: argparse.Namespace) -> int:
    query = urllib.parse.urlencode({"fields": GET_ISSUE_FIELDS})
    issue = client.request("GET", client.api(f"/issue/{args.key}?{query}"))
    if args.json:
        _print_json(issue)
        return EXIT_OK
    _print_issue(client, issue)
    return EXIT_OK


def cmd_search(client: JiraClient, args: argparse.Namespace) -> int:
    payload = {"jql": args.jql, "maxResults": args.limit, "fields": ["summary", "status"]}
    result = client.request("POST", client.api("/search"), payload)
    if args.json:
        _print_json(result)
        return EXIT_OK
    issues = result.get("issues") or []
    for issue in issues:
        fields = issue.get("fields") or {}
        status = _named(fields.get("status"))
        print(f"{str(issue.get('key', '?')):<12} {status:<16} {fields.get('summary', '')}")
    print(f"-- {len(issues)}/{result.get('total', '?')} issue")
    return EXIT_OK


FIELD_HELP: Final = (
    'gán field bất kỳ, lặp lại được: --field customfield_10101=\'{"value":"A"}\' '
    "(giá trị parse được thành JSON thì gửi JSON, không thì gửi chuỗi)"
)


def _add_editable_flags(parser: argparse.ArgumentParser) -> None:
    """Các cờ dùng chung giữa ``create`` và ``update``."""
    parser.add_argument("--description", help="mô tả (text/wiki-markup, KHÔNG phải ADF)")
    parser.add_argument("--label", action="append", help="nhãn, lặp lại được")
    parser.add_argument("--assignee", help="username Jira (không phải email)")
    parser.add_argument("--priority", help="tên priority, ví dụ High")
    parser.add_argument("--field", action="append", metavar="KEY=VALUE", help=FIELD_HELP)


PROG: Final = "jira-cli"
PROJECT_HELP: Final = (
    "key dự án Jira; bỏ trống thì lấy JIRA_PROJECT, rồi dự án có 'repos' khớp repo git hiện tại"
)
#: Lệnh cần biết dự án — chỉ các lệnh này mới đòi khớp dự án (không khớp ⇒ mã 2).
PROJECT_COMMANDS: Final = frozenset({"meta", "create"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "CLI Jira Server (REST v2, xác thực PAT Bearer). Host và dự án lấy từ "
            "config/jira.json của plugin; ghi đè bằng JIRA_BASE_URL / JIRA_PROJECT / --project."
        ),
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="in nguyên response JSON")
    write = argparse.ArgumentParser(add_help=False)
    write.add_argument(
        "--dry-run",
        action="store_true",
        help="in method + URL + payload rồi thoát 0, không gọi mạng",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    whoami = subparsers.add_parser("whoami", parents=[common], help="tài khoản của PAT hiện tại")
    whoami.set_defaults(handler=cmd_whoami)

    meta = subparsers.add_parser(
        "meta", parents=[common], help="issue type + field bắt buộc của project"
    )
    meta.add_argument("--project", help=PROJECT_HELP)
    meta.add_argument(
        "--type",
        help="chỉ xin field của một issue type (tên, không phân biệt hoa thường); "
        "bỏ trống thì liệt kê mọi issue type",
    )
    meta.set_defaults(handler=cmd_meta)

    create = subparsers.add_parser("create", parents=[common, write], help="tạo issue")
    create.add_argument("--summary", required=True)
    create.add_argument("--project", help=PROJECT_HELP)
    create.add_argument("--type", default=DEFAULT_ISSUE_TYPE, help="issue type (mặc định Task)")
    create.add_argument("--parent", help="key issue cha, dùng cho sub-task")
    _add_editable_flags(create)
    create.set_defaults(handler=cmd_create)

    update = subparsers.add_parser("update", parents=[common, write], help="sửa issue")
    update.add_argument("key")
    update.add_argument("--summary")
    _add_editable_flags(update)
    update.set_defaults(handler=cmd_update)

    comment = subparsers.add_parser("comment", parents=[common, write], help="thêm comment")
    comment.add_argument("key")
    comment.add_argument("--body", required=True)
    comment.set_defaults(handler=cmd_comment)

    transitions = subparsers.add_parser(
        "transitions", parents=[common], help="các transition đang mở của issue"
    )
    transitions.add_argument("key")
    transitions.set_defaults(handler=cmd_transitions)

    transition = subparsers.add_parser(
        "transition", parents=[common, write], help="chuyển trạng thái issue"
    )
    transition.add_argument("key")
    transition.add_argument(
        "--to",
        required=True,
        help="tên transition hoặc trạng thái đích, không phân biệt hoa thường",
    )
    transition.add_argument("--comment", help="comment kèm theo lúc chuyển")
    transition.set_defaults(handler=cmd_transition)

    worklog.add_worklog_parser(subparsers, parents=[common, write])

    get = subparsers.add_parser("get", parents=[common], help="tóm tắt một issue")
    get.add_argument("key")
    get.set_defaults(handler=cmd_get)

    search = subparsers.add_parser("search", parents=[common], help="tìm issue bằng JQL")
    search.add_argument("--jql", required=True)
    search.add_argument("--limit", type=int, default=SEARCH_DEFAULT_LIMIT)
    search.set_defaults(handler=cmd_search)
    return parser


def _resolve_project(
    config: jira_config.JiraConfig, args: argparse.Namespace
) -> jira_config.Project | None:
    """Lệnh cần dự án thì không khớp là lỗi; lệnh khác chỉ dùng dự án để chọn host.

    Với lệnh không cần dự án (whoami, get, search...), không khớp dự án nào thì dùng
    ``default_profile`` — đúng thứ tự host đã chốt, không phải nuốt lỗi.
    """
    explicit = getattr(args, "project", None)
    if args.command in PROJECT_COMMANDS:
        return jira_config.resolve_project(config, explicit)
    try:
        return jira_config.resolve_project(config, explicit)
    except ConfigError:
        return None


def build_client(config: jira_config.JiraConfig, project: jira_config.Project | None) -> JiraClient:
    profile = jira_config.resolve_profile(config, project)
    # Truyền hàm chứ không gọi ngay: token chỉ cần khi sắp phát request, nên ``--dry-run`` xem
    # được URL + payload mà không đòi PAT.
    return JiraClient(
        base_url=jira_config.resolve_base_url(profile),
        token=lambda: resolve_token(config, profile),
        api_prefix=profile.api_prefix,
        ssl_context=build_ssl_context(profile),
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = jira_config.load_config()
        project = _resolve_project(config, args)
        if project is not None:
            args.project = project.key
        args.project_config = project
        exit_code: int = args.handler(build_client(config, project), args)
    except JiraCliError as error:
        print(str(error), file=sys.stderr)
        return error.exit_code
    return exit_code
