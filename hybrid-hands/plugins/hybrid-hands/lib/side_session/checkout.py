"""Owned checkout lifecycle; branch refs and runtime history are always retained."""
from __future__ import annotations

import os
import subprocess
import tarfile
import time
from pathlib import Path

from hand_ext.locked_json import locked
from . import constants as C, gc, state


def intent(cfg, st: state.SessionState) -> None:
    st.checkout_owner = str(gc.common_dir(cfg.repo))
    st.checkout_branch = f"{C.BRANCH_PREFIX}{st.name}"
    st.checkout_phase = "intent"
    state.save(cfg.state_dir, st)


def created(cfg, st: state.SessionState) -> None:
    st.checkout_phase = "created"
    state.save(cfg.state_dir, st)


def _owned(cfg, st: state.SessionState) -> Path:
    path = Path(st.dir)
    if (not st.worktree or st.role == "main" or st.checkout_phase != "created"
            or path != cfg.worktree_root / st.name
            or path.absolute() != path.resolve()
            or st.checkout_owner != str(gc.common_dir(cfg.repo))):
        raise ValueError("checkout ownership unconfirmed")
    return path


def _cwd_clear(path: Path, timeout: float = 30) -> None:
    result = subprocess.run(["lsof", "-n", "-a", "-d", "cwd", "-Fn"],
                            capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0 or result.stderr.strip():
        raise ValueError("process cwd snapshot unavailable")
    for line in result.stdout.splitlines():
        if line.startswith("n") and Path(line[1:]).is_relative_to(path):
            raise ValueError("process cwd inside checkout")


def _output_signature(path: Path) -> list[tuple]:
    """Detect output writes during compression before allowing forced removal."""
    root = path / "output"
    paths = [root, *root.rglob("*")] if root.exists() else []
    return [(str(p.relative_to(path)), p.lstat().st_ino, p.lstat().st_size,
             p.lstat().st_mtime_ns, p.lstat().st_ctime_ns) for p in sorted(paths)]


def backup_output(repo: Path, path: Path, *, check=lambda: None) -> str:
    """Exclusive, durable output backup shared by owned and legacy cleanup."""
    output = path / "output/llm"
    if (path / "output").is_symlink() or output.is_symlink():
        raise ValueError("output path is a symlink")
    if not output.exists():
        return ""
    backup_dir = Path.home() / ".hybrid-hands/wt-output-backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{repo.name}-wt-{path.name}-output-llm-{time.time_ns()}.tar.gz"
    with backup.open("xb") as target:
        with tarfile.open(fileobj=target, mode="w:gz", dereference=False) as archive:
            def bounded(info):
                check()
                return info
            archive.add(output, arcname="output/llm", filter=bounded)
        target.flush()
        os.fsync(target.fileno())
    return str(backup)


def _inspect(cfg, st: state.SessionState) -> tuple[dict, bytes]:
    path = _owned(cfg, st)
    entries = gc.worktrees(cfg.repo)
    entry = next((e for e in entries[1:] if e.get("worktree") == str(path)), None)
    if entry is None or "locked" in entry or "prunable" in entry:
        raise ValueError("worktree registration unavailable/locked")
    identity = gc.identity(path, entry, Path(st.checkout_owner), st)
    if identity["branch"] != "refs/heads/" + st.checkout_branch:
        raise ValueError("checkout branch changed")
    if (path / "output").is_symlink() or (path / "output/llm").is_symlink():
        raise ValueError("output path is a symlink")
    # Include ignored files: --force must never discard an unrelated ignored file.
    tracked = gc.git(path, "status", "--porcelain=v1", "-z", "--untracked-files=no")
    if tracked:
        raise ValueError("tracked changes not committed")
    others = gc.git(path, "ls-files", "--others", "-z")
    if any(not os.fsdecode(p).startswith("output/llm/") for p in others.split(b"\0") if p):
        raise ValueError("untracked/ignored files not preserved")
    _cwd_clear(path)
    return identity, others


def remove_done(cfg, st: state.SessionState) -> None:
    if not st.worktree or st.status != C.STATUS_DONE or st.checkout_removed_at:
        return
    try:
        with locked(gc.common_dir(cfg.repo) / "side-session-gc"):
            identity, files = _inspect(cfg, st)
            signature = _output_signature(Path(st.dir))
            output = Path(st.dir) / "output/llm"
            if output.exists():
                backup = backup_output(cfg.repo, Path(st.dir))
                st.checkout_backup = str(backup)
                state.save(cfg.state_dir, st)
            fresh, fresh_files = _inspect(cfg, st)
            if (fresh != identity or fresh_files != files
                    or _output_signature(Path(st.dir)) != signature):
                raise ValueError("checkout changed during backup")
            args = ["worktree", "remove"]
            if files:
                if not st.checkout_backup:
                    raise ValueError("output backup missing")
                args.append("--force")
            gc.git(cfg.repo, *args, "--", st.dir)
            st.checkout_removed_at = time.time()
            st.checkout_reason = "removed; branch retained"
    except (OSError, ValueError, subprocess.TimeoutExpired, tarfile.TarError) as exc:
        st.checkout_reason = str(exc)
    state.save(cfg.state_dir, st)
    print(f"{st.name}: checkout {st.checkout_reason}")


def restore(cfg, st: state.SessionState) -> bool:
    if not st.checkout_removed_at:
        return True
    try:
        with locked(gc.common_dir(cfg.repo) / "side-session-gc"):
            path = _owned(cfg, st)
            if path.exists():
                raise ValueError("checkout path already exists; reconcile before retry")
            gc.git(cfg.repo, "show-ref", "--verify", "refs/heads/" + st.checkout_branch)
            gc.git(cfg.repo, "worktree", "add", "--", st.dir, st.checkout_branch)
            st.checkout_removed_at = None
            st.checkout_reason = "restored from branch"
            state.save(cfg.state_dir, st)
        return True
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"{st.name}: checkout restore failed ({exc}); no runtime reopened")
        return False
