"""Lệnh ``report``: khoảng ngày, JQL, trích key commit và gom dữ liệu với Jira giả.

Không chạm mạng (``JiraClient.request`` bị thay) và không chạy git thật (``read_git_log`` bị thay).
Test format hiển thị nằm ở ``test_jira_report_render.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import pytest

from jira_tools import cli, client, config, report_data
from jira_tools.errors import EXIT_CONFIG_ERROR, EXIT_OK
from jira_tools.report_period import (
    Period,
    commits_by_key,
    done_period,
    plan_jql,
    plan_period,
    resolved_jql,
    worklog_jql,
)

API = config.DEFAULT_API_PREFIX
EPIC_FIELD = "customfield_10108"


@pytest.mark.parametrize("anchor", ["2026-11-06", "2026-11-09", "2026-11-12"])
def test_periods_anchor_on_the_latest_friday(anchor: str) -> None:
    day = date.fromisoformat(anchor)
    assert done_period(day) == Period(date(2026, 10, 30), date(2026, 11, 6))
    assert plan_period(day) == Period(date(2026, 11, 6), date(2026, 11, 12))


def test_thursday_before_friday_belongs_to_previous_week() -> None:
    assert done_period(date(2026, 11, 5)) == Period(date(2026, 10, 23), date(2026, 10, 30))


def test_commit_keys_are_extracted_by_word_boundary() -> None:
    lines = [
        "2026-11-03\tfeat(kb): PROJ-12 nạp tài liệu, PROJ-7",
        "2026-11-01\tfix: PROJ-12 sửa lỗi",
        "2026-11-02\tXPROJ-99 và PROJ-1a không khớp",
        "dòng hỏng không có tab",
    ]
    grouped = commits_by_key(lines, "PROJ")
    assert sorted(grouped) == ["PROJ-12", "PROJ-7"]
    assert [c.day for c in grouped["PROJ-12"]] == ["2026-11-01", "2026-11-03"]


def test_commits_dated_outside_the_period_are_dropped() -> None:
    """``git log --since`` lọc theo ngày commit; commit viết 29/10 rồi rebase vẫn lọt qua."""
    lines = [
        "2026-10-29\tfix(deploy): PROJ-3 viết trước kỳ, rebase vào kỳ",
        "2026-10-30\tfeat: PROJ-4 đầu kỳ",
        "2026-11-06\tfeat: PROJ-5 cuối kỳ",
        "2026-11-07\tfeat: PROJ-6 sau kỳ",
    ]
    grouped = commits_by_key(lines, "PROJ", Period(date(2026, 10, 30), date(2026, 11, 6)))
    assert sorted(grouped) == ["PROJ-4", "PROJ-5"]


def test_done_jql_uses_inclusive_worklog_dates_and_next_day_for_resolved() -> None:
    period = Period(date(2026, 10, 30), date(2026, 11, 6))
    assert worklog_jql("PROJ", None, period) == (
        "project = PROJ AND issuetype != Epic AND worklogAuthor = currentUser() "
        'AND worklogDate >= "2026-10-30" AND worklogDate <= "2026-11-06"'
    )
    assert resolved_jql("PROJ", "anhtp", period) == (
        'project = PROJ AND issuetype != Epic AND assignee = "anhtp" '
        'AND resolved >= "2026-10-30" AND resolved < "2026-11-07"'
    )


def test_plan_jql_with_and_without_excluded_epics() -> None:
    base = (
        "project = PROJ AND issuetype != Epic AND statusCategory != Done "
        "AND assignee = currentUser()"
    )
    assert plan_jql("PROJ", None) == base
    assert plan_jql("PROJ", None, ["PROJ-1", "PROJ-2"]) == (
        base + ' AND ("Epic Link" is EMPTY OR "Epic Link" not in (PROJ-1, PROJ-2))'
    )


def _issue(key: str, summary: str, *, epic: str | None = None, remaining: int = 0,
           category: str = "indeterminate") -> dict[str, Any]:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "status": {"name": "In Progress", "statusCategory": {"key": category}},
            "issuetype": {"name": "Task"},
            "labels": ["luxian"],
            "timetracking": {"remainingEstimateSeconds": remaining},
            "resolutiondate": None,
            EPIC_FIELD: epic,
        },
    }


@dataclass
class FakeJira:
    """Trả search theo đoạn JQL; ghi lại mọi lời gọi."""

    calls: list[tuple[str, str, Any]] = field(default_factory=list)

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        self.calls.append((method, path, payload))
        if method == "GET" and path == f"{API}/field":
            return [{"id": EPIC_FIELD, "name": "Epic Link"}]
        if method == "GET" and path == f"{API}/project/PROJ":
            return {"name": "Dự án mẫu"}
        if method == "POST" and path == f"{API}/search":
            return self._search(str(payload["jql"]))
        raise AssertionError(f"lời gọi không mong đợi: {method} {path}")

    @staticmethod
    def _search(jql: str) -> dict[str, Any]:
        if "worklogAuthor" in jql:
            issues = [_issue("PROJ-3", "Viết API", epic="PROJ-1")]
        elif "resolved >=" in jql:
            issues = [_issue("PROJ-3", "Viết API", epic="PROJ-1"), _issue("PROJ-5", "Sửa UI")]
        elif "statusCategory != Done" in jql:
            issues = [_issue("PROJ-8", "Kế hoạch A", remaining=5400),
                      _issue("PROJ-9", "Kế hoạch B", remaining=3600)]
        elif jql.startswith("key in (PROJ-1)"):
            issues = [{"key": "PROJ-1", "fields": {"summary": "Kho tri thức"}}]
        elif jql.startswith("key in"):
            issues = [_issue("PROJ-3", "Viết API", epic="PROJ-1"), _issue("PROJ-6", "Commit")]
        else:
            raise AssertionError(f"JQL lạ: {jql}")
        return {"issues": issues, "total": len(issues)}


def _install(monkeypatch: pytest.MonkeyPatch, fake: FakeJira) -> list[tuple[str, Any]]:
    monkeypatch.setenv(client.TOKEN_ENV_VAR, "token-giả")
    monkeypatch.setattr(
        client.JiraClient, "request",
        lambda _self, method, path, payload=None: fake.request(method, path, payload),
    )
    git_calls: list[tuple[str, Any]] = []

    def fake_git(repo: str, author: str | None, period: Period) -> list[str]:
        git_calls.append((repo, period))
        return ["2026-11-04\tfeat: PROJ-6 thêm", "2026-11-02\tfix: PROJ-3 sửa"]

    monkeypatch.setattr(report_data, "read_git_log", fake_git)
    return git_calls


def test_report_json_merges_worklog_resolved_and_commit_sources(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeJira()
    git_calls = _install(monkeypatch, fake)

    exit_code = cli.main(["report", "--json", "--anchor", "2026-11-09", "--repo", "/r"])

    assert exit_code == EXIT_OK
    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "Dự án mẫu"
    done = data["done"]
    assert (done["from"], done["to"]) == ("2026-10-30", "2026-11-06")
    by_key = {i["key"]: i for i in done["issues"]}
    assert list(by_key) == ["PROJ-3", "PROJ-5", "PROJ-6"]
    assert by_key["PROJ-3"]["sources"] == ["worklog", "resolved", "commit"]
    assert by_key["PROJ-3"]["epic_name"] == "Kho tri thức"
    assert by_key["PROJ-3"]["commits"] == [{"date": "2026-11-02", "subject": "fix: PROJ-3 sửa"}]
    assert by_key["PROJ-6"]["sources"] == ["commit"]
    assert by_key["PROJ-5"]["sources"] == ["resolved"]
    plan = data["plan"]
    assert (plan["from"], plan["to"], plan["remaining_hours"]) == ("2026-11-06", "2026-11-12", 2.5)
    assert [i["key"] for i in plan["issues"]] == ["PROJ-8", "PROJ-9"]
    assert git_calls == [("/r", Period(date(2026, 10, 30), date(2026, 11, 6)))]


def test_report_kind_plan_with_override_skips_done_and_git(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeJira()
    git_calls = _install(monkeypatch, fake)

    argv = ["report", "--json", "--kind", "plan", "--from", "2026-11-07"]
    argv += ["--exclude-epic", "PROJ-1"]
    assert cli.main(argv) == EXIT_OK

    data = json.loads(capsys.readouterr().out)
    assert "done" not in data and data["plan"]["from"] == "2026-11-07"
    assert git_calls == []
    jqls = [p["jql"] for m, _, p in fake.calls if m == "POST"]
    assert any('"Epic Link" not in (PROJ-1)' in jql for jql in jqls)


def test_report_draft_prints_four_reports_and_remaining_total(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch, FakeJira())
    assert cli.main(["report", "--anchor", "2026-11-06"]) == EXIT_OK
    out = capsys.readouterr().out
    assert out.count("== Báo cáo ") == 4
    assert "== Báo cáo chi tiết đã làm (30/10 – 06/11/2026) ==" in out
    assert out.rstrip().endswith("Tổng ước lượng còn lại: 2.5 giờ")


@pytest.mark.parametrize(
    "argv",
    [
        ["report", "--from", "2026-11-01"],
        ["report", "--anchor", "06/11/2026"],
        ["report", "--kind", "done", "--to", "2026-13-01"],
    ],
)
def test_report_bad_dates_exit_config_error(monkeypatch: pytest.MonkeyPatch,
                                            argv: list[str]) -> None:
    fake = FakeJira()
    _install(monkeypatch, fake)
    assert cli.main(argv) == EXIT_CONFIG_ERROR
    assert fake.calls == []


def test_report_input_renders_without_calling_jira(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("--input không được gọi Jira")

    monkeypatch.setattr(client.JiraClient, "request", forbidden)
    source = tmp_path / "in.json"
    source.write_text(json.dumps({
        "title": "LUXIAN",
        "reports": [{"heading": "Báo cáo tóm tắt đã làm (30/10 – 06/11/2026)", "style": "summary",
                     "groups": [{"name": "Trợ lý AI",
                                 "items": [{"text": "Xong", "keys": ["X-1"]}]}]}],
    }), encoding="utf-8")

    assert cli.main(["report", "--input", str(source)]) == EXIT_OK
    assert capsys.readouterr().out == (
        "== Báo cáo tóm tắt đã làm (30/10 – 06/11/2026) ==\n\nLUXIAN\n1. Trợ lý AI\n - Xong\n"
    )


def test_report_input_with_bad_style_exits_config_error(tmp_path: Any) -> None:
    source = tmp_path / "in.json"
    source.write_text(json.dumps({"title": "T", "reports": [{"style": "x"}]}), encoding="utf-8")
    assert cli.main(["report", "--input", str(source)]) == EXIT_CONFIG_ERROR


def test_read_git_log_outside_a_repo_warns_and_returns_nothing(
    tmp_path: Any, capsys: pytest.CaptureFixture[str]
) -> None:
    period = Period(date(2026, 10, 30), date(2026, 11, 6))
    assert report_data.read_git_log(str(tmp_path), None, period) == []
    assert "bỏ qua nguồn commit" in capsys.readouterr().err
