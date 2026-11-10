"""Asset planning and selective settings reconciliation; no private tree discovery."""
from __future__ import annotations

import errno

from .account_sync_manifest import ManifestError, homes_from, allowed_path
from .account_sync_assets import asset, children
from .account_sync_settings import reconcile


def _row(provider: str, account: str, path: str, action: str, reason: str,
         key: str = '') -> dict:
    return dict(provider=provider, account=account, path=path,
                action=action, reason=reason, key=key)


def build_plan(result, manifest: dict, *, account: str | None = None,
               status: bool = False, apply: bool = False) -> list[dict]:
    source_alias, source, targets = homes_from(result, manifest)
    if account is not None:
        if account == source_alias or account not in targets:
            raise ManifestError('invalid_selector')
        targets = {account: targets[account]}
    rows = []
    items = manifest['items'] or [dict(provider='claude', path=p) for p in
                                 ('CLAUDE.md', 'skills', 'agents', 'commands', 'hooks')]
    for name, target in targets.items():
        for item in items:
            if item['provider'] != 'claude' or any(
                    item['path'] == p or item['path'].startswith(p.rstrip('/') + '/')
                    for p in manifest['exclude']):
                continue
            relative = item['path']
            if '/' not in relative and relative != 'CLAUDE.md':
                # Discovery never approves a child and never traverses it.
                try:
                    names = children(source, relative)
                except OSError as exc:
                    action, reason = ('blocked', 'source_missing') if exc.errno == errno.ENOENT else (
                        ('blocked', 'symlink_parent') if exc.errno in {errno.ELOOP, errno.ENOTDIR}
                        else ('error', 'asset_io_error'))
                    rows.append(_row('claude', name, relative, action, reason))
                    continue
                discovered = [dict(provider='claude', path=relative + '/' + child)
                              for child in names
                              if allowed_path('claude', relative + '/' + child)]
                if not discovered:
                    rows.append(_row('claude', name, relative, 'blocked',
                                     'manifest_approval_required'))
                for child in discovered:
                    if any(child['path'] == p or child['path'].startswith(p.rstrip('/') + '/')
                           for p in manifest['exclude']):
                        continue
                    action, reason = asset(source, target, child, status=status, apply=apply)
                    rows.append(_row('claude', name, child['path'], action, reason))
            else:
                action, reason = asset(source, target, item, status=status, apply=apply)
                rows.append(_row('claude', name, relative, action, reason))
        for setting in reconcile(source, target, manifest['settings'], status=status, apply=apply):
            row = _row('claude', name, 'settings.json', setting.pop('action'),
                       setting.pop('reason'), setting.pop('key'))
            row.update(setting)
            rows.append(row)
        from .account_sync_official import reconcile as official
        for entry in official(source_alias, source, name, target, result.root,
                              manifest.get('plugins', {}), manifest.get('mcp', []),
                              status=status, apply=apply):
            rows.append(_row('claude', name, entry['path'], entry['action'], entry['reason']))
    if account is None:
        for relative in ('AGENTS.md', 'skills', 'agents', 'rules'):
            rows.append(_row('codex', 'hand', relative, 'blocked', 'codex_evidence_required'))
    return rows
