---
name: plan-status
description: Generate a short, visual project status page from the repo's Markdown plans - overall % done, open/done plans, a 4-column table with ▓░ progress bars, a Mermaid pie of done/open/skipped tasks, a milestone flowchart or gantt when order/dates exist, top open tasks and recent git activity - as docs/status/plan-status.md that GitHub renders on a phone, plus an optional self-contained HTML page. Keeps a hand-written notes block between re-runs. Use when the user asks how the project is going, wants a dashboard or to read status on their phone, or after ticking plans. Vietnamese triggers - "tình hình dự án", "tiến độ", "cập nhật plan", "dashboard", "xem trên điện thoại", "status".
---

# plan-status

## Summary

- **Purpose:** turn the repo's plan checkboxes into one phone-readable page, `docs/status/plan-status.md`
  (GitHub app/web renders tables and Mermaid); `--html` also writes a self-contained `plan-status.html`
  (inline CSS/SVG, no JS, no external URL) for offline viewing.
- **What you do:** run the script, read the output, rewrite the manual notes block (3-5 lines), report.
- **Never** commit or push the page unless the user asked.

## 1. Run

```bash
PY=$("${CLAUDE_PLUGIN_ROOT}/scripts/dw" python)
$PY "${CLAUDE_PLUGIN_ROOT}/scripts/plan_status.py" --repo "<repo root>" [--out <dir>] [--html] [--days 14]
```

- Output dir: `--out`, else `out_dir` in section `[plan_status]` of `.claude/dev-workflow.toml`
  (`dw config` warns that this section is unknown; harmless), else `docs/status`.
- Plans scanned: `paths.plans/**/*.md` from the config plus `docs/plans/**`, `docs/**/*plan*.md`,
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

1. Read `plan-status.md`; check the summary against what you know (stale plan, wrong status).
2. Replace the text between `<!-- plan-status:manual:start -->` and `<!-- plan-status:manual:end -->`
   with 3-5 Vietnamese lines: main risks, decisions that need a person, blocked plans. Re-runs keep it.
3. Report the overall %, the running plan and the output path(s) to the user.
