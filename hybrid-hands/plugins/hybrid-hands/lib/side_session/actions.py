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
from . import external, paseo, screen, state, tokens
from .config import SideConfig, claude_account
from .handoff import build_prompt, summary_block


def _running(cfg: SideConfig) -> list[state.SessionState]:
    """Active sessions; a Paseo agent confirmed dead/terminal no longer holds a slot."""
    sessions = state.load_all(cfg.state_dir)
    needs_screen = any(s.transport != C.TRANSPORT_PASEO
                       and s.status in C.ACTIVE_STATUSES for s in sessions)
    alive = screen.screen_names() if needs_screen else set()
    running = []
    for st in sessions:
        if st.role == "main" or st.status not in C.ACTIVE_STATUSES:
            continue
        if st.transport == C.TRANSPORT_PASEO:
            # Unknown (disconnect) still counts; only a confirmed dead agent drops out.
            if (st.provider == C.PROVIDER_CODEX and K.done_path(st.handoff).is_file()) \
                    or paseo.refresh(cfg, st) != "dead":
                running.append(st)
        elif st.screen in alive:
            running.append(st)
    return running


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


def _uses_day_guard(cfg: SideConfig, provider: str, account: str) -> bool:
    # Preserve the existing command guard; accounts without a cap must not inherit v1's.
    return provider != C.PROVIDER_CLAUDE or "max_day_pct" in claude_account(cfg, account)


def _preflight(cfg: SideConfig, a) -> int | None:
    if (cfg.budget_check_cmd
            and _uses_day_guard(cfg, getattr(a, "provider", C.PROVIDER_CLAUDE),
                                getattr(a, "account", None) or "v1")
            and not (a.budget_exempt or a.force_budget)):
        result = budget.check(cfg)
        if result.refused:
            return _refuse_budget(result)
    if getattr(a, "main", False):
        return None
    running = [] if a.dry_run else _running(cfg)
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
    launch_cmds = cmds if st.role == "main" else cmds[:-1]
    for cmd in launch_cmds:
        if subprocess.run(cmd).returncode != 0:
            print(f"side-session: failed: {shlex.join(cmd)}")
            return 1
    state.save(cfg.state_dir, st)
    if st.role != "main" and subprocess.run(cmds[-1]).returncode != 0:
        print("side-session: warning: watchdog failed to start")
    print(done_message)
    return 0


