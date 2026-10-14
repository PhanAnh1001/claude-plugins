"""Fixture chung: config tạm, cwd như đang ở repo example-repo, không chạm Keychain thật."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

LIB_DIR = Path(__file__).resolve().parents[1] / "plugins" / "jira-tools" / "lib"
sys.path.insert(0, str(LIB_DIR))

from jira_tools import client, config  # noqa: E402

TEST_BASE_URL = "https://jira.test.example"
TEST_PROFILE = "testhost"
OTHER_BASE_URL = "https://jira.other.example"
OTHER_PROFILE = "otherhost"
EXAMPLE_REPO = "example-repo"
KEYCHAIN_SERVICE = "jira-test-pat"


def sample_config() -> dict[str, Any]:
    return {
        "profiles": {
            TEST_PROFILE: {"base_url": TEST_BASE_URL, "keychain_service": KEYCHAIN_SERVICE},
            OTHER_PROFILE: {"base_url": OTHER_BASE_URL, "keychain_service": "jira-other-pat"},
        },
        "default_profile": TEST_PROFILE,
        "projects": {
            "PROJ": {
                "profile": TEST_PROFILE,
                "repos": [EXAMPLE_REPO],
                "create_defaults": {"assignee": None},
            },
            "OTH": {"profile": OTHER_PROFILE, "repos": ["other-repo"]},
        },
    }


@pytest.fixture(autouse=True)
def isolated_jira_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / config.CONFIG_FILE_NAME).write_text(json.dumps(sample_config()))
    monkeypatch.setenv(config.CONFIG_DIR_ENV_VAR, str(config_dir))
    for name in (
        client.TOKEN_ENV_VAR,
        config.BASE_URL_ENV_VAR,
        config.PROJECT_ENV_VAR,
        client.SSL_CERT_FILE_ENV_VAR,
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "current_repo_names", lambda cwd=None: (EXAMPLE_REPO,))
    monkeypatch.setattr(client, "read_keychain_token", lambda service: None)
    return config_dir
