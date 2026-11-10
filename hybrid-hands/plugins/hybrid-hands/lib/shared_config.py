"""Memoized plugin/global/repository configuration with leaf provenance."""
from __future__ import annotations

import copy
import json
import io
from functools import lru_cache
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_ENV = "HYBRID_HANDS_CONFIG"
GLOBAL_CONFIG = "~/.hybrid-hands/config.json"
DEFAULT_MAIN_CLAUDE_AUTO_COMPACT_WINDOW = 272000
MAIN_CLAUDE_AUTO_COMPACT_KEY = "main_session.claude_auto_compact_window"
MIN_CLAUDE_AUTO_COMPACT_WINDOW = 100000
MAX_CLAUDE_AUTO_COMPACT_WINDOW = 1000000


def normalize_claude_auto_compact_window(value: Any) -> int | None:
    """Validate a main Claude window; null/exact 'auto' disables the override.

    Pure normalization only: launchers decide whether to inject an environment
    variable. Booleans and numeric strings are deliberately not integer windows.

    Returns the integer unchanged, or None for either disable sentinel.
    Raises ValueError with the dotted config key for every unsupported value.
    The loader supplies the source path when reporting that error.
    This helper neither reads nor writes process environment or settings.
    """
    if value is None or (type(value) is str and value == "auto"):
        return None
    if (type(value) is int
            and MIN_CLAUDE_AUTO_COMPACT_WINDOW <= value <= MAX_CLAUDE_AUTO_COMPACT_WINDOW):
        return value
    raise ValueError(
        f"{MAIN_CLAUDE_AUTO_COMPACT_KEY} phải là số nguyên "
        f"{MIN_CLAUDE_AUTO_COMPACT_WINDOW}..{MAX_CLAUDE_AUTO_COMPACT_WINDOW}, null hoặc 'auto'")


class GlobalConfigError(Exception):
    """Fatal global configuration error; consumers must not silently fall back."""


FILE_SOURCES = ("global", "repo")
# Sections whose child keys are registry entries: unknown names allowed, each entry a dict.
# Tuples, not sets: a set of strings also matches a list/str by containment.
REGISTRY_SECTIONS = ("ext_hand.backends", "ext_hand.claude_accounts", "ext_hand.gpt_accounts")
# Sections which are always objects. Their own leaves are replaceable, so an explicit
# ``price_per_mtok: null`` or ``monthly_limit_usd`` stays allowed.
OBJECT_SECTIONS = REGISTRY_SECTIONS + ("ext_hand.go_usage", "ext_hand.paseo",
                                      "paseo.claude_providers")


@dataclass
class ConfigResult:
    root: Path
    effective: dict
    sources: dict[str, str]
    paths: dict[str, dict]
    # Raw content of each successfully read file, so consumers can re-merge by source.
    sections: tuple[tuple[str, dict], ...] = ()


def _merge(base: dict, over: dict, sources: dict, source: str, prefix: str = "") -> None:
    for key, value in over.items():
        dotted = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            if not isinstance(base.get(key), dict):
                base[key] = {}
                for old in list(sources):
                    if old == dotted or old.startswith(dotted + "."):
                        del sources[old]
            if value:
                sources.pop(dotted, None)
            elif not base[key]:
                sources[dotted] = source
            _merge(base[key], value, sources, source, dotted)
        else:
            for old in list(sources):
                if old == dotted or old.startswith(dotted + "."):
                    del sources[old]
            base[key] = copy.deepcopy(value)
            sources[dotted] = source


def _object_section(prefix: str) -> bool:
    """Root, top-level sections, registry sections and their entries are objects.

    Deeper paths (``ext_hand.backends.codex.price_per_mtok``) are leaves and may be any
    JSON value, ``null`` included.
    """
    if not prefix or "." not in prefix or prefix in OBJECT_SECTIONS:
        return True
    return prefix.rpartition(".")[0] in REGISTRY_SECTIONS


def _validate(value: Any, path: Path, prefix: str = "") -> None:
    """Check object shape and the main Claude compact window in each source."""
    if prefix == MAIN_CLAUDE_AUTO_COMPACT_KEY:
        normalize_claude_auto_compact_window(value)
        return
    if _object_section(prefix):
        if not isinstance(value, dict):
            raise ValueError(f"{path}: {prefix or 'root'} phải là object")
        for key, item in value.items():
            _validate(item, path, f"{prefix}.{key}" if prefix else key)


