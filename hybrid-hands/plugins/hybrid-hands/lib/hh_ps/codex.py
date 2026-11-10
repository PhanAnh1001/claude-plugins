"""Codex hand and Sol usage for `hh-ps`: ledger cost, pinned rollout tokens, GPT samples.

Only `~/.codex-hand` is read: the ledger records with that exact home name and
`<home>/sessions/rollout-*.jsonl`. Conversation records are never parsed: the raw
line header must be a standard `event_msg` envelope whose payload is `token_count`
before JSON decoding, then both types are checked again. Every path is resolved,
and both the sessions root and a pinned rollout must stay inside it (a symlink out
is ignored).

USD is re-estimated from the central table and the ledger/registry token totals.
An explicit backend price overrides the table; unknown models stay unknown.
GPT percentages are account samples, kept in their own Usage fields; they are never
derived from USD. Measured same-rollout weekly movement uses `week_pct`.
"""
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from hand_ext.codex_usage import price_for
from usage_pricing import explicit_options
from hand_ext.constants import CODEX_USAGE_LEDGER_NAME, DEFAULTS
from hand_ext.go_usage import estimate_cost
from side_session.state import load_all as load_side_states

from .constants import STATE_DIR_DEFAULT, STATE_DIR_ENV
from .models import Usage
from .registry_source import load_ps_config
from .timeutil import to_epoch

PLAN_GPT = "GPT"
WINDOW_5H = "5h"
WINDOW_WEEK = "tuần"
SOURCE_LEDGER = "codex_usage"
SOURCE_ROLLOUT = "codex_rollout"
HAND_HOME_NAME = ".codex-hand"
SESSIONS_SUBDIR = "sessions"
ROLLOUT_GLOB = "rollout-*.jsonl"
# A rollout envelope is exactly `{timestamp?, ordinal?, type: "event_msg", payload: {...}}`;
# numeric `ordinal` is metadata, and only a payload whose first key is
# `type: "token_count"` is usage, never chat.
_HEADER_META = (r'(?:"timestamp"\s*:\s*(?:"[^"]*"|-?\d+(?:\.\d+)?|null|true|false)\s*,\s*)?'
                r'(?:"ordinal"\s*:\s*-?\d+\s*,\s*)?')
EVENT_HEADER = re.compile(
    r'^\s*\{\s*' + _HEADER_META +
    r'"type"\s*:\s*"event_msg"\s*,\s*' + _HEADER_META +
    r'"payload"\s*:\s*\{\s*"type"\s*:\s*"token_count"\s*[,}]')
EVENT_RECORD = "event_msg"
TOKEN_RECORD = "token_count"
LEDGER_WINDOWS = ((WINDOW_5H, WINDOW_5H), ("7d", WINDOW_WEEK))
ROLLOUT_WINDOWS = ((WINDOW_5H, WINDOW_5H), ("7d", WINDOW_WEEK))


@dataclass(frozen=True)
class GptWindow:
    """One account sample: used percent and when that window resets."""
    pct: float
    resets_at: Optional[float]
    at: float
    source: str
    duration: float = 604800

    def usable(self, now: float) -> bool:
        return (self.resets_at is not None and self.resets_at > now
                and self.resets_at - self.duration <= self.at <= now)


