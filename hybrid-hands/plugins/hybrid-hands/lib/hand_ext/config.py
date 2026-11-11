"""Load the ext_hand section of <git toplevel>/.claude/hybrid-hands.json over DEFAULTS."""
from __future__ import annotations

import copy
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .parallel import validate_limit
from .constants import (
    CONFIG_SECTION, DEFAULTS, WORKTREE_GC_FINISHED, WORKTREE_GC_MODES, GO_USAGE_DEFAULT_DIR, GO_USAGE_DEFAULT_MONTHLY_LIMIT_USD,
    GO_USAGE_LEDGER_NAME, GO_USAGE_LIVE_DEFAULT, GO_USAGE_LIVE_KEY, GO_USAGE_SECTION,
    GO_USAGE_STATE_DIR_ENV, ISOLATIONS, PLUGIN_PLACEHOLDER, PROJECT_CONFIG_RELPATH,
    WORKTREES_DIRNAME, MAX_PARALLEL,
)

PLUGIN_DIR = Path(__file__).resolve().parents[2]
# Display-only account keys (account_label); never passed to backend options.
LABEL_KEYS = ("plan", "name")


@dataclass
class ExtConfig:
    root: Path
    order: List[str]
    timeout_min: float
    max_tokens: Optional[int]
    sandbox: str
    ledger: Path
    quota_state: Path
    runs_dir: Path
    worktree_root: Path
    isolation: str
    isolation_explicit: bool
    backends: Dict[str, Dict[str, Any]]
    go_usage_ledger: Path
    go_usage_summary: Path
    go_monthly_limit_usd: float
    go_usage_live: bool
    machine_state_dir: Path
    max_parallel: int = MAX_PARALLEL

    claude_accounts: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: copy.deepcopy(DEFAULTS["claude_accounts"]))

    mode: str = "shell"
    paseo: Dict[str, Any] = field(default_factory=dict)

    native: Dict[str, str] = field(default_factory=lambda: copy.deepcopy(DEFAULTS["native"]))

    gpt_accounts: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: copy.deepcopy(DEFAULTS["gpt_accounts"]))
    account_label_format: str = DEFAULTS["account_label_format"]

    disk_guard: Dict[str, Any] = field(default_factory=dict)
    ignore_disk_guard: bool = False
    worktree_gc_auto: str = WORKTREE_GC_FINISHED

    def options(self, name: str) -> Dict[str, Any]:
        account = {"claude-main": "v1", "claude": "v2"}.get(name)
        if name.startswith("claude-v"):
            account = name[len("claude-"):]
        if account is not None:
            if account not in self.claude_accounts:
                raise ValueError(f"tài khoản Claude chưa cấu hình: {account}")
            canonical = f"claude-{account}"
            if canonical in self.backends:
                return dict(self.backends[canonical])
            # Compatibility for callers constructing ExtConfig themselves.
            return {"model": "claude-opus-5-5", "effort": "low", "max_turns": 80,
                    **self.claude_accounts[account], **self.backends.get(name, {})}
        return dict(self.backends.get(name, {}))


def _worktree_gc_auto(raw: object) -> str:
    """Validate ext_hand.worktree_gc.auto (finished|off)."""
    if not isinstance(raw, dict):
        raise ValueError(f"{CONFIG_SECTION}.worktree_gc phải là object")
    mode = raw.get("auto", WORKTREE_GC_FINISHED)
    if mode not in WORKTREE_GC_MODES:
        raise ValueError(f"{CONFIG_SECTION}.worktree_gc.auto phải là một trong {WORKTREE_GC_MODES}")
    return mode


def git_toplevel(cwd: Path) -> Path:
    try:
        out = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return cwd.resolve()
    return Path(out.stdout.strip())


def main_repo_root(root: Path) -> Optional[Path]:
    """Main working tree of a linked worktree: parent of the absolute git common dir."""
    try:
        out = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute",
                              "--git-common-dir"], capture_output=True, text=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return Path(out.stdout.strip()).parent


def _config_path(root: Path) -> Optional[Path]:
    """Own config first; a worktree without one shares its main repo's config."""
    own = root / PROJECT_CONFIG_RELPATH
    if own.is_file():
        return own
    main = main_repo_root(root)
    if main is not None:
        path = main / PROJECT_CONFIG_RELPATH
        if path.is_file():
            return path
    return None


