"""side-session Paseo transport: start shape, fallback rules and lifecycle (no daemon)."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugins" / "hybrid-hands" / "lib"))

from side_session import actions, attach, constants as C, state  # noqa: E402
from side_session.cli import build_parser  # noqa: E402
from side_session.config import SideConfig  # noqa: E402


def cfg_for(tmp: Path, **over) -> SideConfig:
    return SideConfig(
        repo=tmp, handoff_dir=tmp / "handoffs", worktree_root=tmp / "wt",
        max_parallel=2, default_max_tokens=1000, watch_interval_s=0,
        state_dir=tmp / "state", codex_home=tmp / "codex", **over)


def start_args(name: str, **over) -> SimpleNamespace:
    args = build_parser().parse_args(
        ["start", "--name", name, "--prompt", "Task", "--provider", C.PROVIDER_CODEX,
         "--worktree"])
    for key, value in over.items():
        setattr(args, key, value)
    return args


def save_session(cfg: SideConfig, name: str, **over) -> None:
    values = dict(
        name=name, uuid="u", provider=C.PROVIDER_CODEX, dir=str(cfg.worktree_root / name), worktree=True,
        screen="", watch_screen=actions.K.watch_screen(name), max_tokens=1000,
        started=time.time() - 60, status=C.STATUS_RUNNING,
        handoff=str(cfg.handoff_dir / f"{name}.md"), transport=C.TRANSPORT_PASEO,
        paseo_agent_id=f"agent-{name}", paseo_workspace_id=f"workspace-{name}", paseo_target="home:/tmp/paseo")
    values.update(over)
    state.save(cfg.state_dir, state.SessionState(**values))


def write_rollout(path: Path, cwd: Path, created: float, total: dict,
                  thread: str = "codex") -> Path:
    stamp = datetime.fromtimestamp(created, timezone.utc).isoformat()
    records = [
        {"type": "session_meta", "payload": {"id": thread, "cwd": str(cwd),
                                             "timestamp": stamp}},
        {"type": "event_msg", "payload": {"type": "token_count", "info": {
            "total_token_usage": total, "last_token_usage": total}}},
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return path


class RecordingStdin(io.StringIO):
    """Keep what was written after the writer closes the pipe."""

    def __init__(self) -> None:
        super().__init__()
        self.sent = ""

    def close(self) -> None:
        self.sent = self.getvalue()
        super().close()


class FakeAppServer:
    """Minimal `codex app-server` child: predigested JSON-RPC responses."""

    def __init__(self, responses: list[dict]) -> None:
        self.stdin = RecordingStdin()
        self.stdout = iter([json.dumps(message) + "\n" for message in responses])
        self.returncode = None
        self.cmd: list[str] = []
        self.kwargs: dict = {}

    def wait(self, timeout=None):
        self.returncode = 0
        return 0

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


def fake_app_popen(procs: list[FakeAppServer], cmd, **kwargs) -> FakeAppServer:
    proc = FakeAppServer([{"jsonrpc": "2.0", "id": 1, "result": {}},
                          {"jsonrpc": "2.0", "id": 2, "result": {}}])
    proc.cmd, proc.kwargs = list(cmd), kwargs
    procs.append(proc)
    return proc


class PaseoStartTest(unittest.TestCase):
    def setUp(self):
        naming = mock.patch.object(actions.names, "retry")
        naming.start()
        self.addCleanup(naming.stop)

    def test_send_history_and_unknown_delivery(self):
        for provider in (C.PROVIDER_CODEX, C.PROVIDER_CLAUDE):
            for error in (False, True, "notSent"):
                with self.subTest(provider=provider, error=error), tempfile.TemporaryDirectory() as d:
                    cfg = cfg_for(Path(d))
                    save_session(cfg, "a", provider=provider, status=C.STATUS_DONE, worktree=False, dir=str(cfg.repo))
                    st = state.load(cfg.state_dir, "a")
                    Path(st.dir).mkdir(parents=True, exist_ok=True)
                    save_session(cfg, "main", role="main", dir=str(cfg.repo), worktree=False)
                    ack = {"agentArchived": True, "agentId": st.paseo_agent_id,
                           "workspaceId": st.paseo_workspace_id, "targetKey": st.paseo_target, "archived": True}
                    with mock.patch.object(actions.paseo, "_call", return_value=ack) as call, mock.patch.object(actions, "count_tokens", return_value=0), mock.patch.object(actions, "_pin_rollout"), mock.patch.object(actions, "_capture_paseo_thread"):
                        self.assertTrue(actions._finish_codex(cfg, st))
                        self.assertEqual([o["agentId"] for o in call.call_args.args[1]["workspaceOwners"]], [st.paseo_agent_id])
                        self.assertTrue(state.load(cfg.state_dir, "a").paseo_workspace_archived)
                    cfg.handoff_dir.mkdir()
                    marker = actions.K.done_path(st.handoff)
                    marker.write_text("old")
                    prompt = cfg.repo / "prompt.txt"
                    prompt.write_text("next task")
                    args = build_parser().parse_args(["send", "--name", "a", "--prompt-file", str(prompt)])
                    with mock.patch.object(actions, "_preflight", return_value=None), mock.patch.object(
                            actions.paseo, "send", side_effect=actions.paseo.PaseoError("SEND_ACK_UNKNOWN", {"notSent": True} if error == "notSent" else {}) if error else None
                            ) as send, mock.patch.object(actions.subprocess, "run", return_value=SimpleNamespace(returncode=0)):
                        self.assertEqual(actions.send(cfg, args), int(bool(error)))
                        self.assertEqual(send.call_args.args[0].paseo_agent_id, st.paseo_agent_id)
                        self.assertEqual(marker.exists(), error == "notSent")
                        self.assertEqual(len(list(marker.parent.glob("*.history-*"))), 1)
                        current = state.load(cfg.state_dir, "a")
                        self.assertEqual(current.paseo_send_pending, error is True)
                        self.assertEqual(current.started, st.started)
                        self.assertEqual(current.status, C.STATUS_DONE if error else C.STATUS_RUNNING)
                        self.assertEqual(actions.send(cfg, args), 1 if error == "notSent" else C.EXIT_USAGE)
                        self.assertEqual(send.call_count, 2 if error == "notSent" else 1)
                        self.assertTrue(Path(current.dir).is_dir())

    def test_bridge_restores_before_exact_send_and_preserves_on_error(self):
        import subprocess
        # Archived workspace is absent from the active directory until restored; the
        # public 0.15.0 sendMessage resolves {} on acceptance (no create, same agent).
        for broken in ("", "restore", "restore-error", "send", "ack"):
            with self.subTest(broken=broken), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                utils = root / "dist" / "utils"
                utils.mkdir(parents=True)
                (root / "package.json").write_text('{"type":"module"}')
                (utils / "daemon-target.js").write_text('export const selectDaemonTarget=()=>({kind:"instance",home:"/fake"});')
                (utils / "client.js").write_text("""
