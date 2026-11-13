"""Quota metadata only; official CLIs own authentication, never the watcher."""
from __future__ import annotations

import json
import os
import select
import subprocess
import time
from pathlib import Path

from hh_ps.timeutil import to_epoch
from .engine import fresh, number


def read_object(path):
    try:
        obj = json.loads(path.read_text())
        return obj if isinstance(obj, dict) else {}
    except (ValueError, OSError):
        return {}


def cli_json(argv, env=None):
    proc = subprocess.run(argv, env=env, capture_output=True, text=True,
                          timeout=8, check=True)
    return json.loads(proc.stdout)


def codex_rpc(home, cwd, executable='codex'):
    """Initialize stdio, then read limits; no thread, turn, login or token RPC."""
    env = dict(os.environ, CODEX_HOME=home)
    for key in ('OPENAI_API_KEY', 'CODEX_API_KEY', 'CODEX_ACCESS_TOKEN'):
        env.pop(key, None)
    proc = subprocess.Popen([executable, 'app-server'], cwd=cwd, env=env,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, bufsize=0)
    deadline = time.monotonic() + 12
    pending = bytearray()

    def send(value):
        proc.stdin.write(json.dumps(value).encode() + b'\n')
        proc.stdin.flush()

    def response(ident):
        while time.monotonic() < deadline:
            if b'\n' not in pending:
                ready, _, _ = select.select([proc.stdout], [], [], max(0, deadline-time.monotonic()))
                if not ready:
                    break
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    break
                pending.extend(chunk)
                if len(pending) > 2_000_000:
                    raise ValueError('rpc_size_limit')
            while b'\n' in pending:
                line, _, rest = pending.partition(b'\n')
                pending[:] = rest
                value = json.loads(line)
                if value.get('id') == ident:
                    if 'error' in value:
                        raise ValueError('rpc_rejected')
                    return value['result']
        raise TimeoutError('rpc_timeout')

    try:
        send(dict(id=1, method='initialize', params=dict(clientInfo=dict(
            name='hybrid_hands_limit_watch', version='0.58.0'))))
        response(1)
        send(dict(method='initialized'))
        send(dict(id=2, method='account/rateLimits/read'))
        return response(2)
    finally:
        proc.stdin.close()
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)
        proc.stdout.close()


def codex_sample(raw, now, bucket='codex'):
    buckets = raw.get('rateLimitsByLimitId')
    if isinstance(buckets, dict):
        row = buckets.get(bucket)
    else:
        row = raw.get('rateLimits')
        if isinstance(row, dict) and row.get('limitId', 'codex') != bucket:
            row = None
    if not isinstance(row, dict):
        return dict(windows=[], complete=False)
    windows = []
    for key in ('primary', 'secondary'):
        w = row.get(key)
        if isinstance(w, dict):
            windows.append(dict(id=bucket+':'+key, used_pct=w.get('usedPercent'),
                                reset_at=w.get('resetsAt'), observed_at=now,
                                duration_minutes=w.get('windowDurationMins')))
    blocked = bool(row.get('rateLimitReachedType') or row.get('spendControlReached')
                   or raw.get('ordinaryUsageAllowed') is False)
    return dict(windows=windows, complete=bool(windows) and not blocked,
                server_blocked=blocked, source='codex_app_server')


def claude_sample(target, now):
    home = Path(target['account_home'])
    live = read_object(home / '.hh-claude-rate-limit.json')
    entries = live.get('windows', {}) if live.get('version') == 1 else {}
    windows = {}
    if isinstance(entries, dict):
        for key, raw in entries.items():
            if not isinstance(raw, dict):
                continue
            utilization = number(raw.get('utilization'))
            windows[key] = dict(id=key, used_pct=None if utilization is None else utilization*100,
                                reset_at=to_epoch(raw.get('resets_at')),
                                observed_at=number(raw.get('ts')),
                                blocked=raw.get('status') in ('rejected', 'blocked'))
    cache = read_object(home / '.statusline-cache.json')
    for key, prefix in (('five_hour', 'five'), ('seven_day', 'week')):
        candidate = dict(id=key, used_pct=cache.get(prefix),
                         reset_at=to_epoch(cache.get(prefix+'_reset')),
                         observed_at=to_epoch(cache.get(prefix+'_observed_at')))
        # No mtime fallback: existing caches rewrite inherited stale values.
        if key not in windows or (not fresh(windows[key], now) and fresh(candidate, now)):
            windows[key] = candidate
    required = {'five_hour', 'seven_day'}
    if not required <= windows.keys() or not all(fresh(w, now) for w in windows.values()):
        # Match the authenticated account via the official CLI. Only the digest
        # leaves this function, never an email/token/auth response.
        from hh_ps.claude_calibration import identity_digest
        env = dict(os.environ, CLAUDE_CONFIG_DIR=str(home))
        try:
            auth = cli_json(['claude', 'auth', 'status', '--json'], env)
            email = auth.get('email') or (auth.get('account') or {}).get('email')
            rows = cli_json(['paseo', 'usage', '--json'], env) if auth.get('loggedIn') is True and email else []
            matches = [r for r in rows if isinstance(r, dict) and r.get('sourceId') == 'claude'
                       and identity_digest(str((r.get('account') or {}).get('label', ''))) == identity_digest(email)]
            if len(matches) == 1:
                row = matches[0]
                report = row.get('report') or {}
                if report.get('status') == 'available':
                    for w in report.get('windows', []):
                        key = {'weekly': 'seven_day'}.get(w.get('id'), w.get('id'))
                        if not key:
                            continue
                        candidate = dict(id=key, used_pct=w.get('usedPct'),
                                         reset_at=to_epoch(w.get('resetsAt')),
                                         observed_at=to_epoch(row.get('fetchedAt')))
                        if fresh(candidate, now) and (key not in windows or not fresh(windows[key], now)
                                or candidate['observed_at'] > windows[key]['observed_at']):
                            windows[key] = candidate
        except (OSError, ValueError, subprocess.SubprocessError, TypeError, AttributeError):
            pass
    return dict(windows=list(windows.values()), complete=required <= windows.keys(),
                source='claude_metadata')


def observe(target, now):
    if target['provider'] == 'codex':
        return codex_sample(codex_rpc(target['account_home'], target['cwd']), now,
                            target.get('limit_id', 'codex'))
    return claude_sample(target, now)


def day_guard(target, now):
    if target['provider'] != 'claude' or target['account'] != 'v1':
        return True
    from .. import day_budget
    from ..config import load_config
    try:
        cfg = load_config(Path(target['cwd']))
        options = dict(cfg.options('claude-v1'), config_dir=target['account_home'])
        # Never weaken the configured 8% ceiling for a continuation.
        options['max_day_pct'] = min(float(options.get('max_day_pct', 8)), 8)
        return not day_budget.assess(options, now).blocked
    except Exception:
        return False
