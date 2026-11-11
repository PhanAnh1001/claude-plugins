"""Fail-closed recovery of old registered worktrees; never delete refs."""
from __future__ import annotations

import functools
import signal
import threading
import hashlib
import json
import os
import shutil
import stat
import subprocess
import time
from pathlib import Path

LEGACY = "legacy-recoverable"
QUIET_SECONDS = 24 * 60 * 60
AUTO_SECONDS = 20


def bounded(function):
    """Auto GC also bounds legacy helpers, compression and lock acquisition."""
    @functools.wraps(function)
    def call(*args, **kwargs):
        deadline = kwargs.get("deadline")
        if deadline is None:
            return function(*args, **kwargs)
        if threading.current_thread() is not threading.main_thread():
            raise ValueError("auto GC requires a bounded main-thread pass")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("GC time budget exhausted")
        previous = signal.getsignal(signal.SIGALRM)
        timer = signal.getitimer(signal.ITIMER_REAL)
        if timer[0]:
            raise ValueError("auto GC skipped while another deadline is active")
        def expired(_signum, _frame):
            raise RuntimeError("GC time budget exhausted")
        signal.signal(signal.SIGALRM, expired)
        signal.setitimer(signal.ITIMER_REAL, remaining)
        try:
            return function(*args, **kwargs)
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous)
    return call


