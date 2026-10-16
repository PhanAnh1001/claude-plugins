"""Build the traceability report (ID -> task -> test) from a ScanResult (used by trace_check.py).

Errors (make trace_check exit 1): required task/test link missing, ID defined more than once.
Warnings (exit code unaffected): orphan references, malformed IDs, waivers for unknown IDs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trace_scan import ScanResult


@dataclass
class TaskLink:
    task_id: str
    done: bool


@dataclass
class TraceRow:
    id: str
    id_type: str
    defined_at: list[str]
    tasks: list[TaskLink]
    tests: list[str]
    missing_task: bool
    missing_test: bool
    waiver: str | None = None  # reason when the ID is exempt from required links


@dataclass
class TraceReport:
    rows: list[TraceRow]
    orphans: dict[str, list[str]] = field(default_factory=dict)
    duplicates: dict[str, list[str]] = field(default_factory=dict)
    malformed: list[tuple[str, str]] = field(default_factory=list)  # (text, file:line)
    unknown_waivers: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    require_task_types: list[str] = field(default_factory=list)
    require_test_types: list[str] = field(default_factory=list)

    @property
    def missing_task(self) -> list[str]:
        return [row.id for row in self.rows if row.missing_task]

    @property
    def missing_test(self) -> list[str]:
        return [row.id for row in self.rows if row.missing_test]

    @property
    def waived(self) -> dict[str, str]:
        return {row.id: row.waiver for row in self.rows if row.waiver is not None}

    @property
    def errors(self) -> list[str]:
        errors = [f"{i} defined more than once: {', '.join(locs)}" for i, locs in self.duplicates.items()]
        errors += [f"{i} has no task (require_task_types)" for i in self.missing_task]
        errors += [f"{i} has no test (require_test_types)" for i in self.missing_test]
        return errors

    @property
    def ok(self) -> bool:
        return not self.missing_task and not self.missing_test and not self.duplicates

    def count_by_type(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.rows:
            counts[row.id_type] = counts.get(row.id_type, 0) + 1
        return counts


def id_type_of(id_value: str) -> str:
    return id_value.split("-", 1)[0]


def _tasks_by_id(scan: ScanResult) -> dict[str, list[TaskLink]]:
    tasks: dict[str, list[TaskLink]] = {}
    for task in scan.tasks:
        for covered in task.covers:
            tasks.setdefault(covered, []).append(TaskLink(task.task_id, task.done))
    return tasks


def _build_rows(scan: ScanResult, trace: dict[str, Any]) -> list[TraceRow]:
    waivers: dict[str, str] = trace["waivers"]
    tasks_by_id = _tasks_by_id(scan)
    rows = []
    for id_value in sorted(scan.definitions):
        id_type = id_type_of(id_value)
        tasks = tasks_by_id.get(id_value, [])
        tests = sorted(scan.tests.get(id_value, set()))
        waiver = waivers.get(id_value)
        enforced = waiver is None
        rows.append(TraceRow(
            id=id_value,
            id_type=id_type,
            defined_at=[str(loc) for loc in scan.definitions[id_value]],
            tasks=tasks,
            tests=tests,
            missing_task=enforced and id_type in trace["require_task_types"] and not tasks,
            missing_test=enforced and id_type in trace["require_test_types"] and not tests,
            waiver=waiver,
        ))
    return rows


def _warnings(report: TraceReport) -> list[str]:
    warnings = [f"orphan {i} referenced at {', '.join(locs)}" for i, locs in report.orphans.items()]
    warnings += [f"malformed ID {text!r} at {location}" for text, location in report.malformed]
    warnings += [f"waiver for unknown ID {i} ({reason})" for i, reason in report.unknown_waivers.items()]
    return warnings


def build_report(scan: ScanResult, trace: dict[str, Any]) -> TraceReport:
    """`trace` is the merged [trace] config section."""
    report = TraceReport(
        rows=_build_rows(scan, trace),
        orphans={
            id_value: [str(loc) for loc in locations]
            for id_value, locations in sorted(scan.references.items())
            if id_value not in scan.definitions
        },
        duplicates={
            id_value: [str(loc) for loc in locations]
            for id_value, locations in sorted(scan.definitions.items()) if len(locations) > 1
        },
        malformed=[(item.text, str(item.location)) for item in scan.malformed],
        unknown_waivers={
            id_value: reason for id_value, reason in sorted(trace["waivers"].items())
            if id_value not in scan.definitions
        },
        require_task_types=list(trace["require_task_types"]),
        require_test_types=list(trace["require_test_types"]),
    )
    report.warnings = _warnings(report)
    return report
