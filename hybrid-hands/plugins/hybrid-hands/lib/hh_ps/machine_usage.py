"""Whole-machine weekly estimates, independent of the visible project tree."""
from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from hand_ext.codex_usage import price_for
from hand_ext.go_usage import estimate_cost
from usage_pricing import explicit_options

from .codex import _contained
from .native_source import _records
from .timeutil import to_epoch
from .week import _usd_since

WEEK = 7 * 86400
TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens")


def _total(payload):
    info = payload.get("info")
    raw = info.get("total_token_usage") if isinstance(info, dict) else None
    if not isinstance(raw, dict) or not all(isinstance(raw.get(k), int)
            and not isinstance(raw[k], bool) and raw[k] >= 0 for k in TOKEN_KEYS):
        return None
    values = tuple(raw[k] for k in TOKEN_KEYS)
    return values if values[1] <= values[0] else None


def _machine_rollouts(home):
    """Fail closed on an unreadable or escaping source, including archived files."""
    if home.is_symlink():
        raise OSError("unsafe rollout home")
    resolved_home = home.resolve(strict=True)
    paths = set()
    for name in ("sessions", "archived_sessions"):
        candidate = home / name
        try:
            candidate.lstat()
        except FileNotFoundError:
            continue
        root = candidate.resolve(strict=True)
        if resolved_home not in root.parents or not root.is_dir():
            raise OSError("unsafe rollout root")
        def onerror(error):
            raise error
        for directory, dirs, files in os.walk(root, onerror=onerror):
            directory = Path(directory)
            # os.walk skips directory symlinks. Do not report a partial total.
            if any((directory / child).is_symlink() for child in dirs):
                raise OSError("unscanned rollout directory")
            for filename in files:
                if not filename.startswith("rollout-") or not filename.endswith(".jsonl"):
                    continue
                path = _contained(root, directory / filename)
                if path is None or not path.stat().st_mode & (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH):
                    raise OSError("unreadable rollout")
                paths.add(path)
    return sorted(paths)


def _gpt_usd(codex, cfg, start, now):
    # Files can repeat one resumed thread. Merge its metadata records before taking
    # deltas, never add ledger costs to these same rollout totals.
    threads = {}
    try:
        sources = [(path, list(_records(path, token_only=True, strict=True)))
                   for path in _machine_rollouts(codex.home)]
    except (OSError, RuntimeError, ValueError):
        return None
    for path, records in sources:
        sid = next((str(p.get("id") or "") for kind, p, _ in records
                    if kind == "session_meta"), "")
        if not sid:
            return None
        merged = threads.setdefault(sid, {})
        for record in records:
            merged[json.dumps(record, sort_keys=True)] = record
    if not threads:
        return None
    total_usd = 0.0
    for merged in threads.values():
        records = list(merged.values())
        born = next((to_epoch(p.get("timestamp")) or at for kind, p, at in records
                     if kind == "session_meta"), None)
        undated_models = {str(p.get("model")) for kind, p, stamp in records
                          if kind in ("session_meta", "turn_context")
                          and stamp is None and p.get("model")}
        if len(undated_models) > 1:
            return None
        model = ""
        previous = None
        seen_tokens = False
        # Metadata without a timestamp precedes events, preserving file order for ties.
        for kind, p, stamp in sorted(records, key=lambda row: row[2] if row[2] is not None else float("-inf")):
            if kind in ("session_meta", "turn_context"):
                model = str(p.get("model") or model)
                continue
            if stamp is None:
                return None
            if stamp > now:
                continue
            current = _total(p)
            if stamp < start:
                previous = current
                continue
            seen_tokens = True
            if current is None or (previous is None and (born is None or born < start)):
                return None
            decreases = previous is not None and any(a < b for a, b in zip(current, previous))
            if decreases and any(a > b for a, b in zip(current, previous)):
                return None
            delta = (current if previous is None or decreases
                     else tuple(a - b for a, b in zip(current, previous)))
            if delta[1] > delta[0]:
                return None
            previous = current
            if not any(delta):
                continue
            cost = estimate_cost(dict(zip(("input", "cached_input", "output"), delta)),
                                 price_for(explicit_options(cfg, "codex"), model))
            if cost is None:
                return None
            total_usd += cost
        recent_metadata = any(kind == "turn_context" and stamp is not None
                              and start <= stamp <= now for kind, _, stamp in records)
        if not seen_tokens and (born is None or start <= born <= now or recent_metadata):
            return None
    return round(total_usd, 8)


def machine_usage(home, claude_week, codex, cfg, now):
    claude_usd = None
    if (claude_week is not None and claude_week.source
            and claude_week.resets_at is not None and claude_week.resets_at > now
            and claude_week.window_start <= now < claude_week.window_start + WEEK):
        claude_usd = _usd_since(home, claude_week.window_start, now)
    gpt_usd = None
    window = codex.account.get("tuần")
    if window is not None and window.usable(now) and window.resets_at - WEEK <= now:
        gpt_usd = _gpt_usd(codex, cfg, window.resets_at - WEEK, now)
    return [{"plan": "Claude", "window": "tuần", "usd": claude_usd,
             "source": "claude_machine_week"},
            {"plan": "GPT", "window": "tuần", "usd": gpt_usd,
             "source": "codex_rollout_deltas"}]
