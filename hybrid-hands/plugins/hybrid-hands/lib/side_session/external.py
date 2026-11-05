"""Read `hand-ext` run registry entries that belong to an external side session.

Tokens follow the existing Claude counter: `input` includes cache reads in the hand-ext
`Usage` model, so subtract `cached_input` and add `output` (cache writes stay counted, as
Claude's `cache_creation_input_tokens` are). The registry is imported read-only through
`hh_ps.registry_source` (lazy import: that module imports `side_session.state` back).
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

from . import constants as C
from .state import SessionState

if TYPE_CHECKING:
    from hh_ps.models import HandRun


def _source() -> ModuleType:
    from hh_ps import registry_source
    return registry_source


def accepted_labels(name: str) -> tuple[str, str]:
    """Contract label `side:<name>`, plus the `side-<name>` hand-ext writes after sanitising."""
    return (f"{C.EXT_LABEL_PREFIX}{name}", f"{C.EXT_LABEL_SANITIZED_PREFIX}{name}")


def run_for(st: SessionState) -> HandRun | None:
    """Newest hand-ext run labelled for this session and started at/after `state.started`."""
    # RunRegistry writes `started` as ISO-8601 with second precision, so compare seconds:
    # a fractional state.started must not discard the run launched right after it.
    cutoff = int(st.started)
    source = _source()
    runs = source.load_hand_runs(source.state_root(), cutoff)
    wanted = set(accepted_labels(st.name))
    hits = [run for run in runs if run.label in wanted
            and run.started_at is not None and run.started_at >= cutoff]
    return max(hits, key=lambda run: (run.started_at, run.run_id)) if hits else None


def tokens_used(run: HandRun) -> int:
    total_input = max(0, int(run.tokens.get("input") or 0))
    cached = max(0, int(run.tokens.get("cached_input") or 0))
    return max(0, total_input - cached) + max(0, int(run.tokens.get("output") or 0))


def run_dir(run: HandRun) -> Path | None:
    source = _source()
    path = source.state_root() / source.RUNS_SUBDIR / f"{run.run_id}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    raw = data.get("run_dir") if isinstance(data, dict) else None
    return Path(str(raw)) if raw else None


def copy_report(run: HandRun, handoff: Path) -> bool:
    """Copy the run's report.md to the handoff path unless a handoff already exists."""
    if handoff.exists():
        return False
    folder = run_dir(run)
    report = folder / C.EXT_REPORT_FILE if folder is not None else None
    if report is None or not report.is_file():
        return False
    handoff.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(report, handoff)
    return True


def final_status(run: HandRun) -> str:
    return C.STATUS_STOPPED if run.status == C.HAND_RUN_STATUS_OK else C.STATUS_DEAD
