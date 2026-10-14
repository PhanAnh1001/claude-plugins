"""Cấu hình host / dự án Jira, đọc từ ``config/jira.json`` của plugin.

Một host (profile) dùng chung cho nhiều dự án; mỗi dự án khai ``repos`` để CLI tự chọn dự án
theo repo git của thư mục hiện tại. Thứ tự ưu tiên:

- dự án: ``--project`` > ``JIRA_PROJECT`` > dự án có ``repos`` chứa tên repo git hiện tại;
  không khớp thì lỗi cấu hình (mã 2) — **không** âm thầm rơi về một dự án mặc định;
- host: ``JIRA_BASE_URL`` > profile của dự án > ``default_profile``;
- thư mục config: ``JIRA_TOOLS_CONFIG_DIR`` > ``<plugin root>/config``.

Đường dẫn tương đối trong config (``ca_bundle``) tính theo thư mục gốc plugin.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from jira_tools.errors import ConfigError

#: Server 9.14 ⇒ REST **v2**. Đừng đổi sang v3: v3 chỉ có trên Atlassian Cloud và đòi ADF.
DEFAULT_API_PREFIX: Final = "/rest/api/2"

CONFIG_DIR_ENV_VAR: Final = "JIRA_TOOLS_CONFIG_DIR"
BASE_URL_ENV_VAR: Final = "JIRA_BASE_URL"
PROJECT_ENV_VAR: Final = "JIRA_PROJECT"

CONFIG_FILE_NAME: Final = "jira.json"
EXAMPLE_CONFIG_FILE_NAME: Final = "jira.example.json"
SECRETS_FILE_NAME: Final = "secrets.json"

#: ``lib/jira_tools/config.py`` → gốc plugin ở hai cấp trên ``lib``; không phụ thuộc cwd.
PLUGIN_ROOT: Final = Path(__file__).resolve().parents[2]

GIT_TIMEOUT_SECONDS: Final = 5.0


@dataclass(frozen=True)
class Profile:
    """Một host Jira: URL, prefix REST, nơi lấy PAT và CA bundle."""

    name: str
    base_url: str
    api_prefix: str = DEFAULT_API_PREFIX
    keychain_service: str | None = None
    ca_bundle: Path | None = None


@dataclass(frozen=True)
class Project:
    key: str
    profile: str
    repos: tuple[str, ...] = ()
    create_defaults: Mapping[str, Any] = field(default_factory=dict)
    fields: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class JiraConfig:
    profiles: Mapping[str, Profile]
    default_profile: str
    projects: Mapping[str, Project]
    config_dir: Path

    def profile(self, name: str) -> Profile:
        try:
            return self.profiles[name]
        except KeyError:
            known = ", ".join(sorted(self.profiles)) or "(chưa khai profile nào)"
            raise ConfigError(f"Profile {name!r} không có trong config. Đang có: {known}") from None

    def project_listing(self) -> str:
        lines = [
            f"  - {p.key} (profile {p.profile}, repos: {', '.join(p.repos) or '-'})"
            for p in self.projects.values()
        ]
        return "\n".join(lines) or "  (chưa khai dự án nào)"


def config_dir(env: Mapping[str, str] | None = None) -> Path:
    environ = os.environ if env is None else env
    override = (environ.get(CONFIG_DIR_ENV_VAR) or "").strip()
    return Path(override).expanduser() if override else PLUGIN_ROOT / "config"


def missing_config_message(directory: Path) -> str:
    """Hướng dẫn tạo jira.json khi file thật chưa có (máy mới clone repo)."""
    return (
        f"Chưa có file cấu hình {directory / CONFIG_FILE_NAME} (bị gitignore). "
        f"Chép mẫu: cp {PLUGIN_ROOT / 'config' / EXAMPLE_CONFIG_FILE_NAME} "
        f"{directory / CONFIG_FILE_NAME} rồi sửa host/dự án/repo, "
        f"hoặc đặt {CONFIG_DIR_ENV_VAR} trỏ tới thư mục chứa {CONFIG_FILE_NAME}."
    )


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"Không thấy file cấu hình {path}") from None
    except (OSError, ValueError) as error:
        raise ConfigError(f"Không đọc được {path}: {type(error).__name__}") from None


def _resolve_plugin_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PLUGIN_ROOT / path


def _parse_profile(name: str, raw: Mapping[str, Any]) -> Profile:
    base_url = str(raw.get("base_url") or "").strip()
    if not base_url:
        raise ConfigError(f"Profile {name!r} thiếu base_url")
    return Profile(
        name=name,
        base_url=base_url,
        api_prefix=str(raw.get("api_prefix") or DEFAULT_API_PREFIX),
        keychain_service=raw.get("keychain_service") or None,
        ca_bundle=_resolve_plugin_path(raw.get("ca_bundle")),
    )


def _parse_project(key: str, raw: Mapping[str, Any], default_profile: str) -> Project:
    return Project(
        key=key,
        profile=str(raw.get("profile") or default_profile),
        repos=tuple(str(repo) for repo in raw.get("repos") or ()),
        create_defaults=dict(raw.get("create_defaults") or {}),
        fields={str(k): str(v) for k, v in (raw.get("fields") or {}).items()},
    )


def load_config(env: Mapping[str, str] | None = None) -> JiraConfig:
    directory = config_dir(env)
    if not (directory / CONFIG_FILE_NAME).is_file():
        raise ConfigError(missing_config_message(directory))
    raw = _read_json(directory / CONFIG_FILE_NAME)
    if not isinstance(raw, Mapping):
        raise ConfigError(f"{directory / CONFIG_FILE_NAME} phải là một object JSON")
    profiles = {
        name: _parse_profile(name, body) for name, body in (raw.get("profiles") or {}).items()
    }
    default_profile = str(raw.get("default_profile") or "")
    if default_profile not in profiles:
        raise ConfigError(f"default_profile {default_profile!r} không có trong profiles")
    projects = {
        key: _parse_project(key, body, default_profile)
        for key, body in (raw.get("projects") or {}).items()
    }
    return JiraConfig(profiles, default_profile, projects, directory)


def _git_output(args: list[str], cwd: str | None) -> str | None:
    """stdout của một lệnh ``git`` đọc-only, hoặc ``None`` khi lỗi / không phải repo."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = completed.stdout.strip()
    return out if completed.returncode == 0 and out else None