@dataclass
class CodexData:
    """Codex facts read once per snapshot."""
    home: Path
    account: Dict[str, GptWindow]
    ledger: Dict[str, Dict[str, Any]]
    price: Optional[Dict[str, float]]
    price_options: dict = field(default_factory=dict)
    _sessions: Optional[Path] = field(default=None, repr=False)
    _rollouts: Dict[str, Tuple[Optional[dict], Dict[str, GptWindow]]] = field(
        default_factory=dict, repr=False)

    def sessions_root(self) -> Optional[Path]:
        if self._sessions is None:
            self._sessions = _sessions_root(self.home)
        return self._sessions

    def contained_rollout(self, raw: Any) -> Optional[Path]:
        """A pinned rollout only when it resolves inside `<home>/sessions`."""
        text = str(raw or "").strip()
        if not text:
            return None
        path = Path(os.path.expanduser(text))
        if not path.is_absolute():
            return None
        root = self.sessions_root()
        return None if root is None else _contained(root, path)

    def hand_usage(self, run_id: str, tokens: Mapping[str, Any],
                   now: float) -> Optional[Usage]:
        record = self.ledger.get(str(run_id))
        source_tokens = record.get("tokens") if record is not None else None
        if not tokens and isinstance(source_tokens, dict):
            tokens = source_tokens
        windows = _ledger_windows(record) if record is not None else {}
        if not tokens and not windows:
            return None
        model = str(record.get("model") or "") if record else ""
        usd = estimate_cost(dict(tokens), price_for(self.price_options, model))
        return _usage(tokens, windows, usd, now)

    def rollout_usage(self, raw: Any, now: float) -> Optional[Usage]:
        path = self.contained_rollout(raw)
        if path is None:
            return None
        key = str(path)
        if key not in self._rollouts:
            self._rollouts[key] = _read_rollout(path)
        tokens, windows = self._rollouts[key]
        if not tokens and not windows:
            return None
        priced = _priced_tokens(tokens)
        # Resolve the actual rollout model; a default model must not price an
        # unknown or missing one. Import locally to keep metadata parsing shared.
        from .native_source import _records
        model = ""
        for kind, payload, _ in _records(path, token_only=True):
            if kind in ("session_meta", "turn_context"):
                model = str(payload.get("model") or model)
        usd = estimate_cost(priced, price_for(self.price_options, model)) if tokens else None
        usage = _usage(priced, windows, usd, now)
        measured = rollout_week(path, now)
        return replace(usage, week_pct=measured,
                       week_pct_source="codex_rate_limits_delta" if measured is not None else "")


def _options(cfg: Any) -> Dict[str, Any]:
    if cfg is not None:
        try:
            return cfg.options("codex")
        except (AttributeError, TypeError):
            pass
    return dict(DEFAULTS["backends"]["codex"])


def codex_home(_cfg: Any) -> Path:
    """The fixed hand-only home: config `home` and `CODEX_HOME` can never redirect it."""
    return Path.home() / HAND_HOME_NAME


def state_dir(cfg: Any) -> Path:
    if cfg is not None:
        return Path(cfg.machine_state_dir)
    raw = os.environ.get(STATE_DIR_ENV) or STATE_DIR_DEFAULT
    return Path(os.path.expanduser(raw))


def _sessions_root(home: Path) -> Optional[Path]:
    try:
        # A hand home symlinked to another account must not lend that account's rollouts.
        if home.is_symlink():
            return None
        resolved_home = home.resolve(strict=True)
        root = (home / SESSIONS_SUBDIR).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not root.is_dir():
        return None
    # A symlinked sessions directory pointing outside the hand home is not read.
    if root != resolved_home and resolved_home not in root.parents:
        return None
    return root


def _contained(root: Path, path: Path) -> Optional[Path]:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if resolved != root and root not in resolved.parents:
        return None
    return resolved if resolved.is_file() else None


def _iter_json_lines(path: Path, strict: bool = False) -> Iterable[dict]:
    """Decode only standard `event_msg`/`token_count` envelopes, never conversation JSON."""
    from .native_source import _BAD_FLAG, _CODEX_FLAG, _PAYLOAD, stored_records
    try:
        stored = stored_records(path)
    except OSError:
        return
    if stored is None:
        yield from _iter_file_lines(path, strict)
        return
    for item in stored:
        data = item.data
        if not data.get(_CODEX_FLAG):
            continue
        if data.get(_BAD_FLAG):
            if strict:
                yield {}
            continue
        payload = data.get(_PAYLOAD)
        if item.kind != EVENT_RECORD or not isinstance(payload, dict) or payload.get("type") != TOKEN_RECORD:
            continue
        yield {"type": item.kind, "timestamp": item.observed_at, "payload": dict(payload)}


