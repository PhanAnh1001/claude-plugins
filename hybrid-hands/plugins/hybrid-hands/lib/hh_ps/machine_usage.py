"""Whole-machine weekly estimates, independent of the visible project tree."""
from __future__ import annotations

import json
import os
import sqlite3
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
    _forget_unlisted(home, paths)
    return sorted(paths)


def _forget_unlisted(home, paths):
    """A moved/deleted rollout keeps no stored records under its old path."""
    from hh_store import codex_ingest
    for scope in (codex_ingest.SCOPE_SESSIONS, codex_ingest.SCOPE_ARCHIVED):
        codex_ingest.forget(scope, [p for p in paths if codex_ingest.scope_for(p) == scope])


_ROLLOUT_ERRORS = (OSError, RuntimeError, ValueError)


def _sid(records):
    return next((str(p.get("id") or "") for kind, p, _ in records
                 if kind == "session_meta"), "")


def _load(path):
    return list(_records(path, token_only=True, strict=True))


def _merge(records_by_file):
    """Files can repeat one resumed thread: one record per distinct value, first order kept."""
    merged = {}
    for records in records_by_file:
        for record in records:
            merged[json.dumps(record, sort_keys=True)] = record
    return list(merged.values())


class _Pricer:
    """Delta -> USD; options read lazily, one price lookup per model per call."""

    def __init__(self, cfg, options=None):
        self._cfg, self._options, self._prices = cfg, options, {}

    def cost(self, delta, model):
        if self._options is None:
            self._options = explicit_options(self._cfg, "codex")
        if model not in self._prices:
            self._prices[model] = price_for(self._options, model)
        return estimate_cost(dict(zip(("input", "cached_input", "output"), delta)),
                             self._prices[model])


def _thread_outcome(records, start, now, pricer):
    """(costs in add order, observed) for one thread, or None if the whole total is unknown."""
    if not any(kind == "event_msg" for kind, _, _ in records):
        return [], False
    born = next((to_epoch(p.get("timestamp")) or at for kind, p, at in records
                 if kind == "session_meta"), None)
    undated_models = {str(p.get("model")) for kind, p, stamp in records
                      if kind in ("session_meta", "turn_context")
                      and stamp is None and p.get("model")}
    if len(undated_models) > 1:
        return None
    model = ""
    previous = None
    costs, observed = [], False
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
        observed = True
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
        cost = pricer.cost(delta, model)
        if cost is None:
            return None
        costs.append(cost)
    return costs, observed


def _sum(outcomes):
    """Same float add order as one running total over threads in first-seen order."""
    total_usd = 0.0
    observed = False
    for outcome in outcomes:
        if outcome is None:
            return None
        costs, seen = outcome
        observed = observed or seen
        for cost in costs:
            total_usd += cost
    return round(total_usd, 8) if observed else None


def _threads(paths, sid_of):
    """sid -> its files in sorted path order; dict order = first file of each thread."""
    groups = {}
    for path in paths:
        groups.setdefault(sid_of[path], []).append(path)
    return groups


def _legacy_gpt_usd(paths, cfg, start, now):
    try:
        loaded = {path: _load(path) for path in paths}
    except _ROLLOUT_ERRORS:
        return None
    sids = {path: _sid(records) for path, records in loaded.items()}
    if not paths or not all(sids.values()):
        return None
    pricer = _Pricer(cfg)
    return _sum(_thread_outcome(_merge(loaded[p] for p in files), start, now, pricer)
                for files in _threads(paths, sids).values())


# Cross-process cache in the hh-store: per file (stamp -> sid) and per thread
# (file stamps + start + options + prices -> outcome). Bump to drop old rows.
_CACHE_VERSION = 1
_NO_CACHE = object()
_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS gpt_usd_files(path TEXT PRIMARY KEY, stamp TEXT, sid TEXT);
CREATE TABLE IF NOT EXISTS gpt_usd_threads(sid TEXT PRIMARY KEY, key TEXT,
    max_stamp REAL, outcome TEXT);
