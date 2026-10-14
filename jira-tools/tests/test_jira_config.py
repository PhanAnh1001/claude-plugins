"""Lớp cấu hình: chọn dự án theo repo, env ghi đè, thứ tự PAT, create_defaults, thư mục config."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from jira_tools import cli, client, config
from tests.conftest import OTHER_BASE_URL, TEST_BASE_URL, TEST_PROFILE

#: Hàm thật, giữ trước khi fixture autouse của conftest thay nó bằng stub.
_real_current_repo_names = config.current_repo_names


@pytest.fixture
def forbid_http(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbidden(*args: object, **kwargs: object) -> object:
        pytest.fail("--dry-run không được gọi mạng")

    monkeypatch.setattr(client.JiraClient, "request", _forbidden)


def _create_dry_run(capsys: pytest.CaptureFixture[str], *extra: str) -> tuple[int, str, str]:
    exit_code = cli.main(["create", "--summary", "x", "--dry-run", *extra])
    captured = capsys.readouterr()
    return exit_code, captured.out, captured.err


def _payload(out: str) -> dict[str, object]:
    return json.loads(out[out.index("{") :])["fields"]


@pytest.mark.usefixtures("forbid_http")
def test_project_is_picked_from_the_git_repo_name(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code, out, _ = _create_dry_run(capsys)

    assert exit_code == 0
    assert out.startswith(f"POST {TEST_BASE_URL}/rest/api/2/issue")
    assert _payload(out)["project"] == {"key": "PROJ"}


@pytest.mark.usefixtures("forbid_http")
def test_proj_create_sends_an_explicit_null_assignee(capsys: pytest.CaptureFixture[str]) -> None:
    _, out, _ = _create_dry_run(capsys)

    fields = _payload(out)
    assert "assignee" in fields
    assert fields["assignee"] is None


@pytest.mark.usefixtures("forbid_http")
def test_explicit_assignee_flag_wins_over_create_defaults(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out, _ = _create_dry_run(capsys, "--assignee", "jdoe")

    assert _payload(out)["assignee"] == {"name": "jdoe"}


@pytest.mark.usefixtures("forbid_http")
def test_project_without_create_defaults_omits_assignee(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _, out, _ = _create_dry_run(capsys, "--project", "OTH")

    assert "assignee" not in _payload(out)
    # Host đi theo profile của dự án, không phải default_profile.
    assert out.startswith(f"POST {OTHER_BASE_URL}/")


@pytest.mark.usefixtures("forbid_http")
def test_env_project_beats_repo_and_flag_beats_env(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(config.PROJECT_ENV_VAR, "OTH")
    _, out, _ = _create_dry_run(capsys)
    assert _payload(out)["project"] == {"key": "OTH"}

    _, out, _ = _create_dry_run(capsys, "--project", "PROJ")
    assert _payload(out)["project"] == {"key": "PROJ"}


@pytest.mark.usefixtures("forbid_http")
def test_env_base_url_beats_the_project_profile(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(config.BASE_URL_ENV_VAR, "https://override.example")

    _, out, _ = _create_dry_run(capsys)

    assert out.startswith("POST https://override.example/rest/api/2/issue")


@pytest.mark.usefixtures("forbid_http")
def test_unmatched_repo_exits_2_and_lists_the_known_projects(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(config, "current_repo_names", lambda cwd=None: ("repo-la", "repo-chinh"))

    exit_code, out, err = _create_dry_run(capsys)

    assert exit_code == 2
    assert out == ""
    assert "PROJ" in err
    assert "OTH" in err
    assert "repo-la, repo-chinh" in err


@pytest.mark.usefixtures("forbid_http")
def test_outside_any_git_repo_also_exits_2(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(config, "current_repo_names", lambda cwd=None: ())

    exit_code, _, err = _create_dry_run(capsys)

    assert exit_code == 2
    assert "không phải repo git" in err


def test_non_project_command_uses_default_profile_when_no_project_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "current_repo_names", lambda cwd=None: ())
    loaded = config.load_config()

    jira = cli.build_client(loaded, None)

    assert jira.base_url == TEST_BASE_URL


def test_config_dir_env_var_is_honoured(
    isolated_jira_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert config.config_dir() == isolated_jira_config
    assert config.load_config().config_dir == isolated_jira_config

    monkeypatch.delenv(config.CONFIG_DIR_ENV_VAR)
    assert config.config_dir() == config.PLUGIN_ROOT / "config"


def test_missing_config_file_is_a_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv(config.CONFIG_DIR_ENV_VAR, str(tmp_path / "trong"))

    assert cli.main(["whoami"]) == 2
    assert config.CONFIG_FILE_NAME in capsys.readouterr().err


def _write_secret(config_dir: Path, pat: str) -> None:
    body = {"profiles": {TEST_PROFILE: {"pat": pat}}}
    (config_dir / config.SECRETS_FILE_NAME).write_text(json.dumps(body))


def _resolve() -> str:
    loaded = config.load_config()
    return client.resolve_token(loaded, loaded.profile(TEST_PROFILE))


def test_pat_order_env_then_secrets_then_keychain(
    isolated_jira_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(client, "read_keychain_token", lambda service: "tu-keychain")
    assert _resolve() == "tu-keychain"

    _write_secret(isolated_jira_config, "tu-secrets")
    assert _resolve() == "tu-secrets"

    monkeypatch.setenv(client.TOKEN_ENV_VAR, "tu-env")
    assert _resolve() == "tu-env"


def test_secrets_file_wins_without_touching_keychain(
    isolated_jira_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _forbidden(service: str) -> str:
        pytest.fail("đã có PAT trong secrets.json thì không được đụng Keychain")

    monkeypatch.setattr(client, "read_keychain_token", _forbidden)
    _write_secret(isolated_jira_config, "tu-secrets")

    assert _resolve() == "tu-secrets"


def test_ssl_context_uses_profile_bundle_unless_ssl_cert_file_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing = config.Profile(name="p", base_url="https://x", ca_bundle=tmp_path / "khong.pem")
    assert client.build_ssl_context(missing) is None

    monkeypatch.setenv(client.SSL_CERT_FILE_ENV_VAR, "/bat/ky.pem")
    bundled = config.Profile(
        name="p",
        base_url="https://x",
        ca_bundle=config.PLUGIN_ROOT / "config" / config.EXAMPLE_CONFIG_FILE_NAME,
    )
    assert client.build_ssl_context(bundled) is None


def _git(*args: str) -> None:
    subprocess.run(["git", *args], check=True, capture_output=True)


@pytest.fixture
def repo_with_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Repo git thật tên ``example-repo`` và một worktree ``foo`` nằm bên trong nó."""
    main = tmp_path / "example-repo"
    main.mkdir()
    _git("-C", str(main), "init", "-q")
    _git(
        "-C",
        str(main),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@t",
        "commit",
        "-q",
        "--allow-empty",
        "-m",
        "init",
    )
    worktree = main / ".claude" / "worktrees" / "foo"
    _git("-C", str(main), "worktree", "add", "-q", str(worktree))
    return main, worktree


def test_repo_names_inside_a_worktree_include_the_main_repo(
    repo_with_worktree: tuple[Path, Path],
) -> None:
    main, worktree = repo_with_worktree

    assert _real_current_repo_names(str(worktree)) == ("foo", "example-repo")
    assert _real_current_repo_names(str(main)) == ("example-repo",)


def test_project_matches_by_main_repo_name_from_a_worktree(
    repo_with_worktree: tuple[Path, Path],
) -> None:
    _, worktree = repo_with_worktree

    project = config.match_project_by_repo(
        config.load_config(), _real_current_repo_names(str(worktree))
    )

    assert project is not None and project.key == "PROJ"


def test_toplevel_name_wins_over_the_main_repo_name() -> None:
    loaded = config.load_config()

    project = config.match_project_by_repo(loaded, ("other-repo", "example-repo"))

    assert project is not None and project.key == "OTH"


def test_outside_git_has_no_candidate_names(tmp_path: Path) -> None:
    assert _real_current_repo_names(str(tmp_path)) == ()