def backends_from(result: ConfigResult, backend: str) -> dict:
    """Backend options from global/repo files only (no plugin price defaults)."""
    merged: dict = {}
    for source, section in result.sections:
        per_source: dict = {}
        _merge(per_source, section.get("ext_hand", {}).get("backends", {}), {}, source)
        _merge(merged, per_source, {}, source)
    return copy.deepcopy(merged.get(backend) or {})


def _normalize_parallel_policy(data: dict, source: str, path: Path, *, stream=None) -> None:
    """Fail closed before validation/merge, including raw sections consumers reuse.

    Keep the selected file's provenance even when its value is rejected. Never
    include the supplied value in a warning: configuration may contain secrets.
    """
    if not isinstance(data, dict) or "parallel_subagents" not in data:
        return
    section = data["parallel_subagents"]
    if not isinstance(section, dict):
        print(f"warning: {path}: parallel_subagents phải là object; dùng disabled", file=stream if stream is not None else sys.stderr)
        data["parallel_subagents"] = {"enabled": False}
        return
    if "backend" in section:
        if not isinstance(section["backend"], str):
            print(f"warning: {path}: parallel_subagents.backend phải là string; dùng claude-v1", file=stream if stream is not None else sys.stderr)
            section["backend"] = "claude-v1"
        else:
            section["backend"] = canonical_backend(section["backend"])
    if "enabled" not in section:
        return
    if type(section["enabled"]) is not bool:
        print(f"warning: {path}: parallel_subagents.enabled phải là bool; dùng disabled", file=stream if stream is not None else sys.stderr)
        section["enabled"] = False
    elif source == "global" and section["enabled"]:
        print(f"warning: {path}: parallel_subagents.enabled chỉ bật từ repo; bỏ qua global", file=stream if stream is not None else sys.stderr)
        section["enabled"] = False


def canonical_backend(value: str) -> str:
    return {"claude-main": "claude-v1", "claude": "claude-v2"}.get(value, value)


def parallel_backend(value: Any, ext_hand: dict) -> str:
    """Validate against the effective registry without echoing user input."""
    if not isinstance(value, str):
        raise ValueError("parallel_subagents.backend phải là tên backend hợp lệ")
    name = canonical_backend(value)
    names = set(ext_hand["backends"]) | {f"claude-{account}" for account in ext_hand["claude_accounts"]}
    if name not in names:
        raise ValueError("parallel_subagents.backend không tồn tại trong cấu hình hiệu lực")
    return name


def brain_account(value: Any, ext_hand: dict) -> str:
    """Validate a Claude account name without echoing user input."""
    if not isinstance(value, str) or value not in ext_hand["claude_accounts"]:
        raise ValueError("--account không tồn tại trong ext_hand.claude_accounts hiệu lực")
    return value


def load_config(cwd: Path | None = None, *, known_root: Path | None = None,
                config_file: Path | None = None) -> ConfigResult:
    """Resolve files from the current repo, retaining main-worktree fallback.

    ``paths`` records the selected absolute path, existence and successful read.
    Relative values remain raw so each consumer can apply its existing path rules.
    """
    from hand_ext.config import _config_path, git_toplevel
    from hand_ext.constants import PROJECT_CONFIG_RELPATH

    root = Path(known_root).resolve() if known_root is not None else git_toplevel(Path(cwd or Path.cwd()))
    global_path = Path(os.environ.get(CONFIG_ENV) or GLOBAL_CONFIG).expanduser()
    if not global_path.is_absolute():
        global_path = root / global_path
    repo_path = Path(config_file) if config_file is not None else (_config_path(root) or root / PROJECT_CONFIG_RELPATH)
    if not repo_path.is_absolute():
        repo_path = root / repo_path
    result, warnings = _load_config_cached(root, global_path.resolve(), repo_path.resolve(),
                                           file_stamp(global_path), file_stamp(repo_path))
    if warnings:
        sys.stderr.write(warnings)
    # Callers historically mutate these dictionaries; never expose cached state.
    return copy.deepcopy(result)


