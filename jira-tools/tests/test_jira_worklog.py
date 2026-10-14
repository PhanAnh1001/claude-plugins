"""Lệnh ``worklog``: log thời gian thật rồi đọc lại remaining (luật "chuyển Done ⇒ log work,
remaining = 0").

Trước đây CLI không có lệnh này nên các phiên phải gọi thẳng REST
``POST /issue/<KEY>/worklog?adjustEstimate=new&newEstimate=0`` ngoài CLI. Test không chạm mạng:
``FakeJira`` thay ``JiraClient.request``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from jira_tools import cli, client, config, worklog
from jira_tools.errors import EXIT_CONFIG_ERROR, EXIT_OK

KEY = "PROJ-123"
WORKLOG_ID = "201"
STARTED = "2026-09-25T09:00:00.000+0700"
WORKLOG_PATH = f"{config.DEFAULT_API_PREFIX}/issue/{KEY}/worklog"
ISSUE_PATH = f"{config.DEFAULT_API_PREFIX}/issue/{KEY}"


@dataclass
class FakeJira:
    """Jira giả: nhận worklog, ``timetracking`` đọc lại trả ``stored_remaining_seconds``."""

    stored_remaining_seconds: int | None = 0
    return_id: bool = True
    calls: list[tuple[str, str, Any]] = field(default_factory=list)

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        self.calls.append((method, path, payload))
        route = path.split("?", 1)[0]
        if method == "POST" and route == WORKLOG_PATH:
            return {"id": WORKLOG_ID} if self.return_id else {}
        if method == "GET" and route == ISSUE_PATH:
            tracking = {"remainingEstimate": f"{self.stored_remaining_seconds}s"}
            tracking["remainingEstimateSeconds"] = self.stored_remaining_seconds
            return {"fields": {"timetracking": tracking}}
        raise AssertionError(f"lời gọi không mong đợi: {method} {path}")


def _install(monkeypatch: pytest.MonkeyPatch, fake: FakeJira) -> None:
    monkeypatch.setenv(client.TOKEN_ENV_VAR, "token-giả")
    monkeypatch.setattr(
        client.JiraClient,
        "request",
        lambda _self, method, path, payload=None: fake.request(method, path, payload),
    )


def _posts(fake: FakeJira) -> list[tuple[str, Any]]:
    return [(path, payload) for method, path, payload in fake.calls if method == "POST"]


def test_worklog_posts_payload_and_sets_remaining_through_the_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeJira()
    _install(monkeypatch, fake)

    argv = ["worklog", KEY, "--time", "1h30m", "--started", STARTED, "--comment", "Sửa xong"]
    exit_code = cli.main([*argv, "--remaining", "0m"])

    assert exit_code == EXIT_OK
    expected_body = {"timeSpent": "1h 30m", "started": STARTED, "comment": "Sửa xong"}
    assert _posts(fake) == [(f"{WORKLOG_PATH}?adjustEstimate=new&newEstimate=0m", expected_body)]
    assert any(method == "GET" for method, _, _ in fake.calls)  # đã đọc lại timetracking


def test_worklog_without_remaining_lets_jira_adjust_automatically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeJira()
    _install(monkeypatch, fake)

    assert cli.main(["worklog", KEY, "--time", "30m", "--started", STARTED]) == EXIT_OK
    assert _posts(fake) == [
        (f"{WORKLOG_PATH}?adjustEstimate=auto", {"timeSpent": "30m", "started": STARTED})
    ]


def test_worklog_fails_loudly_when_remaining_does_not_read_back(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeJira(stored_remaining_seconds=3600)
    _install(monkeypatch, fake)

    exit_code = cli.main(["worklog", KEY, "--time", "30m", "--remaining", "0m"])

    assert exit_code != EXIT_OK
    assert "remaining" in capsys.readouterr().err


def test_worklog_fails_when_jira_returns_no_worklog_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeJira(return_id=False)
    _install(monkeypatch, fake)

    assert cli.main(["worklog", KEY, "--time", "30m"]) != EXIT_OK


def test_worklog_dry_run_needs_no_token_and_no_network(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def no_network(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("--dry-run không được gọi mạng")

    monkeypatch.setattr(client.JiraClient, "request", no_network)

    argv = ["worklog", KEY, "--time", "30m", "--remaining", "0m", "--started", STARTED]
    exit_code = cli.main([*argv, "--dry-run"])

    out = capsys.readouterr().out
    assert exit_code == EXIT_OK
    assert f"POST https://jira.test.example{WORKLOG_PATH}?adjustEstimate=new&newEstimate=0m" in out
    assert '"timeSpent": "30m"' in out
    assert "token" not in out


@pytest.mark.parametrize("bad", ["30", "1.5h", "30 phút", "h", "1x", ""])
def test_worklog_rejects_durations_jira_cannot_parse(
    bad: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeJira()
    _install(monkeypatch, fake)

    assert cli.main(["worklog", KEY, "--time", bad]) == EXIT_CONFIG_ERROR
    assert cli.main(["worklog", KEY, "--time", "30m", "--remaining", bad]) == EXIT_CONFIG_ERROR
    assert fake.calls == []


def test_worklog_rejects_unparseable_started(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeJira()
    _install(monkeypatch, fake)

    assert cli.main(["worklog", KEY, "--time", "30m", "--started", "hôm qua"]) == (
        EXIT_CONFIG_ERROR
    )
    assert fake.calls == []


@pytest.mark.parametrize(
    ("raw", "seconds"),
    [("30m", 1800), ("2h", 7200), ("1h 30m", 5400), ("1d", 28800), ("1w", 144000)],
)
def test_duration_seconds_follows_server_time_tracking_config(raw: str, seconds: int) -> None:
    assert worklog.duration_seconds(raw) == seconds


def test_started_accepts_iso_and_defaults_to_local_now_in_jira_format() -> None:
    assert worklog.format_started("2026-09-25T09:00:00+07:00") == STARTED
    assert worklog.format_started(STARTED) == STARTED
    fixed = datetime(2026, 10, 9, 8, 5, 7, tzinfo=timezone(timedelta(hours=7)))
    assert worklog.format_started(None, now=fixed) == "2026-10-09T08:05:07.000+0700"