def _iter_file_lines(path: Path, strict: bool = False) -> Iterable[dict]:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if not EVENT_HEADER.match(line):
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    if strict:
                        yield {}
                    continue
                if not isinstance(record, dict) or record.get("type") != EVENT_RECORD:
                    continue
                payload = record.get("payload")
                if not isinstance(payload, dict) or payload.get("type") != TOKEN_RECORD:
                    continue
                yield record
    except (OSError, UnicodeError):
        return


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def _pct(value: Any) -> Optional[float]:
    number = _number(value)
    return number if number is not None and number <= 100 else None


def _token_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError, OverflowError):
        return 0


def _priced_tokens(raw: Optional[dict]) -> Dict[str, int]:
    raw = raw if isinstance(raw, dict) else {}
    return {"input": _token_count(raw.get("input_tokens")),
            "cached_input": _token_count(raw.get("cached_input_tokens")),
            "output": _token_count(raw.get("output_tokens"))}


def _keep_newest(found: Dict[str, GptWindow], label: str,
                 candidate: GptWindow) -> None:
    current = found.get(label)
    if current is None or candidate.at >= current.at:
        found[label] = candidate


def _ledger_windows(record: Optional[dict],
                   at: Optional[float] = None) -> Dict[str, GptWindow]:
    if not isinstance(record, dict):
        return {}
    if at is None:
        at = to_epoch(record.get("ended")) or 0.0
    raw_windows = record.get("windows")
    if not isinstance(raw_windows, dict):
        return {}
    found: Dict[str, GptWindow] = {}
    for key, label in LEDGER_WINDOWS:
        window = raw_windows.get(key)
        if not isinstance(window, dict):
            continue
        pct = _pct(window.get("used_percent"))
        if pct is None:
            continue
        found[label] = GptWindow(pct, to_epoch(window.get("resets_at")),
                                 at, SOURCE_LEDGER, 18000 if label == WINDOW_5H else 604800)
    return found


def _ledger(path: Path) -> Tuple[Dict[str, dict], Dict[str, GptWindow]]:
    records: Dict[str, dict] = {}
    samples: Dict[str, GptWindow] = {}
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return records, samples
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        if str(record.get("codex_home") or "") != HAND_HOME_NAME:
            continue
        run_id = str(record.get("run_id") or "")
        if run_id:
            records[run_id] = record
        ended = to_epoch(record.get("ended"))
        if ended is None:
            continue
        for label, window in _ledger_windows(record, ended).items():
            _keep_newest(samples, label, window)
    return records, samples


def _rate_limit_windows(limits: Any, at: float, explicit_only: bool = False) -> Dict[str, GptWindow]:
    found: Dict[str, GptWindow] = {}
    if not isinstance(limits, dict):
        return found
    for name in ("primary", "secondary"):
        raw = limits.get(name)
        if not isinstance(raw, dict):
            continue
        duration = raw.get("window_minutes")
        if duration is None and not explicit_only:
            duration = 300 if name == "primary" else 10080
        label = ({300: WINDOW_5H, 10080: WINDOW_WEEK}.get(duration)
                 if isinstance(duration, (int, float)) and not isinstance(duration, bool) else None)
        pct = _pct(raw.get("used_percent"))
        reset = to_epoch(raw.get("resets_at"))
        if label and pct is not None and reset is not None:
            found[label] = GptWindow(pct, reset, at, SOURCE_ROLLOUT, duration * 60)
    return found


def _rollout_files(home: Path) -> Iterable[Path]:
    root = _sessions_root(home)
    if root is None:
        return []
    found: List[Path] = []
    try:
        for path in root.rglob(ROLLOUT_GLOB):
            resolved = _contained(root, path)
            if resolved is not None:
                found.append(resolved)
    except OSError:
        return found
    from hh_store import codex_ingest
    codex_ingest.forget(codex_ingest.SCOPE_SESSIONS, found)
    return found


