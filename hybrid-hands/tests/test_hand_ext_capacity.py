"""hand-ext auto + dsh 429 capacity: keep a large patch, fall back to codex low for a small one."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent / "fixtures" / "hand_ext"))

from codex_harness import Sandbox  # noqa: E402
from hand_ext.backends import dsh  # noqa: E402
from hand_ext.constants import CODEX_FALLBACK_EFFORT, CODEX_FALLBACK_MODEL  # noqa: E402

FAKE_DSH = Path(__file__).resolve().parent / "fixtures" / "hand_ext" / "dsh_fake.py"
SOURCE_DIRTY = "user dirty\n"


class AutoCapacityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.sb = Sandbox(order=["dsh"])
        self.addCleanup(self.sb.close)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.aux = Path(tmp.name)
        self.repo = self.sb.dir
        os.environ["HYBRID_HANDS_STATE_DIR"] = str(self.aux / "state")
        dsh_home = self.aux / "dsh-home"
        options = {"home": str(dsh_home), "key_file": str(dsh_home / "go.key"),
                   "capacity_wait_seconds": 0, "capacity_wait_min_lines": 30}
        dsh.DshBackend().setup(options)
        key = dsh_home / "go.key"
        key.write_text("fake-go-key\n", encoding="utf-8")
        key.chmod(0o600)
        config_path = self.repo / ".claude" / "hybrid-hands.json"
        config = json.loads(config_path.read_text())
        config["ext_hand"]["backends"]["dsh"] = options
        config["ext_hand"]["worktree_root"] = str(self.aux / "worktrees")
        config["ext_hand"]["go_usage"] = {"live": False}
        config_path.write_text(json.dumps(config), encoding="utf-8")
        self.sb.cli("setup", "--backend", "codex")
        (self.repo / ".gitignore").write_text("codex-home/\n", encoding="utf-8")
        self._git("init", "-q")
        self._git("config", "user.email", "test@example.invalid")
        self._git("config", "user.name", "Test")
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-qm", "init")
        (self.repo / "tracked.txt").write_text(SOURCE_DIRTY, encoding="utf-8")
        os.environ.update({
            "HAND_EXT_DSH_BIN": str(FAKE_DSH),
            "FAKE_DSH_PROBE": str(self.aux / "probe.json"),
            "FAKE_DSH_COUNTER": str(self.aux / "counter"),
            "FAKE_DSH_PROMPT_LOG": str(self.aux / "prompt.log"),
            "CLAUDE_HOME": str(self.aux / "claude"),
            "HYBRID_HANDS_GO_FETCH": "",
        })

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True,
                              capture_output=True, text=True)

    def _run(self, scenario: str) -> tuple:
        os.environ["FAKE_DSH_SCENARIO"] = scenario
        return self.sb.cli("run", "--brief", str(self.sb.brief), "--backend", "auto")

    def _dsh_dir(self, suffix: str) -> Path:
        runs = (self.repo / "output" / "llm" / "hand-ext").iterdir()
        return next(path for path in runs if path.name.endswith(suffix))

    def _worktrees(self) -> list:
        return [path for path in (self.aux / "worktrees").iterdir() if path.is_dir()]

    def test_small_patch_falls_back_to_codex_low(self) -> None:
        code, out, err = self._run("capacity_small")
        self.assertEqual(code, 0, (out, err))
        entries = self.sb.ledger()
        self.assertEqual([entry["backend"] for entry in entries], ["dsh", "codex"])
        self.assertEqual(entries[0]["status"], "failed")
        self.assertEqual(entries[0]["tokens"],
                         {"input": 100, "cached_input": 0, "output": 10})
        self.assertEqual(entries[1]["status"], "ok")
        logged = json.loads(self.sb.log.read_text())
        self.assertEqual(logged["argv"][logged["argv"].index("-m") + 1], CODEX_FALLBACK_MODEL)
        self.assertIn(f'model_reasoning_effort="{CODEX_FALLBACK_EFFORT}"', logged["argv"])
        self.assertIn(self.sb.brief.read_text().strip(), logged["prompt"])
        self.assertEqual((self.repo / "tracked.txt").read_text(), SOURCE_DIRTY)
        self.assertFalse((self.repo / "small.txt").exists())
        dsh_dir = self._dsh_dir("-dsh")
        report = (dsh_dir / "report.md").read_text()
        for needle in ("bỏ patch dsh", "3 dòng", "ngưỡng 30", "gpt-6.1-sol", "low"):
            self.assertIn(needle, report)
        self.assertTrue((dsh_dir / "changes.patch").is_file())
        self.assertEqual(self._worktrees(), [])

    def test_large_patch_keeps_worktree_after_three_capacity_runs(self) -> None:
        config_path = self.repo / ".claude" / "hybrid-hands.json"
        config = json.loads(config_path.read_text())
        config["ext_hand"]["backends"]["dsh"]["capacity_wait_seconds"] = 7
        config_path.write_text(json.dumps(config), encoding="utf-8")
        with mock.patch("hand_ext.run_cmd.time", wraps=time) as clock:
            clock.sleep = mock.Mock()
            code, out, err = self._run("capacity_large")
            self.assertEqual(clock.sleep.call_args_list, [mock.call(7), mock.call(7)])
        self.assertEqual(code, 1, (out, err))
        entries = self.sb.ledger()
        self.assertEqual([entry["backend"] for entry in entries], ["dsh", "dsh", "dsh"])
        self.assertTrue(all(entry["status"] == "failed" for entry in entries))
        self.assertEqual([entry["tokens"]["input"] for entry in entries], [100, 100, 100])
        go_lines = (self.aux / "state" / "go_usage.jsonl").read_text().splitlines()
        self.assertEqual(len(go_lines), 3)
        registry = [json.loads(path.read_text())
                    for path in (self.aux / "state" / "runs").glob("*.json")]
        self.assertEqual(len(registry), 3)
        self.assertTrue(all(item["tokens"]["input"] == 100 for item in registry))
        self.assertFalse(self.sb.log.exists())
        self.assertNotIn("dsh", self.sb.quota())
        self.assertFalse((self.repo / "new.txt").exists())
        self.assertEqual((self.repo / "tracked.txt").read_text(), SOURCE_DIRTY)
        worktrees = self._worktrees()
        self.assertEqual(len(worktrees), 1)
        self.assertEqual((worktrees[0] / "new.txt").read_text().count("\n"), 5)
        first = (self._dsh_dir("-dsh") / "report.md").read_text()
        final_dir = self._dsh_dir("-dsh-r3")
        self.assertIn("30 dòng", first)
        report = (final_dir / "report.md").read_text()
        for needle in ("giữ patch dsh", "5 dòng", "ngưỡng 30", "7 s/lần", "2/2",
                       "vẫn quá tải sau 3 lần", "giữ worktree và changes.patch",
                       "không áp về gốc", "số dòng giảm"):
            self.assertIn(needle, report)
        self.assertTrue((final_dir / "changes.patch").is_file())
        prompts = [json.loads(line) for line in
                   (self.aux / "prompt.log").read_text().splitlines()]
        self.assertEqual(len(prompts), 3)
        self.assertEqual(len({item["workspace"] for item in prompts}), 1)
        self.assertNotIn("đã có patch, làm tiếp", prompts[0]["stdin"])
        self.assertTrue(all("đã có patch, làm tiếp" in item["stdin"]
                            for item in prompts[1:]))


if __name__ == "__main__":
    unittest.main()
