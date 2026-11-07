"""Implementation of start / ls / stop / watch / handoff."""
from __future__ import annotations

import os
import shlex
import subprocess
import time
import uuid as uuidlib
from pathlib import Path

from . import budget
from . import commands as K
from . import constants as C
from . import external, screen, state, tokens
from .config import SideConfig
from .handoff import build_prompt, summary_block


def _running(cfg: SideConfig) -> list[state.SessionState]:
    alive = screen.screen_names()
    return [s for s in state.load_all(cfg.state_dir)
            if s.status in C.ACTIVE_STATUSES and s.screen in alive]


def _validate_start(a, full_prompt: str) -> int:
    if a.chrome and a.provider != C.PROVIDER_CLAUDE:
        print(f"side-session: --chrome chỉ dùng cho provider claude, không dùng được với "
              f"{a.provider}")
        return C.EXIT_USAGE
    if a.provider in C.EXTERNAL_PROVIDERS:
        if not a.worktree:
            print(f"side-session: provider {a.provider} là hand ngoài, chỉ làm trong worktree: "
                  "thêm --worktree")
            return C.EXIT_USAGE
        if C.PROMPT_RULES_MARKER not in full_prompt:
            print(f"side-session: prompt provider {a.provider} phải có mục "
                  f"'{C.PROMPT_RULES_MARKER}' (chép nguyên văn luật cấm)")
            return C.EXIT_USAGE
    return 0


def _refuse_budget(result: budget.BudgetResult) -> int:
    if result.stdout:
        print(result.stdout.rstrip())
    if result.error:
        print(f"side-session: {result.error}")
    print(f"side-session: budget_check_cmd từ chối (mã {result.code}); "
          "dùng --budget-exempt hoặc --force-budget nếu biết rõ")
    return C.EXIT_BUDGET


def _preflight(cfg: SideConfig, a) -> int | None:
    if cfg.budget_check_cmd and not (a.budget_exempt or a.force_budget):
        result = budget.check(cfg)
        if result.refused:
            return _refuse_budget(result)
    running = _running(cfg)
    if not a.dry_run and len(running) >= cfg.max_parallel:
        print(f"side-session: {len(running)} running >= max_parallel {cfg.max_parallel}: "
              + ", ".join(s.name for s in running))
        return C.EXIT_USAGE
    return None


def _launch(cfg: SideConfig, a, st: state.SessionState, cmds: list[list[str]], *,
            dry_run_kind: str, done_message: str, prompt_file: Path | None = None,
            prompt_text: str = "") -> int:
    if a.dry_run:
        print(f"# dry-run: {dry_run_kind} {st.name} uuid={st.uuid} provider={st.provider} "
              f"chrome={'yes' if st.chrome else 'no'} max_tokens={st.max_tokens} dir={st.dir}")
        if prompt_file is not None:
            print(f"# prompt: {prompt_file}")
        print(f"# state: {state.state_path(cfg.state_dir, st.name)}  handoff: {st.handoff}")
        for cmd in cmds:
            print(shlex.join(cmd))
        return 0
    if prompt_file is not None:
        cfg.state_dir.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(prompt_text, encoding="utf-8")
    for cmd in cmds[:-1]:
        if subprocess.run(cmd).returncode != 0:
            print(f"side-session: failed: {shlex.join(cmd)}")
            return 1
    state.save(cfg.state_dir, st)
    if subprocess.run(cmds[-1]).returncode != 0:
        print("side-session: warning: watchdog failed to start")
    print(done_message)
    return 0


