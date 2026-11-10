"""hand-ext command line: setup, doctor, run, status, usage, report, measure."""
from __future__ import annotations

import argparse
from dataclasses import replace
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Optional

from shared_config import GlobalConfigError, load_config as load_shared

from . import go_live, go_usage, measure, quota_state, render, report
from .backends import BackendUnavailable, KNOWN_BACKENDS, get_backend
from .backends.base import Check
from .config import ExtConfig, load_config
from .native import native_selection
from .constants import (
    ALL_BACKENDS, AUTO_BACKEND, EXIT_ALL_UNAVAILABLE, EXIT_FAIL, EXIT_OK, EXIT_USAGE, GO_LIVE_MISSING, ISOLATIONS,
    SANDBOXES,
)
from .run_cmd import auto_preflight, backend_ready, cmd_run, last_run, with_sandbox


def _execution_key(value):
    from .execution_state import ExecutionKey
    parts = value.split(":")
    if (len(parts) != 3 or not all(parts) or not parts[2].isascii()
            or not parts[2].isdigit() or int(parts[2]) < 1
            or any(c.isspace() for c in parts[0] + parts[1])):
        raise argparse.ArgumentTypeError("key must be invocation:attempt:epoch (epoch >= 1)")
    return ExecutionKey(parts[0], parts[1], int(parts[2]))


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hand-ext",
        description="Chạy hand ngoài qua CLI đăng nhập gói subscription (không API).")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, text in (("setup", "ghi cấu hình CLI, in lệnh đăng nhập gói"),
                       ("doctor", "kiểm cài đặt, đăng nhập gói, cấu hình")):
        s = sub.add_parser(name, help=text)
        s.add_argument("--backend", default=ALL_BACKENDS)
        s.add_argument("--cwd")
    inspect = sub.add_parser("config", help="in cấu hình hiệu lực và nguồn (chỉ đọc)")
    inspect.add_argument("--json", action="store_true")
    inspect.add_argument("--cwd")
    parallel = sub.add_parser("parallel-subagents", aliases=["parallel"],
                              help="xem hoặc bật/tắt policy parallel của repo (parallel: alias cũ)")
    parallel.add_argument("action", nargs="?", choices=("on", "off"))
    parallel.add_argument("--backend")
    parallel.add_argument("--cwd")
    parallel.add_argument("--json", action="store_true")
    provider = sub.add_parser("provider", help="cấu hình ACP provider bằng schema Paseo chính thức")
    provider_sub = provider.add_subparsers(dest="provider_cmd", required=True)
    provider_setup = provider_sub.add_parser("setup")
    provider_setup.add_argument("--home", required=True)
    provider_setup.add_argument("--package-root")
    provider_setup.add_argument("--cwd")
    provider_mode = provider_setup.add_mutually_exclusive_group()
    provider_mode.add_argument("--dry-run", action="store_true")
    provider_mode.add_argument("--apply", action="store_true")
    provider_status = provider_sub.add_parser("status")
    provider_status.add_argument("--cwd")
    managed = sub.add_parser("managed", help="quản lý exact managed execution")
    managed_sub = managed.add_subparsers(dest="managed_cmd", required=True)
    for action in ("ls", "review-approve", "archive", "followup", "recover", "names"):
        command = managed_sub.add_parser(action)
        command.add_argument("--cwd", required=True)
        if action not in ("ls", "names"):
            command.add_argument("--key", required=True, type=_execution_key,
                                 help="invocation:attempt:epoch (epoch >= 1)")
        if action == "names":
            command.add_argument("--apply", action="store_true")
        if action == "recover":
            command.add_argument("--apply", action="store_true")
            command.add_argument("--legacy-attest", action="store_true",
                                 help="operator attests pre-0.35.5 origin (not recorded by old schema)")
            command.add_argument("--reason", help="operator reason attesting pre-0.35.5 origin")
            command.add_argument("--owner-os-start")
            command.add_argument("--root-os-start")
        if action == "followup":
            command.add_argument("--brief", required=True, help="fresh self-contained brief file")
    pick = sub.add_parser("pick", help="chọn backend auto (chỉ đọc)")
    pick.add_argument("--json", action="store_true")
    pick.add_argument("--backend")
    pick.add_argument("--cwd")
    r = sub.add_parser("run", help="chạy một brief")
    r.add_argument("--brief", required=True, help="file brief hoặc - cho stdin")
    r.add_argument("--backend", default=AUTO_BACKEND)
    r.add_argument("--mode", choices=("shell", "auto", "paseo-required"))
    for flag in ("--label", "--cwd", "--model", "--effort"):
        r.add_argument(flag)
    r.add_argument("--timeout-min", type=float)
    r.add_argument("--max-tokens", type=int)
    r.add_argument("--sandbox", choices=SANDBOXES)
    r.add_argument("--isolation", choices=ISOLATIONS,
                   help="chạy trong git worktree sạch (mặc định) hoặc trực tiếp (none)")
    r.add_argument("--no-apply", action="store_true",
                   help="chỉ lưu changes.patch, không áp về thư mục gốc")
    r.add_argument("--keep-worktree", action="store_true",
                   help="giữ worktree sau khi chạy để kiểm tra")
    r.add_argument("--browser", action="store_true",
                   help="bật Playwright MCP cô lập cho backend dsh (chỉ trang công khai)")
    sub.add_parser("status", help="sẵn sàng, hạn mức, lượt gần nhất").add_argument("--cwd")
    use = sub.add_parser("usage", help="mức đã dùng gói OpenCode Go (5h/7d/30d)")
    use.add_argument("--json", action="store_true", help="in JSON của bản tóm tắt")
    use.add_argument("--cwd")
    rep = sub.add_parser("report", help="tổng lượt và token")
    for flag in ("--since", "--backend", "--label", "--cwd"):
        rep.add_argument(flag)
    mea = sub.add_parser("measure", help="đo dòng test/code/docs và thời gian chạy test")
    mea.add_argument("--runs", action="append", required=True, metavar="DIR",
                     help="thư mục runs_dir chứa các thư mục lượt; lặp lại được")
    mea.add_argument("--backend", help="chỉ lấy lượt của backend này")
    mea.add_argument("--since", help="chỉ lấy lượt bắt đầu từ ngày YYYY-MM-DD")
    return p


