"""Conservative collection of registered, finished hand worktrees."""
from __future__ import annotations

import datetime as dt
import fcntl
import json
import hashlib
import os
import re
import sys
from collections import namedtuple
from pathlib import Path

from . import isolation
from .constants import HAND_RUNS_SUBDIR

FINISHED = frozenset(('ok', 'failed', 'timeout', 'capped', 'quota', 'not_logged_in',
                      'completed', 'cancelled', 'error'))
SETTLE_KINDS = ('finalize', 'report', 'ledger', 'go_ledger', 'usage_state')
GIT_OPTIONAL_LOCKS = 'GIT_OPTIONAL_LOCKS'
COMMIT_SHA = re.compile(r'\A(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
Pinned = namedtuple('Pinned', ('sha', 'detached'))


def _read(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('invalid registry')
    return value


def _git_env() -> dict:
    """Clean GIT_* env plus GIT_OPTIONAL_LOCKS=0; never mutates os.environ."""
    env = isolation._git_env()
    env[GIT_OPTIONAL_LOCKS] = '0'
    return env


def _git(path: Path, *args: str) -> str:
    """Read-only git query: never refreshes or writes a statcache index."""
    return isolation._git(list(args), path, env=_git_env()).stdout.decode().strip()


def _common(path: Path) -> Path:
    return Path(_git(path, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()


def _live(value: object) -> bool:
    if value is None:
        return False
    if type(value) is not int or value <= 0:
        return True
    try:
        os.kill(value, 0)
        return True
    except ProcessLookupError:
        return False
    except (OSError, OverflowError, TypeError, ValueError):
        return True


def _bytes(path: Path) -> int:
    """Only lstat metadata, never follow links or open worktree content."""
    size = path.lstat().st_size
    if path.is_dir() and not path.is_symlink():
        for child in path.iterdir():
            size += _bytes(child)
    return size


def _managed_settled(cfg, data: dict, path: Path) -> bool:
    key = data.get('execution_key')
    from .execution_state import ExecutionKey, ExecutionRecord

    root = Path(getattr(cfg, 'paseo', {}).get('state_root') or
                cfg.machine_state_dir / 'executions')
    if root.is_symlink():
        return False
    if not root.exists():
        return key is None
    if not root.is_dir():
        return False
    # Store.get() initializes and locks the store. GC only consumes existing
    # atomic JSON snapshots; filenames never establish ownership or identity.
    records = []
    for item in root.glob('*.json'):
        if item.is_symlink() or not item.is_file():
            return False
        record = ExecutionRecord.from_dict(_read(item))
        identity = record.key
        if (not isinstance(identity.invocation_id, str) or not identity.invocation_id
                or not isinstance(identity.attempt_id, str) or not identity.attempt_id
                or type(identity.epoch) is not int or identity.epoch < 1):
            return False
        digest = hashlib.sha256(json.dumps(dict(
            invocation_id=identity.invocation_id, attempt_id=identity.attempt_id,
            epoch=identity.epoch), sort_keys=True).encode()).hexdigest()
        if item.name != digest + '.json':
            return False
        records.append(record)
    if key is not None:
        if isinstance(key, str):
            invocation, attempt, epoch = key.split(':')
            key = ExecutionKey(invocation, attempt, int(epoch))
        elif isinstance(key, dict):
            key = ExecutionKey(**key)
        else:
            return False
        if type(key.epoch) is not int or key.epoch < 1:
            return False
        matches = [r for r in records if r.key == key]
        run_matches = [r for r in records if r.attempt.run_id == data['run_id']]
        if len(run_matches) != 1 or run_matches[0].key != key:
            return False
    else:
        matches = [r for r in records if r.attempt.run_id == data['run_id']]
        if not matches:
            return True
    if len(matches) != 1:
        return False
    record = matches[0]
    # A followup of the same invocation may hold a newer epoch (even intent or
    # run_id=None) that reuses this worktree: only the sole latest epoch settles.
    siblings = [r for r in records
                if r.key.invocation_id == record.key.invocation_id
                and r.key.epoch >= record.key.epoch]
    if siblings != [record]:
        return False
    # Any placement binding present in the registry must agree with intent.
    for name in ('target_key', 'project_id', 'workspace_id', 'agent_id', 'thread_id'):
        if name in data and data[name] != getattr(record.attempt, name):
            return False
    if not (Path(record.invocation.isolated_cwd).is_absolute()
            and Path(record.invocation.source_cwd).is_absolute()):
        return False
    return (record.attempt.run_id == data['run_id']
            and Path(record.invocation.isolated_cwd).resolve() == path
            and _common(Path(record.invocation.source_cwd)) == _common(cfg.root)
            and record.state in ('awaiting_review', 'archived')
            and record.reservation is None
            and (record.outcome or {}).get('quiescent') is True
            and (record.quiescence or {}).get('confirmed') is True
            and bool((record.quiescence or {}).get('evidence'))
            and all(record.settle_keys.get(k, {}).get('state') == 'completed'
                    for k in SETTLE_KINDS))


def _registry_path(cfg, data: dict, path: Path) -> bool:
    source = Path(data['cwd']).resolve()
    if source == path:
        return True
    source_root = isolation.git_root(source)
    return (source_root is not None and _common(source_root) == _common(cfg.root)
            and path == cfg.worktree_root.resolve() / (source_root.name + '-' + data['run_id']))


def _pinned_head(path: Path) -> Pinned:
    """HEAD plus detached state; a symref HEAD survives `worktree remove`, a raw SHA does not."""
    sha = _git(path, 'rev-parse', '--verify', 'HEAD')
    if not COMMIT_SHA.match(sha):
        raise ValueError('HEAD is not a commit SHA')
    status = isolation._git(['symbolic-ref', '--no-recurse', '--quiet', 'HEAD'], path,
                            env=_git_env(), ok=False).returncode
    if status not in (0, 1):
        # Only 1 means a well-formed detached HEAD; any other status is a failed query.
        raise ValueError('HEAD symbolic-ref query failed')
    return Pinned(sha, status == 1)


def classify(cfg, path: Path) -> dict:
    row = dict(path=str(path), name=path.name, classification='unknown',
               reason='no exact registry ownership', bytes=0, head='', branch='')
    try:
        root = cfg.worktree_root.resolve()
        if path.is_symlink() or path.resolve().parent != root or path.resolve() == cfg.root.resolve():
            return row
        path = path.resolve()
        registered = _git(cfg.root, 'worktree', 'list', '--porcelain', '-z').split('\0')
        if ('worktree ' + str(path)) not in registered:
            return row
        if isolation.git_root(path) != path or _common(path) != _common(cfg.root):
            return row
        # Names are lookup hints only; registry cwd and run id must also agree.
        matches = []
        for registry in (cfg.machine_state_dir / HAND_RUNS_SUBDIR).glob('*.json'):
            data = _read(registry)
            run_id = data.get('run_id')
            if (isinstance(run_id, str) and run_id == registry.stem
                    and path.name.endswith('-' + run_id)
                    and Path(data.get('cwd', '')).is_absolute()
                    and _registry_path(cfg, data, path)):

                matches.append(data)
        if len(matches) != 1:
            return row
        data = matches[0]
        row['registry_revision'] = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        row['run_id'] = data['run_id']
        head = _pinned_head(path)
        if head.detached:
            # Detached HEAD is only reachable through this worktree: remove drops it for good.
            recorded = data.get('base_commit')
            if not isinstance(recorded, str) or not COMMIT_SHA.match(recorded):
                row['reason'] = 'detached HEAD without recorded base commit'
                return row
            if recorded != head.sha:
                row['reason'] = 'detached HEAD moved past recorded base commit'
                return row
        row['head'] = head.sha
        row['branch'] = _git(path, 'rev-parse', '--abbrev-ref', 'HEAD')
        st = path.lstat()
        row['identity'] = [st.st_dev, st.st_ino]
        row['bytes'] = _bytes(path)
        # Removal must never take registry/journal state or run artifacts with it.
        run_dir = Path(data.get('run_dir', ''))
        if any(p == path or path in p.parents for p in [cfg.machine_state_dir.resolve()] +
               ([run_dir.resolve()] if run_dir.is_absolute() else [])):
            row['reason'] = 'state or run artifacts inside worktree'
            return row
        if data.get('status') not in FINISHED or any(_live(data.get(k)) for k in ('pid', 'child_pid')):
            row['reason'] = 'running or unknown runtime'
            return row
        if not _managed_settled(cfg, data, path):
            row['reason'] = 'managed execution not settled'
            return row
        artifact = (run_dir.is_absolute() and any((run_dir / name).is_file()
                    for name in ('changes.patch', 'report.md')))
        if type(data.get('exit_code')) is not int and not artifact:
            row['reason'] = 'no completion evidence'
            return row
        if _git(path, 'status', '--porcelain', '--untracked-files=all'):
            row.update(classification='dirty', reason='unpreserved working changes')
            return row
        row.update(classification='finished', reason='registered finished clean worktree')
    except (OSError, ValueError, TypeError, AttributeError, IndexError, KeyError, isolation.IsolationError):
        row.update(classification='unknown', reason='metadata unavailable or inconsistent')
    return row


def collect(cfg) -> list[dict]:
    if not cfg.worktree_root.is_dir():
        return []
    return [classify(cfg, path) for path in sorted(cfg.worktree_root.iterdir())
            if path.is_dir() or path.is_symlink()]


def run_gc(cfg, *, apply: bool = False) -> list[dict]:
    rows = collect(cfg)
    if not apply:
        return rows
    # Same source repository serializes GC across linked worktrees and configs.
    common = _common(cfg.root)
    with (common / 'hand-ext-gc.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        journal_path = cfg.machine_state_dir / 'worktree-gc.jsonl'
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        # Must be writable before any destructive operation.
        with journal_path.open('a') as journal:
            for row in rows:
                if row['classification'] != 'finished':
                    continue
                fresh = classify(cfg, Path(row['path']))
                if fresh != row:
                    row['reason'] = 'changed during recheck'
                    continue
                error = isolation._remove_worktree(cfg.root, Path(row['path']),
                                                   cfg.worktree_root, gc_safe=True)
                row['removed'] = not bool(error)
                if error:
                    row['error'] = 'git refused removal'
                    row['reason'] = row['error']
                    continue
                entry = dict(row, time=dt.datetime.now().astimezone().isoformat())
                journal.write(json.dumps(entry) + '\n')
                journal.flush()
                os.fsync(journal.fileno())
            isolation._git(['worktree', 'prune'], cfg.root)
    return rows


def command(cfg, args) -> int:
    try:
        rows = run_gc(cfg, apply=args.apply)
    except (OSError, isolation.IsolationError):
        print('hand-ext gc: apply or metadata operation failed', file=sys.stderr)
        return 1
    eligible = [row for row in rows if row['classification'] == 'finished']
    if args.json:
        print(json.dumps(dict(applied=args.apply, worktrees=rows,
                              eligible=len(eligible), bytes=sum(r['bytes'] for r in eligible)), ensure_ascii=False, indent=2))
    else:
        for row in rows:
            print(f"{row['classification']} {row['path']} {row['bytes']} bytes: {row['reason']}")
    return int(any(row.get('error') for row in rows))
