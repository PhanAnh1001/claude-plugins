"""Fake Paseo + Claude tree for cc-switch tests; never touches real HOME."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SECRET_CONFIG = "CONFIG_SECRET_MUST_NOT_LEAK"
SECRET_NATIVE = "NATIVE_HANDLE_SECRET_MUST_NOT_LEAK"
SECRET_SOCKET = "SOCKET_SECRET_MUST_NOT_LEAK"
SECRET_PROMPT = "PROMPT_SECRET_MUST_NOT_LEAK"
SECRET_KEY = "KEY_SECRET_MUST_NOT_LEAK"

FAKE_OPEN = '''#!/usr/bin/env python3
"""Fake open: log argv and the .command file instead of opening a window."""
import json
import os
import sys

path = os.environ.get("CC_SWITCH_OPEN_LOG")
if path:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "argv": sys.argv[1:], "cwd": os.getcwd(),
            "script": (open(sys.argv[-1], encoding="utf-8").read()
                       if sys.argv[1:] and os.path.isfile(sys.argv[-1]) else None),
            "mode": (oct(os.stat(sys.argv[-1]).st_mode & 0o777)
                     if sys.argv[1:] and os.path.isfile(sys.argv[-1]) else None),
        }) + "\\n")
stderr = os.environ.get("CC_SWITCH_OPEN_STDERR", "")
if stderr:
    sys.stderr.write(stderr)
sys.exit(int(os.environ.get("CC_SWITCH_OPEN_EXIT", "0")))
'''

MODEL = "claude-sonnet-4-5"
TITLE_A = "Phiên A"
TITLE_IMPORT = "Phiên import"

AGENT_A = "aaaaaaaa-0000-0000-0000-000000000001"
AGENT_B = "bbbbbbbb-0000-0000-0000-000000000002"
AGENT_P = "cccccccc-0000-0000-0000-000000000003"
AGENT_TUI = "dddddddd-0000-0000-0000-000000000004"
AGENT_ARCHIVED = "eeeeeeee-0000-0000-0000-000000000005"
AGENT_SOLO = "ffffffff-0000-0000-0000-000000000006"
AGENT_OTHER = "11111111-0000-0000-0000-000000000007"
AGENT_ORPHAN = "22222222-0000-0000-0000-000000000008"
IMPORTED_AGENT = "99999999-8888-7777-6666-555555555555"

SID_A = "a1000000-0000-0000-0000-000000000001"
SID_B = "b1000000-0000-0000-0000-000000000002"
SID_P = "c1000000-0000-0000-0000-000000000003"
SID_TUI = "d1000000-0000-0000-0000-000000000004"
SID_SOLO = "f1000000-0000-0000-0000-000000000005"
SID_OTHER = "11000000-0000-0000-0000-000000000006"
SID_IMPORT = "21000000-0000-0000-0000-000000000007"
SID_NO_USER = "31000000-0000-0000-0000-000000000008"
SID_ORPHAN = "41000000-0000-0000-0000-000000000009"

NOW = time.time()


def iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def dead_pid(start: int = 999_000) -> int:
    pid = start
    while pid < start + 2000:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            pass
        pid += 1
    raise RuntimeError("no dead pid found")


def slugify(path: Path) -> str:
    return str(path.resolve()).replace("/", "-").replace(".", "-")


def title_line(cwd: Path, title: str) -> str:
    return json.dumps({
        "type": "custom-title", "customTitle": title, "cwd": str(cwd),
    })


def user_line(cwd: Path, when: float) -> str:
    return json.dumps({
        "type": "user", "cwd": str(cwd), "timestamp": iso(when),
        "message": {"role": "user", "content": SECRET_PROMPT},
    })


def assistant_line(cwd: Path, when: float) -> str:
    return json.dumps({
        "type": "assistant", "cwd": str(cwd), "timestamp": iso(when),
        "message": {"role": "assistant", "content": SECRET_PROMPT},
    })


class CcFixture:
    def __init__(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="cc-switch-"))
        self.home = self.base / "home"
        self.state = self.base / "state"
        self.claude = self.home / ".claude"
        self.paseo = self.base / "paseo"
        self.project = self.base / "project"
        self.solo = self.base / "solo"
        self.empty = self.base / "empty"
        self.other = self.base / "other"
        for path in (self.home, self.state, self.claude, self.paseo, self.project,
                     self.solo, self.empty, self.other):
            path.mkdir(parents=True)
        self.sessions = self.claude / "sessions"
        self.projects = self.claude / "projects"
        self.agents = self.paseo / "agents"
        self.sessions.mkdir()
        self.projects.mkdir()
        self.agents.mkdir()
        self.call_log = self.base / "calls.jsonl"
        self.open_log = self.base / "open.jsonl"
        self.fake_bin = self.base / "bin"
        shutil.copytree(Path(__file__).resolve().parent / "bin", self.fake_bin)
        for name in ("paseo", "claude"):
            (self.fake_bin / name).chmod(0o755)
        self._write_fake_open()
        self.sleeper = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(300)"])
        self.tui_pid = self.sleeper.pid
        self.dead_a = dead_pid()
        self.dead_b = dead_pid(self.dead_a + 1)
        self.dead_p = dead_pid(self.dead_b + 1)
        self._write_sessions()
        self._write_agents()
        self._write_transcripts()
        self.key_path = self.sessions / f"{self.tui_pid}.abcdef.key"
        self.key_path.write_text(SECRET_KEY, encoding="utf-8")
        self.key_path.chmod(0o000)

    # ---- trees ---------------------------------------------------------
    def _write_session(self, pid: int, session_id: str, cwd: Path,
                       entrypoint: str, status: str, name: str) -> None:
        (self.sessions / f"{pid}.json").write_text(json.dumps({
            "pid": pid, "sessionId": session_id, "cwd": str(cwd),
            "entrypoint": entrypoint, "status": status, "name": name,
            "startedAt": int((NOW - 600) * 1000),
            "messagingSocketPath": SECRET_SOCKET,
        }), encoding="utf-8")

    def _write_sessions(self) -> None:
        self._write_session(self.tui_pid, SID_TUI, self.project, "cli", "idle",
                            "tui-live")
        self._write_session(self.dead_a, SID_A, self.project, "sdk-cli", "idle",
                            "paseo-a")
        self._write_session(self.dead_b, SID_B, self.project, "sdk-cli", "idle",
                            "paseo-b")
        self._write_session(self.dead_p, SID_P, self.project, "sdk-cli", "idle",
                            "paseo-p")

    def _agent_record(self, agent_id: str, cwd: Path, title: str,
                      session_id: Optional[str], status: str,
                      persistence_only: bool = False) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "id": agent_id, "cwd": str(cwd), "provider": "claude",
            "title": title, "lastActivityAt": iso(NOW - 100),
            "lastStatus": status,
            "config": {"token": SECRET_CONFIG, "nested": {"value": SECRET_NATIVE}},
        }
        if persistence_only:
            record["persistence"] = {"sessionId": session_id}
        else:
            record["runtimeInfo"] = {
                "sessionId": session_id, "model": MODEL,
                "nativeHandle": SECRET_NATIVE,
            }
            record["persistence"] = {"sessionId": session_id}
        return record

    def _agent(self, project: Path, agent_id: str, title: str,
               session_id: Optional[str], status: str,
               persistence_only: bool = False, archived: bool = False) -> None:
        record = self._agent_record(agent_id, project, title, session_id, status,
                                    persistence_only)
        if archived:
            record["archivedAt"] = iso(NOW - 50)
        folder = self.agents / project.name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{agent_id}.json").write_text(json.dumps(record),
                                                 encoding="utf-8")

    def _write_agents(self) -> None:
        self._agent(self.project, AGENT_A, "Agent A", SID_A, "idle")
        self._agent(self.project, AGENT_B, "Agent B running", SID_B, "running")
        self._agent(self.project, AGENT_TUI, "Agent TUI", SID_TUI, "idle")
        self._agent(self.project, AGENT_ARCHIVED, "Agent archived", None, "idle",
                    archived=True)
        self._agent(self.project, AGENT_P, "Agent persistence", SID_P, "idle",
                    persistence_only=True)
        self._agent(self.project, AGENT_ORPHAN, "Agent no transcript", SID_ORPHAN,
                    "idle")
        self._agent(self.solo, AGENT_SOLO, "Agent solo", SID_SOLO, "idle")
        self._agent(self.other, AGENT_OTHER, "Agent other", SID_OTHER, "idle")

    def _transcript(self, project: Path, session_id: str, lines: List[str],
                    mtime: float) -> Path:
        path = self.projects / slugify(project) / f"{session_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.utime(path, (mtime, mtime))
        return path

    def _write_transcripts(self) -> None:
        self._transcript(self.solo, SID_SOLO,
                         [user_line(self.solo, NOW - 50)], NOW - 50)
        self._transcript(self.project, SID_A,
                         [user_line(self.project, NOW - 100),
                          title_line(self.project, TITLE_A)], NOW - 100)
        self._transcript(self.project, SID_B,
                         [user_line(self.project, NOW - 150)], NOW - 150)
        self._transcript(self.project, SID_P,
                         [user_line(self.project, NOW - 120)], NOW - 120)
        self._transcript(self.project, SID_TUI,
                         [user_line(self.project, NOW - 200)], NOW - 200)
        self._transcript(self.project, SID_IMPORT,
                         [user_line(self.project, NOW - 30),
                          title_line(self.project, TITLE_IMPORT)], NOW - 30)
        self._transcript(self.project, SID_NO_USER,
                         [assistant_line(self.project, NOW - 10)], NOW - 10)
        self._transcript(self.other, SID_OTHER,
                         [user_line(self.other, NOW - 5)], NOW - 5)

    # ---- extra live entries for --self tests ---------------------------
    def add_live_session(self, pid: int, session_id: str,
                         cwd: Optional[Path] = None,
                         entrypoint: str = "cli", status: str = "idle",
                         name: str = "test-live") -> None:
        self._write_session(pid, session_id, cwd or self.project,
                            entrypoint, status, name)

    def add_transcript(self, project: Path, session_id: str,
                       mtime: Optional[float] = None,
                       lines: Optional[List[str]] = None) -> Path:
        moment = time.time() - 10 if mtime is None else mtime
        body = lines if lines is not None else [user_line(project, moment)]
        return self._transcript(project, session_id, body, moment)

    def _write_fake_open(self) -> None:
        path = self.fake_bin / "open"
        path.write_text(FAKE_OPEN, encoding="utf-8")
        path.chmod(0o755)

    def open_calls(self) -> List[Dict[str, Any]]:
        if not self.open_log.exists():
            return []
        return [json.loads(line) for line in
                self.open_log.read_text(encoding="utf-8").splitlines()
                if line]

    # ---- runtime -------------------------------------------------------
    def ls_json(self, statuses: Optional[Dict[str, str]] = None) -> str:
        statuses = statuses or {
            AGENT_A: "idle", AGENT_B: "running", AGENT_P: "idle",
            AGENT_TUI: "idle", AGENT_ARCHIVED: "idle", AGENT_SOLO: "idle",
            AGENT_OTHER: "idle",
        }
        rows = [
            {"id": AGENT_A, "cwd": str(self.project), "title": "Agent A",
             "status": statuses.get(AGENT_A, "idle")},
            {"id": AGENT_B, "cwd": str(self.project), "title": "Agent B running",
             "status": statuses.get(AGENT_B, "idle")},
            {"id": AGENT_P, "cwd": str(self.project), "title": "Agent persistence",
             "status": statuses.get(AGENT_P, "idle")},
            {"id": AGENT_TUI, "cwd": str(self.project), "title": "Agent TUI",
             "status": statuses.get(AGENT_TUI, "idle")},
            {"id": AGENT_ARCHIVED, "cwd": str(self.project), "title": "Agent archived",
             "status": statuses.get(AGENT_ARCHIVED, "idle")},
            {"id": AGENT_SOLO, "cwd": str(self.solo), "title": "Agent solo",
             "status": statuses.get(AGENT_SOLO, "idle")},
            {"id": AGENT_OTHER, "cwd": str(self.other), "title": "Agent other",
             "status": statuses.get(AGENT_OTHER, "idle")},
            {"id": AGENT_ORPHAN, "cwd": str(self.project),
             "title": "Agent no transcript",
             "status": statuses.get(AGENT_ORPHAN, "idle")},
        ]
        return json.dumps(rows)

    def env(self, **overrides: str) -> Dict[str, str]:
        env = dict(os.environ)
        env.update({
            "HOME": str(self.home),
            "HYBRID_HANDS_CONFIG": str(self.home / "absent-config.json"),
            "CLAUDE_CONFIG_DIR": str(self.claude),
            "PASEO_HOME": str(self.paseo),
            "HYBRID_HANDS_STATE_DIR": str(self.state),
            "PATH": str(self.fake_bin) + os.pathsep + env.get("PATH", ""),
            "CC_SWITCH_CALL_LOG": str(self.call_log),
            "CC_SWITCH_OPEN_LOG": str(self.open_log),
            "CC_SWITCH_OPEN_EXIT": "0",
            "CC_SWITCH_OPEN_STDERR": "",
            "PASEO_FAKE_LS_STDOUT": self.ls_json(),
            "PASEO_FAKE_IMPORT_STDOUT": "Importing provider session...\n" +
            json.dumps({"agentId": IMPORTED_AGENT, "status": "created"}) + "\n",
        })
        env.update(overrides)
        return env

    def calls(self) -> List[Dict[str, Any]]:
        if not self.call_log.exists():
            return []
        return [json.loads(line) for line in
                self.call_log.read_text(encoding="utf-8").splitlines() if line]

    def close(self) -> None:
        self.sleeper.terminate()
        try:
            self.sleeper.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.sleeper.kill()
        shutil.rmtree(self.base, ignore_errors=True)
