"""Sandbox facts shared by hand backends that run below Codex's seatbelt.

Codex marks child processes with CODEX_SANDBOX=seatbelt. macOS refuses to nest a second
sandbox-exec below seatbelt, so a backend asked for workspace-write must run unconfined and
let the outer seatbelt limit writes. Read-only cannot be guaranteed there and is refused.
"""
from __future__ import annotations

import json
import os

from .base import RunSpec

OUTER_SANDBOX_ENV = "CODEX_SANDBOX"
OUTER_SANDBOX_SEATBELT = "seatbelt"
SANDBOX_READ_ONLY = "read-only"
SANDBOX_WORKSPACE_WRITE = "workspace-write"
SANDBOX_DANGER_FULL_ACCESS = "danger-full-access"
META_FILE = "meta.json"


def in_codex_seatbelt() -> bool:
    """True when this process (and its children) run below Codex's seatbelt sandbox."""
    return os.environ.get(OUTER_SANDBOX_ENV) == OUTER_SANDBOX_SEATBELT


def record_sandbox(spec: RunSpec, mode: str, requested: str, reason: str,
                   refused: bool = False) -> None:
    """Put the effective sandbox mode and why it changed into the run's meta.json."""
    path = spec.run_dir / META_FILE
    spec.run_dir.mkdir(parents=True, exist_ok=True)
    meta = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if not isinstance(meta, dict):
        raise ValueError(f"{path} phải chứa một JSON object")
    meta["sandbox_mode"] = mode
    meta["sandbox_requested"] = requested
    meta["sandbox_reason"] = reason
    if refused:
        meta["sandbox_refused"] = True
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