def _read_section(root: Path, config_file: Optional[Path] = None) -> Dict[str, Any]:
    from shared_config import load_config as load_shared
    return load_shared(known_root=root, config_file=config_file).effective[CONFIG_SECTION]


def _resolve(root: Path, value: str) -> Path:
    path = Path(os.path.expanduser(value))
    return path if path.is_absolute() else root / path


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return value.replace(PLUGIN_PLACEHOLDER, str(PLUGIN_DIR))
    return value


def merge_backends(base: Dict[str, Dict[str, Any]],
                   over: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    merged = copy.deepcopy(base)
    for name, opts in over.items():
        if not isinstance(opts, dict):
            raise ValueError(f"backends.{name} phải là object")
        merged.setdefault(name, {}).update(opts)
    return {n: {k: _expand(v) for k, v in o.items()} for n, o in merged.items()}


def _state_dir() -> Path:
    raw = os.environ.get(GO_USAGE_STATE_DIR_ENV) or GO_USAGE_DEFAULT_DIR
    return Path(os.path.expanduser(raw))


def _go_usage(root: Path, section: Dict[str, Any]) -> tuple[Path, Path, float, bool]:
    """Ledger and summary beside each other; `HYBRID_HANDS_STATE_DIR` only sets the default."""
    configured = section.get("ledger")
    ledger = (_resolve(root, str(configured)) if configured
              else _state_dir() / GO_USAGE_LEDGER_NAME)
    summary = ledger.with_name(ledger.stem + "_summary.json")
    limit = section.get("monthly_limit_usd", GO_USAGE_DEFAULT_MONTHLY_LIMIT_USD)
    try:
        limit_usd = float(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("go_usage.monthly_limit_usd phải là số") from exc
    if limit_usd <= 0:
        raise ValueError("go_usage.monthly_limit_usd phải lớn hơn 0")
    live = section.get(GO_USAGE_LIVE_KEY, GO_USAGE_LIVE_DEFAULT)
    if not isinstance(live, bool):
        raise ValueError(f"go_usage.{GO_USAGE_LIVE_KEY} phải là true hoặc false")
    return ledger, summary, limit_usd, live


def load_config(cwd: Optional[Path] = None, *, known_root: Optional[Path] = None,
                config_file: Optional[Path] = None) -> ExtConfig:
    """Reuse caller-resolved roots/config paths within a snapshot, without caching globally."""
    root = known_root if known_root is not None else git_toplevel(Path(cwd or Path.cwd()))
    merged = copy.deepcopy(DEFAULTS)
    from shared_config import load_config as load_shared
    result = load_shared(known_root=root, config_file=config_file)
    section = copy.deepcopy(result.effective[CONFIG_SECTION])
    isolation_explicit = result.sources.get("ext_hand.isolation") != "plugin"
    worktree_root_raw = (section.get("worktree_root")
                         if result.sources.get("ext_hand.worktree_root") in ("global", "repo") else None)
    go_section = section.pop(GO_USAGE_SECTION, {}) or {}
    if not isinstance(go_section, dict):
        raise ValueError(f"{CONFIG_SECTION}.{GO_USAGE_SECTION} phải là object")
    effective_backends = section.pop("backends", {})
    overrides = {name: {key: value for key, value in opts.items()
                        if result.sources.get(f"ext_hand.backends.{name}.{key}") != "plugin"}
                 for name, opts in effective_backends.items()}
    backends = merge_backends(effective_backends, {})
    effective_accounts = section.pop("claude_accounts", {})
    account_overrides = {name: {key: value for key, value in opts.items()
                               if result.sources.get(f"ext_hand.claude_accounts.{name}.{key}") != "plugin"}
                         for name, opts in effective_accounts.items()}
    if not isinstance(account_overrides, dict):
        raise ValueError("claude_accounts phải là object")
    accounts = copy.deepcopy(DEFAULTS["claude_accounts"])
    for account, options in account_overrides.items():
        if not re.fullmatch(r"v[1-9][0-9]*", account) or not isinstance(options, dict):
            raise ValueError("claude_accounts cần tài khoản v<N> và options object")
        accounts.setdefault(account, {}).update(options)
    for account, options in accounts.items():
        canonical = f"claude-{account}"
        alias = {"v1": "claude-main", "v2": "claude"}.get(account)
        legacy = overrides.get(alias, {}) if alias else {}
        resolved = {"model": "claude-opus-5-5", "effort": "low", "max_turns": 80,
                    **options, **legacy, **account_overrides.get(account, {}),
                    **overrides.get(canonical, {})}
        if not isinstance(resolved.get("config_dir"), str) or not resolved["config_dir"]:
            raise ValueError(f"claude_accounts.{account}.config_dir phải là đường dẫn")
        accounts[account] = {key: resolved[key] for key in ("config_dir", "max_day_pct") + LABEL_KEYS
                             if key in resolved}
        backends[canonical] = {key: _expand(value) for key, value in resolved.items()
                               if key not in LABEL_KEYS}
        if alias:
            backends[alias] = dict(backends[canonical])
    # Resolve only backend path settings, after account and alias precedence.
    # Keep the account registry raw for side-session and existing callers.
    for name, options in backends.items():
        path_keys = ("config_dir",) if name.startswith("claude") else {
            "codex": ("home",),
            "dsh": ("home", "key_file", "browser_dir"),
        }.get(name, ())
        for key in path_keys:
            value = options.get(key)
            if isinstance(value, str) and value and not value.startswith("~"):
                path = Path(value)
                if not path.is_absolute():
                    options[key] = str(root / path)
    native = section.pop("native")
    if not isinstance(native, dict):
        raise ValueError("ext_hand.native phải là object")
    if set(native) - set(DEFAULTS["native"]) or any(
            value not in ("auto", "off") for value in native.values()):
        raise ValueError("ext_hand.native chỉ nhận claude/codex với auto hoặc off")
    gpt_accounts = section.pop("gpt_accounts")
    if not isinstance(gpt_accounts, dict) or not all(isinstance(v, dict) for v in gpt_accounts.values()):
        raise ValueError("ext_hand.gpt_accounts cần tài khoản v<N> và options object")
    label_fmt = section.pop("account_label_format")
    mode = section.pop("mode")
    if mode not in ("shell", "auto", "paseo-required"):
        raise ValueError("ext_hand.mode phải là shell, auto hoặc paseo-required")
    paseo = section.pop("paseo")
    if not isinstance(paseo, dict):
        raise ValueError("ext_hand.paseo phải là object")
    if set(paseo) - {"package_root", "target", "state_root"}:
        raise ValueError("ext_hand.paseo chứa option không hỗ trợ")
    for key in ("package_root", "state_root"):
        value = paseo.get(key)
        if value:
            paseo[key] = str(_resolve(root, value))
    merged.update(section)
    go_ledger, go_summary, go_limit, go_live = _go_usage(root, go_section)
    max_parallel = validate_limit(merged["max_parallel"])
    max_tokens = merged["max_tokens"]
    isolation = str(merged["isolation"])
    if isolation not in ISOLATIONS:
        raise ValueError(f"{CONFIG_SECTION}.isolation phải là một trong {ISOLATIONS}")
    worktree_root = (_resolve(root, str(worktree_root_raw)) if worktree_root_raw
                     else _state_dir() / WORKTREES_DIRNAME)
    return ExtConfig(
        root=root, order=[str(n) for n in merged["order"]],
        timeout_min=float(merged["timeout_min"]),
        max_tokens=int(max_tokens) if max_tokens is not None else None,
        sandbox=str(merged["sandbox"]),
        ledger=_resolve(root, str(merged["ledger"])),
        quota_state=_resolve(root, str(merged["quota_state"])),
        runs_dir=_resolve(root, str(merged["runs_dir"])),
        worktree_root=worktree_root.resolve(),
        isolation=isolation, isolation_explicit=isolation_explicit,
        backends=backends,
        go_usage_ledger=go_ledger, go_usage_summary=go_summary,
        go_monthly_limit_usd=go_limit,
        go_usage_live=go_live,
        machine_state_dir=_state_dir(),
        max_parallel=max_parallel, claude_accounts=accounts, mode=mode, paseo=paseo, native=native,
        gpt_accounts=gpt_accounts, account_label_format=label_fmt,
        disk_guard=copy.deepcopy(result.effective.get("disk_guard", {})),
        worktree_gc_auto=_worktree_gc_auto(merged.get("worktree_gc", {})),
    )
