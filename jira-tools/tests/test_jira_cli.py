"""Kiểm tra phần thuần của CLI Jira: dựng payload, chọn transition, phân giải token.

Toàn bộ file **không chạm mạng và không chạm database** — đó là lý do ``jira_tools/payloads.py``
tách hẳn khỏi tầng HTTP. Hai bẫy được khoá ở đây từng làm hỏng tích hợp Jira thật:

- ``update`` gửi kèm field không truyền: với Jira, ``null`` nghĩa là *xoá* giá trị đang có;
- tên transition khớp phân biệt hoa thường, làm ``--to "in progress"`` fail dù trạng thái tồn tại.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from jira_tools import cli, client, config, payloads
from jira_tools.errors import ConfigError, TransitionNotFound
from tests.conftest import KEYCHAIN_SERVICE, TEST_BASE_URL, TEST_PROFILE

PROJECT = "PROJ"
SUMMARY = "Sửa lỗi ingest bản vẽ"
#: ``create_defaults`` của PROJ trong ``config/jira.json``.
PROJ_CREATE_DEFAULTS = {"assignee": None}

#: Hình dạng thật của ``GET /rest/api/2/issue/<KEY>/transitions``: tên transition khác tên
#: trạng thái đích, nên CLI phải khớp được cả hai.
TRANSITIONS = [
    {"id": "11", "name": "Start Progress", "to": {"name": "In Progress"}},
    {"id": "31", "name": "Done", "to": {"name": "Done"}},
]


def test_create_payload_carries_project_summary_and_issue_type() -> None:
    payload = payloads.build_create_payload(
        project=PROJECT, summary=SUMMARY, create_defaults=PROJ_CREATE_DEFAULTS
    )

    assert payload == {
        "fields": {
            "project": {"key": PROJECT},
            "issuetype": {"name": payloads.DEFAULT_ISSUE_TYPE},
            "summary": SUMMARY,
            "assignee": None,
        }
    }


def test_create_leaves_the_issue_unassigned_unless_assignee_is_passed() -> None:
    """``assignee: null`` phải đi kèm mọi lần tạo, nếu không project tự gán cho project lead.

    Đo được trên project PROJ: 24 issue tạo qua CLI mà không truyền ``--assignee`` đều về tay
    project lead vì Jira áp default assignee của project. Bỏ trống field là *không đủ*.
    """
    payload = payloads.build_create_payload(
        project=PROJECT, summary=SUMMARY, create_defaults=PROJ_CREATE_DEFAULTS
    )["fields"]

    assert "assignee" in payload
    assert payload["assignee"] is None


def test_update_without_assignee_does_not_touch_the_current_assignee() -> None:
    """Ngược với create: ``update`` bỏ qua field, vì ``null`` ở đây nghĩa là *gỡ* người
    đang nhận việc."""
    payload = payloads.build_update_payload(summary=SUMMARY)["fields"]

    assert "assignee" not in payload


def test_create_payload_wraps_labels_assignee_priority_and_parent() -> None:
    payload = payloads.build_create_payload(
        project=PROJECT,
        summary=SUMMARY,
        issue_type="Sub-task",
        description="mô tả nhiều dòng\nkhông phải ADF",
        labels=["ingest", "drawing"],
        assignee="jdoe",
        priority="High",
        parent="PROJ-1",
    )["fields"]

    assert payload["labels"] == ["ingest", "drawing"]
    # Jira Server định danh bằng ``name``; ``accountId`` (Cloud) sẽ bị từ chối.
    assert payload["assignee"] == {"name": "jdoe"}
    assert payload["priority"] == {"name": "High"}
    assert payload["parent"] == {"key": "PROJ-1"}
    assert payload["issuetype"] == {"name": "Sub-task"}
    assert payload["description"] == "mô tả nhiều dòng\nkhông phải ADF"


def test_field_assignments_keep_json_values_as_json_and_plain_text_as_string() -> None:
    fields = payloads.parse_field_assignments(
        [
            'customfield_10101={"value": "Bảo trì"}',
            "customfield_10102=[1, 2]",
            "customfield_10103=ghi chú thường",
        ]
    )

    assert fields == {
        "customfield_10101": {"value": "Bảo trì"},
        "customfield_10102": [1, 2],
        "customfield_10103": "ghi chú thường",
    }


def test_field_assignments_reach_the_create_payload_and_win_over_defaults() -> None:
    payload = payloads.build_create_payload(
        project=PROJECT,
        summary=SUMMARY,
        fields=payloads.parse_field_assignments(
            ['customfield_10101={"value": "A"}', 'issuetype={"id": "10002"}']
        ),
    )["fields"]

    assert payload["customfield_10101"] == {"value": "A"}
    # ``--field`` ghi đè sau cùng: đó là đường thoát khi project đòi id thay vì tên.
    assert payload["issuetype"] == {"id": "10002"}


@pytest.mark.parametrize("raw", ["customfield_10101", "=giá trị", "  =x"])
def test_field_assignment_without_key_and_equals_fails_loudly(raw: str) -> None:
    with pytest.raises(ConfigError) as excinfo:
        payloads.parse_field_assignments([raw])

    assert "KEY=VALUE" in str(excinfo.value)


def test_update_payload_contains_only_the_fields_passed() -> None:
    payload = payloads.build_update_payload(summary="Tiêu đề mới")

    # Không có description/labels/assignee/priority: gửi kèm ``null`` sẽ xoá dữ liệu thật.
    assert payload == {"fields": {"summary": "Tiêu đề mới"}}


def test_update_payload_is_empty_when_nothing_is_passed() -> None:
    assert payloads.build_update_payload() == {"fields": {}}


def test_update_payload_merges_labels_and_custom_fields() -> None:
    payload = payloads.build_update_payload(
        labels=["ingest"],
        priority="Low",
        fields=payloads.parse_field_assignments(["customfield_10101=x"]),
    )["fields"]

    assert payload == {
        "labels": ["ingest"],
        "priority": {"name": "Low"},
        "customfield_10101": "x",
    }


@pytest.mark.parametrize(
    "target", ["In Progress", "in progress", "  IN PROGRESS  ", "start progress"]
)
def test_transition_name_matches_case_insensitively_on_name_or_target_status(target: str) -> None:
    assert payloads.select_transition(TRANSITIONS, target)["id"] == "11"


def test_unknown_transition_name_lists_the_valid_ones() -> None:
    with pytest.raises(TransitionNotFound) as excinfo:
        payloads.select_transition(TRANSITIONS, "Closed")

    message = str(excinfo.value)
    assert "'Closed'" in message
    assert "In Progress" in message and "Done" in message
    assert excinfo.value.available == [
        "11  Start Progress → In Progress",
        "31  Done → Done",
    ]


def test_transition_payload_adds_comment_only_when_given() -> None:
    assert payloads.build_transition_payload("11") == {"transition": {"id": "11"}}
    assert payloads.build_transition_payload("11", "xong rồi") == {
        "transition": {"id": "11"},
        "update": {"comment": [{"add": {"body": "xong rồi"}}]},
    }


def _test_config_and_profile() -> tuple[config.JiraConfig, config.Profile]:
    loaded = config.load_config()
    return loaded, loaded.profile(TEST_PROFILE)


def test_env_token_wins_over_keychain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(client.TOKEN_ENV_VAR, "  token-từ-env  ")

    def _forbidden(service: str) -> str:
        pytest.fail("đã có JIRA_PAT thì không được đụng tới Keychain")

    monkeypatch.setattr(client, "read_keychain_token", _forbidden)

    assert client.resolve_token(*_test_config_and_profile()) == "token-từ-env"


def test_keychain_token_used_when_env_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(client.TOKEN_ENV_VAR, "   ")
    seen: list[str] = []

    def _lookup(service: str) -> str:
        seen.append(service)
        return "token-từ-keychain\n"

    monkeypatch.setattr(client, "read_keychain_token", _lookup)

    assert client.resolve_token(*_test_config_and_profile()) == "token-từ-keychain"
    assert seen == [KEYCHAIN_SERVICE]


def test_missing_token_everywhere_explains_how_to_create_one() -> None:
    with pytest.raises(ConfigError) as excinfo:
        client.resolve_token(*_test_config_and_profile())

    message = str(excinfo.value)
    assert KEYCHAIN_SERVICE in message
    assert f"{TEST_BASE_URL}/secure/ViewProfile.jspa" in message
    assert "Personal Access Tokens" in message
    assert excinfo.value.exit_code == 2


def test_base_url_comes_from_the_profile_and_env_overrides_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, profile = _test_config_and_profile()
    assert config.resolve_base_url(profile) == TEST_BASE_URL

    monkeypatch.setenv(config.BASE_URL_ENV_VAR, "https://jira.example/")
    jira = client.JiraClient(base_url=config.resolve_base_url(profile), token="x")
    assert jira.browse_url("PROJ-9") == "https://jira.example/browse/PROJ-9"


@pytest.fixture
def no_token_anywhere(monkeypatch: pytest.MonkeyPatch) -> None:
    """Môi trường sạch hoàn toàn: không ``JIRA_PAT``, Keychain cũng không trả gì.

    Máy dev thật có thể đang có mục Keychain của profile, nên phải chặn cả hai đường
    thì test mới nói đúng về hành vi khi chưa có token.
    """
    monkeypatch.delenv(client.TOKEN_ENV_VAR, raising=False)
    monkeypatch.delenv(config.BASE_URL_ENV_VAR, raising=False)
    monkeypatch.delenv(config.PROJECT_ENV_VAR, raising=False)
    monkeypatch.setattr(client, "read_keychain_token", lambda service: None)


@pytest.fixture
def forbid_http(monkeypatch: pytest.MonkeyPatch) -> None:
    """Chặn tầng HTTP: một lệnh ``--dry-run`` chạm tới nó là đã sai, không phải chậm."""

    def _forbidden(*args: object, **kwargs: object) -> object:
        pytest.fail("--dry-run không được gọi mạng")

    monkeypatch.setattr(client.JiraClient, "request", _forbidden)


@pytest.mark.usefixtures("no_token_anywhere", "forbid_http")
def test_create_dry_run_needs_no_token(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(["create", "--summary", SUMMARY, "--dry-run"])

    out = capsys.readouterr().out
    assert exit_code == 0
    # URL vẫn phải đúng: base URL và project không phụ thuộc token.
    assert f"POST {TEST_BASE_URL}/rest/api/2/issue" in out
    assert SUMMARY in out
    assert f'"key": "{PROJECT}"' in out


@pytest.mark.usefixtures("no_token_anywhere", "forbid_http")
def test_transition_dry_run_needs_no_token_and_marks_the_id_as_a_placeholder(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(["transition", "PROJ-12", "--to", "In Progress", "--dry-run"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "<id>" in out
    assert "cần mạng để tra id" in out


@pytest.mark.usefixtures("no_token_anywhere")
def test_read_command_without_token_still_exits_2_with_the_pat_instructions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.main(["whoami"])

    err = capsys.readouterr().err
    assert exit_code == 2
    assert KEYCHAIN_SERVICE in err
    assert "Personal Access Tokens" in err


@pytest.mark.usefixtures("no_token_anywhere", "forbid_http")
def test_update_without_any_field_exits_2_even_in_dry_run(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Lỗi cấu hình lệnh, phát hiện được mà không cần mạng ⇒ vẫn là mã 2, không phải 0.
    exit_code = cli.main(["update", "PROJ-12", "--dry-run"])

    assert exit_code == 2
    assert "ít nhất một field" in capsys.readouterr().err


@pytest.mark.usefixtures("forbid_http")
def test_dry_run_output_never_leaks_the_token(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    secret = "PAT-không-được-in-ra"
    monkeypatch.setenv(client.TOKEN_ENV_VAR, secret)

    exit_code = cli.main(["comment", "PROJ-12", "--body", "ghi chú", "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert secret not in captured.out
    assert secret not in captured.err


def test_get_asks_jira_for_the_description_field() -> None:
    """``description`` phải nằm trong field xin về, nếu không ``get`` im lặng bỏ qua nó.

    Đã xảy ra thật: một lượt đọc PROJ-9 qua CLI kết luận issue có mô tả rỗng, trong khi mô tả
    thật dài vài chục dòng — công cụ không trả về một trường bị đọc thành trường đó rỗng.
    """
    assert "description" in cli.GET_ISSUE_FIELDS.split(",")


def test_issue_printout_puts_the_description_after_the_short_fields() -> None:
    body = "dòng một\ndòng hai"
    issue = {"key": "PROJ-9", "fields": {"summary": SUMMARY, "description": body}}

    lines = _render_issue(issue).splitlines()

    assert lines.index(cli.DESCRIPTION_HEADER) > lines.index(f"summary   {SUMMARY}")
    assert lines[-2:] == ["dòng một", "dòng hai"]


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        (None, cli.DESCRIPTION_ABSENT),
        ("", cli.DESCRIPTION_EMPTY),
        ("   \n", cli.DESCRIPTION_EMPTY),
        ("có nội dung", "có nội dung"),
    ],
)
def test_empty_description_is_marked_instead_of_printed_as_blank(
    description: str | None, expected: str
) -> None:
    """Mô tả rỗng phải phân biệt được với mô tả có nội dung — đó chính là lỗi cần chống."""
    assert cli.render_description(description) == expected


def _render_issue(issue: dict[str, object]) -> str:
    jira = client.JiraClient(base_url=TEST_BASE_URL, token="x")
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        cli._print_issue(jira, issue)
    return buffer.getvalue()
