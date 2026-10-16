#!/usr/bin/env python3
"""Load and validate a repo's `.claude/dev-workflow.toml`, merged over defaults.

Usage:
    python3 dw_config.py [--config PATH] [--get section.key] [--json]

Without --config the file is searched from the current directory upwards.
Exit codes: 0 ok, 2 config missing or invalid. Unknown keys only warn (stderr).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    tomllib = None  # type: ignore[assignment]

CONFIG_RELATIVE_PATH = Path(".claude") / "dev-workflow.toml"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
MIN_PYTHON_MESSAGE = "dev-workflow scripts need Python >= 3.11 (tomllib)"

# Sections whose keys are free-form (glob -> list of doc paths), not a fixed schema.
FREE_FORM_SECTIONS = frozenset({"docs_map"})

DEFAULTS: dict[str, dict[str, Any]] = {
    "project": {
        "name": "",  # empty -> repo directory name
        "doc_language": "vi",
        "max_file_lines": 400,
    },
    "gate": {
        "commands": [],
        "lint": [],
    },
    "paths": {
        "specs": "docs/specs",
        "plans": "docs/plans",
        "adr": "docs/adr",
        "bugs": "docs/bugs",
        "crs": "docs/cr",
        "srs": ["docs/**/srs/*.md", "docs/specs/**/*.md"],
        "traceability": "docs/_shared/traceability.md",
        "templates": "",  # empty -> plugin templates
        # Extra repo file names tried after <name>.md, e.g. a repo that calls design "spec".
        "template_aliases": {"design": "spec.md"},
        "migrations": "",  # empty -> auto-detect
    },
    "frontend": {
        "dev_command": "",
        "checks": [],  # frontend test/lint/typecheck/build commands
        "ui_language": "",  # empty -> project.doc_language
    },
    "docs_map": {},
    "trace": {
        "id_types": ["FR", "NFR", "BR", "E", "SC"],
        "test_globs": ["tests/**/*.py", "**/test_*.py", "**/*_test.py", "**/*.test.*", "**/*.spec.*"],
        "require_test_types": ["FR"],
        "require_task_types": ["FR"],
        "waivers": {},  # "<ID>" = "<reason>": ID exempt from required task/test links
    },
    "jira": {
        "project": "",
        "estimate_factor": 1.1,  # team rule: AI estimates x1.1
        "language": "vi",
        "description_sections": ["Tóm tắt", "Chi tiết", "Tài liệu & trích dẫn"],
        "guide": "",
    },
    "lanes": {
        "l0_max_files": 2,
    },
}


class ConfigError(Exception):
    """The config file is missing, unreadable, or has invalid values."""


@dataclass
class LoadedConfig:
    path: Path
    root: Path
    data: dict[str, dict[str, Any]]
    warnings: list[str] = field(default_factory=list)

    def get(self, dotted_key: str) -> Any:
        section, _, key = dotted_key.partition(".")
        if section not in self.data:
            raise KeyError(dotted_key)
        if not key:
            return self.data[section]
        if key not in self.data[section]:
            raise KeyError(dotted_key)
        return self.data[section][key]


def find_config(start: Path) -> Path | None:
    """Return the nearest `.claude/dev-workflow.toml` at or above `start`."""
    current = start.resolve()
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_RELATIVE_PATH
        if candidate.is_file():
            return candidate
    return None


def repo_root_for(config_path: Path) -> Path:
    """The repo root is the directory that contains `.claude/`."""
    return config_path.resolve().parent.parent


def _type_name(value: Any) -> str:
    return type(value).__name__


def _is_string_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _is_string_table(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )


def _check_value(where: str, default: Any, value: Any) -> None:
    if isinstance(default, dict):
        if not _is_string_table(value):
            raise ConfigError(f"{where}: expected table of strings, got {_type_name(value)}")
        return
    if isinstance(default, bool):
        ok = isinstance(value, bool)
    elif isinstance(default, float):
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    elif isinstance(default, int):
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif isinstance(default, list):
        ok = _is_string_list(value)
    else:
        ok = isinstance(value, type(default))
    if not ok:
        expected = "list of strings" if isinstance(default, list) else _type_name(default)
        raise ConfigError(f"{where}: expected {expected}, got {_type_name(value)}")


def _merge_free_form(section: str, values: dict[str, Any]) -> dict[str, Any]:
    for key, value in values.items():
        if not _is_string_list(value):
            raise ConfigError(f"{section}.{key}: expected list of strings, got {_type_name(value)}")
    return dict(values)


def merge_with_defaults(raw: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Merge user values over DEFAULTS; return (merged, warnings). Raise ConfigError on bad types."""
    merged = copy.deepcopy(DEFAULTS)
    warnings: list[str] = []
    for section, values in raw.items():
        if section not in DEFAULTS:
            warnings.append(f"unknown section [{section}] ignored")
            continue
        if not isinstance(values, dict):
            raise ConfigError(f"[{section}] must be a table, got {_type_name(values)}")
        if section in FREE_FORM_SECTIONS:
            merged[section] = _merge_free_form(section, values)
            continue
        for key, value in values.items():
            if key not in DEFAULTS[section]:
                warnings.append(f"unknown key {section}.{key} ignored")
                continue
            _check_value(f"{section}.{key}", DEFAULTS[section][key], value)
            merged[section][key] = value
    return merged, warnings


def load_config(path: Path) -> LoadedConfig:
    if tomllib is None:
        raise ConfigError(MIN_PYTHON_MESSAGE)
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"config not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {path}: {exc}") from exc
    data, warnings = merge_with_defaults(raw)
    root = repo_root_for(path)
    if not data["project"]["name"]:
        data["project"]["name"] = root.name
    return LoadedConfig(path=path.resolve(), root=root, data=data, warnings=warnings)


def resolve_config(explicit: str | None, start: Path | None = None) -> LoadedConfig:
    """Load the explicit config path, or search upwards from `start` (default: cwd)."""
    if explicit:
        return load_config(Path(explicit))
    found = find_config(start or Path.cwd())
    if found is None:
        raise ConfigError(f"no {CONFIG_RELATIVE_PATH.as_posix()} found from {start or Path.cwd()} upwards")
    return load_config(found)


def _format_value(value: Any, as_json: bool) -> str:
    if as_json or not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, indent=2 if as_json else None)
    return value


def _format_flat(data: dict[str, dict[str, Any]]) -> str:
    lines = []
    for section, values in data.items():
        for key, value in values.items():
            lines.append(f"{section}.{key} = {json.dumps(value, ensure_ascii=False)}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print the merged dev-workflow config.")
    parser.add_argument("--config", help="path to dev-workflow.toml (default: search upwards from cwd)")
    parser.add_argument("--get", metavar="SECTION.KEY", help="print one value, e.g. gate.commands")
    parser.add_argument("--json", action="store_true", help="print JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = resolve_config(args.config)
    except ConfigError as exc:
        print(f"dw_config: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    for warning in config.warnings:
        print(f"dw_config: warning: {warning}", file=sys.stderr)
    if args.get:
        try:
            value = config.get(args.get)
        except KeyError:
            print(f"dw_config: unknown key {args.get}", file=sys.stderr)
            return EXIT_CONFIG_ERROR
        print(_format_value(value, args.json))
        return EXIT_OK
    print(_format_value(config.data, True) if args.json else _format_flat(config.data))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
