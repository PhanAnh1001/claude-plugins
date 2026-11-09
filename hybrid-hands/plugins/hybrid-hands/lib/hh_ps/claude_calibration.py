"""Account-isolated Claude hand calibration. Persist metadata only, never identity."""
from __future__ import annotations
import hashlib
import json
import math
import time
import fcntl
import os
import subprocess
import tempfile
from pathlib import Path
from dataclasses import replace
from .timeutil import to_epoch

TTL = 300
POLL = 120
FAILED_POLL = 15
AUTH_TIMEOUT = 3
PASEO_TIMEOUT = 6
RESET_TOLERANCE = 2
WEEK = 604800
KEYS = ('input', 'output', 'cache_read', 'cache_write_5m', 'cache_write_1h')


def number(v):
    return float(v) if isinstance(v, (float, int)) and not isinstance(v, bool) and math.isfinite(v) else None


def read(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.calibration-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def empty():
    return dict(source='claude_hand_calibration', account_source='', account_5h_pct=None,
                account_week_pct=None, usd_per_pct=None, usd=None, tokens=None,
                sampled_at=None, resets_at=None, precision='unknown', status='unknown')


def valid(sample, now):
    five = number(sample.get('five'))
    sample['five'] = five if five is not None and 0 <= five <= 100 else None
    stamp, reset, pct = (number(sample.get(k)) for k in ('at', 'reset', 'pct'))
    return (stamp is not None and 0 <= now - stamp < TTL and reset is not None
            and now < reset <= now + WEEK and pct is not None and 0 <= pct <= 100)


def command(args, home):
    env = dict(os.environ, CLAUDE_CONFIG_DIR=str(home))
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=PASEO_TIMEOUT if args[0] == "paseo" else AUTH_TIMEOUT, check=True)
    return json.loads(result.stdout)


def quota(home, now):
    began = time.monotonic()
    def moment():
        return now + max(0, time.monotonic() - began)
    try:
        auth = command(['claude', 'auth', 'status', '--json'], home)
        if not isinstance(auth, dict) or auth.get('loggedIn') is not True:
            return None
        email = auth.get('email') or (auth.get('account') or {}).get('email')
        if not isinstance(email, str) or not email.strip():
            return None
        identity = email.strip().casefold()
        digest = hashlib.sha256(identity.encode()).hexdigest()
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, AttributeError):
        return None
    # Local caches belong to the isolated config directory, never the brain cache.
    from .live_rate import read_live_window
    weekly = read_live_window(home, 'seven_day', moment())
    five = read_live_window(home, 'five_hour', moment())
    if weekly is not None:
        sample = dict(at=weekly.ts, reset=weekly.resets_at, pct=weekly.pct,
                      five=five.pct if five else None, source='claude_hand_live')
        if valid(sample, moment()):
            sample['five_reset'] = five.resets_at if five else None
            sample['identity'] = digest
            sample['reset'] = int(round(sample['reset']))
            return sample
    cache_path = home / '.statusline-cache.json'
    cache = read(cache_path)
    if cache:
        sample = dict(at=cache_path.stat().st_mtime, reset=to_epoch(cache.get('week_reset')),
                      pct=cache.get('week'), five=None, source='claude_hand_cache')
        five_reset = to_epoch(cache.get('five_reset'))
        if five_reset is not None and now < five_reset <= now + 18000:
            sample['five'] = cache.get('five')
            sample['five_reset'] = five_reset
        if valid(sample, moment()):
            sample['identity'] = digest
            sample['reset'] = int(round(sample['reset']))
            return sample
    try:
        rows = command(['paseo', 'usage', '--json'], home)
        if not isinstance(rows, list):
            return None
        matching = [r for r in rows if isinstance(r, dict) and r.get('sourceId') == 'claude'
                    and str((r.get('account') or {}).get('label', '')).strip().casefold() == identity]
        if len(matching) != 1:
            return None
        row = matching[0]
        report = row.get('report') or {}
        if report.get('status') != 'available':
            return None
        windows = {w.get('id'): w for w in report.get('windows', []) if isinstance(w, dict)}
        week = windows.get('weekly', {})
        five = windows.get('five_hour', {})
        sample = dict(at=to_epoch(row.get('fetchedAt')), reset=to_epoch(week.get('resetsAt')),
                      pct=week.get('usedPct'), five=None, source='paseo_claude_account',
                      identity=hashlib.sha256(identity.encode()).hexdigest())
        reset = to_epoch(five.get('resetsAt'))
        if reset is not None and now < reset <= now + 18000:
            sample['five'] = five.get('usedPct')
            sample['five_reset'] = reset
        if not valid(sample, moment()):
            return None
        sample['reset'] = int(round(sample['reset']))
        return sample
    except (OSError, ValueError, TypeError, subprocess.SubprocessError, AttributeError):
        return None