class Scan:
    """One collection pass: bounded commands and per-repository object cache."""
    def __init__(self, deadline: float | None = None):
        self.deadline = deadline
        self.objects: dict[str, set[tuple[str, str]]] = {}

    def check_time(self) -> float:
        remaining = 30 if self.deadline is None else self.deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("GC time budget exhausted")
        return min(30, remaining)

    def command(self, args: list[str]) -> bytes:
        result = subprocess.run(args, capture_output=True, timeout=self.check_time(),
                                env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
        if result.returncode or result.stderr.strip():
            raise ValueError("runtime/git snapshot unavailable")
        return result.stdout

    def git(self, repo: Path, *args: str) -> bytes:
        return self.command(["git", "-C", str(repo), *args])

    def entries(self, repo: Path) -> list[dict]:
        rows, row = [], {}
        for field in self.git(repo, "worktree", "list", "--porcelain", "-z").split(b"\0"):
            if not field:
                if row:
                    rows.append(row)
                    row = {}
                continue
            key, _, value = field.partition(b" ")
            row[os.fsdecode(key)] = os.fsdecode(value)
        if row:
            rows.append(row)
        return rows

    def reachable(self, repo: Path) -> set[tuple[str, str]]:
        key = str(repo.resolve())
        if key not in self.objects:
            blobs = {line.split(b" ", 1)[0].decode() for line in
                     self.git(repo, "rev-list", "--all", "--objects").splitlines()}
            modes = set()
            # Raw history includes each introduced blob and its committed mode.
            for line in self.git(repo, "log", "--all", "--raw", "--root", "--no-renames",
                                 "--no-abbrev", "--format=").splitlines():
                fields = line.split(b"\t", 1)[0].split()
                if line.startswith(b":") and len(fields) == 5:
                    mode, blob = fields[1].decode(), fields[3].decode()
                    if blob in blobs:
                        modes.add((blob, mode))
            self.objects[key] = modes
        return self.objects[key]

    def runtime_clear(self, path: Path) -> None:
        from side_session.checkout import _cwd_clear
        _cwd_clear(path, timeout=self.check_time())
        if not shutil.which("paseo"):
            raise ValueError("paseo unavailable")
        data = json.loads(self.command(["paseo", "ls", "--json"]))
        if isinstance(data, dict):
            data = data.get("agents")
        if not isinstance(data, list):
            raise ValueError("paseo snapshot unknown")
        for agent in data:
            if not isinstance(agent, dict) or not isinstance(agent.get("cwd"), str):
                raise ValueError("paseo cwd unknown")
            if Path(agent["cwd"]).resolve().is_relative_to(path) and (agent.get("archived") is not True
                    and not isinstance(agent.get("archivedAt"), str)):
                raise ValueError("unarchived Paseo agent inside worktree")

    def evaluate(self, repo: Path, path: Path) -> dict:
        result = dict(eligible=False, reason="legacy metadata unavailable")
        try:
            entries = self.entries(repo)
            entry = next((e for e in entries[1:] if e.get("worktree") == str(path)), None)
            if (entry is None or path == repo.resolve() or path != path.resolve()
                    or "locked" in entry or "prunable" in entry):
                raise ValueError("main/locked/unregistered worktree")
            refs = self.git(path, "for-each-ref", "--contains=HEAD", "--format=%(refname)",
                            "refs/heads", "refs/remotes", "refs/tags")
            if not refs.strip():
                raise ValueError("HEAD not reachable from any ref")
            ignored = self.git(path, "ls-files", "--others", "--ignored", "--exclude-standard", "-z")
            for raw in filter(None, ignored.split(b"\0")):
                parts = Path(os.fsdecode(raw)).parts
                if parts[0] != "output" and "node_modules" not in parts:
                    raise ValueError("ignored file outside output/node_modules")
            dirty = self.git(path, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=no")
            fields = iter(dirty.split(b"\0"))
            changes = []
            signatures = []
            main = Path(entries[0]["worktree"])
            for field in fields:
                if not field:
                    continue
                raw = field[3:]
                if b"R" in field[:2] or b"C" in field[:2]:
                    next(fields)  # original name; destination is the extant file
                relative = Path(os.fsdecode(raw))
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("unsafe status path")
                target = path / relative
                if relative.parts[0] == "output":
                    if target.exists() or target.is_symlink():
                        changes.append(target.lstat().st_mtime)
                    continue
                if any(p.is_symlink() for p in target.parents if p != path and path in p.parents):
                    raise ValueError("symlink path component")
                if not target.exists() and not target.is_symlink():
                    continue  # deleted files are recoverable from HEAD
                info = target.lstat()
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("changed non-regular file")
                changes.append(info.st_mtime)
                blob = self.git(path, "hash-object", "--no-filters", "--", str(target)).decode().strip()
                mode = "100755" if info.st_mode & stat.S_IXUSR else "100644"
                peer = main / relative
                same = (peer.is_file() and not peer.is_symlink()
                        and not any(p.is_symlink() for p in peer.parents)
                        and hashlib.sha256(target.read_bytes()).digest() == hashlib.sha256(peer.read_bytes()).digest())
                if not same and (blob, mode) not in self.reachable(repo):
                    raise ValueError("changed/untracked file has no recoverable copy: " + str(relative))
                signatures.append((str(relative), blob, mode, info.st_mtime_ns, info.st_ctime_ns))
            gitdir = Path(os.fsdecode(self.git(path, "rev-parse", "--absolute-git-dir")).strip())
            changes.extend(p.stat().st_mtime for p in (gitdir / "HEAD", gitdir / "index", gitdir / "logs/HEAD") if p.exists())
            if not changes or time.time() - max(changes) < QUIET_SECONDS:
                raise ValueError("worktree not quiet for 24h")
            self.runtime_clear(path)
            info = path.stat()
            result.update(eligible=True, reason="legacy-recoverable: HEAD and changed files recoverable; quiet >=24h",
                          identity=(info.st_dev, info.st_ino, entry.get("HEAD"), tuple(signatures), dirty.hex()))
        except (OSError, ValueError, StopIteration, subprocess.TimeoutExpired) as exc:
            result["reason"] = str(exc)
        return result

    def remove(self, repo: Path, path: Path) -> str:
        from side_session.checkout import _output_signature, backup_output
        before = self.evaluate(repo, path)
        if not before["eligible"]:
            raise ValueError(before["reason"])
        # Only llm artifacts are backed up; reject other output data before force.
        for item in (path / "output").rglob("*"):
            if (item.is_symlink() or not item.is_dir()) and not item.is_relative_to(path / "output/llm"):
                raise ValueError("output outside output/llm is not backed up")
        signature = _output_signature(path)
        backup = backup_output(repo, path, check=self.check_time)
        self.objects.clear()  # refs may have changed while the archive was written
        fresh = self.evaluate(repo, path)
        if (fresh != before or _output_signature(path) != signature):
            raise ValueError("worktree/output changed during backup")
        self.git(repo, "worktree", "remove", "--force", "--", str(path))
        return backup
