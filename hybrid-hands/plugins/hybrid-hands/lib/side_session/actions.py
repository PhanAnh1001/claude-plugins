"""Implementation of start / ls / stop / watch / handoff."""
from __future__ import annotations

import shlex
import subprocess
import time
import uuid as uuidlib
from pathlib import Path

from . import commands as K
from . import constants as C
from . import screen, state, tokens
from .config import SideConfig
from .handoff import build_prompt, summary_block


def _running(cfg: SideConfig) -> list[state.SessionState]:
    alive = screen.screen_names()
    return [s for s in state.load_all(cfg.state_dir)
            if s.status in C.ACTIVE_STATUSES and s.screen in alive]


def start(cfg: SideConfig, a) -> int:
    name = a.name
    prompt_text = Path(a.prompt_file).read_text(encoding="utf-8") if a.prompt_file else a.prompt
    running = _running(cfg)
    if not a.dry_run and len(running) >= cfg.max_parallel:
        print(f"side-session: {len(running)} running >= max_parallel {cfg.max_parallel}: "
              + ", ".join(s.name for s in running))
        return 2
    if not a.dry_run and state.state_path(cfg.state_dir, name).is_file() \
            and state.load(cfg.state_dir, name).status in C.ACTIVE_STATUSES:
        print(f"side-session: {name} already running")
        return 2
    sid = str(uuidlib.uuid4())
    workdir = str(cfg.worktree_root / name) if a.worktree else str(cfg.repo)
    handoff = cfg.handoff_dir / f"{name}.md"
    full_prompt = build_prompt(prompt_text, name, handoff, a.brain or "")
    max_tokens = K.max_tokens_for(cfg, a.max_tokens, a.hours)
    cmds = []
    if a.worktree:
        cmds.append(K.worktree_cmd(cfg, name, a.base))
    cmds.append(K.session_cmd(cfg, a.provider, name, sid, workdir, full_prompt))
    cmds.append(K.watch_cmd(cfg, name))
    if a.dry_run:
        print(f"# dry-run: session {name} uuid={sid} provider={a.provider} "
              f"max_tokens={max_tokens} dir={workdir}")
        print(f"# state: {state.state_path(cfg.state_dir, name)}  handoff: {handoff}")
        for cmd in cmds:
            print(shlex.join(cmd))
        return 0
    for cmd in cmds[:-1]:
        if subprocess.run(cmd).returncode != 0:
            print(f"side-session: failed: {shlex.join(cmd)}")
            return 1
    state.save(cfg.state_dir, state.SessionState(
        name=name, uuid=sid, provider=a.provider, dir=workdir, screen=K.session_screen(name),
        watch_screen=K.watch_screen(name), max_tokens=max_tokens, started=time.time(),
        status=C.STATUS_RUNNING, handoff=str(handoff), worktree=bool(a.worktree)))
    if subprocess.run(cmds[-1]).returncode != 0:
        print("side-session: warning: watchdog failed to start")
    print(f"started {name} (screen -r {K.session_screen(name)}), uuid {sid}, cap {max_tokens}")
    return 0


def count_tokens(cfg: SideConfig, st: state.SessionState) -> int:
    if st.provider == C.PROVIDER_CODEX:
        return tokens.codex_tokens(tokens.codex_rollout(cfg.codex_home, st.uuid, st.started))
    return tokens.claude_tokens(tokens.claude_transcript(st.dir, st.uuid))


def _age(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes // 60}h{minutes % 60:02d}m"


def ls(cfg: SideConfig, _a) -> int:
    alive = screen.screen_names()
    rows = [("NAME", "PROVIDER", "STATUS", "LIVE", "TOKENS/CAP", "AGE", "HANDOFF")]
    for st in state.load_all(cfg.state_dir):
        used = count_tokens(cfg, st) if st.status == C.STATUS_RUNNING else st.tokens_used
        rows.append((st.name, st.provider, st.status,
                     "alive" if st.screen in alive else "dead",
                     f"{used}/{st.max_tokens}", _age(time.time() - st.started),
                     "yes" if Path(st.handoff).is_file() else "no"))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
    return 0


def _quit(name: str) -> None:
    if screen.is_alive(name):
        screen.run(screen.quit_cmd(name))


def stop_session(cfg: SideConfig, st: state.SessionState, status: str, *, stop_watch: bool) -> None:
    _quit(st.screen)
    st.status = status
    state.save(cfg.state_dir, st)
    if stop_watch:
        _quit(st.watch_screen)


def stop(cfg: SideConfig, a) -> int:
    st = state.load(cfg.state_dir, a.name)
    st.tokens_used = count_tokens(cfg, st)
    stop_session(cfg, st, C.STATUS_STOPPED, stop_watch=True)
    print(f"stopped {st.name} ({st.tokens_used}/{st.max_tokens} tokens)")
    if st.worktree:
        print(f"worktree kept; remove with: git -C {shlex.quote(str(cfg.repo))} worktree remove "
              f"{shlex.quote(st.dir)} && git -C {shlex.quote(str(cfg.repo))} branch -D "
              f"{C.BRANCH_PREFIX}{st.name}")
    return 0


def watch_tick(cfg: SideConfig, name: str) -> bool:
    """One watchdog step. Returns True while the watch loop should continue."""
    st = state.load(cfg.state_dir, name)
    if st.status != C.STATUS_RUNNING:
        return False
    st.tokens_used = count_tokens(cfg, st)
    if st.tokens_used >= st.max_tokens:
        stop_session(cfg, st, C.STATUS_CAPPED, stop_watch=False)
        print(f"{name}: capped at {st.tokens_used}/{st.max_tokens}")
        return False
    if not screen.is_alive(st.screen):
        st.status = C.STATUS_DEAD
        state.save(cfg.state_dir, st)
        return False
    if st.tokens_used >= C.WARN_RATIO * st.max_tokens:
        print(f"{name}: warning {st.tokens_used}/{st.max_tokens} (>= {C.WARN_RATIO:.0%})")
    state.save(cfg.state_dir, st)
    return True


def watch(cfg: SideConfig, a) -> int:
    interval = a.interval if a.interval is not None else cfg.watch_interval_s
    # Exit condition is the state/screen (watch_tick returns False), not log text.
    while watch_tick(cfg, a.name) and not a.once:
        time.sleep(interval)
    return 0


def handoff(cfg: SideConfig, a) -> int:
    st_file = state.state_path(cfg.state_dir, a.name)
    path = Path(state.load(cfg.state_dir, a.name).handoff) if st_file.is_file() \
        else cfg.handoff_dir / f"{a.name}.md"
    block = summary_block(path)
    if block is None:
        print(f"side-session: no '{C.SUMMARY_HEADING}' block yet in {path}")
        return 1
    print(block)
    return 0
