---
name: session-closeout
description: Close a work session in a fixed order — run the configured gate commands and lint and report their real results, tick the plan, regenerate traceability with trace_check --write, check docs_map coverage, sync Jira through jira-workflow, then write an end-of-session report that opens with a summary (what was done, gate results, what is still open). Never commits or pushes unless the user asked. Use whenever work is about to be reported as finished, at the end of a session, or when the user asks whether it is done. Triggers on "xong chưa", "xong rồi", "chốt phiên", "kết thúc phiên", "báo cáo cuối", "tổng kết", "wrap up", "done?".
---

# session-closeout

## Summary

- **Purpose:** make "done" mean the same thing every time, so the user no longer has to remind the agent
  to run tests, tick the plan, update docs or sync Jira.
- **Order (do not reorder):** 1 gate → 2 plan → 3 traceability → 4 docs_map → 5 Jira → 6 report.
  Each step reports what it really did; a skipped step says why.
- **Inputs:** the diff, the Triage block, the plan, `.claude/dev-workflow.toml`.
- **Outputs:** updated plan (ticks/status), `paths.traceability` (when configured), Jira changes (after
  confirmation), the final report in chat.
- **Never:** commit, push, or close Jira issues on a failing gate unless the user explicitly asked.
- **Brain/hand:** the brain runs closeout. A hand finishing a brief only runs the gate it was given and
  reports results in its own report format.

## 1. Verify

### 1.1 Gate (step 1)

- Read `gate.commands` and `gate.lint` with `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --json` (defaults:
  `${CLAUDE_PLUGIN_ROOT}/skills/dev-triage/references/config-defaults.md`). No config: use the repo's
  own test/lint entry points and say they were inferred.
- Run each command once, after the last code change, in the foreground with a timeout. Use absolute
  paths or tool flags (`make -C <dir>`, `npm --prefix <dir>`), never `cd <dir> && …`.
- Report per command: exit code and the real summary line (passed/failed/skipped counts). Name every
  failing test. A failure that also fails on the untouched base is "pre-existing" only if you ran the base
  to prove it.
- For docs/config-only changes with no runtime effect, a syntax/parse/link check of the changed files
  replaces the test suite; say so.
- Gate red: fix and re-run if it is in scope; otherwise stop here, skip step 5's Done transitions, and
  report the failure.

### 1.2 Self-review

L1/L2 work should already have a CONFIRMED `dev-workflow:self-review`. If it has not run since the last
change, run it now (brain or solo agent only).

## 2. Update the records

### 2.1 Plan (step 2)

Tick every task finished and verified in this session; delete skipped tasks or mark them `- [-] ~~…~~`;
set `status: in-progress` or `completed` per the rules in `dev-workflow:spec-plan` (completed only when
no `[ ]` box is left, including Verification). L0 work and work without a plan: skip and say "no plan".

### 2.2 Traceability (step 3)

When `paths.srs` is configured:

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/dw" trace --write
```

The matrix layout comes from `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" template traceability`; never hand-edit
the generated file. Exit 0: report the coverage line. Exit 1: follow `dev-workflow:trace-check` (add the task/test or record
a waiver), then re-run. Exit 2: config problem — report it, do not hand-edit the traceability file.

### 2.3 docs_map (step 4)

For each changed code file matching a `docs_map` glob, confirm the mapped docs are updated or still
accurate (open them). Update missing docs now. When a plan reached `completed`, make sure its changed
behaviour is reflected in the living docs, not only in the plan.

## 3. Jira (step 5)

Skip when `jira.project` is not configured or the user said not to touch Jira. Otherwise load
`dev-workflow:jira-workflow` and:

- find the issue(s) matching this work (search before create);
- create missing ones, update description/estimate, comment the result;
- on a green gate with finished scope: log the real time with
  `jira-cli worklog <KEY> --time <real> --remaining 0m`, then transition to Done (details and the
  fallback for a CLI without `worklog` are in `dev-workflow:jira-workflow` § 4.2);
- show the planned Jira actions (dry-run) and get the user's confirmation before writing, unless the user
  already asked for exactly these updates in this session.

## 4. Report (step 6)

Write in `project.doc_language`. Summary first, then details in the same order.

```markdown
## Báo cáo cuối phiên            <!-- heading in project.doc_language -->
### Tóm tắt
- Đã làm: <one or two lines, lane, IDs>
- Gate: <command> → <pass/fail + counts>; lint → <result>
- Còn mở: <failing items, open questions, approvals waiting, follow-ups>
### Chi tiết
- Thay đổi: <path — one-line purpose> …
- Plan: <ticked n/m, status>
- Truy vết: <trace_check result or "không cấu hình">
- Tài liệu: <docs updated per docs_map>
- Jira: <issue keys and actions, or "bỏ qua: lý do">
- Bước tiếp theo: <what the user must do: approve, review, commit>
```

- Report honestly: failing or skipped checks are listed in the summary, not buried.
- Mention that nothing was committed or pushed, unless the user asked for it and it was done.
- Stop any background task you started before ending the session.
