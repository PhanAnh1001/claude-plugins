"""Validated metadata only; approval is deliberately not inferred from names."""
from __future__ import annotations

import copy
import re
from pathlib import Path, PurePosixPath

from shared_config import _merge

SHARED_KEYS = frozenset({'statusLine', 'hooks'})
ROOTS = {'claude': {'CLAUDE.md', 'skills', 'agents', 'commands', 'hooks'},
         'codex': {'AGENTS.md', 'skills', 'agents', 'rules'}}
PRIVATE = frozenset({'.env', '.credentials.json', 'auth.json', 'auth.lock', '.claude.json',
    'projects', 'history.jsonl', 'sessions', 'archived_sessions', 'plugins',
    'installed_plugins.json', 'config.toml', '.system', 'models_cache', 'models_cache.json',
    '.statusline-go-usage.json', 'hand_usage.json', 'hand_quota.json',
    'rate_limits.json', 'usage-cache.json', '.cache'})


class ManifestError(ValueError):
    """Only fixed codes are suitable for public diagnostics."""


def allowed_path(provider: str, value: object) -> bool:
    if not isinstance(value, str) or not value or '\\' in value or any(ord(c) < 32 or ord(c) == 127 for c in value):
        return False
    path = PurePosixPath(value)
    parts = path.parts
    if path.is_absolute() or value != path.as_posix() or any(
            p in PRIVATE or p in {'.', '..'} or p.endswith(('.sqlite', '.db'))
            or p.startswith('.env') for p in parts):
        return False
    return isinstance(provider, str) and bool(parts) and parts[0] in ROOTS.get(provider, set()) and (
        len(parts) == 1 or parts[0] not in {'CLAUDE.md', 'AGENTS.md'})


def manifest_from(result, overrides: dict | None = None) -> tuple[dict, dict]:
    """Re-merge aliases in source order so a repo alias wins over global nesting."""
    data, provenance = {}, {}
    from .constants import DEFAULTS
    layers = [('plugin', {'ext_hand': {'account_sync': DEFAULTS['account_sync']}})] + list(result.sections)
    for source, section in layers:
        for raw in (section.get('account_sync', {}),
                    section.get('ext_hand', {}).get('account_sync', {})):
            if not isinstance(raw, dict):
                raise ManifestError('invalid_manifest')
            _merge(data, raw, provenance, source)
    if overrides:
        _merge(data, overrides, provenance, 'cli')
    if set(data) - {'sources', 'targets', 'items', 'exclude', 'settings', 'plugins', 'mcp',
                    'source_override_approved'}:
        raise ManifestError('invalid_manifest')
    if not isinstance(data.get('sources'), dict) or set(data['sources']) - {'claude', 'codex'}:
        raise ManifestError('invalid_sources')
    source = data['sources'].get('claude', 'v1')
    if not isinstance(source, str) or not re.fullmatch(r'v[1-9][0-9]*', source):
        raise ManifestError('invalid_source')
    if source != 'v1' and data.get('source_override_approved') is not True:
        raise ManifestError('source_approval_required')
    settings = data.get('settings', {})
    if not isinstance(settings, dict) or set(settings) - {'shared_keys', 'approved_keys', 'ownership'}:
        raise ManifestError('invalid_settings')
    keys = settings.get('shared_keys', [])
    if not isinstance(keys, list) or any(not isinstance(k, str) or k not in SHARED_KEYS for k in keys):
        raise ManifestError('private_key')
    approved_keys = settings.get('approved_keys', [])
    if not isinstance(approved_keys, list) or any(
            not isinstance(k, str) or k not in SHARED_KEYS for k in approved_keys):
        raise ManifestError('invalid_approval')
    ownership = settings.get('ownership', {})
    if not isinstance(ownership, dict) or any(k not in SHARED_KEYS for k in ownership):
        raise ManifestError('invalid_ownership')
    for evidence in ownership.values():
        if (not isinstance(evidence, dict) or
                set(evidence) != {'approved', 'verified', 'sha256'} or
                type(evidence['approved']) is not bool or type(evidence['verified']) is not bool or
                not isinstance(evidence['sha256'], str) or
                not re.fullmatch(r'[0-9a-f]{64}', evidence['sha256'])):
            raise ManifestError('invalid_ownership')
    for key in ('items', 'exclude'):
        if not isinstance(data.get(key), list):
            raise ManifestError('invalid_manifest')
    if any(not isinstance(p, str) for p in data['exclude']):
        raise ManifestError('invalid_exclude')
    for item in data['items']:
        if not isinstance(item, dict) or set(item) - {'provider', 'path', 'type', 'approved'}:
            raise ManifestError('invalid_item')
        if 'approved' in item and not isinstance(item['approved'], bool):
            raise ManifestError('invalid_approval')
        if not allowed_path(item.get('provider'), item.get('path')):
            raise ManifestError('private_path')
        if item.get('type', 'symlink') not in {'symlink', 'import'}:
            raise ManifestError('invalid_item_type')
    from .account_sync_official import validate_policy
    validate_policy(data.get('plugins', {}), data.get('mcp', []))
    return copy.deepcopy(data), provenance


def home_path(root: Path, raw: object) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ManifestError('invalid_home')
    if any(ord(c) < 32 or ord(c) == 127 for c in raw):
        raise ManifestError('invalid_home')
    path = Path(raw).expanduser()
    if '..' in path.parts:
        raise ManifestError('invalid_home')
    return (path if path.is_absolute() else root / path).absolute()


def homes_from(result, manifest: dict) -> tuple[str, Path, dict[str, Path]]:
    accounts = result.effective['ext_hand']['claude_accounts']
    if not isinstance(accounts, dict) or any(not re.fullmatch(r'v[1-9][0-9]*', k) for k in accounts):
        raise ManifestError('invalid_accounts')
    homes = {}
    for alias, entry in accounts.items():
        if not isinstance(entry, dict):
            raise ManifestError('invalid_accounts')
        homes[alias] = home_path(result.root, entry.get('config_dir'))
    source = manifest['sources'].get('claude', 'v1')
    if source not in homes:
        raise ManifestError('unknown_source')
    try:
        resolved = [p.resolve() for p in homes.values()]
    except (OSError, RuntimeError):
        raise ManifestError('home_cycle') from None
    if len(set(resolved)) != len(resolved) or any(
            a in b.parents or b in a.parents for i, a in enumerate(resolved) for b in resolved[i+1:]):
        raise ManifestError('home_cycle')
    if manifest.get('targets'):
        raise ManifestError('targets_not_supported')
    return source, homes[source], {k: v for k, v in homes.items() if k != source}
