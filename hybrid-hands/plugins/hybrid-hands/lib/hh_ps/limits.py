"""Plan limit rows for `hh-ps`: account total, this machine and the rest.

Claude rows use the statusline plugin's weekly formulas, ported in ``week.py``.
The GPT rows are account samples from `~/.codex-hand` (ledger or rollout), kept as
5h and weekly windows with no machine/other split. The 5-hour and monthly Claude
windows are deliberately not exposed.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Mapping, Optional

from hand_ext.config import ExtConfig, load_config

from .codex import PLAN_GPT, WINDOW_5H, GptWindow
from .constants import STATE_DIR_DEFAULT, STATE_DIR_ENV
from .models import Limit
from .week import ClaudeWeek, LIVE_SOURCE, WEEK_SPLIT_SOURCE, read_claude_week

PLAN_CLAUDE = "Claude"
WEEK_WINDOW = "tuần"
SOURCE_CLAUDE_SPLIT = "statusline_cache+week_split"
SOURCE_CLAUDE_LIVE = "rate_limit_event"
SOURCE_CLAUDE = "statusline_cache"


def load_hand_ext_config(root: Path) -> Optional[ExtConfig]:
    """The hand-ext config for this repo, or None when it is absent/corrupt."""
    try:
        return load_config(root)
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def _state_dir(cfg: Optional[ExtConfig]) -> Path:
    if cfg is not None:
        return cfg.machine_state_dir
    return Path(os.path.expanduser(os.environ.get(STATE_DIR_ENV) or STATE_DIR_DEFAULT))


def _claude_source(week: ClaudeWeek) -> str:
    """The week's own source, with internal names mapped to hh-ps' JSON names."""
    source = week.source or SOURCE_CLAUDE
    if source.startswith(WEEK_SPLIT_SOURCE):
        source = SOURCE_CLAUDE_SPLIT + source[len(WEEK_SPLIT_SOURCE):]
    elif source.startswith(LIVE_SOURCE):
        source = SOURCE_CLAUDE_LIVE + source[len(LIVE_SOURCE):]
    return source


def _claude_limit(week: ClaudeWeek) -> Limit:
    return Limit(plan=PLAN_CLAUDE, window=WEEK_WINDOW,
                 this_machine_pct=week.this_machine_pct, other_pct=week.other_pct,
                 total_pct=week.total_pct, resets_at=week.resets_at,
                 source=_claude_source(week), estimated=week.estimated)


def _gpt_limits(windows: Optional[Mapping[str, GptWindow]], now: float) -> List[Limit]:
    """Account GPT samples: 5h then weekly, only windows that are still running."""
    rows: List[Limit] = []
    for label in (WINDOW_5H, WEEK_WINDOW):
        sample = (windows or {}).get(label)
        if sample is None or not sample.usable(now):
            continue
        rows.append(Limit(plan=PLAN_GPT, window=label,
                          this_machine_pct=None, other_pct=None,
                          total_pct=sample.pct, resets_at=sample.resets_at,
                          source=sample.source, estimated=False))
    return rows


def collect_limits(root: Path, now: float, env: Optional[Mapping[str, str]] = None,
                   cfg: Optional[ExtConfig] = None,
                   claude_week: Optional[ClaudeWeek] = None,
                   codex_windows: Optional[Mapping[str, GptWindow]] = None
                   ) -> List[Limit]:
    """Claude weekly and GPT 5h/weekly rows; absent sources are omitted."""
    environment = os.environ if env is None else env
    cfg = cfg if cfg is not None else load_hand_ext_config(root)
    home = Path(os.path.expanduser(
        environment.get("CLAUDE_HOME") or environment.get("CLAUDE_CONFIG_DIR")
        or "~/.claude"))
    if claude_week is None:
        claude_week = read_claude_week(home, now)
    limits: List[Limit] = []
    if claude_week is not None and claude_week.total_pct is not None:
        limits.append(_claude_limit(claude_week))
    limits.extend(_gpt_limits(codex_windows, now))
    return limits