"""


def _file_stamp(path):
    st = os.stat(path)
    return json.dumps([st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino])


def _base_key(options, start):
    from usage_pricing import load_prices
    return json.dumps([_CACHE_VERSION, start, options, load_prices()],
                      sort_keys=True, default=repr)


def _max_stamp(records):
    return max((stamp for _, _, stamp in records if stamp is not None), default=None)


def _store_conn():
    from hh_store import runtime
    return runtime.connection() if runtime.enabled() else None


def _cached_gpt_usd(paths, cfg, start, now):
    """Same total as the legacy path; _NO_CACHE when the store or config is unusable."""
    conn = _store_conn()
    if conn is None:
        return _NO_CACHE
    try:
        options = explicit_options(cfg, "codex")
        base = _base_key(options, start)
    except Exception:  # noqa: BLE001 - the legacy path raises or answers the same way
        return _NO_CACHE
    try:
        return _from_cache(conn, paths, _Pricer(cfg, options), base, start, now)
    except sqlite3.Error as exc:
        from hh_store import runtime
        runtime.disable_after_error(exc)
        return _NO_CACHE


def _from_cache(conn, paths, pricer, base, start, now):
    conn.executescript(_CACHE_SCHEMA)
    known = dict(((p, (st, sid)) for p, st, sid in
                  conn.execute("SELECT path, stamp, sid FROM gpt_usd_files")))
    saved = {sid: (key, top, outcome) for sid, key, top, outcome in
             conn.execute("SELECT sid, key, max_stamp, outcome FROM gpt_usd_threads")}
    loaded, sids, stamps = {}, {}, {}
    try:
        for path in paths:
            stamps[path] = _file_stamp(path)
            row = known.get(str(path))
            if row is not None and row[0] == stamps[path]:
                sids[path] = row[1]
                continue
            loaded[path] = _load(path)
            sids[path] = _sid(loaded[path])
    except _ROLLOUT_ERRORS:
        return None
    file_rows = [(str(p), stamps[p], sids[p]) for p in paths]
    thread_rows, outcomes, stale = [], [], []
    if paths and all(sids.values()):
        for sid, files in _threads(paths, sids).items():
            key = json.dumps([base, [(str(p), stamps[p]) for p in files]])
            row = saved.get(sid)
            if row is not None and row[0] == key and (row[1] is None or row[1] <= now):
                outcomes.append(json.loads(row[2]))
                continue
            try:
                records = _merge(loaded[p] if p in loaded else _load(p) for p in files)
            except _ROLLOUT_ERRORS:
                return None
            outcome = _thread_outcome(records, start, now, pricer)
            outcomes.append(outcome)
            top = _max_stamp(records)
            if top is None or top <= now:  # later events would change a reused outcome
                thread_rows.append((sid, key, top, json.dumps(outcome)))
            else:
                stale.append((sid,))
    with conn:
        conn.execute("DELETE FROM gpt_usd_files")
        conn.executemany("INSERT INTO gpt_usd_files VALUES(?, ?, ?)", file_rows)
        conn.executemany("INSERT OR REPLACE INTO gpt_usd_threads VALUES(?, ?, ?, ?)", thread_rows)
        live = set(sids.values())
        stale += [(sid,) for sid in saved if sid not in live]
        conn.executemany("DELETE FROM gpt_usd_threads WHERE sid=?", stale)
    return _sum(outcomes) if outcomes else None


def _gpt_usd(codex, cfg, start, now):
    # Never add ledger costs to these same rollout totals.
    try:
        paths = _machine_rollouts(codex.home)
    except _ROLLOUT_ERRORS:
        return None
    result = _cached_gpt_usd(paths, cfg, start, now)
    return _legacy_gpt_usd(paths, cfg, start, now) if result is _NO_CACHE else result


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
             "source": "codex_rollout_observed_deltas"}]
