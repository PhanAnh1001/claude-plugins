"""Kiểm tra lệnh ``meta`` của CLI Jira — endpoint createmeta của Jira Server 9.

Không chạm mạng và không chạm database: ``tools/jira/createmeta.py`` giữ riêng phần dựng URL,
gộp trang và định dạng, nên client giả dưới đây chỉ cần trả JSON dựng sẵn.

Lỗi thật đã đo trên Jira production: ``GET /rest/api/2/issue/createmeta?projectKeys=PROJ`` trả
HTTP 404 kèm ``Issue Does Not Exist`` — Jira 9 đã gỡ endpoint đó và đọc chuỗi ``createmeta`` như
một issue key, nên thông báo lỗi không liên quan gì tới nguyên nhân. Các test ở đây khoá **hình
dạng URL** để lần viết lại theo trí nhớ về Jira Cloud là đỏ ngay.
"""

from __future__ import annotations

import json

import pytest

from jira_tools import cli, config, createmeta
from jira_tools.errors import JiraCliError

PROJECT = "PROJ"

#: Hai trang issue type — ``isLast: false`` ở trang đầu buộc CLI phải xin tiếp ``startAt``.
ISSUE_TYPES_PAGE_1 = {
    "maxResults": 1,
    "startAt": 0,
    "total": 2,
    "isLast": False,
    "values": [{"id": "10002", "name": "Task", "subtask": False}],
}
ISSUE_TYPES_PAGE_2 = {
    "maxResults": 1,
    "startAt": 1,
    "total": 2,
    "isLast": True,
    "values": [{"id": "10003", "name": "Sub-task", "subtask": True}],
}

#: Hình dạng thật một phần tử ``values`` của ``.../issuetypes/<ID>``.
TASK_FIELDS = {
    "maxResults": 50,
    "startAt": 0,
    "total": 3,
    "isLast": True,
    "values": [
        {
            "fieldId": "summary",
            "name": "Summary",
            "required": True,
            "hasDefaultValue": False,
            "schema": {"type": "string"},
        },
        {
            "fieldId": "issuetype",
            "name": "Issue Type",
            "required": True,
            "hasDefaultValue": True,
            "schema": {"type": "issuetype"},
        },
        {
            "fieldId": "labels",
            "name": "Labels",
            "required": False,
            "hasDefaultValue": False,
            "schema": {"type": "array"},
        },
    ],
}
SUBTASK_FIELDS = {"maxResults": 50, "startAt": 0, "total": 0, "isLast": True, "values": []}

EXPECTED_META_PATHS = [
    "/rest/api/2/issue/createmeta/PROJ/issuetypes",
    "/rest/api/2/issue/createmeta/PROJ/issuetypes?startAt=1",
    "/rest/api/2/issue/createmeta/PROJ/issuetypes/10002",
    "/rest/api/2/issue/createmeta/PROJ/issuetypes/10003",
]


class RecordingClient:
    """Client giả: ghi lại mọi path được xin và trả trang đã dựng sẵn."""

    api_prefix = config.DEFAULT_API_PREFIX

    def __init__(self, responses: dict[str, object]) -> None:
        self.responses = responses
        self.paths: list[str] = []

    def request(self, method: str, path: str, payload: object | None = None) -> object:
        assert method == "GET"
        self.paths.append(path)
        if path not in self.responses:
            pytest.fail(f"meta gọi path không lường trước: {path}")
        return self.responses[path]


@pytest.fixture
def meta_client() -> RecordingClient:
    return RecordingClient(
        {
            EXPECTED_META_PATHS[0]: ISSUE_TYPES_PAGE_1,
            EXPECTED_META_PATHS[1]: ISSUE_TYPES_PAGE_2,
            EXPECTED_META_PATHS[2]: TASK_FIELDS,
            EXPECTED_META_PATHS[3]: SUBTASK_FIELDS,
        }
    )


def run_meta(client: RecordingClient, argv: list[str]) -> int:
    args = cli.build_parser().parse_args([*argv, "--project", PROJECT])
    return cli.cmd_meta(client, args)  # type: ignore[arg-type]


