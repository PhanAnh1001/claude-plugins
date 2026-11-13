"""Explicit target registrations; status never contacts a model or quota service."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

from . import adapters, engine, launchd, sources
from .store import Store
from . import registration


def register(sub):
    parser = sub.add_parser('limit-watch', help='chờ quota bằng launchd; không dùng LLM để poll')
    parser.add_argument('action', choices=('on', 'off', 'status', 'tick', 'add', 'done'))
    parser.add_argument('--persistent', action='store_true')
    parser.add_argument('--target', action='append', default=[], metavar='JSON_FILE',
                        help='đăng ký exact identity + checkpoint (lặp lại được, chỉ với on)')
    parser.add_argument('--cwd')
    origin = parser.add_mutually_exclusive_group()
    origin.add_argument('--self', dest='self_target', action='store_true')
    origin.add_argument('--side')
    parser.add_argument('--checkpoint')
    parser.add_argument('--next-step')
    parser.add_argument('--id')
    parser.add_argument('--dry-run', action='store_true')


def target_registration(raw, now):
    if not isinstance(raw, dict):
        raise ValueError('target_must_be_object')
    keys = ('id', 'provider', 'account', 'account_home', 'cwd', 'native_id', 'adapter',
            'agent_id', 'workspace_id', 'target_key', 'paseo_provider', 'checkpoint', 'next_step')
    if any(not isinstance(raw.get(k), str) or not raw[k].strip() for k in keys):
        raise ValueError('target_identity_or_checkpoint_missing')
    if raw['provider'] not in ('claude', 'codex') or raw['adapter'] not in ('paseo', 'side'):
        raise ValueError('unsupported_provider_or_adapter')
    if (raw['provider'] == 'claude' and raw['account'] not in ('v1', 'v2')
            or raw['provider'] == 'codex' and raw['account'] != 'gpt'):
        raise ValueError('unsupported_account')
    if type(raw.get('work_pending')) is not bool:
        raise ValueError('unfinished_work_attestation_required')
    for key in ('cwd', 'account_home'):
        p = Path(raw[key]).expanduser()
        if not p.is_absolute() or not p.is_dir():
            raise ValueError('target_path_missing')
        raw[key] = str(p.resolve())
    endpoint = raw.get('target')
    if not isinstance(endpoint, dict):
        raise ValueError('target_endpoint_required')
    if endpoint.get('kind') == 'instance' and isinstance(endpoint.get('home'), str):
        home = Path(endpoint['home']).expanduser()
        if not home.is_absolute():
            raise ValueError('target_endpoint_invalid')
        endpoint = dict(kind='instance', home=str(home.resolve()))
        key = 'home:'+endpoint['home']
    elif endpoint.get('kind') == 'endpoint' and isinstance(endpoint.get('host'), str):
        host = endpoint['host']
        parsed = urlsplit(host if '://' in host else '//'+host)
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError('credential_endpoint_forbidden')
        endpoint = dict(kind='endpoint', host=host)
        key = 'host:'+hashlib.sha256(host.encode()).hexdigest()
    else:
        raise ValueError('target_endpoint_invalid')
    if key != raw['target_key']:
        raise ValueError('target_endpoint_mismatch')
    target = {k: raw[k] for k in keys}
    target.update(target=endpoint, work_pending=raw['work_pending'], work_observed_at=now,
                  state='armed' if raw['work_pending'] else 'done', armed_after=now, attempts=0)
    if raw.get('limit_id'):
        target['limit_id'] = str(raw['limit_id'])
    if raw['adapter'] == 'side':
        for k in ('side_name', 'side_uuid'):
            if not isinstance(raw.get(k), str) or not raw[k].strip():
                raise ValueError('side_identity_required')
            target[k] = raw[k]
    blocked = raw.get('blocked')
    if blocked is not None:
        if not isinstance(blocked, dict):
            raise ValueError('invalid_block_observation')
        at = engine.number(blocked.get('observed_at'))
        windows = blocked.get('windows')
        if at is None or not 0 < at <= now or not isinstance(windows, list) or not windows:
            raise ValueError('invalid_block_observation')
        seen = set()
        for w in windows:
            if (not isinstance(w, dict) or not isinstance(w.get('id'), str)
                    or not w['id'] or w['id'] in seen or not engine.blocking(w)
                    or engine.number(w.get('reset_at')) is None):
                raise ValueError('invalid_block_window')
            seen.add(w['id'])
        engine.record_block(target, at, [{k: w.get(k) for k in
                            ('id', 'used_pct', 'reset_at', 'observed_at', 'blocked')} for w in windows])
        target['last_block_at'] = at
    return target


def check_registration(state, target):
    old = state['targets'].get(target['id'])
    if old and old['state'] == 'dispatch_pending':
        raise ValueError('pending_receipt_requires_manual_reconciliation')
    if any(t['id'] != target['id'] and (t['target_key'], t['agent_id']) ==
           (target['target_key'], target['agent_id']) for t in state['targets'].values()):
        raise ValueError('duplicate_agent_registration')


def finish_target(store: Store, target_id: str) -> None:
    """Stop one registration under the dispatch lock, preserving its journal.

    An ambiguous receipt requires operator reconciliation; marking it finished
    must never conceal an in-flight continuation. Other targets and the watcher
    configuration remain intact, so no off/on cycle is needed.
    """
    if not isinstance(target_id, str) or not target_id.strip():
        raise registration.RegistrationError('done cần --id ID')
    with store.locked():
        state = store.read()
        target = state['targets'].get(target_id)
        if target is None:
            raise registration.RegistrationError('Không tìm thấy target đã đăng ký')
        if target['state'] == 'dispatch_pending':
            raise registration.RegistrationError('dispatch_pending cần đối soát ACK trước khi done')
        target.update(state='done', work_pending=False, reason='explicit_done')
        store.save(state)


def finish_command(args, store: Store) -> int:
    """Accept only the explicit per-target completion syntax."""
    if (args.self_target or args.side or args.checkpoint or args.next_step
            or args.dry_run or args.target or args.persistent):
        raise registration.RegistrationError('done chỉ nhận --id ID')
    finish_target(store, args.id)
    print(json.dumps(dict(ok=True, id=args.id, state='done'), ensure_ascii=False))
    return 0


def command(args):
    store, now = Store(), time.time()
    try:
        if args.action == 'done':
            return finish_command(args, store)
        if args.action == 'add':
            if not (args.self_target or args.side) or not args.checkpoint or not args.checkpoint.strip():
                raise registration.RegistrationError('Thiếu --self/--side hoặc --checkpoint')
            if args.target or args.persistent:
                raise registration.RegistrationError('add giữ nguyên persistent; không nhận --target/--persistent')
            raw = registration.build(args)
            target = target_registration(raw.copy(), now)
            if args.dry_run:
                print(json.dumps(raw, ensure_ascii=False, indent=2))
                return 0
            with store.locked():
                state = store.read()
                check_registration(state, target)
                path = store.path.parent / 'targets' / (target['id'] + '.json')
                path.parent.mkdir(mode=0o700, exist_ok=True)
                Store(path).save(raw)
                state['targets'][target['id']] = target
                if not state['enabled']:
                    launchd.install()
                    state['enabled'] = True
                store.save(state)
            print(json.dumps(dict(ok=True, id=target['id']), ensure_ascii=False))
            return 0
        if any((args.self_target, args.side, args.checkpoint, args.next_step, args.id, args.dry_run)):
            raise registration.RegistrationError('Cờ đăng ký chỉ dùng với add')
        if args.action != 'on' and (args.target or args.persistent):
            raise ValueError('registration_flags_require_on')
        if args.action == 'tick':
            try:
                engine.tick(store, adapters.runtime, sources.observe, adapters.send, sources.day_guard, now)
            except BlockingIOError:
                return 0
            with store.locked():
                state = store.read()
                if not state['enabled'] and launchd.installed():
                    launchd.remove()
            return 0
        with store.locked():
            state = store.read()
            if args.action == 'on':
                for path in args.target:
                    target = target_registration(json.loads(Path(path).read_text()), now)
                    check_registration(state, target)
                    # An explicit registration may attest an already blocked
                    # session. Identity is still checked again on every tick.
                    state['targets'][target['id']] = target
                state.update(enabled=True, persistent=args.persistent,
                             generation=state['generation']+1)
                store.save(state)
                try:
                    launchd.install()
                except Exception:
                    state['enabled'] = False
                    store.save(state)
                    raise
            elif args.action == 'off':
                state.update(enabled=False, generation=state['generation']+1)
                store.save(state)
                launchd.remove()
            summary = dict(enabled=state['enabled'], persistent=state['persistent'],
                           generation=state['generation'], launch_agent=launchd.installed(),
                           targets=[dict(id=t['id'], state=t['state'], attempts=t['attempts'],
                                         reason=t.get('reason', '')) for t in state['targets'].values()])
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        # Arbitrary JSON/path/subprocess errors can contain user input. Do not
        # echo their values. Safe error types are enough to diagnose with docs.
        error = dict(ok=False, code=type(exc).__name__)
        if isinstance(exc, registration.RegistrationError):
            error['message'] = str(exc)
        print(json.dumps(error, ensure_ascii=False))
        return 1
