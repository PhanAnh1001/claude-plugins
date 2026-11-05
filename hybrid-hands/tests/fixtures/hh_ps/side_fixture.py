"""Side-session v2 fixture: worktree sessions, external rows and unknown parents."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from fixture import (
    HhFixture, MAIN_SESSION, NONAME_SESSION, NOW, dead_pid, iso,
)

WT_SIDE = "b7c9d1e3-2f4a-4b6c-8d0e-1f2a3b4c5d6e"
NESTED_SIDE = "c8d0e2f4-3a5b-4c7d-9e1f-2a3b4c5d6e7f"
LOST_PARENT_SIDE = "d9e1f3a5-4b6c-4d8e-af20-3b4c5d6e7f80"
DSH_SIDE = "e0f2a4b6-5c7d-4e9f-b031-4c5d6e7f8091"
ORPHAN_SIDE = "f1a3b5c7-6d8e-4f00-8123-5d6e7f809102"
UNKNOWN_PARENT = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d"

BASE_STATE_FIELDS = {
    "provider": "claude",
    "screen": "side-x",
    "watch_screen": "side-x-watch",
    "max_tokens": 50000,
    "handoff": "",
    "tokens_used": 0,
    "worktree": True,
}


class SideFixture(HhFixture):
    """The base tree plus Claude/dsh side sessions inside and outside the project."""

    def __init__(self) -> None:
        super().__init__()
        self.orphan_sleeper = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"])
        root = self.base / "fake-project-wt"
        self.wt_side = root / "wt-side"
        self.wt_nested = root / "nested-side"
        self.wt_lost = root / "lost-parent"
        self.wt_orphan = root / "mo-coi"
        self.wt_dsh = root / "dsh-side"
        for path in (self.wt_side, self.wt_nested, self.wt_lost,
                     self.wt_orphan, self.wt_dsh):
            path.mkdir(parents=True)
        self._write_worktree_sessions()
        self._write_side_states()
        self._write_side_runs()

    def _write_worktree_sessions(self) -> None:
        self._session_file(dead_pid(1_100_001), WT_SIDE, self.wt_side,
                           NOW - 1800, "wt-side", "idle", NOW - 1200)
        self._session_file(dead_pid(1_200_001), LOST_PARENT_SIDE, self.wt_lost,
                           NOW - 1700, "lost-parent", "idle", NOW - 1100)
        self._session_file(self.orphan_sleeper.pid, ORPHAN_SIDE, self.wt_orphan,
                           NOW - 1500, "mo-coi", "idle", NOW - 900)
        self._transcript(WT_SIDE, [
            json.dumps({"type": "user", "cwd": str(self.wt_side),
                        "timestamp": iso(NOW - 1800)}),
        ], NOW - 1200)
        self._transcript(NESTED_SIDE, [
            json.dumps({"type": "user", "cwd": str(self.wt_nested),
                        "timestamp": iso(NOW - 1300)}),
        ], NOW - 800)
        self._transcript(LOST_PARENT_SIDE, [
            json.dumps({"type": "user", "cwd": str(self.wt_lost),
                        "timestamp": iso(NOW - 1700)}),
        ], NOW - 1100)
        self._transcript(ORPHAN_SIDE, [
            json.dumps({"type": "user", "cwd": str(self.wt_orphan),
                        "timestamp": iso(NOW - 1500)}),
        ], NOW - 900)

    def _side_state(self, name: str, uuid: str, cwd: Path,
                    started: float, **overrides: Any) -> None:
        data: dict = {
            "name": name,
            "uuid": uuid,
            "dir": str(cwd),
            "started": started,
            "status": "running",
        }
        data.update(BASE_STATE_FIELDS)
        data.update(overrides)
        (self.project / "output" / "state" / f"{name}.json").write_text(
            json.dumps(data), encoding="utf-8")

    def _write_side_states(self) -> None:
        side_path = self.project / "output" / "state" / "side.json"
        side = json.loads(side_path.read_text(encoding="utf-8"))
        side["parent_session"] = MAIN_SESSION
        side_path.write_text(json.dumps(side), encoding="utf-8")
        self._side_state("wt-side", WT_SIDE, self.wt_side, NOW - 1800,
                         status="stopped", parent_session=MAIN_SESSION)
        self._side_state("nested-side", NESTED_SIDE, self.wt_nested, NOW - 1300,
                         status="stopped", parent_session=WT_SIDE)
        self._side_state("lost-parent", LOST_PARENT_SIDE, self.wt_lost, NOW - 1700,
                         status="stopped", parent_session=UNKNOWN_PARENT)
        self._side_state("dsh-side", DSH_SIDE, self.wt_dsh, NOW - 1000,
                         provider="dsh", parent_session=MAIN_SESSION,
                         max_tokens=40000, tokens_used=13000)
        self._side_state("mo-coi", ORPHAN_SIDE, self.wt_orphan, NOW - 1500,
                         max_tokens=50000, tokens_used=5000)
        self._side_state("legacy-side", NONAME_SESSION, self.project, NOW - 900,
                         status="stopped", max_tokens=10000, tokens_used=100)

    def _write_side_runs(self) -> None:
        self._run("dsh-side-run", label="side:dsh-side", parent_session=MAIN_SESSION,
                  backend="dsh", status="ok", exit=0, started=iso(NOW - 900),
                  ended=iso(NOW - 200),
                  tokens={"input": 700, "cached_input": 800, "output": 120})

    def close(self) -> None:
        self.orphan_sleeper.terminate()
        try:
            self.orphan_sleeper.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.orphan_sleeper.kill()
        super().close()
