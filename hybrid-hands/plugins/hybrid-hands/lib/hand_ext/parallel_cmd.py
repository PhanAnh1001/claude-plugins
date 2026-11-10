"""Inspect or atomically change the repository parallel policy opt-in."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from shared_config import ConfigResult, load_config

POLICY_SECTION = "parallel_subagents"
POLICY_KEY = f"{POLICY_SECTION}.enabled"
NEW_SESSION = "mở phiên mới để hook nạp luật"
DEFAULT_FILE = Path(__file__).resolve().parents[1] / "shared_config.py"


def _read_repository(path: Path) -> dict:
    """Read raw bytes separately: the effective loader normalizes invalid sections."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ValueError(f"{path}: JSON không hợp lệ") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root phải là object")
    if POLICY_SECTION in data and not isinstance(data[POLICY_SECTION], dict):
        raise ValueError(f"{path}: {POLICY_SECTION} phải là object")
    return data


def _write_repository(path: Path, enabled: bool) -> None:
    data = _read_repository(path)
    section = data.setdefault(POLICY_SECTION, {})
    section["enabled"] = enabled
    content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _status(result: ConfigResult) -> dict:
    source = result.sources[POLICY_KEY]
    return {
        POLICY_SECTION: result.effective[POLICY_SECTION]["enabled"],
        "source": "default" if source == "plugin" else source,
        "file": str(DEFAULT_FILE) if source == "plugin" else result.paths[source]["path"],
    }


def command(args: argparse.Namespace) -> int:
    result = load_config(Path(args.cwd) if args.cwd else None)
    written = None
    if args.action is not None:
        written = Path(result.paths["repo"]["path"])
        _write_repository(written, args.action == "on")
        # The only effective change is this repository leaf; retain loader provenance.
        result.effective[POLICY_SECTION]["enabled"] = args.action == "on"
        result.sources[POLICY_KEY] = "repo"
    payload = _status(result)
    if args.json:
        if written is not None:
            payload.update(written=str(written), reminder=NEW_SESSION)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        state = "on" if payload[POLICY_SECTION] else "off"
        print(f"parallel_subagents: {state} (nguồn: {payload['source']}, file: {payload['file']})")
        if written is not None:
            print(f"Đã ghi: {written}; {NEW_SESSION}")
    return 0
