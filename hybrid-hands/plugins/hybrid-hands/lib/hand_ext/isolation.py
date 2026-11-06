"""Run a hand in a clean git worktree and return its changes as a patch.

The worktree starts at HEAD, receives the caller's uncommitted tracked diff and the
untracked files that are *not* ignored, and never receives ignored files (`.env`,
`*.demo.env`, ...). Untracked files whose basename looks like a secret are skipped even
when the repo forgot to ignore them, and symlinks resolving outside the repo are not
copied. After the run the worktree is snapshotted into `changes.patch` and that patch is
applied back to the caller's working tree unless `--no-apply` is used.
"""
from __future__ import annotations

import fnmatch
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

from .constants import (
    APPLY_CONFLICT, APPLY_EMPTY, APPLY_ERROR, APPLY_OK, APPLY_SKIPPED,
    CHANGES_PATCH_FILE, ISOLATION_NONE, ISOLATION_WORKTREE, SECRET_FILE_ALLOW,
    SECRET_FILE_PATTERNS, SECRET_SKIP_PREFIX, SYMLINK_OUTSIDE_NOTE,
)

if TYPE_CHECKING:
    from .config import ExtConfig

GIT = "git"
DEFAULT_REPO_NAME = "repo"
DETAIL_MAX_LEN = 300
CHANGES_BASE_PATCH_FILE = "changes.base.patch"
GIT_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")
NOT_GIT_WARNING = (
    "cwd không phải git repo: isolation=worktree mặc định chuyển sang none, hand chạy "
    "trực tiếp trong thư mục gốc (không có worktree sạch); kiểm tra không có .env hay "
    "secret trong cwd trước khi chạy"
)


class IsolationError(ValueError):
    """A clean worktree cannot be prepared or inspected; the run must stop."""


@dataclass
class IsolationChoice:
    mode: str
    explicit: bool = False
    warning: str = ""


@dataclass
class IsolationContext:
    mode: str
    source_root: Path
    run_cwd: Path
    worktree: Optional[Path] = None
    worktree_root: Optional[Path] = None
    baseline_tree: str = ""
    warning: str = ""
    skipped_secrets: List[str] = field(default_factory=list)
    base_commit: Optional[str] = None
    dirty: bool = False
    dirty_files: List[str] = field(default_factory=list)


@dataclass
class ApplyResult:
    status: str = APPLY_SKIPPED
    files: List[str] = field(default_factory=list)
    patch_path: Optional[Path] = None
    detail: str = ""


def _error_text(proc: subprocess.CompletedProcess, argv: List[str]) -> str:
    raw = proc.stderr.decode("utf-8", "replace").strip()
    first = raw.splitlines()[0] if raw else f"git {argv[0]} thoát mã {proc.returncode}"
    return first[:DETAIL_MAX_LEN]


def _git_env() -> Dict[str, str]:
    """Inherit the caller's env but never let an outer GIT_DIR/GIT_INDEX_FILE decide."""
    return {key: value for key, value in os.environ.items() if key not in GIT_ENV_DROP}


def _git(argv: List[str], cwd: Path, *, input_data: Optional[bytes] = None,
         env: Optional[Dict[str, str]] = None, ok: bool = True) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run([GIT, *argv], cwd=str(cwd), input=input_data,
                              capture_output=True, check=False,
                              env=env if env is not None else _git_env())
    except OSError as exc:
        raise IsolationError(f"không chạy được git tại {cwd}: {exc}") from exc
    if ok and proc.returncode != 0:
        raise IsolationError(_error_text(proc, argv))
    return proc


def git_root(path: Path) -> Optional[Path]:
    """Toplevel of the git repo containing `path`, or None when it is not a repo."""
    try:
        proc = _git(["rev-parse", "--show-toplevel"], path, ok=False)
    except IsolationError:
        return None
    if proc.returncode != 0:
        return None
    text = proc.stdout.decode("utf-8", "replace").strip()
    return Path(text).resolve() if text else None


def resolve_choice(cfg: "ExtConfig", cwd: Path, cli_isolation: Optional[str]) -> IsolationChoice:
    """Apply the CLI override, then the default/fallback rule for a non-git cwd."""
    requested = cli_isolation or cfg.isolation
    explicit = bool(cli_isolation) or cfg.isolation_explicit
    if requested == ISOLATION_NONE:
        return IsolationChoice(ISOLATION_NONE, explicit=explicit)
    if git_root(cwd) is None:
        if explicit:
            raise IsolationError(
                f"isolation=worktree được yêu cầu nhưng {cwd} không phải git repo; "
                "dùng --isolation none nếu thật sự muốn chạy trực tiếp")
        return IsolationChoice(ISOLATION_NONE, explicit=False, warning=NOT_GIT_WARNING)
    return IsolationChoice(ISOLATION_WORKTREE, explicit=explicit)