def test_createmeta_paths_put_the_project_key_in_the_path_not_in_projectkeys() -> None:
    issue_types = createmeta.issue_types_path(PROJECT)
    fields = createmeta.issue_type_fields_path(PROJECT, "10002")

    assert issue_types == "/rest/api/2/issue/createmeta/PROJ/issuetypes"
    assert fields == "/rest/api/2/issue/createmeta/PROJ/issuetypes/10002"
    # Dạng cũ của Jira 8/Cloud: máy chủ 9.x trả 404 "Issue Does Not Exist" cho nó.
    for path in (issue_types, fields, createmeta.issue_types_path(PROJECT, 50)):
        assert "createmeta?projectKeys=" not in path
        assert "projectKeys" not in path


def test_meta_command_requests_only_the_jira_9_paths(meta_client: RecordingClient) -> None:
    exit_code = run_meta(meta_client, ["meta"])

    assert exit_code == 0
    assert meta_client.paths == EXPECTED_META_PATHS
    assert not any("projectKeys" in path for path in meta_client.paths)


def test_meta_follows_pagination_and_merges_both_pages(
    meta_client: RecordingClient, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = run_meta(meta_client, ["meta"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # Trang 2 chỉ được xin khi ``isLast: false`` của trang 1 được tôn trọng.
    assert "/rest/api/2/issue/createmeta/PROJ/issuetypes?startAt=1" in meta_client.paths
    assert "Task (id=10002)" in out and "Sub-task (id=10003)" in out


def test_collect_pages_advances_start_at_and_stops_on_is_last() -> None:
    pages = {0: ISSUE_TYPES_PAGE_1, 1: ISSUE_TYPES_PAGE_2}
    asked: list[int] = []

    def fetch(start_at: int) -> object:
        asked.append(start_at)
        return pages[start_at]

    values = createmeta.collect_pages(fetch)

    assert asked == [0, 1]
    assert [value["name"] for value in values] == ["Task", "Sub-task"]


def test_collect_pages_stops_when_the_server_never_advances() -> None:
    """Máy chủ kẹt ở ``startAt: 0`` với ``isLast: false`` không được làm CLI quay vòng."""
    stuck = {"isLast": False, "startAt": 0, "values": [{"id": "1"}], "maxResults": 1}
    asked: list[int] = []

    def fetch(start_at: int) -> object:
        asked.append(start_at)
        return stuck

    values = createmeta.collect_pages(fetch)

    # Lần thứ hai ``startAt`` tính ra không lớn hơn lần trước ⇒ dừng, không chạm trần MAX_PAGES.
    assert asked == [0, 1]
    assert values == [{"id": "1"}, {"id": "1"}]


def test_meta_output_names_required_fields_and_marks_the_ones_with_a_default(
    meta_client: RecordingClient, capsys: pytest.CaptureFixture[str]
) -> None:
    run_meta(meta_client, ["meta"])

    out = capsys.readouterr().out
    assert "required: summary" in out and "[string]" in out
    # Bắt buộc nhưng có sẵn default ⇒ không phải truyền tay, và đó là thứ người đọc cần biết.
    assert "required: issuetype" in out
    assert createmeta.DEFAULT_VALUE_MARK.strip() in out
    # ``labels`` không bắt buộc: chỉ xuất hiện ở dòng liệt kê, không ở dòng ``required``.
    assert "required: labels" not in out
    assert "field dùng được: summary, issuetype, labels" in out
    assert createmeta.SUBTASK_MARK.strip() in out  # Sub-task được đánh dấu


def test_meta_type_filter_asks_fields_for_that_issue_type_only(
    meta_client: RecordingClient,
) -> None:
    exit_code = run_meta(meta_client, ["meta", "--type", "sub-task"])

    assert exit_code == 0
    assert meta_client.paths[-1] == "/rest/api/2/issue/createmeta/PROJ/issuetypes/10003"
    assert "/rest/api/2/issue/createmeta/PROJ/issuetypes/10002" not in meta_client.paths


def test_meta_unknown_type_lists_the_valid_names(meta_client: RecordingClient) -> None:
    with pytest.raises(JiraCliError) as excinfo:
        run_meta(meta_client, ["meta", "--type", "Epic"])

    message = str(excinfo.value)
    assert "'Epic'" in message
    assert "Task" in message and "Sub-task" in message
    assert excinfo.value.exit_code == 1


def test_meta_json_merges_the_fields_into_each_issue_type(
    meta_client: RecordingClient, capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = run_meta(meta_client, ["meta", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["projectKey"] == PROJECT
    assert [row["id"] for row in payload["issuetypes"]] == ["10002", "10003"]
    assert [field["fieldId"] for field in payload["issuetypes"][0]["fields"]] == [
        "summary",
        "issuetype",
        "labels",
    ]
