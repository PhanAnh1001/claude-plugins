"""Read-only hh-ps adapter; no transcript, credentials or pricing access here."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime
from uuid import UUID

TIMEOUT_SECONDS = 2
UNKNOWN = "?"


def executable() -> Path | None:
    override = os.environ.get("HYBRID_HANDS_HH_PS")
    if override:
        candidates = [Path(override)]
    else:
        repo = Path(__file__).resolve().parents[4]
        source = repo / "hybrid-hands/plugins/hybrid-hands/bin/hh-ps"
        cache = Path(os.environ.get("CLAUDE_HOME", str(Path.home() / ".claude"))) / "plugins/cache"
        installed = list(cache.glob("*/hybrid-hands/*/bin/hh-ps"))
        candidates = [source] + sorted(installed, key=version_key, reverse=True)
    return next((p for p in candidates if p.is_file() and os.access(p, os.X_OK)), None)


def version_key(path: Path) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", path.parent.parent.name))


def clean(value: object) -> str:
    return " ".join("".join(c if c.isprintable() else " " for c in str(value or "")).split())


def number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def percent(value: object) -> str:
    n = number(value)
    return UNKNOWN if n is None else f"{n:g}%"


def moment(value: object) -> str:
    if not value:
        return UNKNOWN
    try:
        dt = (datetime.fromtimestamp(value).astimezone() if number(value) is not None else
              datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone())
        return dt.strftime("%d/%m %H:%M:%S")
    except (ValueError, TypeError, OverflowError, OSError):
        return UNKNOWN


def row(item: dict, kind: str, label: object, prefix: str) -> str:
    usage = item.get("usage") or {}
    usd = number(usage.get("usd"))
    cost = "~$?" if usd is None else f"~${usd:.4f}"
    duration = number(item.get("duration_seconds"))
    elapsed = UNKNOWN if duration is None else f"{max(0, int(duration))}s"
    lost = item.get("state") == "lost"
    running = not lost and (item.get("live") is True or item.get("status") in ("running", "silent"))
    if lost and not item.get("ended_at"):
        elapsed = UNKNOWN
    ended = "đang chạy" if running else moment(item.get("ended_at"))
    five = usage.get("account_5h_pct")
    week = usage.get("account_week_pct")
    if five is None:
        five = usage.get("gpt_5h_pct")
    if week is None:
        week = usage.get("gpt_week_pct")
    own_label = "riêng (đo)" if (number(usage.get("week_pct")) is not None and
                                    usage.get("week_pct_source") == "codex_rate_limits_delta") else "riêng"
    plan = clean(usage.get("account_plan")) or ("GPT" if item.get("provider") == "codex" or item.get("backend") == "codex" else UNKNOWN)
    fields = [f"{prefix}{clean(kind)} {clean(label)}", f"model:{clean(item.get('model')) or UNKNOWN}",
              f"effort:{clean(item.get('effort')) or UNKNOWN}", cost,
              f"account:{clean(usage.get('account_plan')) or UNKNOWN}",
              f"5h:{percent(five)}", f"tuần:{percent(week)}",
              f"{plan} {own_label} {percent(usage.get('week_pct'))} tuần", f"ended:{ended}", f"elapsed:{elapsed}"]
    return " | ".join(fields)


def render(snapshot: dict, sid: str) -> list[str]:
    sessions = snapshot.get("sessions") or []
    by_id = {s.get("session_id"): s for s in sessions if isinstance(s, dict)}
    if sid not in by_id:
        return []
    lines: list[str] = []
    seen: set[str] = set()

    def visit(session_id: str, depth: int) -> None:
        if session_id in seen:
            return
        seen.add(session_id)
        session = by_id[session_id]
        prefix = "▶︎ " if depth == 0 else "· " + "↳" * depth + " "
        lines.append(row(session, f"session/{session.get('provider') or UNKNOWN}",
                         session.get("name") or session_id[:8], prefix))
        child_prefix = "· " + "↳" * (depth + 1) + " "
        for agent in session.get("subagents") or []:
            lines.append(row(agent, f"subagent/{agent.get('agent_type') or UNKNOWN}",
                             agent.get("agent_id", ""), child_prefix))
        for run in session.get("hand_runs") or []:
            lines.append(row(run, f"hand-ext/{run.get('backend') or UNKNOWN}",
                             run.get("label") or run.get("run_id"), child_prefix))
        for child_id, child in by_id.items():
            if child.get("parent_session") == session_id:
                visit(child_id, depth + 1)

    visit(sid, 0)
    return lines


def main() -> int:
    if os.environ.get("STATUSLINE_HANDS", "1") == "0" or len(sys.argv) < 2 or not sys.argv[1]:
        return 0
    path = executable()
    if path is None:
        return 0
    args = [str(path), "--json"]
    try:
        current = str(UUID(sys.argv[1]))
    except ValueError:
        current = ""
    if current:
        args += ["--main-session", current]
    if len(sys.argv) > 2 and sys.argv[2]:
        args += ["--cwd", sys.argv[2]]
    try:
        result = subprocess.run(args + ["--once"], capture_output=True, text=True,
                                timeout=TIMEOUT_SECONDS, check=False,
                                env=dict(os.environ, HYBRID_HANDS_CALIBRATION_CACHE_ONLY="1"))
        if result.returncode and "unrecognized arguments: --once" in result.stderr:
            result = subprocess.run(args, capture_output=True, text=True,
                                    timeout=TIMEOUT_SECONDS, check=False,
                                env=dict(os.environ, HYBRID_HANDS_CALIBRATION_CACHE_ONLY="1"))
        if result.returncode:
            return 0
        snapshot = json.loads(result.stdout)
        lines = render(snapshot, sys.argv[1])
        if lines:
            print("\n".join(lines))
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError, AttributeError, KeyError):
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