def start(cfg: SideConfig, a) -> int:
    if a.resume:
        return resume(cfg, a)
    if a.prompt is None and a.prompt_file is None:
        print("side-session: start cần --prompt hoặc --prompt-file")
        return C.EXIT_USAGE
    name = a.name
    prompt_text = Path(a.prompt_file).read_text(encoding="utf-8") if a.prompt_file else a.prompt
    handoff = cfg.handoff_dir / f"{name}.md"
    if a.provider == C.PROVIDER_CODEX:
        full_prompt = K.build_codex_prompt(prompt_text, name, handoff)
    else:
        full_prompt = build_prompt(prompt_text, name, handoff, a.brain or "",
                                   external=a.provider in C.EXTERNAL_PROVIDERS)
    refused = _validate_start(a, full_prompt)
    if refused:
        return refused
    preflight = _preflight(cfg, a)
    if preflight is not None:
        return preflight
    if not a.dry_run and state.state_path(cfg.state_dir, name).is_file() \
            and state.load(cfg.state_dir, name).status in C.ACTIVE_STATUSES:
        print(f"side-session: {name} already running")
        return C.EXIT_USAGE
    sid = str(uuidlib.uuid4())
    workdir = str(cfg.worktree_root / name) if a.worktree else str(cfg.repo)
    max_tokens = K.max_tokens_for(cfg, a.max_tokens, a.hours)
    chrome = K.chrome_enabled(cfg, a.chrome)
    is_external = a.provider in C.EXTERNAL_PROVIDERS
    prompt_file = cfg.state_dir / f"{name}{C.PROMPT_FILE_SUFFIX}" if is_external else None
    # Sandbox writable roots must exist before any provider opens its screen.
    # Keep dry-run free of filesystem changes.
    if not a.dry_run:
        cfg.handoff_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    cmds = []
    if a.worktree:
        cmds.append(K.worktree_cmd(cfg, name, a.base or C.DEFAULT_BASE))
    cmds.append(K.session_cmd(cfg, a.provider, name, sid, workdir, full_prompt, chrome,
                              prompt_file, a.hours, model=a.model, effort=a.effort))
    cmds.append(K.watch_cmd(cfg, name))
    st = state.SessionState(
        name=name, uuid=sid, provider=a.provider, dir=workdir, screen=K.session_screen(name),
        watch_screen=K.watch_screen(name), max_tokens=max_tokens, started=started,
        status=C.STATUS_RUNNING, handoff=str(handoff), worktree=bool(a.worktree),
        parent_session=os.environ.get(C.PARENT_SESSION_ENV, ""), chrome=chrome,
        budget_exempt=bool(a.budget_exempt))
    return _launch(cfg, a, st, cmds, prompt_file=prompt_file, prompt_text=full_prompt,
                   dry_run_kind="session",
                   done_message=f"started {name} (screen -r {K.session_screen(name)}), "
                                f"uuid {sid}, cap {max_tokens}")


def _validate_resume(a) -> int | None:
    if a.provider != C.PROVIDER_CLAUDE:
        print(f"side-session: --resume chỉ dùng với provider {C.PROVIDER_CLAUDE}, "
              f"không dùng được với {a.provider}")
        return C.EXIT_USAGE
    if a.worktree:
        print("side-session: --resume không dùng với --worktree; "
              "giữ worktree của state cũ")
        return C.EXIT_USAGE
    if a.base is not None:
        print("side-session: --resume không dùng với --base")
        return C.EXIT_USAGE
    if a.prompt is not None:
        print("side-session: --resume dùng --prompt-file, không dùng --prompt")
        return C.EXIT_USAGE
    return None


