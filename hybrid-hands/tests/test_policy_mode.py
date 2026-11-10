"""Repository policy mode; hashes captured from 0.36.1 before modification."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/hybrid-hands"
sys.path.insert(0, str(PLUGIN / "lib"))
from shared_config import load_config

HOOKS = ("session-start-policy.sh", "inject-policy.sh")
BASELINE = ("f7da73cac0b0226c9a216b30b1f8aa9af417b3e3014f9e39d580edb71413a40e",
            "15fc1a8b0aa680cbf90118398ac071f1aec61f5e710c4022d1ea83c8b24cab38")
MATCHED_SESSION = "80d4d1479acb5123316647e0d5daa7fa0bb23508c18d59114e728f460a95f45c"


def hooks(cwd, payload=None):
    return [subprocess.run(["bash", str(PLUGIN / "scripts" / hook)], cwd=cwd,
                           input=json.dumps({"cwd": str(cwd)}) if payload is None else payload,
                           capture_output=True, text=True, check=True) for hook in HOOKS]


def context(result, index):
    return (json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
            if index == 0 else result.stdout)


class PolicyModeTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp_path = Path(directory.name).resolve()
        env = {"HOME": str(self.tmp_path), "PWD": str(self.tmp_path),
               "HYBRID_HANDS_CONFIG": str(self.tmp_path / "global.json"),
               "CLAUDE_PLUGIN_ROOT": str(PLUGIN), "CLAUDE_PROJECT_DIR": str(self.tmp_path)}
        patcher = patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.config = self.tmp_path / ".claude/hybrid-hands.json"

    def test_no_key_matches_0361_bytes(self):
        tmp_path = self.tmp_path
        for matched in (False, True):
            if matched:
                (tmp_path / "AGENTS.md").write_text("Thiếu PHẠM VI GHI thì hand coi là CHỈ ĐỌC (fail-closed).\n")
            for i, result in enumerate(hooks(tmp_path)):
                digest = hashlib.sha256(result.stdout.replace(str(PLUGIN), "<ROOT>").encode()).hexdigest()
                assert digest == (MATCHED_SESSION if matched and i == 0 else BASELINE[i])
                assert not result.stderr
        assert load_config(tmp_path).effective["parallel_subagents"]["enabled"] is False


    def test_repo_variant_and_fail_closed_fallbacks(self):
        tmp_path, config = self.tmp_path, self.config
        config.parent.mkdir()
        config.write_text(json.dumps({"parallel_subagents": {"enabled": True}, "ext_hand": {"max_parallel": 2}}))
        for payload in (json.dumps({"cwd": str(tmp_path)}), "invalid-json", '{"cwd":42}'):
            for i, result in enumerate(hooks(tmp_path, payload)):
                text = context(result, i)
                assert text.startswith(f"chế độ parallel_subagents bật bởi {config}\n")
                assert "2" in text and "review code hand mình giao" in text
                assert "Hand theo ext_hand.order" not in text and "| Sol |" not in text
                if i == 0:
                    assert "ext_hand.max_parallel thực = 2" in text and "claude-opus-5-5" in text
                    assert all(law in text for law in ("LUẬT DỮ LIỆU", "LUẬT TIẾP VIỆC", "LUẬT TEST TỐI THIỂU", "LUẬT NGỮ CẢNH BRAIN"))
        for bad in ('{"parallel_subagents":{"enabled":"PRIVATE_VALUE"}}', '{broken'):
            config.write_text(bad)
            for i, result in enumerate(hooks(tmp_path)):
                assert "parallel_subagents bật" not in context(result, i)
                assert "warning:" in result.stderr and "PRIVATE_VALUE" not in result.stderr
        config.write_text('{"parallel_subagents":{"enabled":true}}')
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        os.environ["CLAUDE_PROJECT_DIR"] = str(elsewhere)
        assert "parallel_subagents bật" in context(hooks(tmp_path)[0], 0)  # payload wins
        os.environ.pop("CLAUDE_PROJECT_DIR")
        assert "parallel_subagents bật" in context(hooks(tmp_path, "{}")[0], 0)  # PWD fallback


    def test_global_true_is_ignored_by_hooks_and_consumers(self):
        tmp_path = self.tmp_path
        (tmp_path / "global.json").write_text('{"parallel_subagents":{"enabled":true}}')
        result = load_config(tmp_path)
        assert result.effective["parallel_subagents"]["enabled"] is False
        assert result.sources["parallel_subagents.enabled"] == "global"
        assert result.sections[0][1]["parallel_subagents"]["enabled"] is False
        for i, output in enumerate(hooks(tmp_path)):
            assert hashlib.sha256(output.stdout.replace(str(PLUGIN), "<ROOT>").encode()).hexdigest() == BASELINE[i]
            assert "bỏ qua global" in output.stderr
