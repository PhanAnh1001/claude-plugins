"""`dw plan-status init`: scaffold plan-status for a new repository.

Finds Markdown files with task checkboxes, then proposes (dry-run) or writes (--write):
  .claude/plan-status.toml         one page "main" whose include globs are the plan folders
  .github/workflows/plan-status.yml  thin workflow calling the shared composite Action
  AGENTS.md                        appends a short rule block (only if the file exists and lacks the marker)
Existing config/workflow files are kept unless --force.
Exit code: 0 ok, 2 when no plan file is found or on usage errors.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

EXIT_OK, EXIT_NO_PLANS = 0, 2
CONFIG_PATH = Path(".claude") / "plan-status.toml"
WORKFLOW_PATH = Path(".github") / "workflows" / "plan-status.yml"
AGENTS_PATH = Path("AGENTS.md")
OUT_DIR = "docs/status"
OUT_FILE = f"{OUT_DIR}/plan-status.md"
ACTION_REF = "PhanAnh1001/claude-plugins/dev-workflow/actions/plan-status@plan-status-v1"
SCHEDULE_CRON = "17 */6 * * *"
SIBLING_COLLAPSE_MIN = 2  # >= this many plan dirs under one parent -> "<parent>/*/*.md" (covers future plans)
RULE_MARKER = "<!-- plan-status-rule -->"
SKIP_DIRS = frozenset({".git", "node_modules", "handoffs", "output", "skills", "templates", "references"})
CHECKBOX_RE = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s", re.MULTILINE)

RULE_TEXT = f"""
{RULE_MARKER}
## Trang tình hình plan

- Số liệu trong `{OUT_DIR}/` do GitHub Action plan-status tự cập nhật; không sửa tay phần số liệu.
- Sau khi tick plan hoặc xong việc lớn: `git pull`, có thể chạy `/dev-workflow:plan-status`, viết lại khối
  ghi chú tay (rủi ro, quyết định chờ người dùng, ≤5 dòng) rồi commit `{OUT_DIR}/`.
- Cấu hình ở `.claude/plan-status.toml`; dự án con thêm một `[[page]]`.
"""


def find_plan_dirs(repo: Path) -> list[str]:
    """Relative POSIX dirs that hold at least one .md file with a task checkbox."""
    found: set[str] = set()
    for root, dirs, files in os.walk(repo):
        rel_root = Path(root).relative_to(repo)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")
                         and (rel_root / d).as_posix() != OUT_DIR)
        for name in files:
            if name.endswith(".md") and has_checkbox(Path(root) / name):
                found.add(rel_root.as_posix())
    return sorted(found)


def has_checkbox(path: Path) -> bool:
    try:
        return bool(CHECKBOX_RE.search(path.read_text(encoding="utf-8", errors="replace")))
    except OSError:
        return False


def glob_for(rel_dir: str) -> str:
    return "*.md" if rel_dir == "." else f"{rel_dir}/*.md"


def plan_globs(plan_dirs: list[str]) -> list[str]:
    """One glob per plan dir; sibling dirs sharing a parent collapse into `<parent>/*/*.md`."""
    by_parent: dict[str, list[str]] = {}
    for d in plan_dirs:
        if d != ".":
            by_parent.setdefault(Path(d).parent.as_posix(), []).append(d)
    globs: list[str] = []
    for d in plan_dirs:
        parent = Path(d).parent.as_posix()
        if d != "." and len(by_parent[parent]) >= SIBLING_COLLAPSE_MIN:
            g = "*/*.md" if parent == "." else f"{parent}/*/*.md"
        else:
            g = glob_for(d)
        if g not in globs:
            globs.append(g)
    return globs


def render_config(repo_name: str, plan_dirs: list[str]) -> str:
    include = ", ".join(f'"{g}"' for g in plan_globs(plan_dirs))
    return (f'[defaults]\ndays = 14\nhtml = true\nout_dir = "{OUT_DIR}"\n\n'
            f'[[page]]\nname = "main"\ntitle = "{repo_name}"\ninclude = [{include}]\n'
            f'out = "{OUT_FILE}"\n')


def render_workflow(plan_dirs: list[str]) -> str:
    paths = plan_globs(plan_dirs) + [CONFIG_PATH.as_posix(), WORKFLOW_PATH.as_posix()]
    path_lines = "".join(f'      - "{p}"\n' for p in paths)
    return ("name: plan-status\n\non:\n  push:\n    branches: [main]\n    paths:\n" + path_lines
            + f"  schedule:\n    - cron: '{SCHEDULE_CRON}'\n  workflow_dispatch:\n\n"
            "permissions:\n  contents: write\n\n"
            "concurrency:\n  group: plan-status\n  cancel-in-progress: false\n\n"
            "jobs:\n  plan-status:\n    runs-on: ubuntu-latest\n    steps:\n"
            f"      - uses: {ACTION_REF}\n")


def plan_changes(repo: Path, plan_dirs: list[str], force: bool) -> list[tuple[Path, str, str]]:
    """(path, action, new full content) for every file to create/update."""
    changes = []
    for rel, content in ((CONFIG_PATH, render_config(repo.name, plan_dirs)),
                         (WORKFLOW_PATH, render_workflow(plan_dirs))):
        target = repo / rel
        if not target.exists():
            changes.append((target, "tạo", content))
        elif force:
            changes.append((target, "ghi đè", content))
    agents = repo / AGENTS_PATH
    if agents.is_file():
        text = agents.read_text(encoding="utf-8")
        if RULE_MARKER not in text:
            changes.append((agents, "thêm mục", text.rstrip("\n") + "\n" + RULE_TEXT))
    return changes


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="dw plan-status init", description=__doc__.splitlines()[0])
    parser.add_argument("--repo", required=True, help="repository root")
    parser.add_argument("--write", action="store_true", help="write files (default: dry-run)")
    parser.add_argument("--force", action="store_true", help="overwrite existing config/workflow")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).resolve()
    plan_dirs = find_plan_dirs(repo)
    if not plan_dirs:
        print("plan-status init: không thấy file .md nào có checkbox '- [ ]'/'- [x]'; "
              "tạo plan (vd docs/plans/<tên>.md) rồi chạy lại.", file=sys.stderr)
        return EXIT_NO_PLANS
    changes = plan_changes(repo, plan_dirs, args.force)
    mode = "ghi" if args.write else "dry-run (thêm --write để ghi)"
    print(f"plan-status init [{mode}] — thư mục plan: {', '.join(plan_dirs)}")
    if not changes:
        print("Không có gì cần đổi (dùng --force để ghi đè config/workflow).")
    for target, action, content in changes:
        print(f"- {action}: {target.relative_to(repo).as_posix()}")
        if target.name == CONFIG_PATH.name:
            print(content)
        if args.write:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