def prepare(cfg: "ExtConfig", cwd: Path, run_id: str, run_dir: Path,
            choice: IsolationChoice) -> IsolationContext:
    """Create the clean worktree and capture its baseline tree."""
    resolved_cwd = cwd.resolve()
    if choice.mode == ISOLATION_NONE:
        return IsolationContext(ISOLATION_NONE, resolved_cwd, resolved_cwd,
                                warning=choice.warning)
    root = git_root(resolved_cwd)
    if root is None:
        raise IsolationError(f"{resolved_cwd} không phải git repo")
    name = root.name or DEFAULT_REPO_NAME
    worktree = cfg.worktree_root / f"{name}-{run_id}"
    if worktree.exists() or worktree.is_symlink():
        raise IsolationError(f"worktree đã tồn tại: {worktree}")
    skipped: List[str] = []
    try:
        worktree.parent.mkdir(parents=True, exist_ok=True)
        base_commit = _head_commit(root)
        _git(["worktree", "add", "--detach", str(worktree), "HEAD"], root)
        _apply_tracked_changes(root, worktree)
        skipped = _copy_untracked(root, worktree, run_dir,
                                  _generated_paths(cfg, root, run_dir))
        baseline = _snapshot_tree(worktree, run_dir, "baseline")
        dirty_files = sorted(_changed_files(worktree, base_commit, baseline))
        if dirty_files:
            _write_base_patch(worktree, base_commit, baseline, run_dir)
    except BaseException:
        _remove_worktree(root, worktree, cfg.worktree_root)
        raise
    run_cwd = _run_cwd(root, worktree, resolved_cwd)
    return IsolationContext(ISOLATION_WORKTREE, root, run_cwd, worktree=worktree,
                            worktree_root=cfg.worktree_root, baseline_tree=baseline,
                            skipped_secrets=skipped, base_commit=base_commit,
                            dirty=bool(dirty_files), dirty_files=dirty_files)


def _head_commit(root: Path) -> str:
    commit = _git(["rev-parse", "HEAD"], root).stdout.decode("utf-8", "replace").strip()
    if not commit:
        raise IsolationError("git rev-parse HEAD không trả về commit")
    return commit


def _write_base_patch(worktree: Path, base_commit: str, baseline: str,
                      run_dir: Path) -> None:
    """Save the uncommitted diff the worktree started from, before the hand runs."""
    diff = _git(["diff", "--binary", "--no-color", "--no-ext-diff", "--no-textconv",
                 "--src-prefix=a/", "--dst-prefix=b/", base_commit, baseline, "--"],
                worktree).stdout
    path = run_dir / CHANGES_BASE_PATCH_FILE
    try:
        path.write_bytes(diff)
    except OSError as exc:
        raise IsolationError(f"không ghi được {path.name}: {exc}") from exc


def _apply_tracked_changes(root: Path, worktree: Path) -> None:
    diff = _git(["diff", "HEAD", "--binary", "--no-color", "--no-ext-diff", "--no-textconv",
                 "--src-prefix=a/", "--dst-prefix=b/", "--"], root).stdout
    if not diff.strip():
        return
    _git(["apply", "--binary", "--whitespace=nowarn", "-"], worktree, input_data=diff)


def _copy_untracked(root: Path, worktree: Path, run_dir: Path,
                    skip_paths: List[Path]) -> List[str]:
    """Copy untracked non-ignored files, skipping secret-like names and escaping symlinks."""
    raw = _git(["ls-files", "--others", "--exclude-standard", "-z"], root).stdout
    skipped: List[str] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        rel = os.fsdecode(item)
        source = root / rel
        if _is_within(source, worktree) or _is_within(source, run_dir):
            continue
        if any(_is_within(source, path) for path in skip_paths):
            continue
        if not _safe_relpath(rel):
            raise IsolationError(f"đường dẫn untracked không hợp lệ: {rel!r}")
        if _is_secret_file(rel):
            skipped.append(rel)
            continue
        if source.is_symlink() and _symlink_outside_root(source, root):
            skipped.append(f"{rel} ({SYMLINK_OUTSIDE_NOTE})")
            continue
        destination = worktree / rel
        if destination.exists() or destination.is_symlink():
            raise IsolationError(f"đường dẫn untracked đã có trong worktree: {rel}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            if source.is_symlink():
                destination.symlink_to(os.readlink(source))
            elif source.is_file():
                shutil.copy2(source, destination)
        except OSError as exc:
            raise IsolationError(f"không chép được untracked {rel}: {exc}") from exc
    return skipped


def _is_secret_file(rel: str) -> bool:
    """True when the basename looks like a secret (allow-listed examples win)."""
    name = Path(rel).name
    if any(fnmatch.fnmatchcase(name, pattern) for pattern in SECRET_FILE_ALLOW):
        return False
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in SECRET_FILE_PATTERNS)


