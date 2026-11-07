"""Collect the run ledgers that belong to one repo, including its linked worktrees.

`load_config` roots the ledger at the git toplevel it is run from, so a hand-ext run
inside a worktree writes a ledger under that worktree. A report for the repo must read
the main checkout plus every worktree whose git common dir matches, while never guessing
a repo from a directory name. Reports are read-only: they never create lock files or
directories in the repos they inspect.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import ExtConfig, load_config

GIT = "git"
GIT_DIR_NAME = ".git"
GIT_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")
WORKTREE_LINE = "worktree "
META_FILE = "meta.json"
REPO_PATH_KEYS = ("git_common_dir", "repo", "repo_root", "cwd", "base")
KIND_CWD = "cwd"
KIND_WORKTREE = "worktree"
KIND_LEFTOVER = "worktree còn sót"
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
SHA_MIN_LEN = 7


@dataclass
class LedgerSource:
    root: Path
    ledger: Path
    kind: str
    entries: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Report:
    root: Path
    common_dir: Optional[Path]
    sources: List[LedgerSource]
    entries: List[Dict[str, Any]]
    notes: List[str]


def _normalise(path: Path) -> Path:
    try:
        return path.expanduser().resolve()
    except (OSError, RuntimeError):
        return path.expanduser().absolute()


def _git(root: Path, *args: str) -> Optional[subprocess.CompletedProcess]:
    env = {key: value for key, value in os.environ.items() if key not in GIT_ENV_DROP}
    try:
        return subprocess.run([GIT, "-C", str(root), *args], capture_output=True, text=True,
                              check=False, env=env)
    except OSError:
        return None


def git_common_dir(path: Path) -> Optional[Path]:
    """Common git dir shared by a checkout and all of its linked worktrees."""
    if not path.is_dir():
        return None
    proc = _git(path, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if proc is None or proc.returncode != 0:
        return None
    text = proc.stdout.strip()
    if not text:
        return None
    found = Path(text)
    if not found.is_absolute():
        found = path / found
    return _normalise(found)


def _worktree_roots(root: Path) -> List[Path]:
    proc = _git(root, "worktree", "list", "--porcelain")
    if proc is None or proc.returncode != 0:
        return []
    roots: List[Path] = []
    for line in proc.stdout.splitlines():
        if line.startswith(WORKTREE_LINE):
            raw = line[len(WORKTREE_LINE):].strip()
            if raw:
                roots.append(Path(raw))
    return roots


def _containers(root: Path, cfg: ExtConfig) -> List[Path]:
    """Where hand-ext/side-session keep worktrees: configured root and sibling container."""
    candidates = [cfg.worktree_root]
    if (root / GIT_DIR_NAME).is_file():
        candidates.append(root.parent)
    seen: set[Path] = set()
    containers: List[Path] = []
    for candidate in candidates:
        path = _normalise(candidate)
        if path not in seen:
            seen.add(path)
            containers.append(path)
    return containers


def _children(container: Path, notes: List[str]) -> List[Path]:
    if not container.is_dir():
        return []
    try:
        entries = sorted(container.iterdir(), key=lambda path: path.name)
    except OSError as exc:
        notes.append(f"bỏ qua thư mục worktree {container}: {exc}")
        return []
    return [path for path in entries if path.is_dir() and not path.is_symlink()]


def _read_ledger(path: Path, notes: List[str]) -> Optional[List[Dict[str, Any]]]:
    """Plain read: unlike the writer path this must not create a .lock file."""
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        notes.append(f"bỏ qua sổ {path}: {exc}")
        return None
    if not isinstance(data, list):
        notes.append(f"bỏ qua sổ {path}: cần JSON list")
        return None
    return [entry for entry in data if isinstance(entry, dict)]


def _load(path: Path, notes: List[str]) -> Optional[ExtConfig]:
    try:
        return load_config(path)
    except (OSError, ValueError) as exc:
        notes.append(f"bỏ qua {path}: không đọc được cấu hình: {exc}")
        return None


def _looks_like_sha(value: str) -> bool:
    return len(value) >= SHA_MIN_LEN and all(char in HEX_DIGITS for char in value)


def _entry_path(raw: Any, base: Path) -> Optional[Path]:
    if not isinstance(raw, str):
        return None
    value = raw.strip()
    if not value or _looks_like_sha(value):
        return None  # base_commit is a SHA, not a repo identifier
    path = Path(os.path.expanduser(value))
    return path if path.is_absolute() else base / path


def _path_in_repo(path: Path, common: Path) -> bool:
    found = git_common_dir(path)
    if found is not None:
        return found == common
    normal = _normalise(path)
    return normal == common or normal == common.parent


def _safe_run_id(raw: Any) -> Optional[str]:
    value = str(raw or "").strip()
    if not value or value in (".", ".."):
        return None
    path = Path(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        return None
    return value


def _meta_for(raw_run_id: Any, *configs: ExtConfig) -> Dict[str, Any]:
    run_id = _safe_run_id(raw_run_id)
    if run_id is None:
        return {}
    for cfg in configs:
        path = cfg.runs_dir / run_id / META_FILE
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict):
            return data
    return {}


def _entry_matches(entry: Dict[str, Any], candidate_root: Path, candidate_cfg: ExtConfig,
                   selected_cfg: ExtConfig, common: Path) -> bool:
    meta = _meta_for(entry.get("run_id"), selected_cfg, candidate_cfg)
    for source in (entry, meta):
        for key in REPO_PATH_KEYS:
            path = _entry_path(source.get(key), candidate_root)
            if path is not None and _path_in_repo(path, common):
                return True
    return False


def _add_source(path: Path, kind: str, cfg: Optional[ExtConfig], selected_root: Path,
                common: Optional[Path], sources: List[LedgerSource],
                notes: List[str]) -> None:
    if path != selected_root and common is not None and git_common_dir(path) != common:
        notes.append(f"bỏ qua {path}: khác git common dir")
        return
    current = cfg or _load(path, notes)
    if current is None:
        return
    if path != selected_root and not current.ledger.is_file():
        return
    entries = _read_ledger(current.ledger, notes)
    if entries is None:
        return
    sources.append(LedgerSource(path, current.ledger, kind, entries))


def _add_leftover(path: Path, selected_root: Path, selected_cfg: ExtConfig, common: Path,
                  sources: List[LedgerSource], notes: List[str]) -> None:
    current = _load(path, notes)
    if current is None or not current.ledger.is_file():
        return
    if git_common_dir(path) is not None:
        _add_source(path, KIND_WORKTREE, current, selected_root, common, sources, notes)
        return
    entries = _read_ledger(current.ledger, notes)
    if entries is None:
        return
    matched = [entry for entry in entries
               if _entry_matches(entry, path, current, selected_cfg, common)]
    if not matched:
        notes.append(f"bỏ qua sổ {current.ledger}: không xác minh được cùng repo")
        return
    sources.append(LedgerSource(path, current.ledger, KIND_LEFTOVER, matched))


def collect(cfg: ExtConfig) -> Report:
    root = _normalise(cfg.root)
    common = git_common_dir(root)
    notes: List[str] = []
    sources: List[LedgerSource] = []
    seen: set[Path] = set()

    def add(path: Path, kind: str) -> None:
        path = _normalise(path)
        if path in seen:
            return
        seen.add(path)
        if not path.is_dir():
            notes.append(f"worktree đã mất: {path} (không có sổ để đếm)")
            return
        if path != root and common is not None and git_common_dir(path) is None:
            # Still listed as a worktree but its .git is gone: identify it by metadata.
            _add_leftover(path, root, cfg, common, sources, notes)
            return
        _add_source(path, kind, cfg if path == root else None, root, common, sources, notes)

    add(root, KIND_CWD)
    if common is not None:
        for path in _worktree_roots(root):
            add(path, KIND_WORKTREE)
        for container in _containers(root, cfg):
            for child in _children(container, notes):
                child = _normalise(child)
                if child in seen:
                    continue
                seen.add(child)
                _add_leftover(child, root, cfg, common, sources, notes)

    entries: List[Dict[str, Any]] = []
    run_ids: set[str] = set()
    for source in sources:
        for entry in source.entries:
            run_id = str(entry.get("run_id") or "")
            if run_id:
                if run_id in run_ids:
                    continue
                run_ids.add(run_id)
            entries.append(entry)
    return Report(root, common, sources, entries, notes)


def format_scope(report: Report) -> str:
    lines = [f"Phạm vi: repo `{report.root}`"]
    if report.common_dir is not None:
        lines.append(f"- git common dir: `{report.common_dir}`")
    worktrees = [source for source in report.sources if source.kind != KIND_CWD]
    lines.append(f"- Sổ đã đọc: {len(report.sources)} (repo hiện tại + {len(worktrees)} worktree)")
    lines += [f"- {source.kind}: `{source.ledger}`" for source in report.sources]
    lines += [f"- {note}" for note in report.notes]
    return "\n".join(lines)