def current_repo_names(cwd: str | None = None) -> tuple[str, ...]:
    """Tên ứng viên của repo hiện tại, tên toplevel đứng trước.

    Trong một git worktree (ví dụ ``<repo>/.claude/worktrees/foo``), toplevel có basename
    ``foo``; tên repo chính lấy từ thư mục cha của ``--git-common-dir``. Git cũ không hỗ trợ
    ``--path-format`` thì lệnh đó lỗi và chỉ còn tên toplevel.
    """
    names: list[str] = []
    top = _git_output(["rev-parse", "--show-toplevel"], cwd)
    if top:
        names.append(Path(top).name)
    common = _git_output(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd)
    if common:
        main_name = Path(common).parent.name
        if main_name and main_name not in names:
            names.append(main_name)
    return tuple(names)


def match_project_by_repo(config: JiraConfig, repos: Sequence[str]) -> Project | None:
    """Thử lần lượt từng tên (toplevel trước) — tên đầu khớp được thì thắng."""
    for repo in repos:
        project = next((p for p in config.projects.values() if repo in p.repos), None)
        if project is not None:
            return project
    return None


def resolve_project(
    config: JiraConfig,
    explicit: str | None = None,
    env: Mapping[str, str] | None = None,
) -> Project:
    """``--project`` > ``JIRA_PROJECT`` > repo git hiện tại; không khớp ⇒ ``ConfigError``.

    Key truyền tay nhưng chưa khai trong config vẫn dùng được, với profile mặc định và không
    có ``create_defaults`` — để thử nhanh một dự án mới mà chưa phải sửa config.
    """
    environ = os.environ if env is None else env
    key = (explicit or "").strip() or (environ.get(PROJECT_ENV_VAR) or "").strip()
    if key:
        return config.projects.get(key) or Project(key=key, profile=config.default_profile)
    repos = current_repo_names()
    project = match_project_by_repo(config, repos)
    if project is not None:
        return project
    tried = ", ".join(repos) or "(không phải repo git)"
    raise ConfigError(
        f"Không xác định được dự án Jira: đã thử tên repo {tried} "
        f"không khớp dự án nào trong {config.config_dir / CONFIG_FILE_NAME}.\n"
        f"Truyền --project, đặt {PROJECT_ENV_VAR}, hoặc thêm repo vào 'repos' của dự án.\n"
        f"Dự án đã khai:\n{config.project_listing()}"
    )


def resolve_profile(config: JiraConfig, project: Project | None) -> Profile:
    name = project.profile if project is not None else config.default_profile
    return config.profile(name)


def resolve_base_url(profile: Profile, env: Mapping[str, str] | None = None) -> str:
    environ = os.environ if env is None else env
    return (environ.get(BASE_URL_ENV_VAR) or "").strip() or profile.base_url


def read_secret_pat(config: JiraConfig, profile_name: str) -> str | None:
    """PAT trong ``config/secrets.json`` (file bị gitignore), hoặc ``None`` khi không có."""
    path = config.config_dir / SECRETS_FILE_NAME
    if not path.is_file():
        return None
    raw = _read_json(path)
    entry = (raw.get("profiles") or {}).get(profile_name) if isinstance(raw, Mapping) else None
    pat = entry.get("pat") if isinstance(entry, Mapping) else None
    return str(pat).strip() or None if pat else None
