"""Accounts CLI with fixed diagnostics and approved asset creation only."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from pathlib import Path

from shared_config import CONFIG_ENV, GLOBAL_CONFIG, GlobalConfigError, load_config
from .account_sync_manifest import ManifestError, manifest_from
from .account_sync_plan import build_plan


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's default error includes arbitrary selector values.
        raise ManifestError('invalid_arguments')


def register(subparsers) -> None:
    parser = subparsers.add_parser('accounts', help='status và dry-run tài sản tài khoản')
    commands = parser.add_subparsers(dest='accounts_cmd', required=True,
                                    parser_class=_Parser)
    for name in ('status', 'sync'):
        command = commands.add_parser(name)
        select = command.add_mutually_exclusive_group()
        select.add_argument('--account')
        select.add_argument('--all', action='store_true')
        command.add_argument('--json', action='store_true')
        command.add_argument('--cwd')
        if name == 'sync':
            command.add_argument('--apply', action='store_true')


MAX_CONFIG_PATH = 4096
REDACTED_CONFIG_PATH = '[redacted_config_path]'


def _global_config_path(cwd: str | None) -> str:
    """Reproduce loader selection without exposing exception or file contents."""
    from .config import git_toplevel
    try:
        raw = os.environ.get(CONFIG_ENV) or GLOBAL_CONFIG
        if len(raw) > MAX_CONFIG_PATH or any(not c.isprintable() for c in raw):
            return REDACTED_CONFIG_PATH
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = git_toplevel(Path(cwd) if cwd else Path.cwd()) / path
        normalized = str(path.resolve())
        if len(normalized) > MAX_CONFIG_PATH or any(
                not c.isprintable() for c in normalized):
            return REDACTED_CONFIG_PATH
        return normalized
    except (OSError, ValueError, RuntimeError):
        return REDACTED_CONFIG_PATH


def command(args) -> int:
    try:
        # Shared loader warnings/errors can contain raw file names. This command
        # exposes only fixed diagnostics, while retaining internal provenance.
        with contextlib.redirect_stderr(io.StringIO()):
            result = load_config(Path(args.cwd) if args.cwd else None)
        manifest, provenance = manifest_from(result)
        rows = build_plan(result, manifest, account=args.account,
                          status=args.accounts_cmd == 'status',
                          apply=getattr(args, 'apply', False))
        code = (2 if any(r['action'] == 'error' for r in rows) else
                1 if any(r['action'] not in {'in_sync', 'applied'} for r in rows) else 0)
        payload = dict(schema_version=1, items=rows,
                       sources={k: v for k, v in provenance.items()
                                if k in {'sources.claude', 'items', 'exclude', 'settings.shared_keys'}})
    except GlobalConfigError:
        code = 2
        with contextlib.redirect_stderr(io.StringIO()):
            config_path = _global_config_path(args.cwd)
        payload = dict(schema_version=1, items=[], reason='global_config_error',
                       config_path=config_path)
    except (ManifestError, OSError, ValueError, TypeError, KeyError):
        code = 2
        payload = dict(schema_version=1, items=[], reason='config_or_io_error')
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if 'reason' in payload:
            print(payload['reason'], payload.get('config_path', ''))
        for row in payload['items']:
            fields = [row[k] for k in ('provider', 'account', 'path', 'key', 'action', 'reason')]
            if 'backup_path' in row:
                fields.append(row['backup_path'])
            print(' '.join(fields))
    return code