def start(cfg: SideConfig, a) -> int:
    is_main = getattr(a, "main", False)
    settings = cfg.main_session if is_main else vars(cfg)
    a.provider = a.provider or (C.PROVIDER_CLAUDE if a.resume else
                                settings.get("provider", C.PROVIDER_CODEX))
    if a.provider not in C.PROVIDERS:
        print("side-session: provider cấu hình không hợp lệ")
        return C.EXIT_USAGE
    if is_main and (a.provider not in (C.PROVIDER_CODEX, C.PROVIDER_CLAUDE)
                    or a.worktree or a.resume):
        print("side-session: --main chỉ dùng với provider codex/claude, "
              "không dùng --worktree/--resume")
        return C.EXIT_USAGE
    if a.resume:
        return resume(cfg, a)
    if not is_main and a.prompt is None and a.prompt_file is None:
        print("side-session: start cần --prompt hoặc --prompt-file")
        return C.EXIT_USAGE
    if a.provider not in C.EXTERNAL_PROVIDERS:
        a.model = a.model or settings.get(f"{a.provider}_model", C.CODEX_MODEL_DEFAULT
                                         if a.provider == C.PROVIDER_CODEX else C.CLAUDE_MODEL_DEFAULT)
        a.effort = a.effort or settings.get(f"{a.provider}_effort", C.CODEX_EFFORT_DEFAULT
                                           if a.provider == C.PROVIDER_CODEX else C.CLAUDE_EFFORT_DEFAULT)
    account = getattr(a, "account", None) or settings.get("claude_account", "v1")
    a.transport = settings.get("transport", C.TRANSPORT_PASEO)
    if a.provider == C.PROVIDER_CLAUDE and a.transport not in (C.TRANSPORT_PASEO, C.TRANSPORT_SCREEN):
        print("side-session: transport Claude phải là paseo hoặc screen")
        return C.EXIT_USAGE
    config_dir = ""
    if a.provider == C.PROVIDER_CLAUDE:
        try:
            config_dir = claude_account(cfg, account)["config_dir"]
            a.account = account
        except ValueError as exc:
            print(exc)
            return C.EXIT_USAGE
    elif getattr(a, "account", None):
        print("side-session: --account chỉ dùng với provider claude")
        return C.EXIT_USAGE
    name = a.name
    prompt_text = Path(a.prompt_file).read_text(encoding="utf-8") if a.prompt_file else a.prompt
    handoff = cfg.handoff_dir / f"{name}.md"
    if is_main and a.provider == C.PROVIDER_CODEX:
        full_prompt = K.build_main_codex_prompt(prompt_text or C.MAIN_DEFAULT_PROMPT, a.model, a.effort)
    elif a.provider == C.PROVIDER_CODEX:
        full_prompt = K.build_codex_prompt(prompt_text, name, handoff)
    else:
        try:
            full_prompt = build_prompt(
                prompt_text or C.MAIN_DEFAULT_PROMPT, name, handoff, a.brain or "",
                external=a.provider in C.EXTERNAL_PROVIDERS, account=account, main=is_main)
        except ValueError as exc:
            print(exc)
            return C.EXIT_USAGE
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
    paseo_plan = paseo.plan(cfg, a) if a.provider in (C.PROVIDER_CODEX, C.PROVIDER_CLAUDE) else None
    if paseo_plan is not None and paseo_plan.get("error"):
        return paseo_plan.get("exit_code", C.EXIT_USAGE)
    sid = str(uuidlib.uuid4())
    workdir = str(cfg.worktree_root / name) if a.worktree else str(cfg.repo)
    max_tokens = K.max_tokens_for(cfg, a.max_tokens, a.hours)
    chrome = K.chrome_enabled(cfg, a.chrome)
    is_external = a.provider in C.EXTERNAL_PROVIDERS
    prompt_file = cfg.state_dir / f"{name}{C.PROMPT_FILE_SUFFIX}" if is_external else None
    # Sandbox writable roots must exist before any provider opens its screen.
    # Keep dry-run free of filesystem changes.
    if not a.dry_run and not is_main:
        cfg.handoff_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    st = state.SessionState(
        name=name, uuid=sid, provider=a.provider, dir=workdir, screen=K.session_screen(name),
        watch_screen=K.watch_screen(name), max_tokens=max_tokens, started=started,
        status=C.STATUS_RUNNING, handoff=str(handoff), worktree=bool(a.worktree),
        parent_session=os.environ.get(C.PARENT_SESSION_ENV, ""), chrome=chrome,
        budget_exempt=bool(a.budget_exempt), role="main" if is_main else "",
        account=account, claude_config_dir=config_dir,
        model=a.model or (C.CLAUDE_MODEL_DEFAULT if a.provider == C.PROVIDER_CLAUDE else ""),
        effort=a.effort or (C.CLAUDE_EFFORT_DEFAULT if a.provider == C.PROVIDER_CLAUDE else ""))
    if is_main:
        st.handoff = ""
        st.watch_screen = ""
        st.parent_session = ""
    if paseo_plan is not None:
        return paseo.start_session(cfg, a, st, workdir, full_prompt, paseo_plan["target"])
    cmds = []
    if a.worktree:
        cmds.append(K.worktree_cmd(cfg, name, a.base or C.DEFAULT_BASE))
    cmds.append(K.session_cmd(cfg, a.provider, name, sid, workdir, full_prompt, chrome,
                              prompt_file, a.hours, model=a.model, effort=a.effort,
                              account=account, config_dir=config_dir))
    if not is_main:
        cmds.append(K.watch_cmd(cfg, name))
    return _launch(cfg, a, st, cmds, prompt_file=prompt_file, prompt_text=full_prompt,
                   dry_run_kind="session",
                   done_message=f"started {name} (screen -r {K.session_screen(name)}), "
                                f"uuid {sid}, " + (
                                    f"context {C.CODEX_AUTO_COMPACT_TOKEN_LIMIT} (tự nén)"
                                    if st.provider == C.PROVIDER_CODEX
                                    else f"cap {max_tokens}"))


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
    if old.transport == C.TRANSPORT_PASEO:
        print("side-session: --resume Paseo chưa hỗ trợ; mở lại đúng agent trong Paseo")
        return C.EXIT_USAGE
    if old.provider != C.PROVIDER_CLAUDE:
        print(f"side-session: --resume chỉ dùng cho phiên {C.PROVIDER_CLAUDE}, "
              f"{a.name} là {old.provider}")
        return C.EXIT_USAGE
    if getattr(a, "account", None) not in (None, old.account):
        print("side-session: --resume không đổi tài khoản; mở phiên mới để đổi account")
        return C.EXIT_USAGE
    a.account = old.account
    try:
        account_config = claude_account(cfg, old.account)
        config_dir = old.claude_config_dir or account_config["config_dir"]
    except ValueError as exc:
        print(exc)
        return C.EXIT_USAGE
    if old.role == "main":
        print("side-session: --resume chưa hỗ trợ main; dùng Claude resume trực tiếp")
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
        try:
            prompt = build_prompt(text, a.name, Path(old.handoff), a.brain or "", account=old.account)
        except ValueError as exc:
            print(exc)
            return C.EXIT_USAGE
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
        chrome=chrome, budget_exempt=bool(a.budget_exempt), tokens_used=0,
        account=old.account, claude_config_dir=config_dir,
        model=a.model or old.model, effort=a.effort or old.effort)
    cmds = [
        K.session_cmd(cfg, C.PROVIDER_CLAUDE, a.name, old.uuid, old.dir, prompt, chrome,
                      resume=True, model=st.model or None, effort=st.effort or None,
                      account=st.account, config_dir=config_dir),
        K.watch_cmd(cfg, a.name),
    ]
    return _launch(cfg, a, st, cmds, dry_run_kind="resume",
                   done_message=f"resumed {a.name} (screen -r {screen_name}), "
                                f"uuid {old.uuid}, cap {max_tokens}")


