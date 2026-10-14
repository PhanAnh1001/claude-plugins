"""File cấu hình: ``jira.json`` thật bị gitignore, repo chỉ track mẫu ``jira.example.json``."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from jira_tools import cli, config, session_context
from jira_tools.errors import ConfigError

EXAMPLE_PATH = config.PLUGIN_ROOT / "config" / config.EXAMPLE_CONFIG_FILE_NAME
EXAMPLE_PROJECT = "PROJ"
EXAMPLE_REPO = "example-repo"


@pytest.fixture
def empty_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Thư mục config như trên máy vừa clone: chưa có ``jira.json``."""
    directory = tmp_path / "chua-co-config"
    directory.mkdir()
    monkeypatch.setenv(config.CONFIG_DIR_ENV_VAR, str(directory))
    return directory


def test_missing_config_raises_a_hint_to_copy_the_example(empty_config_dir: Path) -> None:
    with pytest.raises(ConfigError) as caught:
        config.load_config()

    message = str(caught.value)
    assert str(empty_config_dir / config.CONFIG_FILE_NAME) in message
    assert config.EXAMPLE_CONFIG_FILE_NAME in message
    assert config.CONFIG_DIR_ENV_VAR in message


@pytest.mark.usefixtures("empty_config_dir")
def test_cli_without_config_exits_2_with_the_hint(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.main(["create", "--summary", "x", "--dry-run"])

    assert exit_code == 2
    assert config.EXAMPLE_CONFIG_FILE_NAME in capsys.readouterr().err


@pytest.mark.usefixtures("empty_config_dir")
def test_session_start_without_config_still_builds_context() -> None:
    context = session_context.build_context(str(Path.cwd()))

    assert "bin/jira-cli" in context
    assert config.EXAMPLE_CONFIG_FILE_NAME in context


def test_example_config_loads_once_copied_to_jira_json(empty_config_dir: Path) -> None:
    shutil.copy(EXAMPLE_PATH, empty_config_dir / config.CONFIG_FILE_NAME)

    loaded = config.load_config()

    project = config.match_project_by_repo(loaded, (EXAMPLE_REPO,))
    assert project is not None and project.key == EXAMPLE_PROJECT
    assert project.create_defaults == {"assignee": None}
    assert loaded.profile(project.profile).base_url.endswith(".example.com")


def test_example_config_uses_only_fictional_hosts() -> None:
    example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    hosts = [body["base_url"] for body in example["profiles"].values()]
    assert hosts and all(".example." in host for host in hosts)
