"""Uncached plugin/global/repository configuration with leaf provenance."""
from __future__ import annotations

import copy
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CONFIG_ENV = "HYBRID_HANDS_CONFIG"
GLOBAL_CONFIG = "~/.hybrid-hands/config.json"


class GlobalConfigError(Exception):
    """Fatal global configuration error; consumers must not silently fall back."""


FILE_SOURCES = ("global", "repo")
# Sections whose child keys are registry entries: unknown names allowed, each entry a dict.
# Tuples, not sets: a set of strings also matches a list/str by containment.
REGISTRY_SECTIONS = ("ext_hand.backends", "ext_hand.claude_accounts")
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
    """Check object shape only; a leaf value (even ``null``) replaces its default."""
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


def load_config(cwd: Path | None = None, *, known_root: Path | None = None,
                config_file: Path | None = None) -> ConfigResult:
    """Resolve files from the current repo, retaining main-worktree fallback.

    ``paths`` records the selected absolute path, existence and successful read.
    Relative values remain raw so each consumer can apply its existing path rules.
    """
    from hand_ext.config import _config_path, git_toplevel
    from hand_ext.constants import DEFAULTS as HAND_DEFAULTS, PROJECT_CONFIG_RELPATH
    from side_session.constants import DEFAULTS as SIDE_DEFAULTS

    root = Path(known_root).resolve() if known_root is not None else git_toplevel(Path(cwd or Path.cwd()))
    global_path = Path(os.environ.get(CONFIG_ENV) or GLOBAL_CONFIG).expanduser()
    if not global_path.is_absolute():
        global_path = root / global_path
    repo_path = Path(config_file) if config_file is not None else (_config_path(root) or root / PROJECT_CONFIG_RELPATH)
    if not repo_path.is_absolute():
        repo_path = root / repo_path
    defaults = {"ext_hand": HAND_DEFAULTS, "side_session": SIDE_DEFAULTS,
                "main_session": {"provider": "codex", "codex_model": "gpt-6.1-sol",
                                 "codex_effort": "high", "claude_model": "claude-opus-5-5",
                                 "claude_effort": "high", "claude_account": "v1",
                                 "transport": "paseo"},
                "paseo": {"claude_providers": {"v1": "claude"}}}
    effective, sources, paths, sections = {}, {}, {}, []
    _merge(effective, defaults, sources, "plugin")
    for source, path in zip(FILE_SOURCES, (global_path.resolve(), repo_path.resolve())):
        info = paths[source] = {"path": str(path), "exists": path.exists(), "read": False}
        if not info["exists"]:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            _validate(data, path)
            _merge(effective, data, sources, source)
            info["read"] = True
            sections.append((source, data))
        except (OSError, ValueError) as exc:
            error = f"{path}: {exc}"
            if source == "global":
                raise GlobalConfigError(error) from exc
            raise ValueError(error) from exc
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
    return ConfigResult(root, effective, sources, paths, tuple(sections))
