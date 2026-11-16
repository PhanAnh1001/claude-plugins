"""hh-ps reads hand-ext role/tier/escalated_from from run meta (fake fixtures only)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN_LIB = Path(__file__).resolve().parent.parent / "plugins" / "hybrid-hands" / "lib"
sys.path.insert(0, str(PLUGIN_LIB))

from hh_ps.compact import run_line  # noqa: E402
from hh_ps.registry_source import load_hand_runs  # noqa: E402
from hh_ps.render import _hand_run_json  # noqa: E402

NOW = 1_800_000_000.0
BASE = {"backend": "dsh", "model": "m", "effort": "off", "status": "done",
        "started_at": NOW - 60, "ended_at": NOW - 10}


def _load(extra: dict):
    with tempfile.TemporaryDirectory() as tmp:
        runs_dir = Path(tmp) / "runs"
        runs_dir.mkdir()
        (runs_dir / "r1.json").write_text(json.dumps({**BASE, "run_id": "r1", **extra}))
        [run] = load_hand_runs(Path(tmp), cutoff=0.0)
    return run, _hand_run_json(run, NOW), " ".join(c.text for c in run_line(run, NOW).cells)


class RoleTierTest(unittest.TestCase):
    def test_escalated_role(self) -> None:
        run, data, text = _load({"role": "collect", "tier": 2, "escalated_from": "r0"})
        self.assertEqual((data["role"], data["tier"], data["escalated_from"]), ("collect", 2, "r0"))
        self.assertIn("m/off collect B2↑", text)

    def test_legacy_and_bad_tier(self) -> None:
        _, legacy, legacy_text = _load({})
        self.assertEqual((legacy["role"], legacy["tier"], legacy["escalated_from"]), ("", None, ""))
        self.assertIn(" m/off ", f" {legacy_text} ")  # model cell unchanged, no extra tag
        self.assertNotIn("B", legacy_text.split("m/off", 1)[1].split()[0] if legacy_text.split("m/off", 1)[1].split() else "")
        _, bad, _ = _load({"role": "code", "tier": "2"})
        self.assertIsNone(bad["tier"])


if __name__ == "__main__":
    unittest.main()
