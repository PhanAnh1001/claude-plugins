"""Default selection and configured Claude account contract."""
from __future__ import annotations

import sys
import io
import json
import tempfile
from contextlib import redirect_stdout
from unittest import mock
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins" / "hybrid-hands" / "lib"))

from hand_ext.constants import DEFAULTS  # noqa: E402
from hand_ext_case import HandExtTestCase  # noqa: E402


class DefaultsTest(HandExtTestCase):
    def test_default_order_accounts_aliases_and_v3(self) -> None:
        from hand_ext.config import load_config
        from hand_ext.backends import get_backend
        self.assertEqual(DEFAULTS["order"], ["dsh", "codex", "claude-v1", "claude-v2"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.json"
            config.write_text(json.dumps({"ext_hand": {"claude_accounts": {
                "v1": {"config_dir": str(root / "first")},
                "v3": {"config_dir": str(root / "third"), "max_day_pct": 2}}}}))
            cfg = load_config(known_root=root, config_file=config)
            self.assertEqual(cfg.options("codex")["effort"], "low")
            self.assertEqual((cfg.options("dsh")["model"], cfg.options("dsh")["effort"]),
                             ("deepseek-v4.1-flash", "off"))
            from hand_ext.backends import dsh
            self.assertEqual(dsh.DEFAULT_EFFORT, "off")
            self.assertIn("              off: null\n", dsh.TEMPLATE_PATCH.read_text())
            for alias, canonical in (("claude-main", "claude-v1"), ("claude", "claude-v2")):
                self.assertEqual(cfg.options(alias), cfg.options(canonical))
            for name in ("claude-v1", "claude-v2", "claude-v3"):
                self.assertEqual((cfg.options(name)["model"], cfg.options(name)["effort"]),
                                 ("claude-opus-5-5", "low"))
                self.assertEqual(get_backend(name).name, name)
            self.assertEqual(cfg.options("claude-v3")["max_day_pct"], 2)
            self.assertEqual(cfg.options("claude-v1")["max_day_pct"], 8)
            self.assertIs(cfg.options("claude-v1")["day_guard"], True)
            self.assertIs(cfg.claude_accounts["v1"]["day_guard"], True)
            backend = get_backend("claude-v1")
            self.assertEqual(backend._base_env(cfg.options("claude-v1"))["CLAUDE_CONFIG_DIR"],
                             str(root / "first"))
            from types import SimpleNamespace
            from hh_ps.usage_enrichment import enrich_snapshot
            cfg.claude_accounts.pop("v3")
            run = SimpleNamespace(backend="claude-v3", model="claude-opus-5-5", usage=None,
                                  tokens={"input": 100, "output": 10}, week_limit_usd=None,
                                  week_pct_estimated=False)
            snapshot = SimpleNamespace(sessions=[], limits=[], iter_runs=lambda: [run])
            with mock.patch("hh_ps.usage_enrichment._claude_five", return_value=None):
                enrich_snapshot(snapshot, cfg, 1800000000)
            self.assertIsNotNone(run.usage.usd)
            self.assertEqual(run.usage.account_plan, "")
            self.assertIsNone(run.usage.week_pct)
            with self.assertRaises(ValueError):
                cfg.options("claude-v3")

    def test_pick_skips_unavailable_and_blocked_without_writes(self) -> None:
        from argparse import Namespace
        from hand_ext.cli import cmd_pick
        from hand_ext.config import load_config
        from hand_ext.backends.base import Check
        from hand_ext import day_budget
        from hand_ext.backends.codex import CodexBackend
        from hand_ext.backends.dsh import DshBackend
        from hand_ext.backends.claude import ClaudeAccountBackend
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = load_config(known_root=root, config_file=root / "absent.json")
            cfg.quota_state.parent.mkdir(parents=True)
            cfg.quota_state.write_text("{}")
            before = {str(p.relative_to(root)): p.read_bytes() if p.is_file() else None
                      for p in root.rglob("*")}
            with mock.patch.object(DshBackend, "doctor", return_value=[Check("login", False, "fixture")]), \
                    mock.patch.object(CodexBackend, "doctor", return_value=[Check("login", False, "fixture")]), \
                    mock.patch.object(ClaudeAccountBackend, "doctor", autospec=True,
                                      side_effect=lambda backend, opts: [Check("login", False, "fixture")]
                                      if exhausted and backend.name == "claude-v2" else []), \
                    mock.patch.object(day_budget, "assess", return_value=day_budget.DayUsage(5, 1, 5, 5)):
                for exhausted in (False, True):
                    with self.subTest(exhausted=exhausted):
                        cfg.order = list(DEFAULTS["order"])
                        output = io.StringIO()
                        with redirect_stdout(output):
                            code = cmd_pick(cfg, Namespace(json=True))
                        result = json.loads(output.getvalue())
                        self.assertEqual(code, 7 if exhausted else 0)
                        self.assertEqual(result["backend"], None if exhausted else "claude-v2")
                        self.assertEqual([s["backend"] for s in result["skipped"]],
                                         ["dsh", "codex", "claude-v1"] + (["claude-v2"] if exhausted else []))
            self.assertEqual({str(p.relative_to(root)): p.read_bytes() if p.is_file() else None
                              for p in root.rglob("*")}, before)


if __name__ == "__main__":
    unittest.main()