def _find_rollout(cfg: SideConfig, st: state.SessionState) -> Path | None:
    """Exact thread rollout, else cwd discovery for screen sessions only.

    A Paseo session without its thread id has unknown tokens: never fall back to a
    cwd match, because another hand can share the workdir in this CODEX_HOME.
    """
    if getattr(st, "codex_thread_id", ""):
        return tokens.codex_rollout_for_thread(cfg.codex_home, st.codex_thread_id, st.dir)
    if getattr(st, "transport", C.TRANSPORT_SCREEN) == C.TRANSPORT_PASEO:
        return None
    return tokens.codex_rollout(cfg.codex_home, st.dir, st.started)


def _rollout_path(cfg: SideConfig, st: state.SessionState) -> Path | None:
    """Pinned rollout only; never re-search once a path is in the state."""
    pinned = getattr(st, "codex_rollout", "")
    if pinned:
        return Path(pinned)
    return _find_rollout(cfg, st)


def _pin_rollout(cfg: SideConfig, st: state.SessionState) -> None:
    """Remember the first matching rollout so later counts use the same source."""
    if getattr(st, "codex_rollout", ""):
        return
    found = _find_rollout(cfg, st)
    if found is None:
        return
    # Store the real path: a symlinked CODEX_HOME must not re-pin a different path.
    found = found.resolve()
    st.codex_rollout = str(found)
    state.save(cfg.state_dir, st)


def _native_id(st: state.SessionState) -> str:
    """Claude native session id; legacy states/namespaces may lack the field."""
    return getattr(st, "native_session_id", "") or ""