def costs(home, start, end):
    """Reuse ledger's streaming-message dedup and cache-duration token parsing."""
    from .week import _locate_usage_ledger, _ledger_module, STATUSLINE_LEDGER_ENV
    projects = home / 'projects'
    if not projects.is_dir() or not os.access(projects, os.R_OK | os.X_OK):
        return None, None
    try:
        path = _locate_usage_ledger(home)
        # Resolve installed helper CODE through the main plugin registry when the
        # isolated account has no statusline install. Token data stays in home.
        # An explicit override remains authoritative, including an invalid path.
        if path is None and not os.environ.get(STATUSLINE_LEDGER_ENV):
            path = _locate_usage_ledger(Path.home() / '.claude')
        if path is None:
            return None, None
        module = _ledger_module(str(path), path.stat().st_mtime_ns)
        module.refresh_prices()
        messages = module.window_messages([home], math.nextafter(start, math.inf), end)
        tokens = dict.fromkeys(KEYS, 0)
        usd = 0.0
        unpriced = False
        for msg in messages.values():
            if any(number(msg.tokens.get(k)) is None or msg.tokens[k] < 0 for k in KEYS):
                return None, None
            price = module.price_for(msg.model)
            if price is None or any(msg.tokens[k] and getattr(price, attr) is None for k, attr in
                    [('cache_read', 'cached'), ('cache_write_5m', 'cache_write_5m'),
                     ('cache_write_1h', 'cache_write_1h')]):
                unpriced = True
            for key in KEYS:
                tokens[key] += msg.tokens[key]
            if price is not None and not unpriced:
                usd += sum(module.token_costs(price, msg.tokens).values())
        return (None if unpriced else usd), tokens
    except (OSError, ValueError, TypeError, AttributeError, ImportError, SyntaxError, RuntimeError):
        return None, None


def normalize_reset(samples, current, now):
    """Keep one observed reset anchor despite small source-clock jitter."""
    reset = number(current.get("reset"))
    if reset is None or reset <= now:
        return
    anchors = [s for s in samples if s.get("identity") == current.get("identity")
               and number(s.get("reset")) is not None and s["reset"] > now
               and abs(s["reset"] - reset) <= RESET_TOLERANCE
               and number(s.get("at")) is not None and reset-WEEK <= s["at"] <= current["at"]]
    if anchors:
        current["reset"] = min(anchors, key=lambda s: s["at"])["reset"]


def rate(samples, current, home, now, price=costs):
    normalize_reset(samples, current, now)
    if not valid(current, now):
        return None
    same = [s for s in samples if s.get('identity') == current.get('identity')
            and number(s.get('reset')) is not None and s['reset'] > now
            and abs(s['reset'] - current['reset']) <= RESET_TOLERANCE and number(s.get('at')) is not None
            and current['reset'] - WEEK <= s['at'] < current['at']]
    ordered = sorted(same + [current], key=lambda s: s['at'])
    if any(number(s.get('pct')) is None for s in ordered):
        return None
    if any(b['pct'] < a['pct'] for a, b in zip(ordered, ordered[1:])):
        return None
    for first in ordered[:-1]:
        delta = current['pct'] - first['pct']
        fractional = any(float(s['pct']) % 1 for s in ordered)
        if delta <= 0 or (not fractional and delta < 2):
            continue
        usd, _ = price(home, first['at'], current['at'])
        if usd is not None and usd > 0:
            return usd / delta
    return None


def cache_path():
    return Path.home() / '.hybrid-hands' / 'claude-calibration.json'


def pricing_fingerprint():
    from usage_pricing import load_prices
    return hashlib.sha256(json.dumps(load_prices(), sort_keys=True).encode()).hexdigest()


def cached(now):
    state = read(cache_path())
    if state.get('pricing') != pricing_fingerprint():
        return empty()
    header = state.get('header', {})
    if not isinstance(header, dict):
        return empty()
    if (number(header.get('sampled_at')) is None or not 0 <= now-header['sampled_at'] < TTL
            or number(header.get('resets_at')) is None or header['resets_at'] <= now):
        return empty()
    result = empty()
    result.update({k: header.get(k, v) for k, v in result.items()})
    if result['account_source'] not in ('claude_hand_live', 'claude_hand_cache', 'paseo_claude_account'):
        return empty()
    result['source'] = 'claude_hand_calibration'
    result['status'] = result['status'] if result['status'] in ('unknown', 'ready', 'collecting') else 'unknown'
    result['precision'] = result['precision'] if result['precision'] in ('unknown', 'integer', 'fractional') else 'unknown'
    usd = number(result.get('usd'))
    result['usd'] = usd if usd is not None and usd >= 0 else None
    tokens = result.get('tokens')
    if not isinstance(tokens, dict) or any(number(tokens.get(k)) is None or tokens[k] < 0 for k in KEYS):
        result['tokens'] = None
    value = number(result.get('usd_per_pct'))
    result['usd_per_pct'] = value if value is not None and value > 0 else None
    for key in ('account_5h_pct', 'account_week_pct'):
        pct = number(result[key])
        result[key] = pct if pct is not None and 0 <= pct <= 100 else None
    five_reset = number(header.get('account_5h_resets_at'))
    if five_reset is None or five_reset <= now:
        result['account_5h_pct'] = None
    return result


