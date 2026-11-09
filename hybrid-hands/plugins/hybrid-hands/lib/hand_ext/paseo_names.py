"""Best effort managed names, independent of send and lifecycle receipts."""
from pathlib import Path
import unicodedata
import sys

TITLE_LIMIT = 60
NAME_RETRIES = 3
BACKENDS = {'codex', 'dsh', 'claude-v1', 'claude-v2'}


def safe_part(value: object, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        return '?'
    if any(unicodedata.category(c).startswith('C') for c in value) or any(c in value for c in ('/', '\\', '..')):
        return '?'
    return ' '.join(value.split())[:limit]


def parent_name(invocation) -> str:
    try:
        from hh_ps.registry_source import load_ps_config
        from side_session.state import load_all
        states = load_all(load_ps_config(Path(invocation.source_cwd)).side_state_dir)
        matches = [s for s in states if (invocation.parent_session and invocation.parent_session in
                   (s.uuid, s.codex_thread_id, s.native_session_id, s.paseo_agent_id)) or
                   (invocation.parent_paseo_agent_id and
                    invocation.parent_paseo_agent_id == s.paseo_agent_id)]
        if len(matches) == 1:
            state = matches[0]
            return 'chính' if state.role == 'main' else safe_part(state.name, 32)
    except Exception:
        pass  # Missing identity evidence stays unknown, never inferred from cwd.
    return '?'


def title_for(record) -> str:
    backend = {'claude': 'claude-v2', 'claude-main': 'claude-v1'}.get(
        record.invocation.backend, record.invocation.backend)
    backend = backend if backend in BACKENDS else '?'
    prefix = f'{parent_name(record.invocation)} › hand {backend} · '
    controller = (record.receipt or {}).get('controller')
    label = safe_part(controller.get('label') if isinstance(controller, dict) else None, TITLE_LIMIT)
    return prefix + label[:TITLE_LIMIT - len(prefix)]


def latest_records(store, source=None):
    latest = {}
    with store.locked():
        rows = [store._read(p) for p in sorted(store.root.glob('*.json'))]
    for row in rows:
        before = latest.get(row.invocation.invocation_id)
        if before is None or row.attempt.epoch > before.attempt.epoch:
            latest[row.invocation.invocation_id] = row
    return [r for r in latest.values() if source is None or
            Path(r.invocation.source_cwd).resolve() == Path(source).resolve()]


def names_request(transport, key, *, apply=False):
    record = transport.store.get(key)
    from .paseo_controller import records_for
    def provenance(row):
        for epoch in records_for(transport.store, row.invocation.invocation_id):
            if (epoch.attempt.agent_id == row.attempt.agent_id and
                    epoch.attempt.workspace_id == row.attempt.workspace_id):
                meta = (epoch.receipt or {}).get('transport', {})
                if meta.get('agentKey'):
                    return meta
        return {}
    receipt = provenance(record)
    # Keys are durable plugin creation provenance, not names/provider guesses.
    if not receipt.get('agentKey') or not record.attempt.agent_id:
        return {'ok': False, 'code': 'NAME_OWNERSHIP_UNKNOWN'}
    owned = []
    for row in latest_records(transport.store):
        meta = provenance(row)
        if meta.get('agentKey') and meta.get('workspaceKey'):
            owned.append({'agentId': row.attempt.agent_id, 'workspaceId': row.attempt.workspace_id,
                          'parentAgentId': row.invocation.parent_paseo_agent_id,
                          'providerId': meta.get('providerId'), 'cwd': row.invocation.isolated_cwd})
    request = {k: v for k, v in transport._read(key).items() if k != '_source_transport'}
    request.update(title=title_for(record), apply=apply, ownedChildren=owned,
                   workspaceOwned=bool(receipt.get('workspaceKey')))
    return transport._call('names', request)


def retry_names(transport, key):
    """At most three attempts per epoch across dispatch and later polls."""
    try:
        record = transport.store.get(key)
        progress = (record.receipt or {}).get('naming', {})
        if progress.get('done') or progress.get('attempts', 0) >= NAME_RETRIES:
            return
        try:
            result = names_request(transport, key, apply=True)
        except Exception:
            result = {'ok': False}
        done = result.get('ok') is True and not result.get('warning')
        if not done:
            print('warning: NAME_UNRESOLVED', file=sys.stderr)
        record = transport.store.get(key)
        record.receipt['naming'] = {'attempts': progress.get('attempts', 0) + 1,
                                   'done': done,
                                   'warning': None if result.get('ok') and not result.get('warning') else 'NAME_UNRESOLVED'}
        transport.store.compare_and_swap(key, record.revision, record)
    except Exception:
        # Naming cannot affect lifecycle, including malformed optional metadata.
        print('warning: NAME_UNRESOLVED', file=sys.stderr)