def file_stamp(path: Path) -> tuple:
    """A missing/unreadable file is a distinct key and will be retried if changed."""
    try:
        st = path.stat()
        return (st.st_mtime_ns, st.st_ctime_ns, st.st_size, st.st_ino, st.st_mode)
    except OSError:
        return ()


@lru_cache(maxsize=32)
def _load_config_cached(root: Path, global_path: Path, repo_path: Path,
                        global_stamp: tuple, repo_stamp: tuple) -> tuple[ConfigResult, str]:
    warnings = io.StringIO()
    try:
        result = _build_config(root, global_path, repo_path, warnings)
    except (GlobalConfigError, ValueError, OSError):
        # Preserve diagnostics even when a later source/limit fails validation.
        sys.stderr.write(warnings.getvalue())
        raise
    return result, warnings.getvalue()


def _build_config(root: Path, global_path: Path, repo_path: Path,
                  warnings: io.StringIO) -> ConfigResult:
    from hand_ext.constants import DEFAULTS as HAND_DEFAULTS
    from side_session.constants import DEFAULTS as SIDE_DEFAULTS

    defaults = {"parallel_subagents": {"enabled": False, "backend": "claude-v1"}, "ext_hand": HAND_DEFAULTS, "side_session": SIDE_DEFAULTS,
                "main_session": {"provider": "codex", "codex_model": "gpt-6.1-sol",
                                 "codex_effort": "high", "claude_model": "claude-opus-5-5",
                                 "claude_effort": "high", "claude_account": "v1",
                                 "transport": "paseo",
                                 "claude_auto_compact_window": DEFAULT_MAIN_CLAUDE_AUTO_COMPACT_WINDOW},
                "paseo": {"claude_providers": {"v1": "claude"}}}
    effective, sources, paths, sections = {}, {}, {}, []
    _merge(effective, defaults, sources, "plugin")
    for source, path in zip(FILE_SOURCES, (global_path.resolve(), repo_path.resolve())):
        info = paths[source] = {"path": str(path), "exists": path.exists(), "read": False}
        if not info["exists"]:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _normalize_parallel_policy(data, source, path, stream=warnings)
            _validate(data, path)
            _merge(effective, data, sources, source)
            info["read"] = True
            sections.append((source, data))
        except (OSError, ValueError) as exc:
            error = f"{path}: {exc}"
            if source == "global":
                raise GlobalConfigError(error) from exc
            raise ValueError(error) from exc
    try:
        effective["parallel_subagents"]["backend"] = parallel_backend(
            effective["parallel_subagents"]["backend"], effective["ext_hand"])
    except ValueError:
        print("warning: parallel_subagents.backend không hợp lệ; dùng claude-v1", file=warnings)
        effective["parallel_subagents"]["backend"] = "claude-v1"
    # Validate limits after merging, even for consumers which only need side state.
    from hand_ext.parallel import validate_limit
    from side_session.constants import MAX_PARALLEL as SIDE_MAX
    for name, ceiling in (("ext_hand", None), ("side_session", SIDE_MAX)):
        key = f"{name}.max_parallel"
        try:
            value = effective[name]["max_parallel"]
            if ceiling is None:
                validate_limit(value)
            elif type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(f"{key} phải là số nguyên 1..{ceiling}")
        except ValueError as exc:
            source = sources[key]
            path = paths.get(source, {}).get("path", "plugin")
            if source == "global":
                raise GlobalConfigError(f"{path}: {exc}") from exc
            raise ValueError(f"{path}: {exc}") from exc
    # Check the effective value too, including the canonical plugin default.
    key = MAIN_CLAUDE_AUTO_COMPACT_KEY
    try:
        normalize_claude_auto_compact_window(effective["main_session"]["claude_auto_compact_window"])
    except ValueError as exc:
        source = sources[key]
        path = paths.get(source, {}).get("path", "plugin")
        if source == "global":
            raise GlobalConfigError(f"{path}: {exc}") from exc
        raise ValueError(f"{path}: {exc}") from exc
    return ConfigResult(root, effective, sources, paths, tuple(sections))
