#!/usr/bin/env python3
"""Resolve which template file to use for a document kind.

Usage:
    python3 dw_template.py <design|plan|bug|cr|adr|traceability> [--config PATH]
    (skills call it as: "${CLAUDE_PLUGIN_ROOT}/scripts/dw" template <name>)

Prints the template path on stdout and "source: repo|plugin" on stderr.
Lookup: <[paths].templates>/<name>.md, then <[paths].templates>/<[paths].template_aliases[name]>,
then the plugin's templates/<name>.md. Without any config the plugin template is used.
Exit codes: 0 ok, 2 unknown name or invalid config.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from dw_config import EXIT_CONFIG_ERROR, EXIT_OK, ConfigError, LoadedConfig, find_config, load_config

TEMPLATE_NAMES = ("design", "plan", "bug", "cr", "adr", "traceability")
TEMPLATE_SUFFIX = ".md"
PLUGIN_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class TemplateSource(str, Enum):
    REPO = "repo"
    PLUGIN = "plugin"


@dataclass(frozen=True)
class ResolvedTemplate:
    path: Path
    source: TemplateSource


def repo_candidates(config: LoadedConfig, name: str) -> list[Path]:
    """Repo template files to try, in order; empty when [paths].templates is not set."""
    templates_dir = config.data["paths"]["templates"]
    if not templates_dir:
        return []
    base = config.root / templates_dir
    candidates = [base / f"{name}{TEMPLATE_SUFFIX}"]
    alias = config.data["paths"]["template_aliases"].get(name)
    if alias:
        candidates.append(base / alias)
    return candidates


def resolve_template(name: str, config: LoadedConfig | None) -> ResolvedTemplate:
    if name not in TEMPLATE_NAMES:
        raise ValueError(f"unknown template {name!r}; expected one of: {', '.join(TEMPLATE_NAMES)}")
    if config is not None:
        for candidate in repo_candidates(config, name):
            if candidate.is_file():
                return ResolvedTemplate(candidate, TemplateSource.REPO)
    return ResolvedTemplate(PLUGIN_TEMPLATES_DIR / f"{name}{TEMPLATE_SUFFIX}", TemplateSource.PLUGIN)


def optional_config(explicit: str | None) -> LoadedConfig | None:
    """Load the explicit config, or the nearest one above cwd; None when no config exists."""
    if explicit:
        return load_config(Path(explicit))
    found = find_config(Path.cwd())
    return load_config(found) if found else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print the template path for a document kind.")
    parser.add_argument("name", help=f"one of: {', '.join(TEMPLATE_NAMES)}")
    parser.add_argument("--config", help="path to dev-workflow.toml (default: search upwards from cwd)")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.name not in TEMPLATE_NAMES:
        print(f"dw_template: unknown template {args.name!r}; expected one of: {', '.join(TEMPLATE_NAMES)}",
              file=sys.stderr)
        return EXIT_CONFIG_ERROR
    try:
        config = optional_config(args.config)
    except ConfigError as exc:
        print(f"dw_template: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    resolved = resolve_template(args.name, config)
    print(resolved.path)
    print(f"source: {resolved.source.value}", file=sys.stderr)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
