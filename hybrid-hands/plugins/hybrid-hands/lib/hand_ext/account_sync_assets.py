"""Exclusive asset creation through pinned, no-follow directory descriptors."""
from __future__ import annotations

import contextlib
import errno
import fcntl
import os
import stat
from pathlib import Path

from .account_sync_manifest import allowed_path

DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
MAX_IMPORT_BYTES = 16384


@contextlib.contextmanager
def directory(path: Path, *, create_home: bool = False):
    """Never create ancestors outside the exact configured home."""
    fd = os.open('/', DIR_FLAGS)
    try:
        parts = path.absolute().parts[1:]
        for index, part in enumerate(parts):
            if part in {'.', '..'}:
                raise ValueError('invalid_path')
            try:
                child = os.open(part, DIR_FLAGS, dir_fd=fd)
            except FileNotFoundError:
                if not create_home or index != len(parts) - 1:
                    raise
                verify_visible(path.parent, fd)
                os.mkdir(part, mode=0o700, dir_fd=fd)
                child = os.open(part, DIR_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


@contextlib.contextmanager
def parent(home: Path, relative: str, *, create: bool = False):
    with directory(home, create_home=create) as root:
        fd = os.dup(root)
        try:
            visible = home
            for part in Path(relative).parts[:-1]:
                try:
                    child = os.open(part, DIR_FLAGS, dir_fd=fd)
                except FileNotFoundError:
                    if not create:
                        raise
                    verify_visible(visible, fd)
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                    child = os.open(part, DIR_FLAGS, dir_fd=fd)
                os.close(fd)
                fd = child
                visible = visible / part
            yield fd
        finally:
            os.close(fd)


def fingerprint(info) -> tuple[int, int, int]:
    return info.st_dev, info.st_ino, info.st_mode


def verify_visible(path: Path, fd: int) -> None:
    """Rewalk no-follow ancestry; reject detached/replaced pinned directories."""
    with directory(path) as visible:
        if fingerprint(os.fstat(visible)) != fingerprint(os.fstat(fd)):
            raise FileExistsError('directory_changed')


def children(home: Path, relative: str) -> list[str]:
    """Names only; propagate missing/IO failures for per-item diagnostics."""
    with directory(home / relative) as fd:
        return sorted(os.listdir(fd))


def _existing(fd: int, name: str, origin: Path, content: bytes | None, destination: Path) -> tuple[str, str]:
    try:
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return 'missing', 'absent'
    if stat.S_ISLNK(info.st_mode):
        # Accept canonical relative spelling without opening arbitrary link targets.
        link = os.readlink(name, dir_fd=fd)
        same = link in {str(origin), os.path.relpath(origin, destination.parent)}
        return ('in_sync', 'same_link') if same and content is None else ('conflict', 'different_link')
    if content is not None and stat.S_ISREG(info.st_mode):
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            actual = os.fstat(file_fd)
            if (actual.st_dev, actual.st_ino) != (info.st_dev, info.st_ino):
                return 'conflict', 'asset_changed'
            if os.read(file_fd, MAX_IMPORT_BYTES) == content:
                return 'in_sync', 'same_import'
        finally:
            os.close(file_fd)
    return 'conflict', 'existing_asset'


def _asset(source: Path, target: Path, item: dict, *, status: bool, apply: bool, lock_fd: int | None = None) -> tuple[str, str]:
    relative = item['path']
    if not allowed_path('claude', relative):
        return 'blocked', 'private_path'
    if relative.split('/')[0] == 'hooks':
        return 'blocked', 'hook_evidence_required'
    if '/' not in relative and relative != 'CLAUDE.md':
        return 'blocked', 'child_manifest_required'
    origin = source / relative
    content = None
    if relative == 'CLAUDE.md':
        text = str(origin)
        if any(ord(c) < 32 or ord(c) == 127 for c in text) or '\\' in text:
            return 'blocked', 'invalid_import_path'
        content = ('@' + text.replace(' ', '\\ ') + '\n').encode()
    try:
        with parent(source, relative) as source_fd:
            info = os.stat(origin.name, dir_fd=source_fd, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                return 'blocked', 'source_symlink'
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                return 'blocked', 'source_type'
            if content is not None and not stat.S_ISREG(info.st_mode):
                return 'blocked', 'source_type'
            target_identity = None
            try:
                with parent(target, relative) as target_fd:
                    target_identity = fingerprint(os.fstat(target_fd))
                    outcome = _existing(target_fd, origin.name, origin, content, target / relative)
                if outcome[0] != 'missing':
                    return outcome
            except FileNotFoundError:
                pass
            if not apply:
                return ('missing' if status else 'would_create'), 'manifest_approval_required'
            if item.get('approved') is not True:
                return 'blocked', 'manifest_approval_required'
            # Reopen both chains immediately before mutation; no pathname mkdir/write.
            with parent(source, relative) as fresh_source, parent(target, relative, create=True) as target_fd:
                if fingerprint(os.fstat(fresh_source)) != fingerprint(os.fstat(source_fd)):
                    return 'blocked', 'source_changed'
                if target_identity is not None and fingerprint(os.fstat(target_fd)) != target_identity:
                    return 'conflict', 'asset_changed'
                fresh = os.stat(origin.name, dir_fd=fresh_source, follow_symlinks=False)
                if (fresh.st_dev, fresh.st_ino, fresh.st_mode) != (info.st_dev, info.st_ino, info.st_mode):
                    return 'blocked', 'source_changed'
                outcome = _existing(target_fd, origin.name, origin, content, target / relative)
                if outcome[0] != 'missing':
                    return outcome
                verify_visible(target.parent, lock_fd)
                verify_visible(source / Path(relative).parent, fresh_source)
                verify_visible(target / Path(relative).parent, target_fd)
                if fingerprint(os.stat(origin.name, dir_fd=fresh_source, follow_symlinks=False)) != fingerprint(info):
                    return 'blocked', 'source_changed'
                if content is None:
                    os.symlink(str(origin), origin.name, dir_fd=target_fd)
                else:
                    fd = os.open(origin.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=target_fd)
                    try:
                        with os.fdopen(fd, 'wb') as stream:
                            stream.write(content)
                            stream.flush()
                            os.fsync(stream.fileno())
                    except OSError:
                        # Do not delete or overwrite an item after a partial failure.
                        raise
            return 'applied', 'asset_created'
    except FileNotFoundError:
        return 'blocked', 'source_missing'
    except FileExistsError:
        return 'conflict', 'asset_changed'
    except OSError as exc:
        if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
            return 'blocked', 'symlink_parent'
        return 'error', 'asset_io_error'


def asset(source: Path, target: Path, item: dict, *, status: bool, apply: bool) -> tuple[str, str]:
    if not apply:
        return _asset(source, target, item, status=status, apply=False)
    try:
        # A stable parent lock also covers creation of a missing target home.
        # Sibling targets serialize too; no lock file or out-of-home mkdir.
        with directory(target.parent) as lock_fd:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            try:
                verify_visible(target.parent, lock_fd)
                return _asset(source, target, item, status=status, apply=True, lock_fd=lock_fd)
            finally:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
    except FileExistsError:
        return 'conflict', 'asset_changed'
    except FileNotFoundError:
        return 'blocked', 'target_parent_missing'
    except OSError as exc:
        return ('blocked', 'symlink_parent') if exc.errno in {errno.ELOOP, errno.ENOTDIR} else ('error', 'asset_io_error')
