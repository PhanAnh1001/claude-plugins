"""Repository profile drives the hook policy text."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/hybrid-hands"
sys.path.insert(0, str(PLUGIN / "lib"))

HOOKS = ("session-start-policy.sh", "inject-policy.sh")


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
        os.environ.pop("HYBRID_HANDS_ROLE", None)

    def delegation(self, profile, role=None):
        self.config.parent.mkdir(exist_ok=True)
        self.config.write_text(json.dumps({"profile": profile}))
        with patch.dict(os.environ, {"HYBRID_HANDS_ROLE": role} if role else {}):
            session, prompt = (context(r, i) for i, r in enumerate(hooks(self.tmp_path)))
        return session[session.index("PROFILE "):session.index("   LUẬT DỮ LIỆU:")], prompt

    def test_session_role_from_env_marker(self):
        brain, prompt = self.delegation("hybrid", "brain")
        assert "vai phiên này: brain." in brain and "pick --role" in brain and "Vai super brain" not in brain
        assert "vai brain." in prompt
        sup, prompt = self.delegation("hybrid")
        assert "vai phiên này: super brain." in sup and "Thang thu thập" not in sup and "Hết quota" in sup
        assert "vai super brain." in prompt
        mono, _ = self.delegation("gpt-mono", "super")
        assert "vai phiên này: brain." in mono

    def test_payload_session_id_shows_session_profile(self):
        self.config.parent.mkdir()
        self.config.write_text(json.dumps({"profile": "gpt-mono"}))
        state = self.tmp_path / "state/session-profiles"
        state.mkdir(parents=True)
        (state / "claude-abc.json").write_text(json.dumps({"profile": "claude-mono-v2"}))
        with patch.dict(os.environ, {"HYBRID_HANDS_STATE_DIR": str(self.tmp_path / "state")}):
            payload = json.dumps({"cwd": str(self.tmp_path), "session_id": "abc"})
            session, prompt = (context(r, i) for i, r in enumerate(hooks(self.tmp_path, payload)))
        label = "PROFILE claude-mono-v2 (riêng phiên; cấu hình: gpt-mono)"
        assert label + " — vai phiên này: brain." in session and "code: Claude v2 claude-opus-5-5 low" in session
        assert prompt.startswith(label + ", vai brain.")

    def test_profile_table_drives_delegation(self):
        self.config.parent.mkdir()
        cases = {"claude-mono": "code: Claude v1 claude-opus-5-5 low", "gpt-mono": "brain: GPT v1 gpt-6.1-sol high",
                 "hybrid": "super: Claude v2 claude-opus-5-5 high"}
        for name, row in cases.items():
            self.config.write_text(json.dumps({"profile": name}))
            session, prompt = (context(r, i) for i, r in enumerate(hooks(self.tmp_path)))
            delegation = session[session.index("PROFILE "):session.index("   LUẬT DỮ LIỆU:")]
            assert f"PROFILE {name}" in delegation and row in delegation and "B1/B2" in delegation
            assert "order" not in delegation and "dsh" not in delegation
            assert prompt.startswith(f"PROFILE {name}, vai ")
            assert ("super brain" in delegation) == (name == "hybrid")

    def test_missing_profile_prints_setup_hint_and_keeps_laws(self):
        laws = (PLUGIN / "lib/policy_rules.txt").read_text(encoding="utf-8")
        data_law = laws.split("   LUẬT DỮ LIỆU:", 1)[1].split("## Chọn hand", 1)[0]
        for i, result in enumerate(hooks(self.tmp_path)):
            text = context(result, i)
            assert "hand-ext profile set" in text and "hybrid" in text
            assert "ext_hand.order" not in text
            if i == 0:
                assert data_law in text and "LUẬT TEST TỐI THIỂU" in text


class DiskReminderTest(unittest.TestCase):
    def run_render(self, free_gib, git_out=None):
        import policy_mode
        usage = shutil._ntuple_diskusage(0, 0, int(free_gib * 1024 ** 3))
        git = (patch("disk_reminder.subprocess.run", side_effect=OSError) if git_out is None else
               patch("disk_reminder.subprocess.run",
                     return_value=subprocess.CompletedProcess([], 0, git_out, "")))
        with patch("disk_reminder.shutil.disk_usage", return_value=usage), git:
            return policy_mode.render("session", PLUGIN, json.dumps({"cwd": tempfile.gettempdir()}))

    def test_reminder_only_when_low_disk_and_extra_worktree(self):
        two = "worktree /a\nHEAD x\n\nworktree /b\nHEAD y\n"
        low = self.run_render(3, two)
        assert low.count("NHẮC DỌN WORKTREE") == 1 and "1 worktree phụ" in low and "side-session gc --apply" in low
        assert "NHẮC DỌN WORKTREE" not in self.run_render(500, two)
        broken = self.run_render(3)  # git fails: policy unchanged, no reminder
        assert "NHẮC DỌN WORKTREE" not in broken and "LUẬT NGỮ CẢNH BRAIN" in broken