def _cfg(args: argparse.Namespace) -> ExtConfig:
    cwd = getattr(args, "cwd", None)
    return load_config(Path(cwd) if cwd else None)


def _names(cfg: ExtConfig, choice: str) -> List[str]:
    if choice == ALL_BACKENDS:
        return list(dict.fromkeys(cfg.order + list(cfg.backends) + list(KNOWN_BACKENDS)))
    return [choice]


def cmd_pick(cfg: ExtConfig, args: argparse.Namespace) -> int:
    result = {"backend": None, "model": None, "effort": None, "account": None, "skipped": [],
              "native": False, "native_reason": "no backend available"}
    choice = getattr(args, "backend", None)
    if choice is not None:
        from shared_config import canonical_backend
        cfg = replace(cfg, order=[canonical_backend(choice)])
    for backend, name, reason in auto_preflight(cfg):
        if backend is None:
            result["skipped"].append({"backend": name, "reason": reason})
            continue
        options = cfg.options(name)
        account = {"codex": "gpt", "claude-main": "claude-v1", "claude": "claude-v2"}.get(name, name)
        result.update(backend=name, model=options.get("model", ""),
                      effort=options.get("effort", options.get("variant", "")), account=account)
        native, reason = native_selection(cfg, name)
        result.update(native=native, native_reason=reason)
        break
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for skipped in result["skipped"]:
            print(f"bỏ qua {skipped['backend']}: {skipped['reason']}")
        print(f"{result['backend']} model={result['model']} effort={result['effort']} account={result['account']}"
              if result["backend"] else "Không backend nào dùng được.")
    return EXIT_OK if result["backend"] else EXIT_ALL_UNAVAILABLE


def cmd_setup(cfg: ExtConfig, args: argparse.Namespace) -> int:
    for name in _names(cfg, args.backend):
        try:
            lines = get_backend(name).setup(with_sandbox(cfg, name))
        except BackendUnavailable as exc:
            lines = [str(exc)]
        print(f"[{name}]\n" + "\n".join(lines))
    return EXIT_OK


def cmd_doctor(cfg: ExtConfig, args: argparse.Namespace) -> int:
    rows, ready = [], False
    for name in _names(cfg, args.backend):
        try:
            checks = get_backend(name).doctor(with_sandbox(cfg, name))
        except BackendUnavailable as exc:
            checks = [Check("module", False, str(exc))]
        ready = ready or all(c.ok or not c.required for c in checks)
        rows.append((name, checks))
    print(render.doctor_table(rows))
    return EXIT_OK if ready else EXIT_FAIL