def _read_rollout(path: Path) -> Tuple[Optional[dict], Dict[str, GptWindow]]:
    """Last token total and last rate_limits sample from a rollout."""
    tokens: Optional[dict] = None
    windows: Dict[str, GptWindow] = {}
    for record in _iter_json_lines(path):
        payload = record.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != TOKEN_RECORD:
            continue
        info = payload.get("info")
        total = info.get("total_token_usage") if isinstance(info, dict) else None
        # A latest event without a total means unknown, not the pre-compaction total.
        tokens = total if isinstance(total, dict) else None
        at = to_epoch(record.get("timestamp"))
        limits = payload.get("rate_limits")
        if isinstance(limits, dict):
            windows.update(_rate_limit_windows(limits, at if at is not None else 0.0))
    return tokens, windows


def measured_week(records, now: float) -> Optional[float]:
    """Account movement during one rollout, possibly including concurrent usage."""
    samples = []
    for payload, at in records:
        sample = _rate_limit_windows(payload.get("rate_limits"), at or 0, explicit_only=True).get(WINDOW_WEEK)
        if (sample is None or at is None or at > now or sample.resets_at <= now
                or not sample.resets_at - 604800 <= at <= now):
            return None
        if samples and (sample.resets_at != samples[-1].resets_at
                        or at < samples[-1].at or sample.pct < samples[-1].pct):
            return None
        samples.append(sample)
    return samples[-1].pct - samples[0].pct if len(samples) >= 2 else None


def rollout_week(path, now):
    return measured_week(((r.get("payload", {}), to_epoch(r.get("timestamp")))
                          for r in _iter_json_lines(path, strict=True)), now)


def _scan_rollouts(home: Path) -> Dict[str, GptWindow]:
    """Newest account sample per window across every contained rollout."""
    samples: Dict[str, GptWindow] = {}
    for path in _rollout_files(home):
        for record in _iter_json_lines(path):
            if record.get("type") != EVENT_RECORD:
                continue
            payload = record.get("payload")
            if not isinstance(payload, dict) or payload.get("type") != TOKEN_RECORD:
                continue
            limits = payload.get("rate_limits")
            if not isinstance(limits, dict):
                continue
            at = to_epoch(record.get("timestamp"))
            if at is None:
                continue
            for label, window in _rate_limit_windows(limits, at).items():
                _keep_newest(samples, label, window)
    return samples


def _usage(tokens: Optional[Mapping[str, Any]], windows: Mapping[str, GptWindow],
           usd: Optional[float], now: float) -> Usage:
    tokens = tokens if isinstance(tokens, dict) else {}
    total_input = _token_count(tokens.get("input"))
    cached = _token_count(tokens.get("cached_input"))
    five = windows.get(WINDOW_5H)
    week = windows.get(WINDOW_WEEK)
    return Usage(
        read=max(0, total_input - cached), cache_read=cached, cache_write=None,
        out=_token_count(tokens.get("output")), usd=usd, usd_estimated=True,
        gpt_5h_pct=five.pct if five is not None and five.usable(now) else None,
        gpt_week_pct=week.pct if week is not None and week.usable(now) else None)


def load_codex(cfg: Any, now: float) -> CodexData:
    """Read the Codex ledger and every contained rollout once for this snapshot."""
    home = codex_home(cfg)
    records, ledger_samples = _ledger(state_dir(cfg) / CODEX_USAGE_LEDGER_NAME)
    account = dict(ledger_samples)
    for label, sample in _scan_rollouts(home).items():
        _keep_newest(account, label, sample)
    return CodexData(home=home, account=account, ledger=records,
                     price=price_for(explicit_options(cfg, "codex")),
                     price_options=explicit_options(cfg, "codex"))


def pinned_rollouts(roots: Iterable[Path]) -> Dict[str, str]:
    """Pinned rollout paths from side-session state, read-only (never written here)."""
    found: Dict[str, str] = {}
    for root in roots:
        try:
            cfg = load_ps_config(root)
            states = load_side_states(cfg.side_state_dir)
        except (OSError, ValueError, TypeError, KeyError):
            continue
        for state in states:
            uuid = str(getattr(state, "uuid", "") or "")
            rollout = str(getattr(state, "codex_rollout", "") or "")
            if uuid and rollout and uuid not in found:
                found[uuid] = rollout
    return found

