"""Inspect or atomically change the repository parallel policy opt-in."""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

from account_label import PROVIDER_CLAUDE, account_choices, account_label, backend_account_label
from shared_config import ConfigResult, brain_account, load_config, parallel_backend
from .config import load_config as load_ext_config

POLICY_SECTION = "parallel_subagents"
POLICY_KEY = f"{POLICY_SECTION}.enabled"
NEW_SESSION = "mở phiên mới để hook nạp luật"
ACCOUNT_KEY = f"{POLICY_SECTION}.account"
CLAUDE_PREFIX = "claude-"
MISMATCH_WARNING = ("cảnh báo: backend subagent khác tài khoản brain; subagent native chỉ chạy khi "
                    "cùng tài khoản, dùng --account vN")
DEFAULT_FILE = Path(__file__).resolve().parents[1] / "shared_config.py"


def _read_repository(path: Path) -> dict:
    """Read raw bytes separately: the effective loader normalizes invalid sections."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path}: JSON không hợp lệ") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root phải là object")
    if POLICY_SECTION in data and not isinstance(data[POLICY_SECTION], dict):
        raise ValueError(f"{path}: {POLICY_SECTION} phải là object")
    return data


def _write_repository(path: Path, enabled: bool | None, backend: str | None = None,
                      account: str | None = None) -> None:
    data = _read_repository(path)
    section = data.setdefault(POLICY_SECTION, {})
    if enabled is not None:
        section["enabled"] = enabled
    if backend is not None:
        section["backend"] = backend
    if account is not None:
        section["account"] = account
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _status(result: ConfigResult) -> dict:
    source = result.sources[POLICY_KEY]
    backend = result.effective[POLICY_SECTION]["backend"]
    brain = result.effective[POLICY_SECTION].get(
        "account", backend[len(CLAUDE_PREFIX):] if backend.startswith(CLAUDE_PREFIX) else "")
    ext_cfg = load_ext_config(known_root=result.root, config_file=Path(result.paths["repo"]["path"]))
    options = ext_cfg.options(backend)
    return {
        "backend": backend, "model": options.get("model", ""),
        "effort": options.get("effort", options.get("variant", "")),
        "backend_source": result.sources[f"{POLICY_SECTION}.backend"],
        POLICY_SECTION: result.effective[POLICY_SECTION]["enabled"],
        "source": "default" if source == "plugin" else source,
        "file": str(DEFAULT_FILE) if source == "plugin" else result.paths[source]["path"],
        "brain_account": brain, "brain_account_source": result.sources.get(
            ACCOUNT_KEY, result.sources[f"{POLICY_SECTION}.backend"]),
        "account_mismatch": backend.startswith(CLAUDE_PREFIX) and backend != CLAUDE_PREFIX + brain,
        "brain_account_label": account_label(PROVIDER_CLAUDE, brain, ext_cfg),
        "backend_account_label": backend_account_label(backend, ext_cfg),
    }


ACCOUNTS_ACTION = "accounts"
PICK_PROMPT = "Chọn tài khoản [Enter = giữ hiện tại]: "
EXIT_BAD_CHOICE = 2


def _choices(result: ConfigResult) -> list[dict]:
    ext_cfg = load_ext_config(known_root=result.root, config_file=Path(result.paths["repo"]["path"]))
    backend = result.effective[POLICY_SECTION]["backend"]
    if backend.startswith(CLAUDE_PREFIX):
        backend = CLAUDE_PREFIX + result.effective[POLICY_SECTION].get("account", backend[len(CLAUDE_PREFIX):])
    return account_choices(ext_cfg, backend)


def _print_choices(rows: list[dict]) -> None:
    for row in rows:
        mark = "*" if row["selected"] else " "
        print(f"{mark} {row['index']}. {row['label']} ({row['backend']})")


def _is_tty() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def _ask(rows: list[dict]) -> dict | None:
    """Interactive pick; None keeps the current backend, ValueError on a bad entry."""
    raw = input(PICK_PROMPT).strip()
    if not raw:
        return None
    row = next((r for r in rows if raw.isdigit() and r["index"] == int(raw)), None)
    if row is None:
        raise ValueError("lựa chọn tài khoản không hợp lệ")
    return row


def _interactive_on(args: argparse.Namespace, result: ConfigResult) -> None:
    """`on` without flags: list accounts; ask only when stdin and stdout are TTYs."""
    rows = _choices(result)
    _print_choices(rows)
    if not _is_tty():
        return
    row = _ask(rows)
    if row is None:
        return
    if row["provider"] == PROVIDER_CLAUDE:
        args.account = row["slot"]
    else:
        args.backend = row["backend"]


def command(args: argparse.Namespace) -> int:
    result = load_config(Path(args.cwd) if args.cwd else None)
    if args.action == ACCOUNTS_ACTION:
        rows = _choices(result)
        if args.json:
            print(json.dumps(rows, ensure_ascii=False, indent=2))
        else:
            _print_choices(rows)
        return 0
    if args.action == "on" and args.account is None and args.backend is None and not args.json:
        try:
            _interactive_on(args, result)
        except ValueError as exc:
            print(f"lỗi: {exc}", file=sys.stderr)
            return EXIT_BAD_CHOICE
    written = None
    backend = (parallel_backend(args.backend, result.effective["ext_hand"])
               if args.backend is not None else None)
    account = brain_account(args.account, result.effective["ext_hand"]) if args.account is not None else None
    if account is not None:
        if backend is not None and backend != CLAUDE_PREFIX + account:
            raise ValueError("--backend phải trùng claude-<account> khi dùng --account")
        backend = CLAUDE_PREFIX + account
    if args.action is not None or backend is not None:
        written = Path(result.paths["repo"]["path"])
        _write_repository(written, args.action == "on" if args.action is not None else None, backend, account)
        # The only effective change is this repository leaf; retain loader provenance.
        if args.action is not None:
            result.effective[POLICY_SECTION]["enabled"] = args.action == "on"
            result.sources[POLICY_KEY] = "repo"
        if backend is not None:
            result.effective[POLICY_SECTION]["backend"] = backend
            result.sources[f"{POLICY_SECTION}.backend"] = "repo"
        if account is not None:
            result.effective[POLICY_SECTION]["account"] = account
            result.sources[ACCOUNT_KEY] = "repo"
    payload = _status(result)
    if args.json:
        if written is not None:
            payload.update(written=str(written), reminder=NEW_SESSION)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        state = "on" if payload[POLICY_SECTION] else "off"
        print(f"parallel_subagents: {state} (nguồn: {payload['source']}, file: {payload['file']})")
        print(f"backend: {payload['backend']} model={payload['model']} effort={payload['effort']}"
              f"{' account=' + payload['backend_account_label'] if payload['backend_account_label'] else ''} (nguồn: {payload['backend_source']})")
        print(f"brain: {payload['brain_account_label']} (nguồn: {payload['brain_account_source']})")
        if payload["account_mismatch"]:
            print(MISMATCH_WARNING)
        if written is not None:
            print(f"Đã ghi: {written}; {NEW_SESSION}")
    return 0
