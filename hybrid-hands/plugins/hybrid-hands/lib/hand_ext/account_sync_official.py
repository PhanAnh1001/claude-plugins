"""Official CLI adapter. Raw output and payloads never cross this boundary."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from .account_sync_assets import directory
from .account_sync_manifest import ManifestError

TIMEOUT_SECONDS = 30
SCOPES = ('user', 'project', 'local')
NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}')
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}@[A-Za-z0-9][A-Za-z0-9_-]{0,127}')


def safe_name(value) -> bool:
    return isinstance(value, str) and NAME.fullmatch(value) is not None


def safe_url(value) -> bool:
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() for c in value):
        return False
    try:
        url = urlsplit(value)
        return (url.scheme == 'https' and bool(url.hostname) and not url.username
                and not url.password and not url.query and not url.fragment
                and all(ord(c) >= 32 and ord(c) != 127 for c in value))
    except ValueError:
        return False


def safe_path(value) -> bool:
    return (isinstance(value, str) and 0 < len(value) <= 4096
            and not any(ord(c) < 32 or ord(c) == 127 for c in value)
            and Path(value).is_absolute() and '..' not in Path(value).parts
            and str(Path(value)) == value and value != '/')


def checked_directory(value):
    if not safe_path(value):
        return None
    try:
        with directory(Path(value)):
            return value
    except (OSError, ValueError, RuntimeError):
        return None


def validate_policy(plugins, mcp) -> None:
    if not isinstance(plugins, dict) or set(plugins) - {'marketplaces', 'items'}:
        raise ManifestError('invalid_plugin_policy')
    markets = plugins.get('marketplaces', {})
    if not isinstance(markets, dict):
        raise ManifestError('invalid_plugin_policy')
    for name, policy in markets.items():
        if (not safe_name(name) or not isinstance(policy, dict) or
                set(policy) - {'approved', 'url', 'path'} or
                type(policy.get('approved', False)) is not bool or
                not ((set(policy) & {'url', 'path'} == {'url'} and safe_url(policy['url'])) or
                     (set(policy) & {'url', 'path'} == {'path'} and safe_path(policy['path'])))):
            raise ManifestError('invalid_marketplace_policy')
    items = plugins.get('items', [])
    if not isinstance(items, list):
        raise ManifestError('invalid_plugin_policy')
    seen = set()
    for item in items:
        if (not isinstance(item, dict) or set(item) - {'id', 'scope', 'approved', 'verified', 'repo_used'}
                or not isinstance(item.get('id'), str) or not IDENTIFIER.fullmatch(item['id'])
                or item.get('scope') not in SCOPES
                or any(type(item.get(k, False)) is not bool for k in ('approved', 'verified', 'repo_used'))):
            raise ManifestError('invalid_plugin_policy')
        if item['id'] in seen:
            raise ManifestError('duplicate_plugin_policy')
        seen.add(item['id'])
    if not isinstance(mcp, list) or any(not isinstance(i, dict) or
            set(i) - {'name', 'approved'} or not safe_name(i.get('name')) or
            type(i.get('approved', False)) is not bool for i in mcp):
        raise ManifestError('invalid_mcp_policy')


def _call(args, alias: str, home: Path, cwd: Path, *, mutation=False):
    env = os.environ.copy()
    env.pop('CLAUDE_CONFIG_DIR', None)
    if alias != 'v1':
        env['CLAUDE_CONFIG_DIR'] = str(home)
    try:
        completed = subprocess.run(['claude', 'plugin', *args], cwd=str(cwd), env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=TIMEOUT_SECONDS, check=False)
        if completed.returncode:
            return None, 'cli_error'
        raw = completed.stdout.splitlines()[-1] if mutation else completed.stdout
        data = json.loads(raw)
        if mutation:
            # A zero exit without a documented success ACK is still ambiguous.
            expected = 'marketplace-add' if args[:2] == ['marketplace', 'add'] else 'install'
            if (not isinstance(data, dict) or data.get('command') != expected
                    or data.get('outcome') not in ('ok', 'failed')
                    or not isinstance(data.get('message'), str)):
                return None, 'cli_ack_unknown'
            if data['outcome'] == 'failed':
                return None, 'cli_error'
        elif not isinstance(data, list):
            return None, 'cli_schema_error'
        return data, ''
    except subprocess.TimeoutExpired:
        return None, 'cli_timeout_unknown'
    except (OSError, ValueError, IndexError):
        return None, 'cli_unavailable_or_schema_error'


def _plugins(alias, home, cwd, identifier, approved_root=None):
    raw, error = _call(['list', '--json'], alias, home, cwd)
    if error:
        return [], error
    projected = []
    for item in raw:
        if isinstance(item, dict) and item.get('id') != identifier:
            continue
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str)
                or not IDENTIFIER.fullmatch(item['id']) or item.get('scope') not in SCOPES
                or type(item.get('enabled')) is not bool):
            return [], 'cli_schema_error'
        if item['scope'] != 'user' and item.get('projectPath') != str(cwd):
            return [], 'plugin_project_scope_unverified'
        version = item.get('folderVersion', item.get('version'))
        path = item.get('readFromFolder', item.get('installPath'))
        if (not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9.+_-]{1,128}', version)
                or version.lower() in {'unknown', 'none', 'null'}
                or not isinstance(path, str) or len(path) > 4096
                or any(ord(c) < 32 or ord(c) == 127 for c in path)
                or not Path(path).is_absolute() or '..' in Path(path).parts):
            return [], 'cli_schema_error'
        # Folder overrides must be concrete no-follow directories even in-home.
        if 'readFromFolder' in item and not checked_directory(path):
            return [], 'plugin_path_unapproved'
        # Retain account paths or descendants of the exact approved marketplace.
        if not Path(path).is_relative_to(home) and not (approved_root
                and Path(path).is_relative_to(Path(approved_root))
                and checked_directory(path)):
            return [], 'plugin_path_unapproved'
        projected.append(dict(id=item['id'], version=version, scope=item['scope'],
                              enabled=item['enabled'], path=path))
    return projected, ''


def _markets(alias, home, cwd, market):
    raw, error = _call(['marketplace', 'list', '--json'], alias, home, cwd)
    if error:
        return {}, error
    projected = {}
    for item in raw:
        if isinstance(item, dict) and item.get('name') != market:
            continue
        if not isinstance(item, dict) or not safe_name(item.get('name')):
            return {}, 'cli_schema_error'
        # Never retain arbitrary source commands, helpers, diagnostics or IDs.
        if item['name'] in projected:
            return {}, 'cli_schema_error'
        source = item.get('source')
        if source in ('url', 'git') and safe_url(item.get('url')):
            projected[item['name']] = item['url']
        elif source == 'directory':
            projected[item['name']] = checked_directory(item.get('path'))
        else:
            projected[item['name']] = None
    return projected, ''


def reconcile(source_alias, source, alias, target, cwd, policy, mcp, *, status=False, apply=False):
    rows = []
    for server in mcp:
        rows.append(dict(path='mcp/' + server['name'], action='blocked',
                         reason='mcp_safe_transport_unverified' if server.get('approved') else 'mcp_approval_required'))
    items = policy.get('items', [])
    if not items:
        return rows
    try:
        # Reject symlink ancestry before allowing CLI to select either account.
        for home in (source, target):
            with directory(home):
                pass
    except (OSError, ValueError, RuntimeError):
        return rows + [dict(path='plugin/' + i['id'], action='blocked', reason='account_home_unverified') for i in items]
    for item in items:
        identifier, scope = item['id'], item['scope']
        market = identifier.split('@')[1]
        approval = policy.get('marketplaces', {}).get(market, {})
        url = approval.get('url') if 'url' in approval else checked_directory(approval.get('path'))
        root = url if approval.get('approved') is True and 'path' in approval else None
        source_plugins, source_error = _plugins(source_alias, source, cwd, identifier, root)
        target_plugins, target_error = _plugins(alias, target, cwd, identifier, root)
        source_markets, sm_error = _markets(source_alias, source, cwd, market)
        target_markets, tm_error = _markets(alias, target, cwd, market)
        row = dict(path='plugin/' + identifier, action='blocked', reason='plugin_approval_required')
        rows.append(row)
        def outcome(action, reason):
            row.update(action=action, reason=reason)
        error = source_error or target_error or sm_error or tm_error
        if error:
            outcome('blocked' if error in {'plugin_path_unapproved', 'plugin_project_scope_unverified',
                                          'cli_schema_error'} else 'error', error)
            continue
        origin = [p for p in source_plugins if p['id'] == identifier and p['scope'] == scope]
        existing = [p for p in target_plugins if p['id'] == identifier]
        if len(origin) != 1 or not origin[0]['enabled']:
            outcome('blocked', 'source_enabled_scope_unverified')
            continue
        if existing:
            same = len(existing) == 1 and existing[0]['scope'] == scope
            outcome('in_sync' if same and existing[0]['enabled'] and existing[0]['version'] == origin[0]['version'] else 'conflict',
                    'plugin_matches' if same and existing[0]['enabled'] and existing[0]['version'] == origin[0]['version'] else 'plugin_drift')
            continue
        if (approval.get('approved') is not True or not (safe_url(url) or ('path' in approval and root))
                or source_markets.get(market) != url):
            outcome('blocked', 'marketplace_approval_required')
            continue
        if not item.get('approved') or not item.get('verified'):
            continue
        if scope != 'user' and item.get('repo_used') is not True:
            outcome('blocked', 'repo_usage_approval_required')
            continue
        if market in target_markets and target_markets[market] != url:
            outcome('conflict', 'marketplace_drift')
            continue
        if not apply:
            outcome('missing' if status else 'would_create', 'official_install_required')
            continue
        added = False
        if market not in target_markets:
            _, error = _call(['marketplace', 'add', url, '--scope', scope, '--json'], alias, target, cwd, mutation=True)
            if error:
                outcome('error', error)
                continue
            observed, error = _markets(alias, target, cwd, market)
            if error or observed.get(market) != url:
                outcome('error', 'marketplace_partial_unverified')
                continue
            target_markets = observed
            added = True
        _, error = _call(['install', identifier, '--scope', scope, '--json'], alias, target, cwd, mutation=True)
        if error:
            outcome('error', 'marketplace_added_' + error if added else error)
            continue
        observed, error = _plugins(alias, target, cwd, identifier, root)
        matches = [p for p in observed if p['id'] == identifier and p['scope'] == scope]
        if error or len(matches) != 1:
            outcome('error', 'install_partial_unverified')
        elif not matches[0]['enabled'] or matches[0]['version'] != origin[0]['version']:
            outcome('conflict', 'installed_plugin_drift')
        else:
            outcome('applied', 'official_install_verified')
            target_plugins = observed
    return rows
