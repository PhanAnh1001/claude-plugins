"""Run the `paseo` CLI by name through PATH; parse its JSON without shell."""
from __future__ import annotations

import json
import shlex
import subprocess
from typing import Dict, List, Optional

from .constants import (
    EXIT_PASEO, PASEO_TIMEOUT_SECONDS, SHORT_ERROR_MAX_CHARS,
)
from .errors import CcSwitchError


class PaseoError(CcSwitchError):
    def __init__(self, message: str) -> None:
        super().__init__(message, EXIT_PASEO)


def _run(args: List[str], timeout: Optional[int]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["paseo", *args], capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except FileNotFoundError as exc:
        raise PaseoError("không tìm thấy lệnh `paseo` trong PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise PaseoError(f"`paseo {args[0]}` quá thời gian chờ") from exc
    except OSError as exc:
        raise PaseoError(f"không chạy được `paseo`: {exc}") from exc


def _short(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    return lines[-1][:SHORT_ERROR_MAX_CHARS]


def _check(result: subprocess.CompletedProcess, action: str) -> None:
    if result.returncode == 0:
        return
    detail = _short(result.stderr) or _short(result.stdout)
    suffix = f": {detail}" if detail else ""
    raise PaseoError(f"`paseo {action}` lỗi (mã {result.returncode}){suffix}")


def command_line(args: List[str]) -> str:
    return shlex.join(["paseo", *args])


def extract_json(text: str, opener: str):
    start = (text or "").find(opener)
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    except ValueError:
        return None
    return value


def wait(agent_id: str) -> None:
    """Wait without a timeout: the user explicitly wants the agent to go idle."""
    result = _run(["wait", agent_id], None)
    _check(result, "wait")


def reload_agent(agent_id: str) -> None:
    result = _run(["agent", "reload", agent_id], PASEO_TIMEOUT_SECONDS)
    _check(result, "agent reload")


def import_session(session_id: str, cwd: str) -> str:
    result = _run(["import", session_id, "--provider", "claude",
                   "--cwd", cwd, "--json"], PASEO_TIMEOUT_SECONDS)
    _check(result, "import")
    data = extract_json(result.stdout, "{")
    if not isinstance(data, dict):
        raise PaseoError("`paseo import` không trả JSON có agentId")
    agent_id = data.get("agentId")
    if not isinstance(agent_id, str) or not agent_id:
        raise PaseoError("`paseo import` không trả agentId")
    return agent_id


def statuses() -> Dict[str, str]:
    result = _run(["ls", "--json"], PASEO_TIMEOUT_SECONDS)
    _check(result, "ls")
    data = extract_json(result.stdout, "[")
    if not isinstance(data, list):
        return {}
    found: Dict[str, str] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        agent_id = item.get("id")
        status = item.get("status")
        if isinstance(agent_id, str) and isinstance(status, str):
            found[agent_id] = status
    return found
