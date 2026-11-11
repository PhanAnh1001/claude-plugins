"""Git helpers for plan_status.py: run git, read plans from an unmerged ref, build web links."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

GIT_TIMEOUT_SECONDS = 20
DEFAULT_REMOTE = "origin"
MAIN_BRANCHES = frozenset({"main", "master"})
GITHUB_URL_RES = (re.compile(r"^https://github\.com/([^/]+)/(.+?)(?:\.git)?/?$"),
                  re.compile(r"^git@github\.com:([^/]+)/(.+?)(?:\.git)?$"))
WEB_BASE = "https://github.com/{owner}/{repo}/blob/{branch}"


def git_lines(repo: Path, *args: str) -> list[str]:
    """stdout lines of a git command; [] when git fails or is missing."""
    try:
        result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                                timeout=GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return []
    return result.stdout.splitlines() if result.returncode == 0 else []


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Whole-path glob: `**/` any dirs, `**` anything, `*` and `?` stay inside one segment."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        else:
            ch = pattern[i]
            out.append("[^/]*" if ch == "*" else "[^/]" if ch == "?" else re.escape(ch))
            i += 1
    return re.compile("".join(out) + r"\Z")


def remotes(repo: Path) -> set[str]:
    return set(git_lines(repo, "remote"))


def split_ref(repo: Path, ref: str) -> tuple[str, str]:
    """(remote, branch) for a ref; a local branch uses the default remote."""
    head, sep, rest = ref.partition("/")
    if sep and head in remotes(repo):
        return head, rest
    return DEFAULT_REMOTE, ref


def web_base(repo: Path, ref: str) -> str:
    """https://github.com/o/r/blob/<branch>, or '' when the remote URL is not a GitHub URL."""
    remote, branch = split_ref(repo, ref)
    url = next(iter(git_lines(repo, "remote", "get-url", remote)), "")
    for pattern in GITHUB_URL_RES:
        match = pattern.match(url)
        if match:
            return WEB_BASE.format(owner=match.group(1), repo=match.group(2), branch=branch)
    return ""


class RefSource:
    """Plans read from `git show <ref>:<path>` instead of the working tree."""

    def __init__(self, repo: Path, ref: str, link_base: str = "") -> None:
        sha = next(iter(git_lines(repo, "rev-parse", "--verify", "--quiet", "--short", f"{ref}^{{commit}}")), "")
        if not sha:
            raise ValueError(f"git ref '{ref}' not found in {repo} (run 'git fetch' for a remote ref)")
        self.repo, self.ref, self.sha = repo, ref, sha
        self.branch = split_ref(repo, ref)[1]
        self.base = (link_base or web_base(repo, ref)).rstrip("/")

    def files(self, include: list[str], exclude_files: list[str], skip_dir) -> list[str]:
        """Repo-relative paths at the ref matching include, minus excludes; skip_dir(name) drops dirs."""
        inc = [glob_to_regex(g) for g in include]
        exc = [glob_to_regex(g) for g in exclude_files]
        keep = []
        for path in git_lines(self.repo, "ls-tree", "-r", "--name-only", self.ref):
            if not any(r.match(path) for r in inc) or any(r.match(path) for r in exc):
                continue
            if not any(skip_dir(d) for d in path.split("/")[:-1]):
                keep.append(path)
        return sorted(keep)

    def plans(self, page, parse, out_rel: Path | None) -> list:
        """Parsed plans (with web url) for a plan_status Page; skips files under the output dir."""
        prefix = f"{out_rel.as_posix()}/" if out_rel and out_rel.parts else None
        found = []
        skip = lambda d: d in page.exclude_dirs or d.startswith(".")  # noqa: E731
        for rel in self.files(page.include, page.exclude_files, skip):
            plan = None if prefix and rel.startswith(prefix) else parse(self.read(rel), rel)
            if plan:
                plan.url = self.url(rel)
                found.append(plan)
        return found

    def read(self, path: str) -> str:
        result = subprocess.run(["git", "-C", str(self.repo), "show", f"{self.ref}:{path}"],
                                capture_output=True, timeout=GIT_TIMEOUT_SECONDS, check=False)
        if result.returncode != 0:
            raise ValueError(f"cannot read {path} at {self.ref}")
        return result.stdout.decode("utf-8", errors="replace")

    def url(self, path: str) -> str:
        return f"{self.base}/{path}" if self.base else ""

    def source_line(self, repo: Path) -> str:
        """Summary line naming the branch, unless it is the current branch or main."""
        current = next(iter(git_lines(repo, "rev-parse", "--abbrev-ref", "HEAD")), "")
        if self.branch in MAIN_BRANCHES or self.branch == current:
            return ""
        return f"- **Nguồn:** nhánh `{self.branch}` @ `{self.sha}` (chưa merge vào main)."