def count_tokens(cfg: SideConfig, st: state.SessionState) -> int:
    native = _native_id(st)
    if (st.provider == C.PROVIDER_CLAUDE
            and getattr(st, "transport", C.TRANSPORT_SCREEN) == C.TRANSPORT_PASEO
            and not native):
        # The launcher UUID is not the daemon's native Claude session.
        return 0
    if st.provider == C.PROVIDER_CLAUDE and cfg.token_file:
        return tokens.token_file_tokens(cfg.token_file, native or st.uuid)
    if st.provider in C.EXTERNAL_PROVIDERS:
        run = external.run_for(st)
        return external.tokens_used(run) if run is not None else 0
    if st.provider == C.PROVIDER_CODEX:
        return tokens.codex_tokens(_rollout_path(cfg, st))
    config_dir = (getattr(st, "claude_config_dir", "")
                  or claude_account(cfg, getattr(st, "account", "v1"))["config_dir"])
    return tokens.claude_tokens(
        tokens.claude_transcript(st.dir, native or st.uuid, config_dir=config_dir))


def _age(seconds: float) -> str:
    minutes = int(seconds // 60)
    return f"{minutes // 60}h{minutes % 60:02d}m"


def _token_display(cfg: SideConfig, st: state.SessionState, used: int) -> tuple[int | None, int]:
    """Display Codex context separately from its cumulative accounting counter.

    Read the pinned rollout even for a stopped session, whose persisted
    tokens_used remains cumulative usage for reports. No pinned rollout or a
    pinned file that disappeared means unknown, shown as `?`.
    """
    if st.provider == C.PROVIDER_CODEX:
        rollout = _rollout_path(cfg, st)
        if rollout is None or not rollout.is_file():
            return None, C.CODEX_AUTO_COMPACT_TOKEN_LIMIT
        return tokens.codex_context_tokens(rollout), C.CODEX_AUTO_COMPACT_TOKEN_LIMIT
    return used, st.max_tokens


def _token_cell(cfg: SideConfig, st: state.SessionState, used: int) -> str:
    used, cap = _token_display(cfg, st, used)
    if used is None:
        return "?"
    cell = f"{used}/{cap}"
    if st.provider != C.PROVIDER_CODEX and used >= cap:
        cell += C.OVER_CAP_SUFFIX
    return cell


def _codex_idle(cfg: SideConfig, st: state.SessionState) -> None:
    if st.transport != C.TRANSPORT_PASEO:
        st.status = (C.STATUS_IDLE_NO_DONE if tokens.codex_turn_idle(_rollout_path(cfg, st))
                     else C.STATUS_RUNNING)
        state.save(cfg.state_dir, st)
    if st.status == C.STATUS_IDLE_NO_DONE:
        print(f"{st.name}: warning: turn kết thúc nhưng thiếu .done; giữ slot và watch")


def _close_codex_screen(st: state.SessionState) -> bool:
    """Confirm screen cleanup; an unavailable screen command requires a retry."""
    try:
        if _quit(st.screen):
            return True
        # A failed quit can also mean the runtime exited before the command.
        if not screen.is_alive(st.screen):
            return True
    except OSError as exc:
        print(f"{st.name}: warning: .done cleanup lỗi ({exc}); giữ active và thử lại")
        return False
    print(f"{st.name}: warning: .done cleanup screen còn sống; giữ active và thử lại")
    return False


def _finish_codex(cfg: SideConfig, st: state.SessionState) -> bool:
    """Persist done only after the owning transport has closed the runtime."""
    if st.transport == C.TRANSPORT_PASEO:
        _capture_paseo_thread(cfg, st)
    _pin_rollout(cfg, st)
    st.tokens_used = count_tokens(cfg, st)
    if st.transport == C.TRANSPORT_PASEO:
        failure = paseo.finish(st)
        if failure:
            print(f"{st.name}: warning: .done cleanup lỗi ({failure}); giữ active và thử lại")
            state.save(cfg.state_dir, st)
            return False
    elif st.screen and not _close_codex_screen(st):
        state.save(cfg.state_dir, st)
        return False
    st.status = C.STATUS_DONE
    if st.transport == C.TRANSPORT_PASEO:
        st.paseo_workspace_archived = True
    state.save(cfg.state_dir, st)
    return True


def _revive_done(cfg: SideConfig, st: state.SessionState) -> None:
    """Reopen the private workspace of a done agent the user unarchived.

    Failed cleanup keeps status done with a one-line warning; the next ls/watch
    retries. A revived session never runs _finish_codex, even with a stale .done.
    """
    revived, failure = paseo.revive(st)
    if failure:
        print(f"{st.name}: warning: workspace reconcile lỗi ({failure}); giữ state và thử lại")
        return
    if not revived:
        return
    st.paseo_workspace_archived = False
    st.paseo_revived = True
    state.save(cfg.state_dir, st)
    print(f"{st.name}: đã revive workspace riêng; bỏ qua .done cũ cho tới khi agent archive lại")


def _rearchive_revived(cfg: SideConfig, st: state.SessionState) -> None:
    """Hide the private workspace once a revived agent is archived again."""
    archived, failure = paseo.rearchive(st)
    if failure:
        print(f"{st.name}: warning: workspace reconcile lỗi ({failure}); giữ state và thử lại")
        return
    if not archived:
        return
    st.paseo_workspace_archived = True
    st.paseo_revived = False
    state.save(cfg.state_dir, st)
    print(f"{st.name}: đã archive lại workspace riêng sau khi agent archive")


def _reconcile_done(cfg: SideConfig, st: state.SessionState) -> None:
    """Done Codex/Paseo sessions follow the user's agent archive/revive, never .done."""
    if st.role == "main" or st.status != C.STATUS_DONE \
            or st.provider != C.PROVIDER_CODEX or st.transport != C.TRANSPORT_PASEO:
        return
    if st.paseo_revived:
        _rearchive_revived(cfg, st)
    elif st.paseo_workspace_archived:
        _revive_done(cfg, st)


def ls(cfg: SideConfig, _a) -> int:
    sessions = state.load_all(cfg.state_dir)
    candidates = [st for st in sessions if st.role != "main"
                  and st.status == C.STATUS_DONE and st.provider == C.PROVIDER_CODEX
                  and st.transport == C.TRANSPORT_PASEO
                  and (st.paseo_workspace_archived or st.paseo_revived)]
    candidate_names = {st.name for st in candidates}
    archive_states = {}
    if candidates:
        try:
            archive_states = paseo.agent_archive_states(candidates)
        except paseo.PaseoError as exc:
            print(f"side-session: warning: workspace reconcile lỗi ({exc.code}); giữ state và thử lại")
    needs_screen = any(s.transport != C.TRANSPORT_PASEO
                       and s.status in C.ACTIVE_STATUSES for s in sessions)
    alive = screen.screen_names() if needs_screen else set()
    rows = [("NAME", "PROVIDER", "CHROME", "STATUS", "LIVE", "TOKENS/CAP", "AGE", "HANDOFF")]
    for st in sessions:
        if st.provider == C.PROVIDER_CODEX:
            _pin_rollout(cfg, st)
        done = st.role != "main" and K.done_path(st.handoff).is_file()
        live = "alive" if st.screen in alive else "dead"
        # Finish and reconcile are exclusive per tick: a session just finished,
        # revived or rearchived here is never handled twice in the same listing.
        # A revived session never finishes again, even with a stale .done marker.
        if done and st.provider == C.PROVIDER_CODEX and not st.paseo_revived and (
                st.status in C.ACTIVE_STATUSES
                or (st.status == C.STATUS_DONE and st.transport == C.TRANSPORT_PASEO
                    and not st.paseo_workspace_archived)):
            _finish_codex(cfg, st)
        elif st.name in candidate_names and st.paseo_agent_id in archive_states:
            archived = archive_states[st.paseo_agent_id]
            if (st.paseo_revived and archived) or (not st.paseo_revived and not archived):
                _reconcile_done(cfg, st)
        if st.transport == C.TRANSPORT_PASEO:
            # Pending .done retains its slot even if archive partially closed the agent.
            live = ("unknown" if done and st.provider == C.PROVIDER_CODEX
                    and st.status in C.ACTIVE_STATUSES else paseo.refresh(cfg, st))
        if not done and st.provider == C.PROVIDER_CODEX and st.status in C.ACTIVE_STATUSES:
            _codex_idle(cfg, st)
        # A .done marker only advances a still-active state; it must not turn a
        # stopped/daystop session back into done in the listing.
        status = (C.STATUS_DONE if done and st.provider != C.PROVIDER_CODEX
                  and st.status in C.ACTIVE_STATUSES else st.status)
        used = (count_tokens(cfg, st) if status in C.ACTIVE_STATUSES
                else st.tokens_used)
        token_cell = _token_cell(cfg, st, used)
        rows.append((st.name, st.provider, "yes" if st.chrome else "no", status,
                     live, token_cell, _age(time.time() - st.started),
                     "yes" if Path(st.handoff).is_file() else "no"))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for r in rows:
        print("  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip())
    return 0


def _quit(name: str) -> bool:
    return screen.quit(name)


def stop_session(cfg: SideConfig, st: state.SessionState, status: str, *, stop_watch: bool) -> None:
    if st.screen:
        _quit(st.screen)
    st.status = status
    state.save(cfg.state_dir, st)
    if stop_watch and st.watch_screen:
        _quit(st.watch_screen)


def _stopped_message(st: state.SessionState) -> str:
    if st.provider == C.PROVIDER_CODEX:
        return (f"stopped {st.name} "
                f"(context {C.CODEX_AUTO_COMPACT_TOKEN_LIMIT} (tự nén))")
    return f"stopped {st.name} ({st.tokens_used}/{st.max_tokens} tokens)"


def stop(cfg: SideConfig, a) -> int:
    st = state.load(cfg.state_dir, a.name)
    st.tokens_used = count_tokens(cfg, st)
    if st.transport == C.TRANSPORT_PASEO:
        failure = paseo.interrupt(st)
        if failure:
            print(f"side-session: không dừng được Paseo agent ({failure}); "
                  "giữ nguyên state và watchdog")
            return 1
    stop_session(cfg, st, C.STATUS_STOPPED, stop_watch=True)
    print(_stopped_message(st))
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
    if not cfg.budget_check_cmd or not _uses_day_guard(cfg, st.provider, st.account):
        return False
    result = budget.check(cfg)
    if not budget.daystop(result, st.budget_exempt):
        return False
    if st.transport == C.TRANSPORT_PASEO:
        failure = paseo.interrupt(st)
        if failure:
            # The agent still runs: keep it active and let the watcher retry, so
            # max_parallel never releases a slot for a second writer.
            print(f"{st.name}: warning: không interrupt được Paseo agent ({failure}); "
                  "giữ active và thử lại vòng sau")
            state.save(cfg.state_dir, st)
            return False
        st.status = C.STATUS_DAYSTOP
        state.save(cfg.state_dir, st)
    else:
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
        _codex_idle(cfg, st)
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


def _capture_paseo_thread(cfg: SideConfig, st: state.SessionState) -> None:
    """Best-effort thread id for a done-first tick; a connection error is not fatal."""
    native_id = (_native_id(st) if st.provider == C.PROVIDER_CLAUDE
                 else st.codex_thread_id)
    if native_id or not st.paseo_agent_id:
        return
    try:
        result = paseo.status(st.paseo_agent_id, st.paseo_target)
    except paseo.PaseoError:
        return
    thread = str(result.get("threadId") or "")
    if thread:
        paseo.capture_native_id(st, thread)
        state.save(cfg.state_dir, st)


def _paseo_tick(cfg: SideConfig, st: state.SessionState) -> bool:
    """Keep watching through idle; connection failure is unknown, never `dead`."""
    if not st.paseo_agent_id:
        if st.status == C.STATUS_UNKNOWN:
            # A lost create reply requires explicit reconciliation via done/stop.
            return True
        st.status = C.STATUS_DEAD
        state.save(cfg.state_dir, st)
        print(f"{st.name}: dead (Paseo state thiếu agent id)")
        return False
    try:
        result = paseo.status(st.paseo_agent_id, st.paseo_target)
    except paseo.PaseoError as exc:
        if exc.code == C.PASEO_AGENT_NOT_FOUND:
            st.status = C.STATUS_DEAD
            state.save(cfg.state_dir, st)
            print(f"{st.name}: dead (Paseo không còn agent)")
            return False
        print(f"{st.name}: Paseo unknown ({exc.code}); giữ trạng thái và max_parallel")
        return True
    thread = str(result.get("threadId") or "")
    if thread and paseo.capture_native_id(st, thread):
        # The first tick had no thread yet: pin now that the exact id is known.
        _pin_rollout(cfg, st)
    raw = str(result.get("status") or "")
    if raw in C.PASEO_AGENT_ALIVE:
        st.status = C.STATUS_RUNNING
    elif raw == C.PASEO_AGENT_IDLE:
        st.status = (C.STATUS_IDLE_NO_DONE if st.provider == C.PROVIDER_CODEX
                     else C.STATUS_IDLE)
    elif raw in C.PASEO_AGENT_DEAD:
        st.status = C.STATUS_DEAD
        state.save(cfg.state_dir, st)
        print(f"{st.name}: dead (Paseo agent {raw})")
        return False
    else:
        print(f"{st.name}: Paseo unknown (status {raw or '?'})")
        return True
    st.tokens_used = count_tokens(cfg, st)
    state.save(cfg.state_dir, st)
    if st.provider == C.PROVIDER_CODEX:
        _codex_idle(cfg, st)
        print(f"{st.name}: {_token_cell(cfg, st, st.tokens_used)} context tokens")
    else:
        if st.tokens_used >= st.max_tokens and cfg.enforce_token_cap:
            failure = paseo.interrupt(st)
            if failure:
                print(f"{st.name}: Paseo interrupt lỗi ({failure}); giữ active")
                return True
            st.status = C.STATUS_CAPPED
            state.save(cfg.state_dir, st)
            print(f"{st.name}: capped at {st.tokens_used}/{st.max_tokens}")
            return False
        if st.tokens_used >= st.max_tokens:
            print(C.OVER_CAP_WARNING.format(name=st.name, used=st.tokens_used,
                                            cap=st.max_tokens))
        elif st.tokens_used >= C.WARN_RATIO * st.max_tokens:
            print(f"{st.name}: warning {st.tokens_used}/{st.max_tokens} (>= {C.WARN_RATIO:.0%})")
        print(f"{st.name}: {st.tokens_used}/{st.max_tokens} tokens")
    return True


def watch_tick(cfg: SideConfig, name: str) -> bool:
    """One watchdog step. Returns True while the watch loop should continue."""
    st = state.load(cfg.state_dir, name)
    if st.role == "main":
        return False
    # A done Codex/Paseo session follows the agent's archive state instead of .done,
    # one step per tick; a revived one is kept watched to see its next archive.
    if (st.status == C.STATUS_DONE and st.provider == C.PROVIDER_CODEX
            and st.transport == C.TRANSPORT_PASEO):
        if st.paseo_revived or st.paseo_workspace_archived:
            _reconcile_done(cfg, st)
            return st.paseo_revived
        return not _finish_codex(cfg, st)
    if st.status not in C.ACTIVE_STATUSES:
        return False
    done = st.role != "main" and K.done_path(st.handoff).is_file()
    if st.provider == C.PROVIDER_CODEX:
        # Pin before the done branch: a session that finishes on its first tick
        # must still remember the rollout that produced its token count. A Paseo
        # thread learned only at done time is fetched best-effort first.
        if done and st.transport == C.TRANSPORT_PASEO and not st.codex_thread_id:
            _capture_paseo_thread(cfg, st)
        _pin_rollout(cfg, st)
    if done:
        if st.provider == C.PROVIDER_CODEX:
            if not _finish_codex(cfg, st):
                return True
            print(f"{st.name}: done")
            return False
        if st.provider == C.PROVIDER_CLAUDE and st.transport == C.TRANSPORT_PASEO:
            _capture_paseo_thread(cfg, st)
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
    if st.transport == C.TRANSPORT_PASEO:
        return _paseo_tick(cfg, st)
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