def cmd_status(cfg: ExtConfig, args: argparse.Namespace) -> int:
    print("| backend | sẵn sàng | hết hạn mức tới | lượt gần nhất |\n|---|---|---|---|")
    for name in cfg.order:
        try:
            ok = render.mark(backend_ready(get_backend(name), cfg))
        except BackendUnavailable:
            ok = "chưa có"
        until = quota_state.exhausted_until(cfg.quota_state, name)
        last = last_run(cfg, name)
        shown = f"{last['started']} {last['status']}" if last else "-"
        print(f"| {name} | {ok} | {quota_state.iso(until) if until else '-'} | {shown} |")
    summary = go_usage.read_summary(cfg.go_usage_summary)
    now = time.time()
    live = go_live.read_live(go_live.cache_path(go_live.claude_home(os.environ)), now)
    if live is not None:
        print()
        print(go_live.live_line(live, now))
    if summary and summary.get("models"):
        print()
        print(go_usage.format_text(summary))
    return EXIT_OK


def cmd_usage(cfg: ExtConfig, args: argparse.Namespace) -> int:
    live = go_live.refresh_and_read(cfg.go_usage_live, os.environ)
    now = time.time()
    summary = go_usage.refresh(cfg)
    if args.json:
        print(json.dumps({**summary, "live": live}, ensure_ascii=False, indent=2))
    else:
        print(go_live.live_line(live, now) if live is not None else GO_LIVE_MISSING)
        print()
        print(go_usage.format_text(summary))
    return EXIT_OK


def cmd_report(cfg: ExtConfig, args: argparse.Namespace) -> int:
    scope = report.collect(cfg)
    entries = scope.entries
    if args.since:
        entries = [e for e in entries if str(e.get("started", ""))[:10] >= args.since]
    for key in ("backend", "label"):
        if getattr(args, key):
            entries = [e for e in entries if e.get(key) == getattr(args, key)]
    print(report.format_scope(scope))
    print()
    print(render.ledger_report(entries))
    return EXIT_OK


def cmd_measure(cfg: ExtConfig, args: argparse.Namespace) -> int:
    runs = measure.collect_runs([Path(item) for item in args.runs],
                                backend=args.backend, since=args.since)
    print(measure.format_report(runs))
    return EXIT_OK