def _symlink_outside_root(source: Path, root: Path) -> bool:
    """A symlink is safe only when it is relative, stays inside the repo and is not a secret.

    An absolute link would still point at the source tree from inside the worktree (reads
    of ignored files, writes that bypass the patch), so it is never copied.
    """
    try:
        if os.path.isabs(os.readlink(source)):
            return True
        target = source.resolve()
    except (OSError, RuntimeError):
        return True
    return not _is_within(target, root) or _is_secret_file(target.name)


def _generated_paths(cfg: "ExtConfig", root: Path, run_dir: Path) -> List[Path]:
    """Wrapper-owned paths never belong in the hand's workspace (old reports, ledgers)."""
    candidates = [run_dir, cfg.runs_dir, cfg.ledger, cfg.quota_state, cfg.machine_state_dir]
    root = root.resolve()
    return [path for path in candidates if path.resolve() != root]


def _safe_relpath(rel: str) -> bool:
    path = Path(rel)
    return bool(rel) and not path.is_absolute() and ".." not in path.parts


def _is_within(path: Path, parent: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(Path(os.path.abspath(parent)))
    except ValueError:
        return False
    return True


def _snapshot_tree(worktree: Path, run_dir: Path, tag: str) -> str:
    """Tree hash of the whole working tree, using a private index (no repo index changes)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    index = (run_dir / f".isolation-{tag}.index").resolve()
    env = {key: value for key, value in os.environ.items() if key not in GIT_ENV_DROP}
    env["GIT_INDEX_FILE"] = str(index)
    try:
        _git(["add", "-A"], worktree, env=env)
        tree = _git(["write-tree"], worktree, env=env).stdout.decode().strip()
        if not tree:
            raise IsolationError("git write-tree không trả về tree")
        return tree
    finally:
        try:
            index.unlink()
        except OSError:
            pass


def _run_cwd(root: Path, worktree: Path, cwd: Path) -> Path:
    try:
        relative = cwd.relative_to(root)
    except ValueError:
        return worktree
    target = worktree / relative
    target.mkdir(parents=True, exist_ok=True)
    return target


def finalize(ctx: IsolationContext, run_dir: Path, *, apply_changes: bool,
             skip_reason: str = "--no-apply") -> ApplyResult:
    """Snapshot the worktree, save `changes.patch`, and apply it when allowed."""
    if ctx.mode != ISOLATION_WORKTREE or ctx.worktree is None:
        return ApplyResult(APPLY_SKIPPED, detail="không dùng worktree")
    patch_path = run_dir / CHANGES_PATCH_FILE
    files: List[str] = []
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        final_tree = _snapshot_tree(ctx.worktree, run_dir, "final")
        diff = _git(["diff", "--binary", "--no-color", "--no-ext-diff", "--no-textconv",
                     "--src-prefix=a/", "--dst-prefix=b/",
                     ctx.baseline_tree, final_tree, "--"], ctx.worktree, ok=False)
        if diff.returncode != 0:
            return ApplyResult(APPLY_ERROR, detail=_error_text(diff, ["diff"]))
        patch = diff.stdout
        files = _changed_files(ctx.worktree, ctx.baseline_tree, final_tree)
        patch_path.write_bytes(patch)
    except (IsolationError, OSError) as exc:
        return ApplyResult(APPLY_ERROR, files=files, detail=str(exc))
    if not patch.strip():
        return ApplyResult(APPLY_EMPTY, files=files, patch_path=patch_path)
    if not apply_changes:
        return ApplyResult(APPLY_SKIPPED, files=files, patch_path=patch_path,
                           detail=skip_reason)
    try:
        return _apply_patch(ctx.source_root, patch, patch_path, files)
    except (IsolationError, OSError) as exc:
        return ApplyResult(APPLY_ERROR, files=files, patch_path=patch_path, detail=str(exc))


def _changed_files(worktree: Path, baseline: str, final: str) -> List[str]:
    proc = _git(["diff", "--name-only", "-z", baseline, final, "--"], worktree, ok=False)
    if proc.returncode != 0:
        raise IsolationError(_error_text(proc, ["diff", "--name-only"]))
    return [os.fsdecode(item) for item in proc.stdout.split(b"\0") if item]


def _apply_patch(root: Path, patch: bytes, patch_path: Path,
                 files: List[str]) -> ApplyResult:
    check = _git(["apply", "--check", "--binary", "--whitespace=nowarn", "-"], root,
                 input_data=patch, ok=False)
    if check.returncode != 0:
        return ApplyResult(APPLY_CONFLICT, files=files, patch_path=patch_path,
                           detail=_error_text(check, ["apply"]))
    applied = _git(["apply", "--binary", "--whitespace=nowarn", "-"], root,
                   input_data=patch, ok=False)
    if applied.returncode != 0:
        return ApplyResult(APPLY_CONFLICT, files=files, patch_path=patch_path,
                           detail=_error_text(applied, ["apply"]))
    return ApplyResult(APPLY_OK, files=files, patch_path=patch_path)


def cleanup(ctx: IsolationContext, *, keep: bool) -> str:
    """Remove the worktree unless it is kept; return a warning when cleanup failed."""
    if ctx.mode != ISOLATION_WORKTREE or ctx.worktree is None or keep:
        return ""
    return _remove_worktree(ctx.source_root, ctx.worktree, ctx.worktree_root)


def _remove_worktree(root: Path, worktree: Path, worktree_root: Optional[Path]) -> str:
    try:
        if worktree.resolve() == root.resolve():
            return "từ chối xoá thư mục nguồn"
        if worktree_root is not None and worktree.parent.resolve() != worktree_root.resolve():
            return f"vị trí worktree không khớp worktree_root: {worktree}"
        if not worktree.exists() and not worktree.is_symlink():
            _git(["worktree", "prune"], root, ok=False)
            return ""
        removed = _git(["worktree", "remove", "--force", str(worktree)], root, ok=False)
        if removed.returncode == 0:
            pruned = _git(["worktree", "prune"], root, ok=False)
            return "" if pruned.returncode == 0 else _error_text(pruned, ["worktree", "prune"])
        detail = _error_text(removed, ["worktree", "remove"])
        shutil.rmtree(worktree)
        _git(["worktree", "prune"], root, ok=False)
        return f"git worktree remove lỗi ({detail}); đã xoá thư mục"
    except (OSError, IsolationError) as exc:
        return f"không dọn được worktree: {exc}"


def _apply_text(result: ApplyResult) -> str:
    count = len(result.files)
    if result.status == APPLY_OK:
        return f"ok ({count} file)"
    if result.status == APPLY_CONFLICT:
        detail = f"; {result.detail}" if result.detail else ""
        return f"xung đột — không ghi đè ({count} file){detail}"
    if result.status == APPLY_EMPTY:
        return "bỏ qua (patch rỗng)"
    if result.status == APPLY_SKIPPED:
        return f"bỏ qua ({result.detail or 'không áp'})"
    if result.status == APPLY_ERROR:
        return f"lỗi: {result.detail}"
    return result.status


def report_block(ctx: IsolationContext, result: ApplyResult, *, kept: bool,
                 cleanup_note: str = "") -> str:
    lines = ["## Cách ly worktree", f"- Chế độ: `{ctx.mode}`"]
    if ctx.warning:
        lines.append(f"- Cảnh báo: {ctx.warning}")
    if ctx.mode != ISOLATION_WORKTREE:
        lines.append("- Chạy trực tiếp trong thư mục gốc; không tạo worktree.")
        return "\n".join(lines)
    lines.append(f"- Nguồn: `{ctx.source_root}`")
    lines.append(f"- Worktree: `{ctx.worktree}`")
    if ctx.skipped_secrets:
        lines.append(SECRET_SKIP_PREFIX + ", ".join(ctx.skipped_secrets))
    if result.patch_path is None:
        lines.append("- Patch: không tạo được")
    else:
        lines.append(f"- Patch: `{result.patch_path}` ({len(result.files)} file)")
    lines.append(f"- Áp về gốc: {_apply_text(result)}")
    if result.files:
        lines.append("- File thay đổi: " + ", ".join(f"`{name}`" for name in result.files))
    if kept:
        lines.append(f"- Worktree: giữ lại `{ctx.worktree}` (--keep-worktree)")
    elif cleanup_note:
        lines.append(f"- Worktree: dọn lỗi — {cleanup_note}")
    else:
        lines.append("- Worktree: đã dọn")
    return "\n".join(lines)


def summary_line(ctx: IsolationContext, result: ApplyResult, *, kept: bool,
                 cleanup_note: str = "") -> str:
    if ctx.mode != ISOLATION_WORKTREE:
        suffix = f" — {ctx.warning}" if ctx.warning else ""
        return f"cách ly: none{suffix}"
    if kept:
        state = "giữ lại"
    elif cleanup_note:
        state = "dọn lỗi"
    else:
        state = "đã dọn"
    return f"cách ly: worktree; áp patch: {_apply_text(result)}; worktree: {state}"


def failure_block(message: str) -> str:
    return "\n".join(["## Cách ly worktree", f"- Lỗi: {message}"])


def append_report(path: Path, block: str) -> None:
    """Append the isolation block to report.md without touching the hand's own report."""
    try:
        old = path.read_text(encoding="utf-8") if path.is_file() else ""
        body = old.rstrip()
        text = (body + "\n\n" if body else "") + block.rstrip() + "\n"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        print(f"cảnh báo: không ghi được cách ly vào {path}: {exc}", file=sys.stderr)