def resume(cfg: SideConfig, a) -> int:
    refused = _validate_resume(a)
    if refused is not None:
        return refused
    path = state.state_path(cfg.state_dir, a.name)
    if not path.is_file():
        print(f"side-session: no session named {a.name!r} ({path})")
        return C.EXIT_USAGE
    old = state.load(cfg.state_dir, a.name)
    if old.provider != C.PROVIDER_CLAUDE:
        print(f"side-session: --resume chỉ dùng cho phiên {C.PROVIDER_CLAUDE}, "
              f"{a.name} là {old.provider}")
        return C.EXIT_USAGE
    screen_name = K.session_screen(a.name)
    if screen_name in screen.screen_ids():
        print(f"side-session: {screen_name} vẫn còn sống; dừng phiên rồi mới --resume")
        return C.EXIT_USAGE
    preflight = _preflight(cfg, a)
    if preflight is not None:
        return preflight
    if a.prompt_file:
        text = Path(a.prompt_file).read_text(encoding="utf-8")
        prompt = build_prompt(text, a.name, Path(old.handoff), a.brain or "")
    else:
        prompt = C.RESUME_PROMPT
    max_tokens = a.max_tokens if a.max_tokens is not None else old.max_tokens
    chrome = old.chrome if a.chrome is None else a.chrome
    st = state.SessionState(
        name=a.name, uuid=old.uuid, provider=C.PROVIDER_CLAUDE, dir=old.dir,
        screen=screen_name, watch_screen=K.watch_screen(a.name), max_tokens=max_tokens,
        started=time.time(), status=C.STATUS_RUNNING, handoff=old.handoff,
        worktree=old.worktree,
        parent_session=os.environ.get(C.PARENT_SESSION_ENV) or old.parent_session,
        chrome=chrome, budget_exempt=bool(a.budget_exempt), tokens_used=0)
    cmds = [
        K.session_cmd(cfg, C.PROVIDER_CLAUDE, a.name, old.uuid, old.dir, prompt, chrome,
                      resume=True),
        K.watch_cmd(cfg, a.name),
    ]
    return _launch(cfg, a, st, cmds, dry_run_kind="resume",
                   done_message=f"resumed {a.name} (screen -r {screen_name}), "
                                f"uuid {old.uuid}, cap {max_tokens}")


def count_tokens(cfg: SideConfig, st: state.SessionState) -> int:
    if st.provider == C.PROVIDER_CLAUDE and cfg.token_file:
        return tokens.token_file_tokens(cfg.token_file, st.uuid)
    if st.provider in C.EXTERNAL_PROVIDERS:
        run = external.run_for(st)
        return external.tokens_used(run) if run is not None else 0
    if st.provider == C.PROVIDER_CODEX:
        return tokens.codex_tokens(tokens.codex_rollout(cfg.codex_home, st.uuid, st.started))
    return tokens.claude_tokens(tokens.claude_transcript(st.dir, st.uuid))


