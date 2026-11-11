---
name: plan-status
description: Generate a short, visual project status page from the repo's Markdown plans - overall % done, open/done plans, a 4-column table with ▓░ progress bars, a Mermaid pie of done/open/skipped tasks, a milestone flowchart or gantt when order/dates exist, top open tasks and recent git activity - as docs/status/plan-status.md that GitHub renders on a phone, plus an optional self-contained HTML page. Keeps a hand-written notes block between re-runs. Use when the user asks how the project is going, wants a dashboard or to read status on their phone, or after ticking plans. Vietnamese triggers - "tình hình dự án", "tiến độ", "cập nhật plan", "dashboard", "xem trên điện thoại", "status".
---

# plan-status

## Summary

- **Purpose:** turn the repo's plan checkboxes into one phone-readable page, `docs/status/plan-status.md`
  (GitHub app/web renders tables and Mermaid); `--html` also writes a self-contained `plan-status.html`
  (inline CSS/SVG, no JS, no external URL) for offline viewing.
- **Many pages:** `.claude/plan-status.toml` can define one page per sub-project; with >= 2 pages an
  index `docs/status/README.md` (page | ▓░ % | open) links them all.
- **What you do:** run one command, read the output, rewrite the manual notes block (3-5 lines), report.
- **Never** commit or push the page unless the user asked.

## 1. Run

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/dw" plan-status --repo "<repo root>" [--page <name>] [--out <dir>] [--html] [--days 14]
```

- Config: `.claude/plan-status.toml` when present (no need for `.claude/dev-workflow.toml`), else
  section `[plan_status]` (`out_dir`, `exclude`, `days`, `html`) of `.claude/dev-workflow.toml`:

  ```toml
  [defaults]
  days = 14
  html = true
  exclude = ["handoffs"]                              # extra directory names to skip
  out_dir = "docs/status"                             # where README.md index goes
  [[page]]
  name = "game"                                       # for --page
  title = "Game LIVE TikTok"
  include = ["docs/work-in-progress/*.md"]            # globs relative to the repo
  exclude_files = ["docs/work-in-progress/*social*"]  # file globs to skip
  out = "docs/status/game.md"                         # .html with the same name
  git_paths = ["src", "docs/work-in-progress"]        # optional git log filter
  [[page]]
  name = "trend"
  include = ["docs/**/*trend*.md"]                    # whole-path globs, ** = any dirs
  out = "docs/status/trend.md"
  ref = "origin/feat/trend-listening"                 # read plans from this unmerged branch
  # link_base = "https://github.com/o/r/blob/feat/trend-listening"  # optional link override
  ```

- `ref` (optional): the page reads its plan files from that git ref (`git ls-tree` + `git show`), not
  the working tree, so the command still runs from the main checkout. Head commit and git log come from
  the ref; links go to `https://github.com/<o>/<r>/blob/<branch>/<path>` derived from the remote URL
  (`link_base` overrides; no GitHub remote -> plain path text); the summary adds a "Nguồn: nhánh ..."
  line unless the ref is main or the current branch. Run `git fetch` first for a remote ref. An
  unknown ref exits 2 and stops every page.

- No `[[page]]`: one page `<out_dir>/plan-status.md`. With pages: every page runs, `--page` runs one
  (the index is only rewritten when all pages run), `--out <dir>` is only valid for a single page.
  Each page keeps its own manual block.
- Plans scanned (no page `include`): `paths.plans/**/*.md` from the config plus `docs/plans/**`, `docs/**/*plan*.md`,
  `docs/**/*roadmap*.md`, `docs/**/*milestone*.md`, `docs/work-in-progress/**`; only files with at
  least one task checkbox count. Exit 2 when none is found. Paths with a `handoffs`, `node_modules` or
  hidden (`.x`) directory are skipped; add more directory names with `exclude = ["drafts"]` in `[plan_status]`.
- Links: relative to the output dir when it is inside the repo, else the repo-relative plan path.
  Plan titles are cut to 40 chars in the table, 30 next to open tasks.
- Open tasks and "Việc kế tiếp" list real plans first (file name contains `plan` or frontmatter
  `type: plan`), then design/spec files, each group by path.
- Task syntax (spec-plan standard): `- [x]` done, `- [ ]` open, `- [-]`/`- [~]` or a `~~struck~~` body
  skipped. Frontmatter `status: completed|done` marks a plan done. A milestone `M<n>` in the title or
  file name orders the flowchart; frontmatter `start:` + `due:`/`end:` (YYYY-MM-DD) give a gantt instead.
  No dates are invented: missing data drops the chart.

## 2. Read and annotate

1. Read each written page; check the summary against what you know (stale plan, wrong status).
2. Replace the text between `<!-- plan-status:manual:start -->` and `<!-- plan-status:manual:end -->`
   with 3-5 Vietnamese lines: main risks, decisions that need a person, blocked plans. Re-runs keep it.
3. Report the overall %, the running plan and the output path(s) to the user.

## 3. Deploy to a new repo

1. `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" plan-status init --repo "<repo root>"` (dry-run): finds `.md` files with
   checkboxes and prints the files it would create - `.claude/plan-status.toml` (page "main"),
   `.github/workflows/plan-status.yml` (calls the shared Action
   `PhanAnh1001/claude-plugins/dev-workflow/actions/plan-status@plan-status-v1`) and a marked rule block
   appended to `AGENTS.md`. Exit 2 = no plan found. Existing config/workflow are kept unless `--force`.
2. Review the proposal with the user, then rerun with `--write`; re-runs never duplicate the AGENTS.md block.
3. Commit and push; pushing a workflow file needs a token with the `workflow` scope.
