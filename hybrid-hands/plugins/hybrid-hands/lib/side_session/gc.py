"""Conservative worktree inspection and explicitly requested garbage collection."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import time
import wt_legacy

from hand_ext.locked_json import locked
from pathlib import Path
from typing import Callable

from . import constants as C, paseo, state
from .config import SideConfig

ENDED = frozenset({C.STATUS_DONE, C.STATUS_STOPPED, C.STATUS_DEAD,
                   C.STATUS_CAPPED, C.STATUS_ERROR})
GIT_TIMEOUT = 30


def git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                            timeout=GIT_TIMEOUT, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    if result.returncode:
        raise ValueError("git metadata unavailable")
    return result.stdout


def runtime_ended(st: state.SessionState, records: list[state.SessionState]) -> bool:
    """Query exact runtime identities without mutating state or workspace visibility."""
    if st.transport == C.TRANSPORT_PASEO:
        if not (st.paseo_agent_id and st.paseo_workspace_id and st.paseo_target):
            return False
        result = paseo.status(st.paseo_agent_id, st.paseo_target)
        if (result.get("agentId") != st.paseo_agent_id
                or result.get("workspaceId") != st.paseo_workspace_id
                or result.get("targetKey") != st.paseo_target
                or result.get("status") not in (*C.PASEO_AGENT_DEAD, C.PASEO_AGENT_IDLE)):
            return False
        if paseo.agent_archive_states([st]).get(st.paseo_agent_id) is not True:
            return False
        if st.paseo_workspace_shared:
            # A shared workspace belongs to the calling chat (see actions._revive_done):
            # side-session never archives it, so the archived agent is the whole proof.
            return True
        return paseo.tidy_workspace(st, records, False).get("archived") is True
    if st.transport != C.TRANSPORT_SCREEN or not st.screen:
        return False
    result = subprocess.run(["screen", "-ls"], capture_output=True, text=True,
                            timeout=GIT_TIMEOUT)
    # macOS screen also exits 1 for a successful, nonempty socket listing.
    # Require a complete snapshot: an exit code alone cannot prove absence.
    import re

    if result.returncode not in (0, 1) or result.stderr.strip():
        return False
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if len(lines) == 1 and re.fullmatch(r"No Sockets found in .+\.", lines[0]):
        return True
    if len(lines) < 3 or lines[0] not in {"There are screens on:", "There is a screen on:"}:
        return False
    trailer = re.fullmatch(r"([1-9][0-9]*) Sockets? in .+\.", lines[-1])
    if trailer is None or int(trailer[1]) != len(lines) - 2:
        return False
    names: set[str] = set()
    for line in lines[1:-1]:
        # Some screen versions include a creation date before the status.
        entry = re.fullmatch(
            r"[1-9][0-9]*\.([^\s]+)\s+(?:\([^()]+\)\s+)?\((?:Attached|Detached)\)", line)
        if entry is None:
            return False
        names.add(entry[1])
    if len(names) != len(lines) - 2:
        return False
    return not any(name in names for name in (st.screen, st.watch_screen) if name)


def worktrees(repo: Path) -> list[dict]:
    entries, current = [], {}
    for field in git(repo, "worktree", "list", "--porcelain", "-z").split(b"\0"):
        if not field:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = field.partition(b" ")
        current[os.fsdecode(key)] = os.fsdecode(value)
    if current:
        entries.append(current)
    return entries


def file_bytes(root: Path, paths: bytes) -> int:
    """lstat only: never follow a symlink in any path component."""
    total = 0
    for raw in set(paths.split(b"\0")) - {b""}:
        relative = Path(os.fsdecode(raw))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("unsafe git path")
        path = root
        for index, part in enumerate(relative.parts):
            path = path / part
            try:
                info = path.lstat()
            except FileNotFoundError:
                break  # deleted tracked file or sparse checkout
            if index == len(relative.parts) - 1:
                if not stat.S_ISDIR(info.st_mode):
                    total += info.st_size
            elif not stat.S_ISDIR(info.st_mode):
                break
    return total


def bases(cfg: SideConfig, st: state.SessionState) -> list[str]:
    base = st.base or cfg.default_base
    if not base or base.startswith("-"):
        raise ValueError("base unknown")
    refs = []
    for ref in (base, f"origin/{base}"):
        try:
            refs.append(git(cfg.repo, "rev-parse", "--verify", f"{ref}^{{commit}}").decode().strip())
        except ValueError:
            continue
    if not refs:
        raise ValueError("base unknown")
    return list(dict.fromkeys(refs))


def merged(path: Path, refs: list[str]) -> tuple[bool, int]:
    ahead = []
    for ref in refs:
        ahead.append(int(git(path, "rev-list", "--count", f"{ref}..HEAD")))
        if ahead[-1] == 0:
            return True, 0
        if not any(line.startswith(b"+") for line in git(path, "cherry", ref, "HEAD").splitlines()):
            return True, min(ahead)
    return False, min(ahead)


def common_dir(repo: Path) -> Path:
    return Path(os.fsdecode(git(repo, "rev-parse", "--path-format=absolute",
                                "--git-common-dir")).strip()).resolve(strict=True)


def identity(path: Path, entry: dict, common: Path, owner: state.SessionState) -> dict:
    """Reject aliases before running any git command against a candidate."""
    absolute = Path(os.path.abspath(path))
    if absolute != path.resolve(strict=True) or not absolute.is_dir():
        raise ValueError("symlink/renamed worktree path")
    if Path(os.path.abspath(owner.dir)) != absolute:
        raise ValueError("ownership path alias")
    info = path.stat()
    if common_dir(path) != common:
        raise ValueError("foreign git common directory")
    head = git(path, "rev-parse", "--verify", "HEAD").decode().strip()
    branch = git(path, "symbolic-ref", "HEAD").decode().strip()
    if head != entry.get("HEAD") or branch != entry.get("branch"):
        raise ValueError("registered worktree identity mismatch")
    return {"device": info.st_dev, "inode": info.st_ino, "head": head,
            "branch": branch, "common_dir": str(common)}


REASON_MAX_CHARS = 160  # keep one gc table row readable


def failure_reason(step: str, exc: BaseException) -> str:
    detail = getattr(exc, "code", None) or str(exc) or type(exc).__name__
    return f"{step} failed: {type(exc).__name__}: {detail}"[:REASON_MAX_CHARS]


def handoff_mirror(cfg: SideConfig, path: Path, relative: str) -> bool:
    """An untracked worktree copy of a handoff that the main handoff dir holds byte-for-byte."""
    try:
        handoff_rel = cfg.handoff_dir.resolve().relative_to(cfg.repo.resolve())
    except ValueError:
        return False
    candidate = Path(relative)
    if candidate.parent != handoff_rel or candidate.suffix not in {".md", C.DONE_SUFFIX}:
        return False
    copy, original = path / candidate, cfg.handoff_dir / candidate.name
    if copy.is_symlink() or not copy.is_file() or not original.is_file():
        return False
    return copy.read_bytes() == original.read_bytes()


def dirty_entries(cfg: SideConfig, path: Path) -> list[str]:
    raw = git(path, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries = [os.fsdecode(item) for item in raw.split(b"\0") if item]
    return [item for item in entries
            if not (item.startswith("?? ") and handoff_mirror(cfg, path, item[3:]))]


def remove_worktree(cfg: SideConfig, path: Path) -> None:
    """Drop re-verified handoff mirrors only, then a non-forced `git worktree remove`."""
    raw = git(path, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    for item in (os.fsdecode(entry) for entry in raw.split(b"\0") if entry):
        if item.startswith("?? ") and handoff_mirror(cfg, path, item[3:]):
            (path / item[3:]).unlink()
    result = subprocess.run(["git", "-C", str(cfg.repo), "worktree", "remove", "--", str(path)],
                            capture_output=True, text=True, timeout=GIT_TIMEOUT)
    if result.returncode:
        raise ValueError(result.stderr.strip().splitlines()[-1] if result.stderr.strip()
                         else f"git exit {result.returncode}")


def inspect(cfg: SideConfig, *, name: str | None = None,
            runtime: Callable = runtime_ended, scan=None) -> dict:
    scan = scan or wt_legacy.Scan()
    records = state.load_all(cfg.state_dir)
    owners: dict[Path, list[state.SessionState]] = {}
    for record in records:
        owners.setdefault(Path(record.dir).resolve(), []).append(record)
    common = common_dir(cfg.repo)
    entries = worktrees(cfg.repo)
    main_path = Path(entries[0]["worktree"]).resolve() if entries else cfg.repo.resolve()
    rows = []
    for entry in entries:
        registered_path = Path(entry["worktree"])
        path = registered_path.resolve()
        matches = owners.get(path, [])
        if name and not any(item.name == name for item in matches):
            continue
        row = dict(class_="E", name=matches[0].name if len(matches) == 1 else path.name,
                   path=str(path), branch=entry.get("branch", "").removeprefix("refs/heads/"),
                   ahead=None, tracked_bytes=None, ignored_bytes=None, reason="no exact plugin ownership")
        rows.append(row)
        if path in {main_path, cfg.repo.resolve()} or any(item.role == "main" for item in matches):
            row.update(class_="D", reason="protected main checkout/session")
            continue
        if len(matches) != 1:
            if matches:
                row.update(class_="D", reason="ambiguous/shared ownership")
            continue
        st = matches[0]
        if st.worktree is not True:
            continue
        row.update(class_="D", reason="runtime/status unknown or active")
        if st.status not in ENDED or st.paseo_send_pending or st.paseo_revived:
            continue
        if "locked" in entry or "prunable" in entry or not row["branch"]:
            row["reason"] = "protected/locked/prunable/detached worktree"
            continue
        step = "identity"
        try:
            row["identity"] = identity(registered_path, entry, common, st)
            step = "runtime"
            if not runtime(st, records):
                row["reason"] = "runtime not ended (agent not archived/closed or screen alive)"
                continue
            step = "bases"
            refs = bases(cfg, st)
            step = "git"
            dirty = dirty_entries(cfg, path)
            row["tracked_bytes"] = file_bytes(path, git(path, "ls-files", "-z", "--cached"))
            row["ignored_bytes"] = file_bytes(path, git(path, "ls-files", "-z", "--others",
                                                       "--ignored", "--exclude-standard"))
            if dirty:
                row.update(class_="C", reason=f"tracked changes or untracked files ({len(dirty)}, e.g. {dirty[0][3:]})"[:REASON_MAX_CHARS])
                continue
            is_merged, row["ahead"] = merged(path, refs)
            row.update(class_="A" if is_merged else "B",
                       reason="merged/equivalent in base" if is_merged else "unmerged commits")
        except (OSError, ValueError, subprocess.TimeoutExpired, paseo.PaseoError) as exc:
            row.update(class_="D", reason=failure_reason(step, exc))
    for row in rows:
        path = Path(row['path'])
        matches = owners.get(path, [])
        entry = next(e for e in entries if Path(e['worktree']).resolve() == path)
        protected = (path in {main_path, cfg.repo.resolve()} or 'locked' in entry
                     or len(matches) > 1 or any(item.role == 'main' or item.paseo_send_pending
                     or item.paseo_revived or item.status in {C.STATUS_RUNNING, C.STATUS_IDLE, C.STATUS_IDLE_NO_DONE}
                     for item in matches))
        if not protected and row['class_'] not in {'A', 'B'}:
            legacy = scan.evaluate(cfg.repo, path)
            if legacy['eligible']:
                row.update(class_=wt_legacy.LEGACY, reason=legacy['reason'],
                           identity=legacy['identity'], tracked_bytes=0, ignored_bytes=0)
            else:
                row['reason'] += '; legacy: ' + legacy['reason']
        row["class"] = row.pop("class_")
    eligible = [row for row in rows if row["class"] in {"A", wt_legacy.LEGACY}]
    return {"dry_run": True, "worktrees": rows,
            "totals": {"eligible": len(eligible), "eligible_bytes": sum(
                row["tracked_bytes"] + row["ignored_bytes"] for row in eligible)}}


def eligible_totals(report: dict, include_unmerged: bool = False) -> None:
    classes = {"A", "B", wt_legacy.LEGACY} if include_unmerged else {"A", wt_legacy.LEGACY}
    rows = [row for row in report["worktrees"] if row["class"] in classes]
    report["totals"] = {"eligible": len(rows), "eligible_bytes": sum(
        row["tracked_bytes"] + row["ignored_bytes"] for row in rows)}


@wt_legacy.bounded
def apply(cfg: SideConfig, *, name: str | None = None,
          include_unmerged: bool = False, prune_branches: bool = False,
          fetch: bool = False, deadline=None) -> dict:
    """Serialize by repository, not by the caller's possibly distinct state dir."""
    from . import checkout
    scan = wt_legacy.Scan(deadline)
    for st in state.load_all(cfg.state_dir):
        if deadline is not None and time.monotonic() >= deadline:
            break
        if (not name or st.name == name) and st.checkout_owner and not st.checkout_removed_at:
            checkout.remove_done(cfg, st)
    common = common_dir(cfg.repo)
    with locked(common / "side-session-gc"):
        if fetch:
            git(cfg.repo, "fetch", "origin")
        report = inspect(cfg, name=name, scan=scan)
        eligible_totals(report, include_unmerged)
        report.update(dry_run=False, errors=[])
        cfg.state_dir.mkdir(parents=True, exist_ok=True)
        # Opening before removal is mandatory: an unavailable audit sink blocks GC.
        with (cfg.state_dir / "worktree-gc.jsonl").open("a", encoding="utf-8") as journal:
            for row in report["worktrees"]:
                if row["class"] not in ({"A", "B", wt_legacy.LEGACY} if include_unmerged else {"A", wt_legacy.LEGACY}):
                    continue
                if deadline is not None and time.monotonic() >= deadline:
                    break
                fresh = inspect(cfg, name=name, scan=scan)["worktrees"]
                current = next((r for r in fresh if r["path"] == row["path"]), None)
                keys = ("name", "path", "branch", "class", "identity")
                if (common_dir(cfg.repo) != common or current is None
                        or any(current.get(k) != row.get(k) for k in keys)):
                    row["result"] = "skipped: identity/class/runtime changed"
                    continue
                try:
                    if row['class'] == wt_legacy.LEGACY:
                        row['backup'] = scan.remove(cfg.repo, Path(row['path']))
                    else:
                        remove_worktree(cfg, Path(row["path"]))
                except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                    row["result"] = f"remove failed: {exc}"[:REASON_MAX_CHARS]
                    report["errors"].append(row["result"])
                    continue
                event = {"timestamp": time.time(), "name": row["name"],
                         "path": row["path"], "branch": row["branch"],
                         "HEAD": (row["identity"][2] if row["class"] == wt_legacy.LEGACY else row["identity"]["head"]), "class": row["class"],
                         "bytes": current["tracked_bytes"] + current["ignored_bytes"],
                         "backup": row.get("backup", "")}
                # A write/fsync failure propagates: removal must never look successful.
                journal.write(json.dumps(event, ensure_ascii=True) + "\n")
                journal.flush()
                os.fsync(journal.fileno())
                row["result"] = "removed"
        git(cfg.repo, "worktree", "prune")
        return report


def run(cfg: SideConfig, args) -> int:
    try:
        if getattr(args, "apply", False):
            report = apply(cfg, name=args.name,
                           include_unmerged=getattr(args, "include_unmerged", False),
                           prune_branches=getattr(args, "prune_branches", False), fetch=args.fetch)
        else:
            if args.fetch:
                git(cfg.repo, "fetch", "origin")
            report = inspect(cfg, name=args.name)
            eligible_totals(report, getattr(args, "include_unmerged", False))
    except (OSError, ValueError, subprocess.TimeoutExpired):
        print("side-session gc: GC failed (metadata, git or journal); inspect worktrees/journal before retry")
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=True))
    else:
        print("class\tname\tpath\tbranch\tahead\ttracked_bytes\tignored_bytes\treason")
        for row in report["worktrees"]:
            print("\t".join(json.dumps(row[key], ensure_ascii=True) for key in
                            ("class", "name", "path", "branch", "ahead", "tracked_bytes", "ignored_bytes", "reason")))
            if "result" in row:
                print(row["result"])
        print(f"eligible: {report['totals']['eligible']}; bytes: {report['totals']['eligible_bytes']}")
    return 1 if report.get("errors") else 0