def _age(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes // 60}h{minutes % 60:02d}m"


def _token_display(cfg: SideConfig, st: state.SessionState, used: int) -> tuple[int, int]:
    """Display Codex context separately from its cumulative accounting counter.

    Read the latest rollout even for a stopped session, whose persisted
    tokens_used remains cumulative usage for reports.
    """
    if st.provider == C.PROVIDER_CODEX:
        rollout = tokens.codex_rollout(cfg.codex_home, st.uuid, st.started)
        return tokens.codex_context_tokens(rollout), C.CODEX_AUTO_COMPACT_TOKEN_LIMIT
    return used, st.max_tokens


def _token_cell(cfg: SideConfig, st: state.SessionState, used: int) -> str:
    used, cap = _token_display(cfg, st, used)
    cell = f"{used}/{cap}"
    if st.provider != C.PROVIDER_CODEX and used >= cap:
        cell += C.OVER_CAP_SUFFIX
    return cell


def ls(cfg: SideConfig, _a) -> int:
    alive = screen.screen_names()
    rows = [("NAME", "PROVIDER", "CHROME", "STATUS", "LIVE", "TOKENS/CAP", "AGE", "HANDOFF")]
    for st in state.load_all(cfg.state_dir):
        done = st.status == C.STATUS_RUNNING and K.done_path(st.handoff).is_file()
        status = C.STATUS_DONE if done else st.status
        used = (count_tokens(cfg, st) if status == C.STATUS_RUNNING
                else st.tokens_used)
        token_cell = _token_cell(cfg, st, used)
        rows.append((st.name, st.provider, "yes" if st.chrome else "no", status,
                     "alive" if st.screen in alive else "dead", token_cell,
                     _age(time.time() - st.started),
                     "yes" if Path(st.handoff).is_file() else "no"))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
    return 0


def _quit(name: str) -> None:
    screen.quit(name)


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


def _finish_external(cfg: SideConfig, st: state.SessionState, run) -> bool:
    st.tokens_used = external.tokens_used(run)
    external.copy_report(run, Path(st.handoff))
    st.status = external.final_status(run)
    state.save(cfg.state_dir, st)
    print(f"{st.name}: {st.status} ({st.tokens_used}/{st.max_tokens} tokens)")
    return False


def _budget_daystop(cfg: SideConfig, st: state.SessionState) -> bool:
    if not cfg.budget_check_cmd:
        return False
    result = budget.check(cfg)
    if not budget.daystop(result, st.budget_exempt):
        return False
    stop_session(cfg, st, C.STATUS_DAYSTOP, stop_watch=False)
    print(f"{st.name}: daystop (budget_check_cmd mã {C.BUDGET_DAYSTOP_CODE})")
    return True


def _external_tick(cfg: SideConfig, st: state.SessionState, run) -> bool:
    if run is None:
        if not screen.is_alive(st.screen):
            st.status = C.STATUS_DEAD
            state.save(cfg.state_dir, st)
            return False
        state.save(cfg.state_dir, st)
        return True
    st.tokens_used = external.tokens_used(run)
    return _after_token_check(cfg, st)


def _after_token_check(cfg: SideConfig, st: state.SessionState) -> bool:
    # Codex owns context compaction; cumulative spending must never stop it.
    if st.provider == C.PROVIDER_CODEX:
        # The day-budget and done-marker checks still run before this branch.
        # Persist cumulative tokens_used, but display the current context only.
        if not screen.is_alive(st.screen):
            st.status = C.STATUS_DEAD
            state.save(cfg.state_dir, st)
            return False
        print(f"{st.name}: {_token_cell(cfg, st, st.tokens_used)} context tokens")
        state.save(cfg.state_dir, st)
        return True
    over_cap = st.tokens_used >= st.max_tokens
    if over_cap and cfg.enforce_token_cap:
        stop_session(cfg, st, C.STATUS_CAPPED, stop_watch=False)
        print(f"{st.name}: capped at {st.tokens_used}/{st.max_tokens}")
        return False
    if not screen.is_alive(st.screen):
        st.status = C.STATUS_DEAD
        state.save(cfg.state_dir, st)
        return False
    if over_cap:
        print(C.OVER_CAP_WARNING.format(name=st.name, used=st.tokens_used,
                                        cap=st.max_tokens))
    elif st.tokens_used >= C.WARN_RATIO * st.max_tokens:
        print(f"{st.name}: warning {st.tokens_used}/{st.max_tokens} (>= {C.WARN_RATIO:.0%})")
    state.save(cfg.state_dir, st)
    return True


def watch_tick(cfg: SideConfig, name: str) -> bool:
    """One watchdog step. Returns True while the watch loop should continue."""
    st = state.load(cfg.state_dir, name)
    if st.status != C.STATUS_RUNNING:
        return False
    if K.done_path(st.handoff).is_file():
        st.tokens_used = count_tokens(cfg, st)
        st.status = C.STATUS_DONE
        state.save(cfg.state_dir, st)
        print(f"{st.name}: done")
        return False
    run = external.run_for(st) if st.provider in C.EXTERNAL_PROVIDERS else None
    if run is not None and not run.running:
        return _finish_external(cfg, st, run)
    if _budget_daystop(cfg, st):
        return False
    if st.provider in C.EXTERNAL_PROVIDERS:
        return _external_tick(cfg, st, run)
    st.tokens_used = count_tokens(cfg, st)
    return _after_token_check(cfg, st)


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
