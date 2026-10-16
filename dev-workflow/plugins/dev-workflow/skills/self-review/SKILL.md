---
name: self-review
description: Checklist review of the current diff before reporting work as done — scope, repo rules (AGENTS.md, CLAUDE.md, .claude/rules), file-length ceiling, docs required by docs_map, tests for new behaviour and red-then-green tests for bugs, no secrets or machine absolute paths, traceability, and producer/consumer contracts in sync. Each item ends CONFIRMED, needs-fix or n/a with evidence. Run by the agent working alone or by the brain (never by a hand) after the gate and before session-closeout on L1/L2 work. Triggers on "review", "tự review", "kiểm tra lại diff", "xem lại thay đổi", "check lại code", "đã đúng chưa", "review trước khi xong".
---

# self-review

## Summary

- **Purpose:** catch the mistakes that recur when an agent reports "done": out-of-scope edits, rule
  violations, missing docs/tests, broken contracts. It complements, not replaces, a bug hunt with
  `/code-review`.
- **Who runs it:** the agent working alone, or the **brain** under the brain/hand policy. A hand never
  issues a verdict; when asked, a hand only runs commands and returns raw evidence.
- **Input:** the diff (`git diff`, plus untracked files), the task/brief, the Triage block, the plan.
- **Output:** a review table in chat (no file unless the repo asks for one), overall verdict
  **CONFIRMED** or **needs-fix**.
- **Config keys:** `project.max_file_lines`, `docs_map`, `gate.commands`, `gate.lint`, `paths.srs`;
  read with `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --json` (see `${CLAUDE_PLUGIN_ROOT}/skills/dev-triage/references/config-defaults.md`).

## 1. Collect the diff

```bash
git status --short
git diff --stat
git diff
git diff --name-only --diff-filter=d
git ls-files --others --exclude-standard
```

Read every changed file region, not only the stat. Config per
`${CLAUDE_PLUGIN_ROOT}/skills/dev-triage/references/config-defaults.md`.

## 2. Checklist

### 2.1 Scope and rules

- **R1 Scope:** every changed file belongs to the task/brief; no drive-by refactors, formatting churn or
  unrelated files. Anything extra is needs-fix (revert) or is reported as a separate finding.
- **R2 Repo rules:** read root `AGENTS.md`/`CLAUDE.md`, nested ones in changed directories, and
  `.claude/rules/*.md` whose `globs` match changed paths. Check the diff against each rule that applies.
- **R3 File length:** `wc -l` on each changed file ≤ `project.max_file_lines`. A file that crossed the
  ceiling in this diff is needs-fix (split by responsibility), not a note.

### 2.2 Tests

- **T1 New behaviour has a test** that would fail without the change. Name the test.
- **T2 Bug fix has a red-then-green test:** evidence that it failed for the right reason (assertion on the
  wrong behaviour, not an import error) before the fix and passes after.
- **T3 Requirement IDs:** tests for an FR/E carry the ID in the name or marker when the repo uses that
  convention (`test_FR_<feature>_001_…`).
- **T4 Test quality:** expected values are literals or independent anchors, not taken from the code
  under test; no skipped or deleted tests to make the gate green.

### 2.3 Docs

- **D1 docs_map:** for each changed code file matching a `docs_map` glob, the mapped docs are either in the
  diff or still accurate — open them and say which. Missing update is needs-fix.
- **D2 Plan/spec:** ticked boxes match what the diff actually does; no superseded design left in the
  spec.
- **D3 Doc rules:** new/changed docs open with a summary, use relative links, respect the repo's
  frontmatter rules.

### 2.4 Hygiene

- **H1 No secrets:** grep added lines for tokens, passwords, PATs, private keys, connection strings with
  credentials.
- **H2 No machine paths:** added lines contain no developer-machine absolute paths (home directories,
  temp directories, the tilde home shorthand). Server or container paths documented as such are fine.
- **H3 Command examples:** no `cd <dir> && …` compound commands in docs or scripts meant for agents.
- **H4 Leftovers:** no debug prints, commented-out code, TODOs without an owner, stray files.

```bash
git diff -U0 | grep -nE '^\+.*(password|passwd|secret|token|api[_-]?key|BEGIN [A-Z ]*PRIVATE KEY)'
git diff -U0 | grep -nE '^\+.*(/Use[r]s/|/home/[a-z]|/priva[t]e/tmp/|[~]/)'
```

A hit is not automatically a finding (a variable named `token` is fine) — open it and decide.

### 2.5 Traceability and contracts

- **X1 trace check:** required on L2 and whenever requirement IDs are involved:
  `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" trace`. Exit 1 is needs-fix
  (see `dev-workflow:trace-check`).
- **X2 Contracts in sync:** for every changed producer, find its consumers and check they changed too:
  API response/request ↔ frontend types and clients; DB schema ↔ migration ↔ models/queries; config
  keys ↔ loader ↔ example config ↔ docs; CLI flags ↔ help/docs; event/message payloads ↔ handlers.
  Grep the field or route name across the repo.

### 2.6 Gate

- **G1 Gate ran after the last change:** the commands from `gate.commands` and `gate.lint` were run on the
  final diff and passed; quote the real summary line. A gate run before a later edit does not count.

## 3. Deeper review

The checklist is not a bug hunt. For L2 work, changes to shared state, concurrency, security-sensitive
code, or when the checklist found more than one needs-fix, also run `/code-review` on the diff (and
`/security-review` for auth, input handling or secrets). Treat their findings like checklist items.

## 4. Report

Write in `project.doc_language`. Summary line first, then the table.

```markdown
### Self-review — needs-fix (2 items)
| Item | Result | Evidence |
|---|---|---|
| R1 Scope | CONFIRMED | 4 files, all in `<module>` |
| R3 File length | needs-fix | `<path>`: 431 lines > 400 |
| D1 docs_map | needs-fix | `<code glob>` changed, `<doc>` not updated |
| X2 Contracts | n/a | no API/schema change |
```

- **CONFIRMED** only when no item is needs-fix. Every result cites evidence (command output, path:line).
- needs-fix: fix it (brain/hand: one hand per finding, with the finding as the brief), then re-run only
  the affected items and the gate. Do not report the work as done while any item is needs-fix.
- Then continue with `dev-workflow:session-closeout`.