import {appendFileSync} from 'node:fs';
export async function connectToDaemon(){let active=false; const log=x=>appendFileSync(process.env.TEST_EVENTS,x+'\\n'); return {
 fetchAgent:async()=>({agent:{id:'a',workspaceId:'w',archivedAt:'2026-01-01'}}),
 fetchWorkspaces:async()=>({entries:active?[{id:'w',workspaceDirectory:'/repo'},{id:'main',workspaceDirectory:'/repo'}]:[],pageInfo:{nextCursor:null}}),
 inspectWorkspaceRecovery:async()=>active?{kind:'unavailable',reason:'workspace_not_archived',workspaceId:'w'}:{kind:'recoverable',action:'unarchive',workspaceId:'w'},
 restoreWorkspace:async id=>{log('restore:'+id); if(process.env.TEST_BROKEN==='restore')throw Error(); if(process.env.TEST_BROKEN==='restore-error')return {error:'RESTORE_FAILED'};active=true;return {};},
 createAgent:async()=>log('create'),
 sendMessage:async(id,text)=>{log('send:'+id);if(process.env.TEST_BROKEN==='send')throw Error();return process.env.TEST_BROKEN==='ack'?{deliveryStatus:'bogus'}:{};},
 close:async()=>{} };}
""")
                events = root / "events"
                proc = subprocess.run(["node", str(actions.paseo.BRIDGE), str(root)], input=json.dumps({
                    "command": "send", "agentId": "a", "expectedWorkspaceId": "w",
                    "expectedTargetKey": "home:/fake", "workdir": "/repo", "text": "task"}), text=True,
                    capture_output=True, timeout=5, env={**os.environ, "TEST_EVENTS": str(events), "TEST_BROKEN": broken})
                result = json.loads(proc.stdout)
                self.assertEqual(result["ok"], not bool(broken))
                if broken:
                    self.assertEqual(result["data"].get("notSent", False), broken.startswith("restore"))
                self.assertEqual(events.read_text().splitlines(), ["restore:w"] + ([] if broken.startswith("restore") else ["send:a"]))

    def test_bridge_start_joins_caller_workspace_or_falls_back(self):
        import subprocess
        # Also: Claude account provider claude-v2 is used only when the daemon lists it ready.
        for archived, shared, listed in ((False, True, "claude-v2"), (True, False, "")):
            with self.subTest(archived=archived), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                utils = root / "dist" / "utils"
                utils.mkdir(parents=True)
                (root / "package.json").write_text('{"type":"module"}')
                (utils / "daemon-target.js").write_text('export const selectDaemonTarget=()=>({kind:"instance",home:"/fake"});')
                (utils / "client.js").write_text("""
import {appendFileSync} from 'node:fs';
const log=x=>appendFileSync(process.env.TEST_EVENTS,x+'\\n');
export async function connectToDaemon(){return {
 addProject:async()=>({project:{projectId:'p'}}),
 fetchAgent:async({agentId})=>({agent:{id:agentId,workspaceId:agentId==='chat'?'wchat':undefined,
   archivedAt:agentId==='chat'&&process.env.TEST_ARCHIVED?'2026-01-01':null}}),
 inspectWorkspaceRecovery:async id=>({kind:'unavailable',reason:'workspace_not_archived',workspaceId:id}),
 createWorkspace:async()=>{log('createWorkspace');return {workspace:{id:'wnew'}};},
 getProvidersSnapshot:async()=>({entries:[{provider:'claude',enabled:true,status:'ready'},
   ...(process.env.TEST_LISTED?[{provider:process.env.TEST_LISTED,enabled:true,status:'ready'}]:[])]}),
 createAgent:async a=>{if(Object.keys(a).some(k=>/parent|label|initiator/i.test(k)))throw Error('parent metadata');log('createAgent:'+a.workspaceId+':'+a.provider);return {id:'side'};},
 close:async()=>{} };}
