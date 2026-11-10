"""Selective settings reconciliation. Contents and exception text stay internal.

ownership[key] requires approved/verified booleans and sha256 of the canonical
JSON source value (UTF-8, sorted keys, compact separators, ensure_ascii=False).
This explicitly approves the complete command/hook value, never merely its name.
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import secrets
import stat
from pathlib import Path

from .account_sync_assets import directory, verify_visible
from .account_sync_manifest import SHARED_KEYS

SETTINGS = 'settings.json'
MAX_BYTES = 8 * 1024 * 1024
# Builtin class, not an errno attribute; a partial errno module cannot change it.
_NOT_FOUND = FileNotFoundError


def _missing(exc: OSError, number: int | None) -> bool:
    """Only os.open's own ENOENT counts; missing errno.ENOENT narrows to it."""
    return isinstance(exc, _NOT_FOUND) and (number is None or exc.errno == number)


class CommitDurabilityUnknown(OSError):
    def __init__(self, backup: Path):
        super().__init__('commit_durability_unknown')
        self.backup = backup



def value_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _read(fd: int) -> tuple[dict, bytes | None, tuple | None, int]:
    try:
        handle = os.open(SETTINGS, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    except FileNotFoundError:
        return {}, None, None, 0o600
    with os.fdopen(handle, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError('invalid_settings')
        content = stream.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError('invalid_settings')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_key')
            result[key] = value
        return result
    def invalid_constant(_):
        raise ValueError('invalid_number')
    data = json.loads(content, object_pairs_hook=unique, parse_constant=invalid_constant)
    if not isinstance(data, dict):
        raise ValueError('invalid_settings')
    identity = (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                info.st_mtime_ns, info.st_ctime_ns, hashlib.sha256(content).digest())
    return data, content, identity, stat.S_IMODE(info.st_mode)


def _backup(home: Path, target: Path, content: bytes | None) -> Path:
    digest = hashlib.sha256(str(target.absolute()).encode()).hexdigest()
    location = home / '.hybrid-hands' / 'backups' / digest
    # All levels are opened without following links; mkdir only inside HOME.
    with directory(home) as root:
        fd = os.dup(root)
        try:
            visible = home
            for part in ('.hybrid-hands', 'backups', digest):
                verify_visible(visible, fd)
                try:
                    os.mkdir(part, 0o700, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
                visible /= part
                if stat.S_IMODE(os.fstat(fd).st_mode) != 0o700:
                    raise PermissionError('backup_mode')
            verify_visible(location, fd)
            # A final file alone is not evidence of a completed backup. Legacy
            # direct writes and interrupted publication fail closed, without reads.
            name = 'original.json' if content is not None else 'absent'
            names = set(os.listdir(fd))
            if names:
                originals = names & {'original.json', 'absent'}
                if len(originals) != 1 or names != originals | {'complete'}:
                    raise ValueError('backup_incomplete')
                for entry in names:
                    info = os.stat(entry, dir_fd=fd, follow_symlinks=False)
                    if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600:
                        raise ValueError('backup_invalid')
                os.fsync(fd)
                return location / originals.pop()
            for final, payload in ((name, content if content is not None else b'absent\n'),
                                   ('complete', b'complete-v1\n')):
                temporary = '.backup-' + secrets.token_hex(12)
                handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=fd)
                # On failure leave artifacts in place: a later attempt must not
                # mistake an unfinished backup for a usable original.
                with os.fdopen(handle, 'wb') as stream:
                    os.fchmod(stream.fileno(), 0o600)
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
                verify_visible(location, fd)
                os.link(temporary, final, src_dir_fd=fd, dst_dir_fd=fd,
                        follow_symlinks=False)
                os.unlink(temporary, dir_fd=fd)
                os.fsync(fd)
            verify_visible(location, fd)
            return location / name
        finally:
            os.close(fd)


def _write(source: Path, target: Path, source_id: tuple, target_id: tuple | None,
           original: bytes | None, data: dict, mode: int) -> Path:
    # Lock a pinned existing parent, covering absent homes without lock files.
    with directory(target.parent) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with directory(source) as src, directory(target, create_home=True) as dst:
            verify_visible(target.parent, lock)
            if _read(src)[2] != source_id or _read(dst)[2] != target_id:
                raise FileExistsError('settings_changed')
            backup = _backup(Path.home(), target / SETTINGS, original)
            temporary = '.settings-' + secrets.token_hex(12)
            handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=dst)
            try:
                with os.fdopen(handle, 'wb') as stream:
                    stream.write((json.dumps(data, ensure_ascii=False, indent=2,
                                             allow_nan=False) + '\n').encode())
                    os.fchmod(stream.fileno(), mode)
                    stream.flush()
                    os.fsync(stream.fileno())
                verify_visible(target.parent, lock)
                verify_visible(source, src)
                verify_visible(target, dst)
                if _read(src)[2] != source_id or _read(dst)[2] != target_id:
                    raise FileExistsError('settings_changed')
                os.replace(temporary, SETTINGS, src_dir_fd=dst, dst_dir_fd=dst)
                try:
                    os.fsync(dst)
                except OSError:
                    raise CommitDurabilityUnknown(backup) from None
            finally:
                try:
                    os.unlink(temporary, dir_fd=dst)
                except FileNotFoundError:
                    pass
            return backup


def reconcile(source: Path, target: Path, policy: dict, *, status: bool,
              apply: bool) -> list[dict]:
    keys = policy.get('shared_keys', [])
    rows = [dict(key=k, action='blocked', reason='ownership_approval_required') for k in keys]
    if not rows:
        return rows
    try:
        try:
            with directory(source) as fd:
                src, _, source_id, _ = _read(fd)
        except OSError as exc:
            if not _missing(exc, getattr(errno, 'ENOENT', None)):
                raise
            # A missing source home (or ancestor) is a policy block, not an IO
            # error; target is left unread and untouched. Later FileNotFound
            # failures stay on the generic OSError path.
            for row in rows:
                row['reason'] = 'source_missing'
            return rows
        try:
            with directory(target) as fd:
                dst, original, target_id, mode = _read(fd)
        except FileNotFoundError:
            # Validate the existing parent even during read-only planning.
            with directory(target.parent):
                pass
            dst, original, target_id, mode = {}, None, None, 0o600
        changed = []
        for row in rows:
            key = row['key']
            evidence = policy.get('ownership', {}).get(key, {})
            if key not in SHARED_KEYS:
                row['reason'] = 'private_key'
            elif key not in src:
                row['reason'] = 'source_missing'
            elif not (evidence.get('approved') is True and evidence.get('verified') is True
                      and evidence.get('sha256') == value_digest(src[key])):
                row['reason'] = 'command_approval_required'
            elif key in dst and value_digest(dst[key]) == value_digest(src[key]):
                row.update(action='in_sync', reason='same_settings')
            else:
                row.update(action=('missing' if key not in dst else 'drift') if status else
                           ('would_create' if key not in dst else 'would_update'), reason='owned_key')
                dst[key] = src[key]
                changed.append(row)
        if apply and changed:
            backup = _write(source, target, source_id, target_id, original, dst, mode)
            for row in changed:
                row.update(action='applied', reason='settings_updated', backup_path=str(backup))
    except CommitDurabilityUnknown as exc:
        for row in changed:
            row.update(action='error', reason='commit_durability_unknown',
                       backup_path=str(exc.backup))
    except FileExistsError:
        for row in rows:
            row.update(action='conflict', reason='settings_changed')
    except OSError as exc:
        policy_error = exc.errno in {errno.ELOOP, errno.ENOTDIR}
        for row in rows:
            row.update(action='blocked' if policy_error else 'error',
                       reason='settings_symlink' if policy_error else 'settings_io_error')
    except (ValueError, UnicodeError, TypeError):
        for row in rows:
            row.update(action='blocked', reason='settings_invalid')
    return rows
