"""Đo lượt hand-ext: dòng test/code/docs, lệnh test và thời gian chạy.

Đọc `changes.patch`, `events.jsonl` và `meta.json` trong từng thư mục lượt.
Lượt cũ thiếu meta hoặc thiếu `ts` vẫn được đếm dòng; phần thời gian để trống.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .backends import KNOWN_BACKENDS, REMOVED_BACKENDS
from .constants import EVENTS_FILE

PATCH_FILE = "changes.patch"
META_FILE = "meta.json"
REPORT_FILE = "report.md"
UNKNOWN = "unknown"
NO_VALUE = "-"

TEST = "test"
CODE = "code"
DOCS = "docs"

TEST_DIRS = frozenset({"tests", "test", "__tests__", "spec"})
DOCS_DIRS = frozenset({"docs"})
DOCS_SUFFIXES = (".md", ".rst", ".txt")
TEST_PATTERNS = ("test_*", "*_test.*", "*.spec.*", "*.test.*", "*.bats")
BACKENDS = frozenset(KNOWN_BACKENDS) | frozenset(REMOVED_BACKENDS)

RUN_NAME_RE = re.compile(r"^(\d{8})-(\d{6})-")
HUNK_RE = re.compile(r"^@@")
TEST_COMMAND_RE = re.compile(
    r"(?<![\w.-])(?:pytest|unittest|bats|npm\s+test|npx\s+vitest|"
    r"go\s+test|cargo\s+test)(?![\w.-])",
    re.IGNORECASE)


@dataclass(frozen=True)
class RunMetrics:
    """Số liệu một thư mục lượt."""

    name: str
    path: Path
    version: str
    backend: str
    test_lines: int
    code_lines: int
    docs_lines: int
    test_commands: int
    test_seconds: Optional[float]
    seconds: Optional[float]
    date: Optional[dt.date]

    @property
    def test_percent(self) -> Optional[float]:
        total = self.test_lines + self.code_lines
        return 100.0 * self.test_lines / total if total else None


def _local(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo is not None else value.astimezone()


def _event_ts(event: dict) -> Optional[dt.datetime]:
    raw = event.get("ts")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return _local(dt.datetime.fromisoformat(raw.replace("Z", "+00:00")))
    except ValueError:
        return None


def _command(value: object) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return " ".join(str(item) for item in value)
    return None


def _tool_calls(event: dict) -> List[Tuple[str, str]]:
    """Các cặp (id, lệnh) của tool_call kiểu shell trong một event."""
    kind = event.get("type")
    found: List[Tuple[str, str]] = []
    if kind == "tool_call":
        call_id = event.get("callId") or event.get("call_id") or event.get("id")
        payload = event.get("input")
        command = _command(payload.get("command")) if isinstance(payload, dict) else None
        if call_id and command:
            found.append((str(call_id), command))
    elif kind in ("item.started", "item.completed"):
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "command_execution":
            call_id = item.get("id") or event.get("id")
            command = _command(item.get("command"))
            if call_id and command:
                found.append((str(call_id), command))
    elif kind == "assistant":
        message = event.get("message")
        blocks = message.get("content") if isinstance(message, dict) else None
        for block in blocks if isinstance(blocks, list) else []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            payload = block.get("input")
            command = _command(payload.get("command")) if isinstance(payload, dict) else None
            if block.get("id") and command:
                found.append((str(block["id"]), command))
    return found


def _result_ids(event: dict) -> List[str]:
    """Các id tool_call mà event này là kết quả tương ứng."""
    kind = event.get("type")
    if kind == "tool_result":
        call_id = event.get("callId") or event.get("call_id") or event.get("id")
        return [str(call_id)] if call_id else []
    if kind in ("item.completed", "item.failed"):
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "command_execution":
            call_id = item.get("id") or event.get("id")
            return [str(call_id)] if call_id else []
    if kind == "user":
        message = event.get("message")
        blocks = message.get("content") if isinstance(message, dict) else None
        ids = []
        for block in blocks if isinstance(blocks, list) else []:
            if isinstance(block, dict) and block.get("type") == "tool_result":
                call_id = block.get("tool_use_id")
                if call_id:
                    ids.append(str(call_id))
        return ids
    return []


def _read_events(path: Path) -> Tuple[int, Optional[float], List[dt.datetime]]:
    """Trả về (số lệnh test, tổng giây đã đo, mọi mốc ts)."""
    if not path.is_file():
        return 0, None, []
    commands = 0
    seconds = 0.0
    timed = 0
    stamps: List[dt.datetime] = []
    pending: Dict[str, Optional[dt.datetime]] = {}
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0, None, []
    for line in lines:
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        ts = _event_ts(event)
        if ts is not None:
            stamps.append(ts)
        for call_id, command in _tool_calls(event):
            if call_id in seen:
                continue
            seen.add(call_id)
            if not TEST_COMMAND_RE.search(command):
                continue
            commands += 1
            pending[call_id] = ts
        for call_id in _result_ids(event):
            if call_id not in pending:
                continue
            start = pending.pop(call_id)
            if start is not None and ts is not None and ts >= start:
                seconds += (ts - start).total_seconds()
                timed += 1
    return commands, (seconds if timed else None), stamps


def _classify(path: str) -> str:
    normalized = path.replace("\\", "/").lstrip("/")
    parts = Path(normalized).parts
    name = parts[-1] if parts else normalized
    if any(part in TEST_DIRS for part in parts[:-1]):
        return TEST
    if any(fnmatch.fnmatch(name, pattern) for pattern in TEST_PATTERNS):
        return TEST
    if any(part in DOCS_DIRS for part in parts[:-1]):
        return DOCS
    if name.lower().endswith(DOCS_SUFFIXES):
        return DOCS
    return CODE


def _patch_path(raw: str) -> Optional[str]:
    value = raw.strip().split("\t", 1)[0].strip()
    if value == "/dev/null" or not value:
        return None
    if value.startswith(("a/", "b/")):
        value = value[2:]
    return value or None


def count_patch(path: Path) -> Dict[str, int]:
    """Đếm dòng thêm trong một unified git diff theo loại file."""
    counts = {TEST: 0, CODE: 0, DOCS: 0}
    if not path.is_file():
        return counts
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return counts
    current: Optional[str] = None
    in_hunk = False
    for line in lines:
        if line.startswith("diff --git "):
            current, in_hunk = None, False
        elif not in_hunk and line.startswith("+++ "):
            current = _patch_path(line[4:])
        elif HUNK_RE.match(line):
            in_hunk = True
        elif in_hunk and line.startswith("+") and current:
            counts[_classify(current)] += 1
    return counts


def _read_meta(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _run_start(path: Path) -> Optional[dt.datetime]:
    match = RUN_NAME_RE.match(path.name)
    if not match:
        return None
    try:
        return _local(dt.datetime.strptime(match.group(1) + match.group(2),
                                           "%Y%m%d%H%M%S"))
    except ValueError:
        return None


def _file_times(path: Path) -> List[float]:
    try:
        return [item.stat().st_mtime for item in path.iterdir() if item.is_file()]
    except OSError:
        return []


def _backend(path: Path, meta: dict) -> str:
    name = str(meta.get("backend") or "").strip()
    if name:
        return name
    suffix = path.name.rsplit("-", 1)[-1]
    return suffix if suffix in BACKENDS else UNKNOWN


def _measure_run(path: Path) -> RunMetrics:
    counts = count_patch(path / PATCH_FILE)
    commands, seconds, stamps = _read_events(path / EVENTS_FILE)
    meta = _read_meta(path / META_FILE)
    start = _run_start(path)
    if len(stamps) >= 2:
        run_seconds: Optional[float] = (max(stamps) - min(stamps)).total_seconds()
    else:
        times = _file_times(path)
        if start is not None and times:
            run_seconds = max(0.0, max(times) - start.timestamp())
        elif len(times) >= 2:
            run_seconds = max(0.0, max(times) - min(times))
        else:
            run_seconds = None
    if start is not None:
        day = start.date()
    elif stamps:
        day = min(stamps).astimezone().date()
    else:
        times = _file_times(path)
        day = dt.datetime.fromtimestamp(min(times)).date() if times else None
    return RunMetrics(
        name=path.name,
        path=path,
        version=str(meta.get("plugin_version") or UNKNOWN),
        backend=_backend(path, meta),
        test_lines=counts[TEST],
        code_lines=counts[CODE],
        docs_lines=counts[DOCS],
        test_commands=commands,
        test_seconds=seconds,
        seconds=run_seconds,
        date=day,
    )


def _discover(root: Path) -> List[Path]:
    if not root.is_dir():
        raise ValueError(f"không thấy thư mục runs: {root}")
    if any((root / name).is_file() for name in (PATCH_FILE, EVENTS_FILE, META_FILE,
                                                REPORT_FILE)):
        return [root]
    return [child for child in sorted(root.iterdir())
            if child.is_dir() and any(
                (child / name).is_file()
                for name in (PATCH_FILE, EVENTS_FILE, META_FILE, REPORT_FILE))]


def _since_date(value: Optional[str]) -> Optional[dt.date]:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"--since phải có dạng YYYY-MM-DD, nhận {value!r}") from exc


def collect_runs(paths: Iterable[Path], backend: Optional[str] = None,
                 since: Optional[str] = None) -> List[RunMetrics]:
    """Đo mọi thư mục lượt trong các runs_dir, đã lọc backend/since."""
    day_limit = _since_date(since)
    found: List[RunMetrics] = []
    seen: set[Path] = set()
    for raw in paths:
        root = Path(raw).expanduser()
        for run_dir in _discover(root):
            key = run_dir.resolve()
            if key in seen:
                continue
            seen.add(key)
            run = _measure_run(run_dir)
            if backend and run.backend != backend:
                continue
            if day_limit is not None and (run.date is None or run.date < day_limit):
                continue
            found.append(run)
    return sorted(found, key=lambda run: (run.name, str(run.path)))


def _percent(test_lines: int, code_lines: int) -> str:
    total = test_lines + code_lines
    return f"{100.0 * test_lines / total:.1f}%" if total else NO_VALUE


def _seconds(value: Optional[float]) -> str:
    return NO_VALUE if value is None else f"{value:.1f}"


def _version_key(version: str) -> Tuple[bool, str]:
    return version == UNKNOWN, version


def _group_table(runs: Sequence[RunMetrics]) -> List[str]:
    groups: Dict[str, List[RunMetrics]] = {}
    for run in runs:
        groups.setdefault(run.version, []).append(run)
    if not groups:
        return []
    out = ["## Gộp theo plugin_version", "",
           "| version | lượt | test | code | docs | % test | TB test | trung vị test |",
           "|---|---|---|---|---|---|---|---|"]
    for version in sorted(groups, key=_version_key):
        rows = groups[version]
        test_lines = sum(row.test_lines for row in rows)
        code_lines = sum(row.code_lines for row in rows)
        docs_lines = sum(row.docs_lines for row in rows)
        tests = [row.test_lines for row in rows]
        mean = sum(tests) / len(tests)
        median = statistics.median(tests)
        out.append(f"| {version} | {len(rows)} | {test_lines} | {code_lines} | "
                   f"{docs_lines} | {_percent(test_lines, code_lines)} | "
                   f"{mean:.1f} | {median:.1f} |")
    return out


def format_report(runs: Sequence[RunMetrics]) -> str:
    """Bảng theo lượt và phần gộp theo plugin_version."""
    if not runs:
        return "Không có lượt nào khớp bộ lọc."
    out = ["## Theo lượt", "",
           "| lượt | version | backend | test | code | docs | % test | "
           "lệnh test | giây test | giây lượt |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for run in runs:
        out.append(
            f"| {run.name} | {run.version} | {run.backend} | {run.test_lines} | "
            f"{run.code_lines} | {run.docs_lines} | "
            f"{_percent(run.test_lines, run.code_lines)} | {run.test_commands} | "
            f"{_seconds(run.test_seconds)} | {_seconds(run.seconds)} |")
    grouped = _group_table(runs)
    if grouped:
        out += ["", *grouped]
    return "\n".join(out)