""")
                events = root / "events"
                proc = subprocess.run(["node", str(actions.paseo.BRIDGE), str(root)], input=json.dumps({
                    "command": "start", "projectRoot": "/repo", "workdir": "/repo/wt",
                    "source": {"kind": "directory", "path": "/repo/wt"}, "callerAgentId": "chat",
                    "provider": "claude", "accountProvider": "claude-v2"}),
                    text=True, capture_output=True, timeout=5,
                    env={**os.environ, "TEST_EVENTS": str(events), "TEST_ARCHIVED": "1" if archived else "",
                         "TEST_LISTED": listed})
                result = json.loads(proc.stdout)
                self.assertEqual((result["workspaceShared"], result["workspaceId"]),
                                 (shared, "wchat" if shared else "wnew"))
                self.assertEqual("createWorkspace" in events.read_text(), not shared)
                self.assertEqual(result["provider"], listed or "claude")

    def test_start_stores_shared_and_done_never_touches_shared_workspace(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = cfg_for(Path(d))
            st = state.SessionState(name="s", uuid="u", provider=C.PROVIDER_CODEX, dir=str(cfg.repo),
                                    screen="", watch_screen="", max_tokens=1, started=0.0, status="", handoff="")
            reply = {"agentId": "side", "workspaceId": "wchat", "workspaceShared": True, "targetKey": "t"}
            with mock.patch.dict(os.environ, {C.PASEO_CALLER_AGENT_ENV: "chat"}), \
                    mock.patch.object(actions.paseo, "start_agent", return_value=reply) as start, \
                    mock.patch.object(actions.paseo.codex_trust, "ensure_codex_compact_limit"), \
                    mock.patch.object(actions.K, "watch_cmd", return_value=["true"]):
                actions.paseo.start_session(cfg, start_args("s", worktree=False), st, str(cfg.repo), "p", "t")
            self.assertEqual(start.call_args.kwargs["caller_agent_id"], "chat")
            self.assertEqual((st.paseo_workspace_id, st.paseo_workspace_shared), ("wchat", True))
            st.status = C.STATUS_RUNNING
            ok = {"agentArchived": True, "agentId": "side", "workspaceId": "wchat", "targetKey": "t"}
            out = io.StringIO()
            with mock.patch.object(actions.paseo, "_call", return_value=ok) as call, \
                    mock.patch.object(actions, "count_tokens", return_value=0), \
                    mock.patch.object(actions, "_pin_rollout"), mock.patch.object(actions, "_capture_paseo_thread"), \
                    redirect_stdout(out):
                self.assertTrue(actions._finish_codex(cfg, st))
                actions.watch_tick(cfg, "s")
            self.assertEqual([c.args[0] for c in call.call_args_list], ["finish"])
            self.assertFalse(call.call_args.args[1]["privateWorkspace"])
            self.assertNotIn("warning: workspace", out.getvalue())
            st.paseo_name_done, st.paseo_name_attempts = False, 0
            named = {"agentNamed": True, "workspaceNamed": False, "warning": "NAME_WORKSPACE_BLOCKED"}
            with mock.patch.object(actions.paseo, "_call", return_value=named), redirect_stdout(out):
                mock.patch.stopall()  # real names.retry (setUp stubs it)
                actions.names.retry(cfg, st)
                self.assertEqual(actions.tidy(cfg, build_parser().parse_args(["tidy", "--name", "s"])), 0)
            self.assertTrue(st.paseo_name_done)
            self.assertNotIn("NAME_WORKSPACE_BLOCKED", out.getvalue())
            self.assertIn("skip workspace=wchat (shared)", out.getvalue())

    def test_tidy_defaults_and_preserves_state_on_error(self):
        for apply, broken in ((False, False), (True, False), (True, True)):
            with tempfile.TemporaryDirectory() as d:
                cfg = cfg_for(Path(d))
                save_session(cfg, "a", status=C.STATUS_DONE, worktree=False, dir=str(cfg.repo))
                before = state.state_path(cfg.state_dir, "a").read_text()
                args = build_parser().parse_args(["tidy", "--name", "a"] + (["--apply"] if apply else []))
                result = {"eligible": True, "archived": apply, "workspaceId": "workspace-a",
                          "targetKey": "home:/tmp/paseo", "agentIds": []}
                with mock.patch.object(actions.paseo, "_call", return_value=result,
                        side_effect=actions.paseo.PaseoError("FAILED") if broken else None) as call, redirect_stdout(io.StringIO()):
                    self.assertEqual(actions.tidy(cfg, args), int(broken))
                    self.assertEqual(call.call_args.args[1]["apply"], apply)
                self.assertEqual(state.load(cfg.state_dir, "a").paseo_workspace_archived, apply and not broken)
                if not apply or broken:
                    self.assertEqual(state.state_path(cfg.state_dir, "a").read_text(), before)

    def test_main_start(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(actions.paseo, "plan", return_value={"target": "fake"}), mock.patch.object(actions.paseo, "start_agent", return_value={"agentId": "main"}) as agent, mock.patch.object(actions.K, "watch_cmd") as watch, mock.patch.object(actions.paseo.codex_trust, "ensure_codex_compact_limit") as compact:
            cfg = cfg_for(Path(d))
            with mock.patch.object(actions, "_running", return_value=[None] * cfg.max_parallel), mock.patch.dict(os.environ, {"PASEO_AGENT_ID": "chat", "PASEO_WORKSPACE_ID": ""}):
                self.assertEqual(actions.start(cfg, start_args("main", main=True, worktree=False, prompt=None)), 0)
            call = agent.call_args.kwargs
            self.assertEqual(call["caller_agent_id"], "chat")
            self.assertEqual((call["workdir"], call["effort"]), (str(cfg.repo), "high"))
            self.assertIn("PHIÊN CHÍNH", call["initial_prompt"])
            self.assertIn(C.MAIN_DEFAULT_PROMPT, call["initial_prompt"])
            st = state.load(cfg.state_dir, "main")
            self.assertEqual((st.role, st.handoff, st.watch_screen, call["hand_scope"]), ("main", "", "", st.uuid))
            self.assertEqual(actions._running(cfg), [])
            self.assertFalse(cfg.handoff_dir.exists())
            watch.assert_not_called()
            compact.assert_called_once_with(cfg.codex_home, C.CODEX_AUTO_COMPACT_TOKEN_LIMIT)

    def test_main_marker_idle_and_stop_never_archive(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = cfg_for(Path(d))
            save_session(cfg, "main", role="main")
            cfg.handoff_dir.mkdir()
            actions.K.done_path(state.load(cfg.state_dir, "main").handoff).touch()
            with mock.patch.object(actions.paseo, "_call", return_value={"status": "idle"}) as call, mock.patch.object(actions, "count_tokens", return_value=0), mock.patch.object(actions, "_quit"):
                self.assertFalse(actions.watch_tick(cfg, "main"))
                call.assert_not_called()
                self.assertEqual(actions.paseo.finish(state.load(cfg.state_dir, "main")), "MAIN_ARCHIVE_FORBIDDEN")
                actions.ls(cfg, None)
                self.assertEqual(state.load(cfg.state_dir, "main").status, C.STATUS_IDLE)
                self.assertEqual(actions.stop(cfg, SimpleNamespace(name="main")), 0)
                self.assertEqual([c.args[0] for c in call.call_args_list], ["status", "stop"])

    def test_main_invalid_options(self):
        for over in ({"worktree": True}, {"worktree": False, "provider": "dsh"}):
            self.assertEqual(actions.start(cfg_for(Path("/fake")), start_args("bad", main=True, **over)), 2)

    def test_main_requires_daemon(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(actions.paseo, "disabled", return_value=False), mock.patch.object(actions.paseo, "cli_package_root", return_value=Path("/fake")), mock.patch.object(actions.paseo, "ready", side_effect=actions.paseo.PaseoError("DAEMON_UNREACHABLE")) as ready, mock.patch.object(actions.K, "session_cmd") as screen:
            cfg = cfg_for(Path(d))
            self.assertEqual(actions.start(cfg, start_args("main", main=True, worktree=False)), 1)
            screen.assert_not_called(); ready.reset_mock()
            self.assertEqual(actions.start(cfg, start_args("dry", main=True, worktree=False, dry_run=True)), 0)
            ready.assert_not_called()


    def test_watch_flags_idle_without_done_and_closes_done_agent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cfg = cfg_for(Path(d))
            save_session(cfg, "idle-done", worktree=True)
            st = state.load(cfg.state_dir, "idle-done")
            work = Path(st.dir)
            work.mkdir(parents=True)
            cfg.handoff_dir.mkdir()
            out = io.StringIO()
            with mock.patch.object(actions.paseo, "status",
                                   return_value={"status": "idle"}) as agent_status, \
                    mock.patch.object(actions.paseo, "_call", return_value={"ok": True, "archived": True, "agentArchived": True,
                        "agentId": st.paseo_agent_id, "workspaceId": st.paseo_workspace_id,
                        "targetKey": st.paseo_target}) as call, \
                    mock.patch.object(actions, "_quit") as quit_session, \
                    redirect_stdout(out):
                self.assertTrue(actions.watch_tick(cfg, st.name))
                self.assertEqual(state.load(cfg.state_dir, st.name).status, "idle_no_done")
                self.assertIn(".done", out.getvalue())
                self.assertIn("warning", out.getvalue().lower())
                actions.ls(cfg, None)
                self.assertIn("idle_no_done", out.getvalue())
                self.assertEqual(len(actions._running(cfg)), 1)
                call.assert_not_called()
                for raw in ("initializing", "running"):
                    agent_status.return_value = {"status": raw}
                    self.assertTrue(actions.watch_tick(cfg, st.name))
                    self.assertEqual(state.load(cfg.state_dir, st.name).status, C.STATUS_RUNNING)
                handoff = Path(st.handoff)
                handoff.write_text("## Tóm tắt\n- Kết quả: xong\n")
                handoff.with_suffix(C.DONE_SUFFIX).touch()
                # A failed cleanup must retain its slot and retry on the next tick.
                call.side_effect = actions.paseo.PaseoError("PASEO_TIMEOUT")
                self.assertTrue(actions.watch_tick(cfg, st.name))
                self.assertIn(state.load(cfg.state_dir, st.name).status, C.ACTIVE_STATUSES)
                self.assertEqual(len(actions._running(cfg)), 1)
                listing = io.StringIO()
                with redirect_stdout(listing):
                    actions.ls(cfg, None)
                self.assertNotRegex(listing.getvalue(), r"(?m)^idle-done\s+codex\s+no\s+done\s+")
                call.side_effect = actions.paseo.PaseoError(C.PASEO_AGENT_NOT_FOUND)
                self.assertTrue(actions.watch_tick(cfg, st.name))
                pending = state.load(cfg.state_dir, st.name)
                pending.status = C.STATUS_RUNNING
                state.save(cfg.state_dir, pending)
                call.side_effect = None
                call.reset_mock()
                self.assertFalse(actions.watch_tick(cfg, st.name))
                self.assertEqual(state.load(cfg.state_dir, st.name).status, C.STATUS_DONE)
                self.assertEqual(actions._running(cfg), [])
                # Dedicated lifecycle operation must preserve the conversation.
                self.assertEqual([c.args[0] for c in call.call_args_list], ["finish", "rearchive"])
                self.assertEqual(call.call_args.args[1]["agentId"], st.paseo_agent_id)
                self.assertEqual(call.call_args.args[1]["expectedWorkspaceId"], st.paseo_workspace_id)
                pending = state.load(cfg.state_dir, st.name)
                pending.paseo_workspace_archived = False
                state.save(cfg.state_dir, pending)
                call.side_effect = actions.paseo.PaseoError("WORKSPACE_ARCHIVE_FAILED")
                self.assertFalse(actions.watch_tick(cfg, st.name))
                self.assertEqual(state.load(cfg.state_dir, st.name).status, C.STATUS_DONE)
                call.side_effect = None
                call.return_value = {"ok": True, "archived": True}
                actions.ls(cfg, None)
                self.assertTrue(state.load(cfg.state_dir, st.name).paseo_workspace_archived)
                self.assertEqual(call.call_args.args[1]["expectedTargetKey"], st.paseo_target)
                quit_session.assert_not_called()
            self.assertTrue(work.is_dir())
            self.assertTrue(Path(st.handoff).is_file())

    def test_start_creates_codex_hand_agent_and_stores_live_state(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            cfg = cfg_for(tmp)
            cfg.codex_home.mkdir(parents=True)
            response = {"ok": True, "agentId": "agent-1", "workspaceId": "ws-1",
                        "threadId": "thread-1", "targetKey": "home:/tmp/paseo"}
            procs: list[FakeAppServer] = []
            events: list[tuple[str, object]] = []
            real_save = actions.state.save

            def save(state_dir, st):
                events.append(("save", st.status))
                real_save(state_dir, st)

            def run(cmd, *args, **kwargs):
                events.append(("run", list(cmd)))
                return SimpleNamespace(returncode=0, stdout="")

            def popen(cmd, **kw):
                proc = fake_app_popen(procs, cmd, **kw)
                proc.stdout = io.StringIO("".join(proc.stdout))
                return proc

            out = io.StringIO()
            with mock.patch.object(actions.paseo, "disabled", return_value=False), \
                    mock.patch.object(actions.paseo, "cli_package_root",
                                      return_value=Path("/fake/cli")), \
                    mock.patch.object(actions.paseo, "ready",
                                      return_value={"targetKey": "home:/tmp/paseo"}), \
                    mock.patch.object(actions.paseo, "_call", return_value=response) as call, \
                    mock.patch.object(actions.paseo, "status",
                                      return_value={"status": "running",
                                                    "threadId": "thread-1"}), \
                    mock.patch.object(actions.K, "watch_cmd",
                                      return_value=["watch-ok"]) as watch_cmd, \
                    mock.patch.object(actions.K, "session_cmd") as session_cmd, \
                    mock.patch.object(actions.subprocess, "run", side_effect=run), \
                    mock.patch.object(actions.state, "save", side_effect=save), \
                    mock.patch.object(actions.paseo.codex_trust.subprocess, "Popen",
                                      side_effect=popen), \
                    mock.patch.object(actions.screen, "screen_names", return_value=set()), \
                    redirect_stdout(out):
                self.assertEqual(actions.start(cfg, start_args("n")), 0)
            session_cmd.assert_not_called()
            payload = call.call_args.args[1]
            self.assertEqual(payload["provider"], C.PASEO_PROVIDER)
            self.assertEqual(payload["title"], "n · Sol phụ")
            self.assertEqual(payload["source"], {"kind": "directory", "path": str(tmp / "wt" / "n")})
            self.assertEqual(payload["workdir"], str(tmp / "wt" / "n"))
            self.assertEqual(payload["model"], C.CODEX_MODEL_DEFAULT)
            self.assertEqual(payload["effort"], C.CODEX_EFFORT_DEFAULT)
            self.assertEqual(payload["env"]["CODEX_HOME"], str(cfg.codex_home))
            self.assertEqual(payload["env"]["HYBRID_HANDS_HAND_SCOPE"], actions.state.load(cfg.state_dir, "n").uuid)
            self.assertNotIn("modeId", payload)
            options = payload["providerOptions"]
            self.assertEqual(options["approval_policy"], "never")
            self.assertEqual(options["sandbox_mode"], "danger-full-access")
            self.assertNotIn("sandbox_workspace_write", options)
            self.assertNotIn(C.CODEX_COMPACT_KEY, json.dumps(options))
            self.assertEqual(payload["expectedTargetKey"], "home:/tmp/paseo")
            st = state.load(cfg.state_dir, "n")
            self.assertEqual((st.transport, st.paseo_agent_id, st.paseo_workspace_id),
                             (C.TRANSPORT_PASEO, "agent-1", "ws-1"))
            self.assertEqual((st.codex_thread_id, st.paseo_target),
                             ("thread-1", "home:/tmp/paseo"))
            self.assertEqual((st.status, st.screen), (C.STATUS_RUNNING, ""))
            self.assertEqual(st.watch_screen, actions.K.watch_screen("n"))
            with mock.patch.object(actions.paseo, "status",
                                   return_value={"status": "running",
                                                 "threadId": "thread-1"}):
                self.assertEqual(len(actions._running(cfg)), 1)
            self.assertEqual([event for event in events if event[0] == "save"],
                             [("save", C.STATUS_RUNNING)] * 3)
            self.assertEqual(events[-2:], [("save", C.STATUS_RUNNING), ("run", ["watch-ok"])])
            watch_cmd.assert_called_once_with(cfg, "n")
            # Native config RPC, not a TOML regex edit; no thread/turn/model/auth call.
            proc = procs[0]
            self.assertEqual(proc.cmd, [C.CODEX_APP_SERVER, "app-server"])
            self.assertEqual(proc.kwargs["env"]["CODEX_HOME"], str(cfg.codex_home))
            self.assertEqual(proc.kwargs["cwd"], str(cfg.codex_home))
            requests = [json.loads(line) for line in proc.stdin.sent.splitlines()]
            self.assertEqual([request.get("method") for request in requests],
                             ["initialize", "initialized", "config/value/write"])
            self.assertEqual(requests[0]["params"]["clientInfo"]["name"],
                             C.CODEX_CONFIG_CLIENT_NAME)
            self.assertEqual(requests[2]["params"],
                             {"keyPath": C.CODEX_COMPACT_KEY, "value": 272000,
                              "mergeStrategy": "replace"})

            child = mock.Mock(stdin=io.StringIO(), stdout=io.StringIO())
            child.wait.side_effect = [actions.subprocess.TimeoutExpired("fake", 1),
                                      actions.subprocess.TimeoutExpired("fake", 1), 0]
            self.assertTrue(actions.paseo.codex_trust._stop_app_server(child))
            child.kill.assert_called_once_with()
            self.assertEqual(child.wait.call_count, 3)
            self.assertTrue(child.stdout.closed)

    def test_daemon_absent_falls_back_but_create_failure_does_not(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            cfg = cfg_for(tmp)
            with mock.patch.object(actions.paseo, "disabled", return_value=False), \
                    mock.patch.object(actions.paseo, "cli_package_root",
                                      return_value=Path("/fake/cli")), \
                    mock.patch.object(actions.paseo, "ready",
                                      side_effect=actions.paseo.PaseoError("DAEMON_UNREACHABLE")), \
                    mock.patch.object(actions.K, "session_cmd", return_value=["true"]) as screen_cmd, \
                    mock.patch.object(actions.K, "watch_cmd", return_value=["true"]), \
                    mock.patch.object(actions.subprocess, "run",
                                      return_value=SimpleNamespace(returncode=0)), \
                    mock.patch.object(actions.screen, "screen_names", return_value=set()), \
                    mock.patch.object(actions.checkout.gc, "common_dir", return_value=tmp / "git"), \
                    redirect_stdout(io.StringIO()) as out:
                self.assertEqual(actions.start(cfg, start_args("fallback")), 0)
            self.assertIn("DAEMON_UNREACHABLE", out.getvalue())
            self.assertIn("dùng screen", out.getvalue())
            screen_cmd.assert_called_once()
            self.assertEqual(state.load(cfg.state_dir, "fallback").transport,
                             C.TRANSPORT_SCREEN)

            # A dry-run only plans the screen fallback: no daemon probe is claimed.
            out = io.StringIO()
            dry = start_args("dry", dry_run=True)
            with redirect_stdout(out):
                self.assertIsNone(actions.paseo.plan(cfg, dry))
            self.assertIn("screen fallback", out.getvalue())

            # A ready daemon plus codex_profile must fail, never silently use screen.
            profile_cfg = cfg_for(tmp, codex_profile="work")
            out = io.StringIO()
            with mock.patch.object(actions.paseo, "disabled", return_value=False), \
                    mock.patch.object(actions.paseo, "cli_package_root",
                                      return_value=Path("/fake/cli")), \
                    mock.patch.object(actions.paseo, "ready",
                                      return_value={"targetKey": "home:/tmp/paseo"}), \
                    mock.patch.object(actions.K, "session_cmd") as screen_cmd, \
                    mock.patch.object(actions.screen, "screen_names", return_value=set()), \
                    redirect_stdout(out):
                self.assertEqual(actions.start(profile_cfg, start_args("profile")),
                                 C.EXIT_USAGE)
            screen_cmd.assert_not_called()
            self.assertIn("không fallback screen", out.getvalue())
            self.assertFalse(state.state_path(profile_cfg.state_dir, "profile").exists())

            # A native config failure is reported and never falls back to screen.
            out = io.StringIO()
            with mock.patch.object(actions.paseo, "disabled", return_value=False), \
                    mock.patch.object(actions.paseo, "cli_package_root",
                                      return_value=Path("/fake/cli")), \
                    mock.patch.object(actions.paseo, "ready",
                                      return_value={"targetKey": "home:/tmp/paseo"}), \
                    mock.patch.object(actions.paseo.codex_trust,
                                      "ensure_codex_compact_limit",
                                      side_effect=actions.paseo.codex_trust.ConfigWriteError(
                                          "CONFIG_WRITE_REJECTED")), \
                    mock.patch.object(actions.paseo, "start_agent") as start_agent, \
                    mock.patch.object(actions.K, "session_cmd") as screen_cmd, \
                    mock.patch.object(actions.subprocess, "run",
                                      return_value=SimpleNamespace(returncode=0, stdout="")), \
                    mock.patch.object(actions.screen, "screen_names", return_value=set()), \
                    redirect_stdout(out):
                self.assertEqual(actions.start(cfg, start_args("cfgfail")), 1)
            self.assertIn("CONFIG_WRITE_FAILED", out.getvalue())
            start_agent.assert_not_called()
            screen_cmd.assert_not_called()

            # A non-zero bridge process is an error even when its last line says ok.
            with mock.patch.object(actions.paseo, "cli_package_root",
                                   return_value=Path("/fake/cli")), \
                    mock.patch.object(actions.paseo.shutil, "which",
                                      return_value="/usr/bin/node"), \
                    mock.patch.object(actions.subprocess, "run",
                                      return_value=SimpleNamespace(
                                          returncode=1, stdout='{"ok": true}\n',
                                          stderr="secret")):
                with self.assertRaises(actions.paseo.PaseoError) as raised:
                    actions.paseo._call("ready", timeout=1)
            self.assertNotIn("secret", raised.exception.code)

            # Workspace failure before agent creation: error state, no slot, no screen.
            with mock.patch.object(actions.paseo, "disabled", return_value=False), \
                    mock.patch.object(actions.paseo, "cli_package_root",
                                      return_value=Path("/fake/cli")), \
                    mock.patch.object(actions.paseo, "ready",
                                      return_value={"targetKey": "home:/tmp/paseo"}), \
                    mock.patch.object(actions.paseo.codex_trust, "ensure_codex_compact_limit"), \
                    mock.patch.object(actions.paseo, "start_agent",
                                      side_effect=actions.paseo.PaseoError(
                                          "WORKSPACE_CREATE_FAILED", {"workspaceId": "ws-bad"})), \
                    mock.patch.object(actions.K, "session_cmd") as screen_cmd, \
                    mock.patch.object(actions.subprocess, "run",
                                      return_value=SimpleNamespace(returncode=0, stdout="")), \
                    mock.patch.object(actions.screen, "screen_names", return_value=set()), \
                    redirect_stdout(io.StringIO()) as out:
                self.assertEqual(actions.start(cfg, start_args("bad")), 1)
            self.assertIn("không fallback screen", out.getvalue())
            screen_cmd.assert_not_called()
            bad = state.load(cfg.state_dir, "bad")
            self.assertEqual((bad.status, bad.paseo_workspace_id),
                             (C.STATUS_ERROR, "ws-bad"))
            self.assertNotIn("bad", [item.name for item in actions._running(cfg)])

            # Lost create reply without an ID holds the slot and blocks name reuse.
            timeout = actions.paseo.PaseoError("AGENT_CREATE_FAILED")
            with mock.patch.object(actions.paseo, "disabled", return_value=False), \
                    mock.patch.object(actions.paseo, "cli_package_root",
                                      return_value=Path("/fake/cli")), \
                    mock.patch.object(actions.paseo, "ready",
                                      return_value={"targetKey": "home:/tmp/paseo"}), \
                    mock.patch.object(actions.paseo.codex_trust, "ensure_codex_compact_limit"), \
                    mock.patch.object(actions.paseo, "start_agent",
                                      side_effect=timeout) as start_agent, \
                    mock.patch.object(actions.K, "watch_cmd") as watch_cmd, \
                    mock.patch.object(actions.K, "session_cmd") as screen_cmd, \
                    mock.patch.object(actions.subprocess, "run",
                                      return_value=SimpleNamespace(returncode=0, stdout="")), \
                    mock.patch.object(actions.screen, "screen_names", return_value=set()), \
                    redirect_stdout(io.StringIO()) as out:
                self.assertEqual(actions.start(cfg, start_args("pending")), 1)
                self.assertTrue(actions.watch_tick(cfg, "pending"))
                pending = state.load(cfg.state_dir, "pending")
                self.assertEqual(pending.status, C.STATUS_UNKNOWN)
                self.assertIn("pending", [item.name for item in actions._running(cfg)])
                self.assertEqual(actions.start(cfg, start_args("pending")), C.EXIT_USAGE)
                with mock.patch.object(actions.screen, "quit"):
                    self.assertEqual(actions.stop(cfg, SimpleNamespace(name="pending")), 0)
                self.assertNotIn("pending", [item.name for item in actions._running(cfg)])
            self.assertIn("giữ slot", out.getvalue())
            self.assertIn("paseo ls", out.getvalue())
            self.assertIn("SAU ĐÓ chạy `side-session stop pending`", out.getvalue())
            self.assertNotIn("side-session stop --name", out.getvalue())
            watch_cmd.assert_not_called()
            screen_cmd.assert_not_called()
            start_agent.assert_called_once()

    def test_idle_watch_done_pins_thread_rollout_and_stop_targets_agent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            cfg = cfg_for(tmp)
            work = tmp / "work"
            other = tmp / "other"
            work.mkdir(parents=True)
            other.mkdir()
            handoff = cfg.handoff_dir / "n.md"
            handoff.parent.mkdir(parents=True)
            handoff.write_text("## Tóm tắt\n- Kết quả: xong\n")
            started = time.time() - 60
            day = cfg.codex_home / C.CODEX_SESSIONS_SUBDIR / "2026/11/07"
            right = write_rollout(day / "rollout-2026-11-07T00-00-00-thread-abc.jsonl",
                                  work, started + 2, {"input_tokens": 50},
                                  thread="thread-abc")
            # Substring-but-not-suffix, matching name with wrong meta id, and wrong cwd.
            write_rollout(day / "rollout-2026-11-07T00-00-01-thread-abc-old.jsonl",
                          work, started + 3, {"input_tokens": 900}, thread="thread-abc")
            write_rollout(day / "rollout-2026-11-07T00-00-02-thread-abc.jsonl",
                          work, started + 4, {"input_tokens": 901}, thread="other")
            write_rollout(day / "rollout-2026-11-07T00-00-03-thread-abc.jsonl",
                          other, started + 5, {"input_tokens": 902}, thread="thread-abc")
            write_rollout(day / "rollout-2026-11-07T00-00-04-other.jsonl",
                          work, started + 6, {"input_tokens": 903}, thread="other")
            save_session(cfg, "n", started=started, dir=str(work), handoff=str(handoff),
                         worktree=True, paseo_agent_id="agent-1",
                         codex_thread_id="thread-abc")

            late_thread = {"id": ""}
            agent_live = {"agent-1": "running"}

            def fake_status(agent_id, _target):
                if agent_id == "agent-gone":
                    raise actions.paseo.PaseoError(C.PASEO_AGENT_NOT_FOUND)
                if agent_id == "agent-flaky":
                    raise actions.paseo.PaseoError("PASEO_TIMEOUT")
                if agent_id == "agent-late":
                    return {"status": "running", "threadId": late_thread["id"]}
                if agent_id == "agent-d":
                    return {"status": "running"}
                if agent_id == "agent-u":
                    return {"status": "running"}
                return {"status": agent_live["agent-1"], "threadId": "thread-abc"}

            u_handoff = cfg.handoff_dir / "u.md"
            u_handoff.write_text("## Tóm tắt\n")
            u_handoff.with_suffix(C.DONE_SUFFIX).write_text("")
            save_session(cfg, "u", started=started, dir=str(work),
                         handoff=str(u_handoff), watch_screen="", paseo_agent_id="agent-u")
            late_rollout = write_rollout(
                day / "rollout-2026-11-07T00-00-05-thread-late.jsonl", work,
                started + 7, {"input_tokens": 77}, thread="thread-late")
            save_session(cfg, "late", started=started, dir=str(work),
                         watch_screen="", paseo_agent_id="agent-late")
            for name in ("gone", "flaky"):
                save_session(cfg, name, started=started, dir=str(work),
                             watch_screen="", paseo_agent_id=f"agent-{name}")

            with mock.patch.object(actions.paseo, "status", side_effect=fake_status), \
                    mock.patch.object(actions.paseo, "stop_agent") as stop_agent, \
                    mock.patch.object(actions.paseo, "finish", return_value=None), \
                    mock.patch.object(actions.screen, "quit") as quit_screen:
                self.assertTrue(actions.watch_tick(cfg, "n"))
                first = state.load(cfg.state_dir, "n")
                self.assertEqual(Path(first.codex_rollout).resolve(), right.resolve())
                self.assertEqual(first.tokens_used, 50)
                agent_live["agent-1"] = "idle"
                self.assertTrue(actions.watch_tick(cfg, "n"))
                self.assertEqual(state.load(cfg.state_dir, "n").status, C.STATUS_IDLE_NO_DONE)
                handoff.with_suffix(C.DONE_SUFFIX).write_text("")
                self.assertFalse(actions.watch_tick(cfg, "n"))
                done = state.load(cfg.state_dir, "n")
                self.assertEqual(done.status, C.STATUS_DONE)
                self.assertEqual(Path(done.codex_rollout).resolve(), right.resolve())
                out_done = io.StringIO()
                with redirect_stdout(out_done):
                    self.assertEqual(actions.ls(cfg, None), 0)
                self.assertEqual(state.load(cfg.state_dir, "n").status, C.STATUS_DONE)
                self.assertRegex(out_done.getvalue(), r"(?m)^n\s+codex\s+no\s+done\s+")

                # No thread on a Paseo state: never fall back to a cwd rollout.
                self.assertFalse(actions.watch_tick(cfg, "u"))
                no_thread = state.load(cfg.state_dir, "u")
                self.assertEqual((no_thread.status, no_thread.codex_rollout,
                                  no_thread.tokens_used), (C.STATUS_DONE, "", 0))

                # A thread learned after the first pin is pinned on the next tick.
                self.assertTrue(actions.watch_tick(cfg, "late"))
                self.assertEqual(state.load(cfg.state_dir, "late").codex_rollout, "")
                late_thread["id"] = "thread-late"
                self.assertTrue(actions.watch_tick(cfg, "late"))
                self.assertEqual(
                    Path(state.load(cfg.state_dir, "late").codex_rollout).resolve(),
                    late_rollout.resolve())

                names = [item.name for item in actions._running(cfg)]
                self.assertNotIn("gone", names)
                self.assertEqual(state.load(cfg.state_dir, "gone").status, C.STATUS_DEAD)
                self.assertIn("flaky", names)

                self.assertEqual(actions.stop(cfg, SimpleNamespace(name="n")), 0)
                self.assertEqual(state.load(cfg.state_dir, "n").status, C.STATUS_STOPPED)
                quit_screen.assert_called_once_with(actions.K.watch_screen("n"))
                out_stopped = io.StringIO()
                with redirect_stdout(out_stopped):
                    self.assertEqual(actions.ls(cfg, None), 0)
                self.assertEqual(state.load(cfg.state_dir, "n").status, C.STATUS_STOPPED)
                self.assertRegex(out_stopped.getvalue(), r"(?m)^n\s+codex\s+no\s+stopped\s+")
                self.assertNotIn("n", [item.name for item in actions._running(cfg)])

                # Daystop interrupt failure keeps the agent active and retries.
                budget_cfg = cfg_for(tmp, budget_check_cmd=["true"])
                save_session(cfg, "d", started=started, dir=str(work),
                             watch_screen="", paseo_agent_id="agent-d")
                out_day = io.StringIO()
                with mock.patch.object(actions.budget, "check", return_value=object()), \
                        mock.patch.object(actions.budget, "daystop", return_value=True), \
                        mock.patch.object(actions.paseo, "interrupt",
                                          return_value="PASEO_TIMEOUT"), \
                        redirect_stdout(out_day):
                    self.assertTrue(actions.watch_tick(budget_cfg, "d"))
                self.assertEqual(state.load(cfg.state_dir, "d").status, C.STATUS_RUNNING)
                self.assertIn("giữ active", out_day.getvalue())
                self.assertIn("d", [item.name for item in actions._running(budget_cfg)])

            stop_agent.assert_called_once_with("agent-1", "home:/tmp/paseo")

            hint_out = io.StringIO()
            code = attach.run_attach(
                "n", ids_fn=mock.Mock(return_value={}), exec_fn=mock.Mock(),
                input_fn=mock.Mock(), print_fn=lambda text: hint_out.write(text + "\n"),
                screen_bin="/usr/bin/screen",
                transport_fn=lambda name: (C.TRANSPORT_PASEO, "agent-1"))
            self.assertEqual(code, 0)
            self.assertIn("paseo attach agent-1", hint_out.getvalue())


    def test_done_revive_and_rearchive_follow_agent_archive(self) -> None:
        # Scripted bridge answers read from mutable fixtures.
        for kind in ("ls", "watch"):
            with tempfile.TemporaryDirectory() as d:
                cfg = cfg_for(Path(d))
                cfg.handoff_dir.mkdir()
                fake = {"revive": (False, None), "rearchive": (False, None),
                        "events": [], "archived": False}

                def revive(st):
                    fake["events"].append(("revive", st.name))
                    return fake["revive"]

                def rearchive(st, owners):
                    fake["events"].append(("rearchive", st.name))
                    return fake["rearchive"]

                def step() -> str:
                    out = io.StringIO()
                    with mock.patch.object(actions.paseo, "revive", side_effect=revive), \
                            mock.patch.object(actions.paseo, "rearchive", side_effect=rearchive), \
                            mock.patch.object(actions.paseo, "agent_archive_states",
                                              side_effect=lambda _: {"agent-a": fake["archived"]}) as listing, \
                            mock.patch.object(actions, "_finish_codex") as finish_codex, \
                            mock.patch.object(actions.paseo, "refresh", return_value="alive"), \
                            redirect_stdout(out):
                        if kind == "ls":
                            self.assertEqual(actions.ls(cfg, None), 0)
                        else:
                            actions.watch_tick(cfg, "a")
                    self.assertEqual(listing.call_count, int(kind == "ls"))
                    finish_codex.assert_not_called()
                    return out.getvalue()

                def snapshot() -> tuple[str, bool, bool]:
                    st = state.load(cfg.state_dir, "a")
                    return st.status, st.paseo_revived, st.paseo_workspace_archived

                save_session(cfg, "a", status=C.STATUS_DONE, paseo_workspace_archived=True)
                done = Path(cfg.handoff_dir / "a.md").with_suffix(C.DONE_SUFFIX)
                done.write_text("")  # a stale .done must never finish a revived session
                # Done + private workspace archived + agent unarchived: restore, persist.
                fake["revive"] = (True, None)
                self.assertNotIn("warning", step())
                self.assertEqual(snapshot(), (C.STATUS_DONE, True, False))
                self.assertTrue(done.is_file())
                # Workspace already active (agent archived again later): no restore needed.
                step()
                self.assertEqual(snapshot(), (C.STATUS_DONE, True, False))
                # Revived and agent archived again: workspace archived, agent untouched.
                fake["archived"] = True
                fake["rearchive"] = (True, None)
                step()
                self.assertEqual(snapshot(), (C.STATUS_DONE, False, True))
                # Exactly one rearchive succeeds once the agent is archived again.
                self.assertEqual(fake["events"], [("revive", "a")]
                                 + ([("rearchive", "a")] if kind == "watch" else [])
                                 + [("rearchive", "a")])
                # Fail closed: workspace untouched and a single warning, status stays done.
                fake["archived"] = False
                for code in ("WORKSPACE_RECOVERY_UNSUPPORTED", "WORKSPACE_ID_MISMATCH"):
                    save_session(cfg, "a", status=C.STATUS_DONE, paseo_workspace_archived=True)
                    fake["revive"] = (None, code)
                    log = step()
                    self.assertEqual(snapshot(), (C.STATUS_DONE, False, True))
                    self.assertIn(f"warning: workspace reconcile lỗi ({code})", log)
                    self.assertEqual(fake["events"][-1], ("revive", "a"))
                # A just-finished session is reconciled only on the next call, never twice in one.
                for run_step in (lambda: actions.ls(cfg, None), lambda: actions.watch_tick(cfg, "a")):
                    fake["events"].clear()
                    save_session(cfg, "a", status=C.STATUS_IDLE)
                    done.write_text("")
                    with mock.patch.object(actions.paseo, "finish", return_value=None), \
                            mock.patch.object(actions.paseo, "revive", side_effect=revive), \
                            mock.patch.object(actions.paseo, "rearchive", side_effect=rearchive), \
                            mock.patch.object(actions.paseo, "refresh", return_value="alive"), \
                            mock.patch.object(actions.paseo, "agent_archive_states", return_value={"agent-a": False}), \
                            mock.patch.object(actions, "_capture_paseo_thread"), \
                            mock.patch.object(actions, "_pin_rollout"), \
                            mock.patch.object(actions, "count_tokens", return_value=0), \
                            redirect_stdout(io.StringIO()):
                        run_step()
                        self.assertEqual(fake["events"], [("rearchive", "a")])
                        self.assertEqual(snapshot(), (C.STATUS_DONE, False, True))
                        run_step()
                    self.assertEqual(fake["events"], [("rearchive", "a"), ("revive", "a")])

    def test_ls_skips_missing_and_mismatched_done_agents(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cfg = cfg_for(Path(d))
            for name in ("valid", "missing", "mismatch"):
                save_session(cfg, name, status=C.STATUS_DONE, paseo_workspace_archived=True)
            response = {"targetKey": "home:/tmp/paseo", "agents": [
                {"agentId": "agent-valid", "workspaceId": "workspace-valid", "archivedAt": None},
                {"agentId": "agent-mismatch", "workspaceId": "other", "archivedAt": None}]}
            out = io.StringIO()
            with mock.patch.object(actions.paseo, "_call", return_value=response), \
                    mock.patch.object(actions.paseo, "revive", return_value=(True, None)) as revive, \
                    mock.patch.object(actions.paseo, "refresh", return_value="alive"), \
                    redirect_stdout(out):
                self.assertEqual(actions.paseo.agent_archive_states(state.load_all(cfg.state_dir)),
                                 {"agent-valid": False})
                self.assertEqual(actions.ls(cfg, None), 0)
            self.assertEqual([c.args[0].name for c in revive.call_args_list], ["valid"])
            self.assertEqual([state.load(cfg.state_dir, name).paseo_revived
                              for name in ("valid", "missing", "mismatch")], [True, False, False])
            self.assertNotIn("warning", out.getvalue())

    def test_ls_batches_done_agent_archive_states(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            cfg = cfg_for(Path(d))
            cfg.handoff_dir.mkdir()
            names = [f"archived-{i}" for i in range(27)] + ["unarchived", "revived"]
            for name in names:
                save_session(cfg, name, status=C.STATUS_DONE,
                             paseo_workspace_archived=name != "revived",
                             paseo_revived=name == "revived")
            entries = [{"agentId": f"agent-{name}", "workspaceId": f"workspace-{name}",
                        "archivedAt": None if name == "unarchived" else "2026-11-09T00:00:00Z"}
                       for name in names]
            response = {"agents": entries, "targetKey": "home:/tmp/paseo"}
            with mock.patch.object(actions.paseo, "_call", return_value=response) as call, \
                    mock.patch.object(actions.paseo, "revive", return_value=(True, None)) as revive, \
                    mock.patch.object(actions.paseo, "rearchive", return_value=(True, None)) as rearchive, \
                    mock.patch.object(actions.paseo, "refresh", return_value="alive"), \
                    redirect_stdout(io.StringIO()):
                actions.ls(cfg, None)
            self.assertEqual([c.args[0] for c in call.call_args_list], ["agent-archive-states"])
            self.assertEqual([c.args[0].name for c in revive.call_args_list], ["unarchived"])
            self.assertEqual([c.args[0].name for c in rearchive.call_args_list], ["revived"])
            before = [(st.name, st.status, st.paseo_workspace_archived, st.paseo_revived)
                      for st in state.load_all(cfg.state_dir)]
            for result in (actions.paseo.PaseoError("DAEMON_FAILED"),
                           {**response, "targetKey": "home:/other"},
                           {**response, "agents": [{**entries[0], "archivedAt": True}]}):
                out = io.StringIO()
                with mock.patch.object(actions.paseo, "_call",
                                       side_effect=result if isinstance(result, Exception) else None,
                                       return_value=result) as call, \
                        mock.patch.object(actions.paseo, "revive") as revive, \
                        mock.patch.object(actions.paseo, "rearchive") as rearchive, \
                        mock.patch.object(actions.paseo, "refresh", return_value="alive"), \
                        redirect_stdout(out):
                    actions.ls(cfg, None)
                self.assertEqual(call.call_count, 1)
                revive.assert_not_called()
                rearchive.assert_not_called()
                self.assertEqual(out.getvalue().count("warning: workspace reconcile lỗi"), 1)
                self.assertEqual([(st.name, st.status, st.paseo_workspace_archived, st.paseo_revived)
                                  for st in state.load_all(cfg.state_dir)], before)

    def test_revive_guards_never_call_bridge(self) -> None:
        with mock.patch.object(actions.paseo, "_call") as call:
            for st in (state.SessionState(
                    name="n", uuid="u", provider=C.PROVIDER_CODEX, dir="", screen="",
                    watch_screen="", max_tokens=1, started=0, status=C.STATUS_DONE,
                    handoff="", role="main", paseo_agent_id="a", paseo_workspace_id="w"),
                    state.SessionState(
                    name="n", uuid="u", provider=C.PROVIDER_CODEX, dir="", screen="",
                    watch_screen="", max_tokens=1, started=0, status=C.STATUS_DONE,
                    handoff="", paseo_agent_id="a")):
                self.assertEqual(actions.paseo.revive(st)[0], None)
                self.assertEqual(actions.paseo.rearchive(st)[0], None)
            call.assert_not_called()


if __name__ == "__main__":
    unittest.main()


def setUpModule():  # keep hh-store revision bumps out of the real ~/.hybrid-hands
    import os as _os, tempfile as _tempfile
    from unittest import mock as _mock
    global _STATE_TMP, _STATE_ENV
    _STATE_TMP = _tempfile.TemporaryDirectory()
    _STATE_ENV = _mock.patch.dict(_os.environ, {"HYBRID_HANDS_STATE_DIR": _STATE_TMP.name})
    _STATE_ENV.start()


def tearDownModule():
    _STATE_ENV.stop()
    _STATE_TMP.cleanup()