def retain(samples, sample):
    normalize_reset(samples, sample, sample["at"])
    rows = [dict(s, reset=sample["reset"]) for s in samples if s.get("identity") == sample["identity"]
            and number(s.get("reset")) is not None and s["reset"] > sample["at"]
            and abs(s["reset"] - sample["reset"]) <= RESET_TOLERANCE and number(s.get("at")) is not None
            and sample["reset"] - WEEK <= s["at"] < sample["at"] and number(s.get("pct")) is not None]
    rows.sort(key=lambda s: s["at"])
    if rows and sample["pct"] < rows[-1]["pct"]:
        return [sample]
    rows.append(sample)
    # Keep the observed first anchor across a slow week, plus bounded recent history.
    return rows if len(rows) <= 256 else [rows[0], *rows[-255:]]


def _collect(now):
    began = time.monotonic()
    def moment():
        return now + max(0, time.monotonic() - began)
    path = cache_path()
    state = read(path)
    if state.get('pricing') != pricing_fingerprint():
        state = {}
    previous_header = state.get('header')
    poll = (POLL if isinstance(previous_header, dict) and previous_header.get('sampled_at') is not None
            else FAILED_POLL)
    if number(state.get('polled_at')) is not None and 0 <= now-state['polled_at'] < poll:
        previous = cached(moment())
        # A successful cache expiring early may poll once before the normal interval.
        if previous['sampled_at'] is not None or poll == FAILED_POLL:
            return previous
    home = Path.home() / '.claude-hand'
    sample = quota(home, moment()) if home.is_dir() else None
    header = empty()
    samples = state.get('samples', [])
    samples = [s for s in samples if isinstance(s, dict)] if isinstance(samples, list) else []
    if sample is not None and valid(sample, moment()):
        normalize_reset(samples, sample, moment())
        usd, tokens = costs(home, sample['reset'] - WEEK, sample['at'])
        value = rate(samples, sample, home, moment())
        header.update(account_source=sample['source'], account_week_pct=sample['pct'],
                      account_5h_pct=sample['five'], account_5h_resets_at=sample.get('five_reset'), sampled_at=sample['at'], resets_at=sample['reset'],
                      usd=usd, tokens=tokens, usd_per_pct=value,
                      precision='fractional' if float(sample['pct']) % 1 else 'integer',
                      status='ready' if value is not None else 'collecting')
        samples = retain(samples, sample)
    write(path, dict(polled_at=moment(), pricing=pricing_fingerprint(), header=header, samples=samples))
    return cached(moment())


def collect(now):
    began = time.monotonic()
    if os.environ.get("HYBRID_HANDS_CALIBRATION_CACHE_ONLY") == "1":
        return cached(now)
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with (path.parent / 'claude-calibration.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return cached(now + max(0, time.monotonic() - began))
        return _collect(now + max(0, time.monotonic() - began))


def enrich(snapshot, now):
    try:
        snapshot.claude_calibration = collect(now)
    except (OSError, ValueError, TypeError):
        snapshot.claude_calibration = empty()
    value = snapshot.claude_calibration.get('usd_per_pct')
    if number(value) is None or value <= 0:
        return
    for session in snapshot.sessions:
        for row, provider in [(session, session.provider)] + [
                (agent, agent.provider or session.provider) for agent in session.subagents]:
            if provider != 'claude' or row.usage is None:
                continue
            usage = row.usage
            if usage.usd is None:
                continue
            pct = usage.usd / value if value and usage.usd is not None else None
            row.usage = replace(usage, week_pct=pct, week_pct_estimated=pct is not None,
                                week_pct_source='claude_hand_calibration' if pct is not None else '')

    for run in snapshot.iter_runs():
        if run.backend not in ('claude', 'claude-main') or run.usage is None:
            continue
        usage = run.usage
        if usage.usd is None:
            continue
        pct = usage.usd / value if value and usage.usd is not None else None
        run.usage = replace(usage, week_pct=pct, week_pct_estimated=pct is not None,
                            week_pct_source='claude_hand_calibration' if pct is not None else '')
