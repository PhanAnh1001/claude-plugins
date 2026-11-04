"""Fake Claude Code / hand-ext tree for hh-ps tests (no real HOME or state dir)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

SECRET_PROMPT = "SECRET_PROMPT_MUST_NEVER_BE_PRINTED"
SECRET_SOCKET = "fake-socket-token"
SECRET_KEY = "fake-key-content-must-never-be-read"
MAIN_SESSION = "sess-main"
SIDE_SESSION = "sess-side"
ENDED_SESSION = "sess-ended"
NONAME_SESSION = "sess-noname"
OLD_SESSION = "sess-old"
OTHER_SESSION = "sess-other"
TRANSCRIPT_SLUG = "-fake-project-slug"
NOW = time.time()


def iso(epoch: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def dead_pid(start: int = 999_999) -> int:
    pid = start
    while pid < start + 1000:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            pass
        pid += 1
    raise RuntimeError("no dead pid found")


def usage_line(context_input: int, cached: int, created: int, output: int,
               timestamp: str) -> str:
    return json.dumps({
        "type": "assistant",
        "timestamp": timestamp,
        "message": {
            "role": "assistant",
            "content": [{"type": "text", "text": SECRET_PROMPT}],
            "usage": {
                "input_tokens": context_input,
                "cache_read_input_tokens": cached,
                "cache_creation_input_tokens": created,
                "output_tokens": output,
            },
        },
    })


def title_line(title: str, session_id: str) -> str:
    return json.dumps({"type": "custom-title", "customTitle": title,
                       "sessionId": session_id})


class HhFixture:
    """One project with two live sessions, recent/old transcripts, subagents and runs."""

    def __init__(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="hh-ps-"))
        self.home = self.base / "home"
        self.home.mkdir()
        self.claude = self.base / "claude"
        self.sessions = self.claude / "sessions"
        self.projects = self.claude / "projects"
        self.sessions.mkdir(parents=True)
        self.projects.mkdir(parents=True)
        self.project = self.base / "fake-project"
        self.other_project = self.base / "other-project"
        self.project.mkdir()
        self.other_project.mkdir()
        self.state = self.base / "state"
        self.runs = self.state / "runs"
        self.runs.mkdir(parents=True)
        self.ended_pid = dead_pid()
        self.old_pid = dead_pid(self.ended_pid + 1)
        self.other_pid = dead_pid(self.old_pid + 1)
        self.sleeper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
        self.live_side_pid = self.sleeper.pid
        self.main_pid = os.getpid()
        self._write_sessions()
        self._write_transcripts()
        self._write_subagents()
        self._write_runs()
        self._write_meta_and_config()
        self._write_key()

    # ---- fixtures -------------------------------------------------------
    def _session_file(self, pid: int, session_id: str, cwd: Path, started: float,
                      name: Optional[str], status: str = "idle",
                      updated: Optional[float] = None) -> None:
        data: Dict[str, Any] = {
            "pid": pid, "sessionId": session_id, "cwd": str(cwd),
            "startedAt": int(started * 1000), "version": "2.1.318",
            "kind": "interactive", "entrypoint": "cli", "nameSource": "auto",
            "updatedAt": int((updated or started) * 1000), "status": status,
            "statusUpdatedAt": int((updated or started) * 1000),
            "messagingSocketPath": SECRET_SOCKET,
        }
        if name:
            data["name"] = name
        (self.sessions / f"{pid}.json").write_text(json.dumps(data), encoding="utf-8")

    def _write_sessions(self) -> None:
        self._session_file(self.main_pid, MAIN_SESSION, self.project,
                           NOW - 7200, "live-main", "busy", NOW - 300)
        self._session_file(self.live_side_pid, SIDE_SESSION, self.project,
                           NOW - 3600, "live-side", "idle", NOW - 600)
        self._session_file(self.ended_pid, ENDED_SESSION, self.project,
                           NOW - 5000, "ended-name", "busy", NOW - 1800)
        self._session_file(self.old_pid, OLD_SESSION, self.project,
                           NOW - 9 * 3600, "old-name", "idle", NOW - 8 * 3600)
        self._session_file(self.other_pid, OTHER_SESSION, self.other_project,
                           NOW - 2400, None, "idle", NOW - 1200)

    def _transcript(self, session_id: str, lines: List[str], mtime: float) -> Path:
        path = self.projects / TRANSCRIPT_SLUG / f"{session_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.utime(path, (mtime, mtime))
        return path

    def _write_transcripts(self) -> None:
        cwd = json.dumps({"type": "user", "cwd": str(self.project),
                          "timestamp": iso(NOW - 7200)})
        self._transcript(MAIN_SESSION, [
            cwd, title_line("WP-23b", MAIN_SESSION),
            usage_line(1000, 2000, 3000, 200, iso(NOW - 300)),
        ], NOW - 300)
        self._transcript(SIDE_SESSION, [
            json.dumps({"type": "user", "cwd": str(self.project),
                        "timestamp": iso(NOW - 3600)}),
            usage_line(2000, 4000, 6000, 300, iso(NOW - 600)),
        ], NOW - 600)
        self._transcript(ENDED_SESSION, [
            json.dumps({"type": "user", "cwd": str(self.project),
                        "timestamp": iso(NOW - 5000)}),
            usage_line(1000, 2000, 2000, 100, iso(NOW - 1800)),
        ], NOW - 1800)
        self._transcript(NONAME_SESSION, [
            json.dumps({"type": "user", "cwd": str(self.project),
                        "timestamp": iso(NOW - 900)}),
            usage_line(100, 200, 300, 50, iso(NOW - 900)),
        ], NOW - 900)
        self._transcript(OLD_SESSION, [
            json.dumps({"type": "user", "cwd": str(self.project),
                        "timestamp": iso(NOW - 8 * 3600)}),
            usage_line(10, 20, 30, 5, iso(NOW - 8 * 3600)),
        ], NOW - 8 * 3600)
        self._transcript(OTHER_SESSION, [
            json.dumps({"type": "user", "cwd": str(self.other_project),
                        "timestamp": iso(NOW - 1200)}),
            usage_line(50, 60, 70, 5, iso(NOW - 1200)),
        ], NOW - 1200)

    def _agent(self, agent_id: str, description: str, finished: bool,
               context: int, mtime: float) -> None:
        folder = self.projects / TRANSCRIPT_SLUG / MAIN_SESSION / "subagents"
        folder.mkdir(parents=True, exist_ok=True)
        meta = {
            "agentType": "hybrid-hands:hand", "description": description,
            "toolUseId": f"tool-{agent_id}", "spawnDepth": 1,
            "requestShape": "background", "pickedEffortModel": "claude-opus-5-5",
            "finished": finished,
        }
        (folder / f"agent-{agent_id}.meta.json").write_text(json.dumps(meta),
                                                            encoding="utf-8")
        jsonl = folder / f"agent-{agent_id}.jsonl"
        jsonl.write_text(json.dumps({
            "type": "assistant", "timestamp": iso(mtime),
            "message": {"usage": {"input_tokens": context, "cache_read_input_tokens": 0,
                                  "cache_creation_input_tokens": 0, "output_tokens": 10}},
        }) + "\n", encoding="utf-8")
        os.utime(jsonl, (mtime, mtime))
        os.utime(folder / f"agent-{agent_id}.meta.json", (mtime, mtime))

    def _write_subagents(self) -> None:
        self._agent("run", "việc đang chạy " + "x" * 60, False, 2000, NOW - 120)
        self._agent("done", "việc đã xong", True, 4000, NOW - 600)
        self._agent("silent", "việc im lặng", False, 1000, NOW - 1900)
        self._agent("old", "việc cũ đã xong", True, 500, NOW - 8 * 3600)

    def _run(self, name: str, **overrides: Any) -> None:
        data = {
            "run_id": name, "label": name, "backend": "dsh",
            "model": "deepseek-v4.1-flash", "cwd": str(self.project),
            "run_dir": str(self.project / "output" / "llm" / "hand-ext" / name),
            "pid": os.getpid(), "child_pid": os.getpid(), "parent_session": None,
            "parent_claude_pid": os.getpid(), "started": iso(NOW - 600),
            "updated_at": int(NOW), "status": "running",
            "tokens": {"input": 0, "cached_input": 0, "output": 0},
        }
        data.update(overrides)
        (self.runs / f"{name}.json").write_text(json.dumps(data), encoding="utf-8")

    def _write_runs(self) -> None:
        self._run("main-run", parent_session=MAIN_SESSION,
                  tokens={"input": 1000, "cached_input": 2000, "output": 300})
        self._run("side-run", parent_session=SIDE_SESSION, status="ok", exit=0,
                  started=iso(NOW - 3600), ended=iso(NOW - 3000),
                  tokens={"input": 500, "cached_input": 700, "output": 100})
        self._run("orphan-run", parent_session=None, status="ok", exit=0,
                  started=iso(NOW - 2400), ended=iso(NOW - 1800),
                  tokens={"input": 40, "cached_input": 50, "output": 6})
        self._run("lost-run", parent_session=MAIN_SESSION, pid=self.ended_pid,
                  started=iso(NOW - 900))
        self._run("old-run", parent_session=MAIN_SESSION, status="ok", exit=0,
                  started=iso(NOW - 9 * 3600), ended=iso(NOW - 8 * 3600))

    def _write_meta_and_config(self) -> None:
        meta_dir = self.project / "meta"
        meta_dir.mkdir()
        (meta_dir / "WP-23b.meta").write_text(
            f"uuid={MAIN_SESSION}\ncap_usd=200000\nstarted={int(NOW - 7200)}\n"
            f"screen_pid={self.main_pid}\nexempt=1\n", encoding="utf-8")
        state_dir = self.project / "output" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "side.json").write_text(json.dumps({
            "name": "side", "uuid": SIDE_SESSION, "provider": "claude",
            "dir": str(self.project), "screen": "side-x", "watch_screen": "side-x-watch",
            "max_tokens": 50000, "started": NOW - 3600, "status": "running",
            "handoff": "", "tokens_used": 12000, "worktree": False,
        }), encoding="utf-8")
        (self.project / ".claude").mkdir()
        (self.project / ".claude" / "hybrid-hands.json").write_text(json.dumps({
            "ps": {"session_meta_globs": ["meta/*.meta"]},
            "side_session": {"state_dir": "output/state"},
        }), encoding="utf-8")

    def _write_key(self) -> None:
        key = self.sessions / f"{self.main_pid}.abcdef.key"
        key.write_text(SECRET_KEY, encoding="utf-8")
        key.chmod(0o000)
        self.key_path = key

    # ---- runtime --------------------------------------------------------
    @contextmanager
    def env(self) -> Iterator[None]:
        saved = dict(os.environ)
        os.environ.update({
            "HOME": str(self.home),
            "CLAUDE_CONFIG_DIR": str(self.claude),
            "HYBRID_HANDS_STATE_DIR": str(self.state),
            "CLAUDE_CODE_SESSION_ID": MAIN_SESSION,
            "CLAUDE_PID": str(self.main_pid),
        })
        os.environ.pop("NO_COLOR", None)
        try:
            yield
        finally:
            os.environ.clear()
            os.environ.update(saved)

    def close(self) -> None:
        self.sleeper.terminate()
        try:
            self.sleeper.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.sleeper.kill()
        shutil.rmtree(self.base, ignore_errors=True)
