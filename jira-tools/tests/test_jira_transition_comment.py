"""regression test: ``transition --comment`` báo thành công nhưng comment không được lưu
(2026-09-23).

Jira Server 9.14 của công ty **bỏ qua lặng lẽ** ``update.comment[].add`` trong
``POST /issue/<KEY>/transitions`` khi transition không có screen chứa field Comment — vẫn trả 204.
Đo thật trên hai issue: ``GET .../transitions?expand=transitions.fields`` trả ``fields = {}``
cho cả ``In Progress`` lẫn ``Done``, và sau ba lần chuyển trạng thái kèm ``--comment``,
``GET .../comment`` vẫn trả ``total: 0``. Vì vậy CLI phải đăng comment bằng endpoint riêng rồi
đọc lại, và thoát khác 0 nếu đọc lại không thấy — không bao giờ báo thành công giả.

Test không chạm mạng: ``FakeJira`` thay ``JiraClient.request`` và mô phỏng đúng hành vi đo được.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from jira_tools import cli, client, config
from jira_tools.errors import EXIT_OK

KEY = "PROJ-135"
COMMENT = "Bắt đầu xử lý"
COMMENT_ID = "900"
TRANSITIONS_PATH = f"{config.DEFAULT_API_PREFIX}/issue/{KEY}/transitions"
COMMENT_PATH = f"{config.DEFAULT_API_PREFIX}/issue/{KEY}/comment"
#: Hình dạng thật đo được: transition không screen ⇒ không có field ``comment``.
TRANSITIONS_WITHOUT_SCREEN = [
    {"id": "21", "name": "In Progress", "to": {"name": "In Progress"}, "fields": {}},
]


@dataclass
class FakeJira:
    """Jira giả: transition nuốt ``update.comment`` như server thật; endpoint comment thì lưu."""

    stored_body: str | None = None
    lose_comment: bool = False
    calls: list[tuple[str, str, Any]] = field(default_factory=list)

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        self.calls.append((method, path, payload))
        route = path.split("?", 1)[0]
        if method == "GET" and route == TRANSITIONS_PATH:
            return {"transitions": TRANSITIONS_WITHOUT_SCREEN}
        if method == "POST" and route == TRANSITIONS_PATH:
            return None  # 204, ``update.comment`` bị bỏ qua lặng lẽ
        if method == "POST" and route == COMMENT_PATH:
            if not self.lose_comment:
                self.stored_body = payload["body"]
            return {"id": COMMENT_ID, "body": payload["body"]}
        if method == "GET" and route == f"{COMMENT_PATH}/{COMMENT_ID}":
            return {"id": COMMENT_ID, "body": self.stored_body}
        raise AssertionError(f"lời gọi không mong đợi: {method} {path}")


def _install(monkeypatch: pytest.MonkeyPatch, fake: FakeJira) -> None:
    monkeypatch.setenv(client.TOKEN_ENV_VAR, "token-giả")
    monkeypatch.setattr(
        client.JiraClient,
        "request",
        lambda _self, method, path, payload=None: fake.request(method, path, payload),
    )


def test_transition_comment_is_posted_through_the_comment_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeJira()
    _install(monkeypatch, fake)

    exit_code = cli.main(["transition", KEY, "--to", "In Progress", "--comment", COMMENT])

    assert exit_code == EXIT_OK
    assert ("POST", COMMENT_PATH, {"body": COMMENT}) in fake.calls
    assert fake.stored_body == COMMENT
    # Comment đi sau transition: transition hỏng thì không để lại comment mồ côi.
    posts = [path for method, path, _ in fake.calls if method == "POST"]
    assert posts == [TRANSITIONS_PATH, COMMENT_PATH]


def test_transition_fails_loudly_when_the_comment_is_not_stored(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeJira(lose_comment=True)
    _install(monkeypatch, fake)

    exit_code = cli.main(["transition", KEY, "--to", "In Progress", "--comment", COMMENT])

    assert exit_code != EXIT_OK
    assert "comment" in capsys.readouterr().err


def test_transition_without_comment_never_touches_the_comment_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeJira()
    _install(monkeypatch, fake)

    assert cli.main(["transition", KEY, "--to", "In Progress"]) == EXIT_OK
    assert all(COMMENT_PATH not in path for _, path, _ in fake.calls)
