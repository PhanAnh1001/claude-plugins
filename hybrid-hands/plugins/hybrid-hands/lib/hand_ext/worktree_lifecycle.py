"""Durable ownership and conservative cleanup of isolated hand checkouts."""
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .isolation import IsolationContext, ApplyResult

from .locked_json import read_json, write_atomic

REGENERABLE_IGNORED_PARTS = frozenset({
    '__pycache__',
    '.pytest_cache',
    '.mypy_cache',
    '.ruff_cache',
    'node_modules',
    '.DS_Store',
})
REGENERABLE_IGNORED_SUFFIXES = ('.pyc', '.pyo')


def _first_preserved_ignored(worktree: Path) -> str:
    """Keep unknown ignored data; only discard explicitly regenerable caches.

    Use NUL-delimited Git paths so spaces and newlines remain part of a path.
    Match whole components, rather than substrings such as node_modules-backup.
    """
    from . import isolation
    ignored = isolation._git([
        'ls-files', '--others', '--ignored', '--exclude-standard', '-z',
    ], worktree)
    for raw_path in ignored.stdout.split(b'\0'):
        if not raw_path:
            continue
        path = os.fsdecode(raw_path)
        if REGENERABLE_IGNORED_PARTS.intersection(Path(path).parts):
            continue
        if path.endswith(REGENERABLE_IGNORED_SUFFIXES):
            continue
        return path
    return ''


def ownership(root: Path, worktree: Path, base_commit: str, mode: str, backend: str) -> dict:
    from . import isolation
    common = isolation._git(['rev-parse', '--git-common-dir'], root).stdout.decode().strip()
    return dict(worktree=str(worktree.resolve()), base_commit=base_commit,
                repo_common_dir=str((root / common).resolve()), mode=mode, backend=backend)


def record(path: Path, **updates) -> None:
    """Ownership is mandatory, unlike the best-effort live usage projection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = read_json(path, {})
    write_atomic(path, dict(data, **updates))
    sync_file(path)


def sync_file(path: Path) -> None:
    with path.open('rb') as stream:
        os.fsync(stream.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def remove_preserved(ctx: "IsolationContext", result: "ApplyResult", run_dir: Path) -> str:
    """Recheck HEAD, ignored files and the full binary snapshot before removal."""
    from . import isolation
    if ctx.worktree is None or not ctx.worktree.exists():
        return ''
    try:
        patch = result.patch_path
        if patch is None or patch.resolve().is_relative_to(ctx.worktree.resolve()):
            return 'chưa bảo toàn: patch nằm trong checkout hoặc thiếu'
        sync_file(patch)
        if ctx.dirty:
            base_patch = run_dir / isolation.CHANGES_BASE_PATCH_FILE
            sync_file(base_patch)
            expected = isolation._git(['diff', '--binary', '--no-color', '--no-ext-diff',
                '--no-textconv', '--src-prefix=a/', '--dst-prefix=b/', ctx.base_commit,
                ctx.baseline_tree, '--'], ctx.worktree).stdout
            if base_patch.read_bytes() != expected:
                return 'chưa bảo toàn: baseline thay đổi'
        if ctx.base_commit and isolation._head_commit(ctx.worktree) != ctx.base_commit:
            return 'chưa bảo toàn: HEAD thay đổi'
        ignored = _first_preserved_ignored(ctx.worktree)
        if ignored:
            return f'chưa bảo toàn: file ignored {ignored}'
        final = isolation._snapshot_tree(ctx.worktree, run_dir, 'cleanup')
        actual = isolation._git(['diff', '--binary', '--no-color', '--no-ext-diff',
            '--no-textconv', '--src-prefix=a/', '--dst-prefix=b/', ctx.baseline_tree,
            final, '--'], ctx.worktree).stdout
        if actual != patch.read_bytes():
            return 'chưa bảo toàn: patch không khớp checkout'
        return isolation.cleanup(ctx, keep=False)
    except (OSError, isolation.IsolationError) as exc:
        return f'chưa bảo toàn: {exc}'
