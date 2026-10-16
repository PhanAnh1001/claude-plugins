"""Scan a repo for requirement IDs, plan tasks and tests (used by trace_check.py).

ID format: `<TYPE>-<feature>-NNN` (feature kebab-case lowercase, NNN 2-3 digits).
Tests link by the literal ID or the underscore form `<TYPE>_<feature_with_underscores>_NNN`.
Tasks are plan lines holding `T-<feature>-NN` and `covers: <ID>, <ID>`.
Skipped tasks (`- [-]` checkbox, or the task ID inside `~~...~~`) are not tasks and cover nothing.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

FEATURE_PATTERN = r"[a-z0-9]+(?:-[a-z0-9]+)*"
FEATURE_UNDERSCORE_PATTERN = r"[a-z0-9]+(?:_[a-z0-9]+)*"
NUMBER_PATTERN = r"\d{2,3}"
# Lookarounds stop "NFR" matching as "FR" and "FR-x-0012" matching as "FR-x-001".
BEFORE_ID = r"(?<![A-Za-z0-9])"
AFTER_ID = r"(?![0-9A-Za-z])"
TASK_PATTERN = rf"{BEFORE_ID}T-{FEATURE_PATTERN}-{NUMBER_PATTERN}{AFTER_ID}"
TASK_RE = re.compile(TASK_PATTERN)
COVERS_MARKER = "covers:"
DONE_CHECKBOX_RE = re.compile(r"^\s*[-*]\s*\[[xX]\]")
SKIPPED_CHECKBOX_RE = re.compile(r"^\s*[-*]\s*\[-\]")
# A task ID inside a strikethrough span marks the task as skipped, whatever its checkbox says.
STRUCK_TASK_RE = re.compile(rf"~~[^~]*{TASK_PATTERN}[^~]*~~")
TABLE_ROW_RE = re.compile(r"^\s*\|([^|]*)\|")
HEADING_RE = re.compile(r"^\s*#{1,6}\s+(.*)$")
MARKDOWN_SUFFIX = ".md"
# Decoration allowed around an ID in a table cell: code spans and bold/italic markers.
CELL_DECORATION = "`* "
# Directories never worth scanning for docs or tests.
SKIPPED_DIRS = frozenset({
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "dist", "build", ".tox", ".idea", ".vscode",
})


@dataclass(frozen=True)
class Location:
    path: str  # posix path relative to the repo root
    line: int

    def __str__(self) -> str:
        return f"{self.path}:{self.line}"


@dataclass
class Task:
    task_id: str
    done: bool
    covers: list[str]
    location: Location


@dataclass(frozen=True)
class MalformedId:
    text: str
    location: Location


@dataclass
class ScanResult:
    definitions: dict[str, list[Location]] = field(default_factory=dict)
    malformed: list[MalformedId] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    tests: dict[str, set[str]] = field(default_factory=dict)  # ID -> test files
    references: dict[str, list[Location]] = field(default_factory=dict)


class IdMatcher:
    """Find requirement IDs (hyphen and underscore forms) for the configured types."""

    def __init__(self, id_types: Iterable[str]) -> None:
        # Longest first so alternation prefers "NFR" over a shorter overlapping type.
        types = "|".join(sorted((re.escape(t) for t in id_types), key=len, reverse=True))
        self._hyphen = re.compile(rf"{BEFORE_ID}(?:{types})-{FEATURE_PATTERN}-{NUMBER_PATTERN}{AFTER_ID}")
        self._underscore = re.compile(
            rf"{BEFORE_ID}({types})_({FEATURE_UNDERSCORE_PATTERN})_({NUMBER_PATTERN})(?![0-9])"
        )
        # A whole cell that looks like an ID attempt (type, separator, has a digit) but is not valid.
        self._id_like = re.compile(rf"(?:{types})[-_][A-Za-z0-9_-]*[0-9][A-Za-z0-9_-]*")

    def is_malformed_cell(self, cell: str) -> bool:
        text = cell.strip(CELL_DECORATION)
        return bool(self._id_like.fullmatch(text)) and not self._hyphen.fullmatch(text)

    def hyphen_ids(self, text: str) -> list[str]:
        return self._hyphen.findall(text)

    def all_ids(self, text: str) -> list[str]:
        found = self.hyphen_ids(text)
        for id_type, feature, number in self._underscore.findall(text):
            found.append(f"{id_type}-{feature.replace('_', '-')}-{number}")
        return found


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a repo-relative glob (`**` spans directories, `*` does not) to a regex."""
    out: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            out.append("(?:.*/)?")
            index += len("**/")
        elif pattern.startswith("**", index):
            out.append(".*")
            index += len("**")
        elif pattern[index] == "*":
            out.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(out) + r"\Z")