def cmd_provider(cfg: ExtConfig, args: argparse.Namespace) -> int:
    from .paseo_provider import setup_provider, status_provider, ProviderError
    from .paseo_controller import transport_from_config, PaseoUnavailable
    from .paseo_transport import TransportError
    try:
        if args.provider_cmd == 'setup':
            result = setup_provider(Path(args.home), apply=args.apply,
                package_root=args.package_root or cfg.paseo.get('package_root'))
        else:
            result = status_provider(transport_from_config(cfg, None))
    except (ProviderError, PaseoUnavailable, TransportError) as exc:
        result = {'ok': False, 'code': str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_OK if result.get('ok') else EXIT_FAIL


def _managed_summary(record):
    key = record.key
    return dict(key=f"{key.invocation_id}:{key.attempt_id}:{key.epoch}",
                state=record.state, backend=record.invocation.backend,
                model=record.invocation.model, effort=record.invocation.effort,
                parent_session=record.invocation.parent_session,
                naming_warning=("NAME_UNRESOLVED" if (record.receipt or {}).get("naming", {}).get("warning") else None),
                agent_id=record.attempt.agent_id, workspace_id=record.attempt.workspace_id,
                review_approved=(record.artifacts.get("review") or {}).get("approved") is True)


def cmd_managed(cfg: ExtConfig, args: argparse.Namespace) -> int:
    from .execution_state import ExecutionStore, StateConflict, StateCorrupt
    from .execution_admission import AdmissionDenied, AdmissionFull
    from .paseo_controller import (PaseoController, transport_from_config,
        PaseoUnavailable, ExecutionUnresolved, _completion_service)
    from .paseo_transport import TransportError
    root = Path(cfg.paseo.get("state_root") or cfg.machine_state_dir / "executions")
    source = Path(args.cwd).resolve()
    try:
        if not root.exists():
            if args.managed_cmd not in ("ls", "names"):
                raise StateConflict("execution not found")
            result = {"ok": True, "executions": []}
        else:
            store = ExecutionStore(root)
            if args.managed_cmd == "names":
                from .paseo_names import latest_records, names_request
                transport = transport_from_config(cfg, store)
                result = {"ok": True, "applied": args.apply, "names": [
                    names_request(transport, row.key, apply=args.apply)
                    for row in latest_records(store, source)]}
            elif args.managed_cmd == "ls":
                with store.locked():
                    rows = [store._read(p) for p in sorted(store.root.glob("*.json"))]
                from .paseo_names import latest_records, retry_names
                naming_failed = False
                if cfg.paseo.get('package_root') and cfg.paseo.get('target'):
                    try:
                        transport = transport_from_config(cfg, store)
                        for row in latest_records(store, source):
                            retry_names(transport, row.key)
                    except Exception:
                        naming_failed = True
                        print('warning: NAME_UNRESOLVED', file=sys.stderr)
                    rows = [store.get(row.key) for row in rows]
                summaries = [_managed_summary(r) for r in rows
                             if Path(r.invocation.source_cwd).resolve() == source]
                if naming_failed:
                    for summary in summaries:
                        summary["naming_warning"] = "NAME_UNRESOLVED"
                result = {"ok": True, "executions": summaries}
            else:
                record = store.get(args.key)
                if Path(record.invocation.source_cwd).resolve() != source:
                    raise StateConflict("execution belongs to another repo")
                if args.managed_cmd == "recover":
                    from .paseo_recovery import recover
                    record = recover(store, args.key, source, cfg.paseo.get('package_root'),
                                     apply=args.apply, target=cfg.paseo.get('target'),
                                     legacy_attest=args.legacy_attest, reason=args.reason,
                                     owner_os_start=args.owner_os_start, root_os_start=args.root_os_start)
                    print(json.dumps({"ok": True, "applied": args.apply,
                                      "execution": _managed_summary(record)}))
                    return EXIT_OK
                brief = None
                if args.managed_cmd == "followup":
                    brief = Path(args.brief).read_text()
                    if not brief.strip():
                        raise ValueError("fresh self-contained brief required")
                transport = (None if args.managed_cmd == "review-approve"
                             else transport_from_config(cfg, store))
                controller = PaseoController(cfg, store, transport)
                if args.managed_cmd == "review-approve":
                    record = controller.approve_review(args.key)
                elif args.managed_cmd == "archive":
                    record = controller.archive(args.key)
                else:
                    controller.completion = _completion_service(store, controller.supervisor,
                                                                controller.admission)
                    record = controller.followup(args.key, brief)
                result = {"ok": True, "execution": _managed_summary(record)}
    except (StateConflict, StateCorrupt, FileNotFoundError, AdmissionDenied,
            AdmissionFull, PaseoUnavailable, ExecutionUnresolved, TransportError) as exc:
        # Never echo arbitrary transport/backend text, briefs, or persisted options.
        result = {"ok": False, "code": type(exc).__name__}
        from .legacy_attestation import LegacyOwnerAlive
        if isinstance(exc, LegacyOwnerAlive):
            result["hint"] = "close exact child through public Paseo"
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 8 if isinstance(exc, AdmissionFull) else EXIT_FAIL
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return EXIT_OK


COMMANDS = {"managed": cmd_managed, "provider": cmd_provider, "pick": cmd_pick, "setup": cmd_setup, "doctor": cmd_doctor, "run": cmd_run,
            "status": cmd_status, "usage": cmd_usage, "report": cmd_report,
            "measure": cmd_measure}


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.cmd in ("parallel-subagents", "parallel"):
            from .parallel_cmd import command
            return command(args)
        if args.cmd == "config":
            result = load_shared(Path(args.cwd) if args.cwd else None)
            _cfg(args)
            payload = {"effective": result.effective, "sources": result.sources, "paths": result.paths}
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return EXIT_OK
        return COMMANDS[args.cmd](_cfg(args), args)
    except BackendUnavailable as exc:
        print(f"hand-ext: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except (OSError, ValueError, GlobalConfigError) as exc:
        print(f"hand-ext: {exc}", file=sys.stderr)
        return EXIT_USAGE
