#!/usr/bin/env python3
"""Check requirement traceability: ID (SRS) -> task (plan) -> test.

Usage:
    python3 trace_check.py [--config PATH] [--write] [--format md|json]
    (skills call it as: "${CLAUDE_PLUGIN_ROOT}/scripts/dw" trace ...)

Exit codes: 0 all required links present, 1 missing task/test links or an ID defined
more than once, 2 config error. Orphan references, malformed IDs and waivers for unknown
IDs are warnings only. IDs listed in [trace].waivers are exempt from required links.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dw_config import EXIT_CONFIG_ERROR, EXIT_OK, ConfigError, LoadedConfig, resolve_config
from trace_render import render_json, render_markdown
from trace_report import build_report
from trace_scan import (
    IdMatcher, ScanResult, markdown_files_under, match_globs, scan_definitions, scan_plans, scan_tests,
)

EXIT_MISSING_LINKS = 1
FORMAT_MARKDOWN = "md"
FORMAT_JSON = "json"


def scan_repo(config: LoadedConfig) -> ScanResult:
    root = config.root
    paths = config.data["paths"]
    trace = config.data["trace"]
    matcher = IdMatcher(trace["id_types"])
    excluded = {paths["traceability"].strip("/")}
    result = ScanResult()
    srs_files = [f for f in match_globs(root, paths["srs"]) if f not in excluded]
    plan_files = [f for f in markdown_files_under(root, paths["plans"]) if f not in excluded]
    test_files = [f for f in match_globs(root, trace["test_globs"]) if f not in excluded]
    scan_definitions(root, srs_files, matcher, result)
    scan_plans(root, plan_files, matcher, result)
    scan_tests(root, test_files, matcher, result)
    return result


def write_traceability(config: LoadedConfig, markdown: str) -> Path:
    target = config.root / config.data["paths"]["traceability"]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    return target


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check ID -> task -> test traceability.")
    parser.add_argument("--config", help="path to dev-workflow.toml (default: search upwards from cwd)")
    parser.add_argument("--write", action="store_true", help="write [paths].traceability")
    parser.add_argument("--format", choices=[FORMAT_MARKDOWN, FORMAT_JSON], default=FORMAT_MARKDOWN)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = resolve_config(args.config)
    except ConfigError as exc:
        print(f"trace_check: {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    for warning in config.warnings:
        print(f"trace_check: config warning: {warning}", file=sys.stderr)
    report = build_report(scan_repo(config), config.data["trace"])
    for error in report.errors:
        print(f"trace_check: error: {error}", file=sys.stderr)
    for warning in report.warnings:
        print(f"trace_check: warning: {warning}", file=sys.stderr)
    markdown = render_markdown(report)
    if args.write:
        target = write_traceability(config, markdown)
        print(f"trace_check: wrote {target.relative_to(config.root).as_posix()}", file=sys.stderr)
    output = render_json(report) + "\n" if args.format == FORMAT_JSON else markdown
    sys.stdout.write(output)
    return EXIT_OK if report.ok else EXIT_MISSING_LINKS


if __name__ == "__main__":
    sys.exit(main())