def iter_repo_files(root: Path) -> Iterator[str]:
    """Yield posix paths relative to `root`, skipping vendored and cache directories."""
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIPPED_DIRS)
        relative_dir = Path(directory).relative_to(root).as_posix()
        for name in sorted(filenames):
            yield name if relative_dir == "." else f"{relative_dir}/{name}"


def match_globs(root: Path, patterns: Iterable[str]) -> list[str]:
    regexes = [glob_to_regex(p) for p in patterns]
    if not regexes:
        return []
    return [rel for rel in iter_repo_files(root) if any(r.match(rel) for r in regexes)]


def markdown_files_under(root: Path, directory: str) -> list[str]:
    prefix = directory.strip("/")
    return [
        rel for rel in iter_repo_files(root)
        if rel.endswith(MARKDOWN_SUFFIX) and (not prefix or rel.startswith(prefix + "/"))
    ]


def read_lines(root: Path, relative: str) -> list[str]:
    try:
        return (root / relative).read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return []  # binary or unreadable files cannot hold IDs


def defined_id_on_line(line: str, matcher: IdMatcher) -> str | None:
    """An ID is defined by a table row whose first cell holds it, or by a heading containing it."""
    row = TABLE_ROW_RE.match(line)
    if row:
        ids = matcher.hyphen_ids(row.group(1))
        return ids[0] if ids else None
    heading = HEADING_RE.match(line)
    if heading:
        ids = matcher.hyphen_ids(heading.group(1))
        return ids[0] if ids else None
    return None


def _add_reference(result: ScanResult, id_value: str, location: Location) -> None:
    result.references.setdefault(id_value, []).append(location)


def _record_malformed(line: str, matcher: IdMatcher, location: Location, result: ScanResult) -> None:
    row = TABLE_ROW_RE.match(line)
    if row and matcher.is_malformed_cell(row.group(1)):
        result.malformed.append(MalformedId(row.group(1).strip(CELL_DECORATION), location))


def scan_definitions(root: Path, files: Iterable[str], matcher: IdMatcher, result: ScanResult) -> None:
    for relative in files:
        for number, line in enumerate(read_lines(root, relative), start=1):
            location = Location(relative, number)
            defined = defined_id_on_line(line, matcher)
            if defined:
                result.definitions.setdefault(defined, []).append(location)
            else:
                _record_malformed(line, matcher, location, result)
            for id_value in matcher.hyphen_ids(line):
                if id_value != defined:
                    _add_reference(result, id_value, location)


def is_skipped_task_line(line: str) -> bool:
    return bool(SKIPPED_CHECKBOX_RE.match(line) or STRUCK_TASK_RE.search(line))


def parse_task_line(line: str, matcher: IdMatcher, location: Location) -> Task | None:
    task_match = TASK_RE.search(line)
    if not task_match or is_skipped_task_line(line):
        return None
    covers_text = line.split(COVERS_MARKER, 1)[1] if COVERS_MARKER in line else ""
    covers = list(dict.fromkeys(matcher.hyphen_ids(covers_text)))
    done = bool(DONE_CHECKBOX_RE.match(line))
    return Task(task_id=task_match.group(0), done=done, covers=covers, location=location)


def scan_plans(root: Path, files: Iterable[str], matcher: IdMatcher, result: ScanResult) -> None:
    for relative in files:
        for number, line in enumerate(read_lines(root, relative), start=1):
            location = Location(relative, number)
            task = parse_task_line(line, matcher, location)
            if task:
                result.tasks.append(task)
            for id_value in matcher.hyphen_ids(line):
                _add_reference(result, id_value, location)


def scan_tests(root: Path, files: Iterable[str], matcher: IdMatcher, result: ScanResult) -> None:
    for relative in files:
        for number, line in enumerate(read_lines(root, relative), start=1):
            for id_value in matcher.all_ids(line):
                result.tests.setdefault(id_value, set()).add(relative)
                _add_reference(result, id_value, Location(relative, number))
