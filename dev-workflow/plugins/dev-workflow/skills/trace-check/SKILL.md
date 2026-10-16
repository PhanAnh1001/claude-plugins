---
name: trace-check
description: Run and act on the dev-workflow traceability check (scripts/trace_check.py), which scans requirement IDs (FR/NFR/BR/E/SC) in the SRS, task IDs with `covers:` in plans, and IDs in test names, then reports requirements without a task or test and orphan IDs, optionally regenerating the traceability matrix. Use after editing an SRS, plan or tests, during session-closeout, before an L2 review, and whenever the check exits 1. Triggers on "trace check", "truy vết", "kiểm truy vết", "ma trận truy vết", "traceability", "FR nào chưa có test", "thiếu test cho FR", "orphan ID", "cập nhật traceability".
---

# trace-check

## Summary

- **Purpose:** prove every requirement has a task and, where required, a test — automatically, instead of
  a hand-kept matrix.
- **Command:** `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" trace [--write] [--format md|json] [--config PATH]`, run from the repo root.
  The wrapper picks a Python ≥ 3.11; do not run `trace_check.py` with the system interpreter.
- **Exit codes:** `0` all required links present · `1` a required task/test link is missing or an ID is
  defined twice · `2` config missing/invalid, usage error or no Python ≥ 3.11. Orphan and malformed IDs
  are warnings; they do not change the exit code, but still need fixing.
- **Output file:** with `--write`, the matrix at `paths.traceability` (generated — never hand-edit it;
  its layout comes from `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" template traceability`).
- **Config keys:** `paths.srs`, `paths.plans`, `paths.traceability`, `trace.id_types`,
  `trace.test_globs`, `trace.require_test_types`, `trace.require_task_types`, `trace.waivers`.
- **No config:** the script exits 2; report "traceability not configured" and offer to create the config
  from the example. No SRS files matched by `paths.srs`: nothing to check; say so.

## 1. When to run

| Moment | Mode | Why |
|---|---|---|
| After editing an SRS, plan or tests | report only | Catch broken links while the edit is fresh |
| Before presenting an L2 design/plan for approval | report only | Every `implements` ID must have a task |
| Before an L2 review / in `self-review` (X1) | report only | Every required ID must have a test |
| In `session-closeout` | `--write` | Regenerate the committed matrix |

Report mode (no `--write`) changes no file; use it freely. `--format json` is for scripting; read `md`.

## 2. Read the report

### 2.1 Sections to expect

- **Coverage summary:** counts per ID type, how many have tasks and tests.
- **Missing task:** an ID of a type in `trace.require_task_types` that no plan task `covers`.
- **Missing test:** an ID of a type in `trace.require_test_types` that no test (matched by
  `trace.test_globs`) names.
- **Orphans:** IDs referenced in plans or tests that no SRS defines (warning).
- **Duplicates:** the same ID defined in more than one place (exit 1).
- **Malformed IDs:** strings that look like an ID but do not match `<TYPE>-<feature>-NNN` (warning).
- **Waived:** IDs listed in `trace.waivers`, shown with their reason.

The exact headings come from the script; trust its output over this list.

### 2.2 Verify before acting

A "missing" link can be a spelling difference (`FR-auth-01` vs `FR-auth-001`) or a test outside
`trace.test_globs`. Grep for the ID across the repo before adding anything.

## 3. Fix the gaps (exit 1, and orphan warnings)

### 3.1 Missing task

- The requirement is in scope: add a task `T-<feature>-NN` with `covers: <ID>` to the plan (new number,
  never renumber), via `dev-workflow:spec-plan` rules.
- Out of scope for this plan: it belongs in another plan or the backlog — link it there.

### 3.2 Missing test

- Write the test the SRS `Verify by` column asks for, named with the ID per the repo convention
  (`test_FR_<feature>_001_…`), or add the ID to an existing test that truly verifies it.
- Verification genuinely is not an automated test (manual check, UAT, hardware, external review): propose
  a waiver (§ 3.4). Never add a fake test to make the check pass.

### 3.3 Orphan IDs

- Typo: fix the reference.
- Requirement was removed or renamed in the SRS: update or remove the reference in plan/tests.
- Requirement genuinely missing from the SRS: do not add it yourself to an approved SRS — raise a CR
  (`paths.crs`, template from `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" template cr`) and tell the user.

### 3.4 Waivers

- **When:** only when the link cannot exist for a stated reason — verification is manual/UAT, the ID is
  deferred to a later release by decision, or it is covered outside this repo. "No time to write the
  test" is not a reason.
- **How:** one entry per ID in `.claude/dev-workflow.toml`:

  ```toml
  [trace.waivers]
  "FR-<feature>-007" = "Kiểm tra thủ công trong UAT; xem <relative doc path>"
  ```

  The reason is mandatory, in `project.doc_language`, and points at where the verification lives.
- **Who approves:** the user (or the reviewer they name). Propose the entry and stop; add it only after
  approval, since the config is a committed file. List every waiver in the report.
- **Remove** the waiver as soon as a task/test appears, so the matrix shows the real link.

### 3.5 Duplicate IDs (exit 1)

One ID, one definition. Keep the definition in the canonical SRS file and turn the others into
references, or give the second requirement a new number if it is a different requirement. In an
approved SRS this is a CR, not a silent edit.

### 3.6 Malformed IDs (warning)

Fix the spelling to `<TYPE>-<feature>-NNN` (type from `trace.id_types`, three-digit number), or reword the
text if it is not meant to be an ID.

## 4. Exit 2

Config missing or invalid, usage error, or no Python ≥ 3.11 found. Show the message, check
`"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --json`, and fix the config only with the user's
agreement (it is a committed file).

## 5. Report

One line per run in `project.doc_language`: exit code, coverage counts, and each remaining gap with the
action taken (task added, test added, waiver proposed/approved, CR raised). Re-run after fixes; a gap is closed only when
the script agrees.
