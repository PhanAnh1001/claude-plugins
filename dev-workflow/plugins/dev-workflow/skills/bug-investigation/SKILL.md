---
name: bug-investigation
description: Investigate and repair a defect the disciplined way - reproduce it, write the smallest test that fails for the real reason (an assertion, not an ImportError), search git log/blame/bisect for the commit that introduced it, state the root cause, write a bug report from the bug.md template, then STOP for approval before fixing; after approval fix, run the gate, update living docs and self-review. Use this whenever the user reports something broken or behaving unexpectedly, even if they only ask "why", and also when they ask for a fix directly. Vietnamese triggers - "lỗi", "bug", "sao lại", "không chạy", "bị sai", "điều tra", "tại sao", "hỏng", "sửa lỗi".
---

# Bug Investigation and Repair

## Summary

- **Purpose:** turn a reported defect into evidence (a red test + root cause + git history) before any
  production code changes, so the fix is targeted and does not reintroduce an old bug.
- **Two phases, one gate:**
  1. **Investigate** (no production code touched): reproduce → red test → git history → root cause →
     bug report.
  2. **Approval gate:** stop and report; wait for the user to choose the repair scope.
  3. **Repair:** fix → test green + gate → living docs → self-review → final report.
- **Skip the gate only when** the user explicitly said "fix it now" (`sửa luôn`), or the task was
  triaged as lane L0 and the defect is obvious (typo, wrong constant, ≤ 2 files, no behaviour/API change).
  Say in the report that the gate was skipped and why.
- **Output:** `<[paths].bugs>/<YYYY-MM-DD>-<slug>.md` (from the template printed by
  `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" template bug`),
  a test that went red then green, and a report.
- **Config keys used:** `[paths].bugs`, `[paths].templates`, `[paths].template_aliases`, `[gate].commands`, `[gate].lint`,
  `[docs_map]`, `[project].doc_language`, `[project].max_file_lines`.

## Inputs and setup

- The symptom as reported (message, screenshot, log, issue key). Quote it verbatim in the report.
- Read config once: `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --json`. Exit code 2 with a "not found" message means the
  repo has no `.claude/dev-workflow.toml`; then use defaults (`docs/bugs/`, the repo's documented test
  command from `AGENTS.md`/`CLAUDE.md`) and mention the missing config in the report.
- If the repo's own `AGENTS.md` has a stricter bug workflow, follow the stricter one; this skill is the floor.
- If the lane is unclear (single module vs. many modules vs. non-deterministic), run
  `dev-workflow:dev-triage` first. Non-deterministic or performance symptoms belong to lane L3: combine
  this skill with `dev-workflow:measurement-evidence`.

## Phase 1 - Investigate (no production code changes)

### 1.1 Reproduce

- Reproduce with the smallest input and the exact command. Record: command, input, observed output,
  expected output, environment (branch, commit `git rev-parse --short HEAD`, relevant versions).
- If it does not reproduce, say so and list what differs between the reporter's environment and yours;
  do not guess a cause from code reading alone.
- Trace the code path from entry point to the wrong output. Open the real source; a docstring, comment
  or spec is not evidence of what the code does.

### 1.2 Write the smallest red test

- Put it in the test suite closest to the code path, following the repo's test layout and naming.
- **Fail-side case:** fails on current code **at an assertion about the wrong behaviour**. An
  `ImportError`, missing symbol, fixture error or syntax error is not a reproduction - fix the test
  until the failure message describes the bug.
- **Pass-side case:** the neighbouring expectation that already works, so the fix cannot "pass" by
  breaking it.
- Expected values are literals or independent anchors, never computed by the code under test.
- Run it and keep the exact command and the decisive output lines for the report.
- If no harness can reach the path (UI-only, external service), record deterministic manual repro steps
  plus observed vs expected, and state the gap explicitly.

### 1.3 Check git history

- `git log --oneline -- <paths>` and `git log -S '<symbol or literal>'` for fixes, reverts and test
  changes in the affected area.
- `git blame -L <start>,<end> <file>` on the faulty lines to find the commit and its message.
- When a known-good commit exists, `git bisect` with the red test as the oracle
  (`git bisect run <test command>`); always finish with `git bisect reset`.
- Conclude: **regression** (name the introducing commit) or **latent defect**; and for every repair
  option, whether it could reintroduce a previously fixed bug.

### 1.4 Root cause

- One or two sentences: the mechanism, not the symptom ("the sort has no tie-breaker so equal keys keep
  input order", not "results are in the wrong order").
- Mark anything unproven as a hypothesis with what would prove it.
- List impact: who or what else is affected (other callers, stored data, API consumers).

### 1.5 Write the bug report

- Copy the file printed by `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" template bug` to `<[paths].bugs>/<YYYY-MM-DD>-<slug>.md`
  (`slug` = short kebab-case English summary). Write the prose in `[project].doc_language`.
- Fill every section: symptom, reproduction, red test (command + output), git history, root cause,
  repair options (scope, risk, regression risk, files touched), approval gate (status `pending`).
- Open with a short summary per the document rules: what is broken, root cause, recommended option,
  what the reader must decide.

## Phase 2 - Approval gate

- Report to the user: symptom, evidence, root cause, red-test status, git-history verdict, repair
  options with a recommendation. Then **stop**.
- Do not write production code, a spec or a plan before approval. Exceptions: see Summary (explicit
  "fix now", or obvious L0).
- The gate covers the primary defect. Secondary findings are listed in the report as separate items;
  do not fix them silently.
- Always ask before destructive or irreversible operations, behaviour changes nobody requested, or
  design choices that shape the roadmap - even when the gate was waived.
- An investigation-only request ("tại sao…", "điều tra…") ends here.

## Phase 3 - Repair (after approval)

### 3.1 Choose the lane for the repair

- Fix within one module, no contract change → **L1**: continue below.
- Fix changes schema, API or contracts, or spans modules → **L2**: run `dev-workflow:spec-plan` first;
  link the bug report from the design/plan. Schema changes also use `dev-workflow:db-migration`.

### 3.2 Fix and verify

- Implement the approved option only. Keep files under `[project].max_file_lines`.
- Run the step-1.2 test: fail-side now passes, pass-side still passes.
- Run every command in `[gate].commands` and `[gate].lint` (lint only touched files when the repo says
  so). Report exact commands and results; a skipped check is reported with its reason.

### 3.3 Living docs

- Use `[docs_map]` to find the docs that describe the changed code; update behaviour, contracts and
  operations there in the same change.
- Update the bug report: approval status, chosen option, final test results, commit/PR reference if known.

### 3.4 Self-review and report

- Run `dev-workflow:self-review` on the diff.
- Final report: scope implemented, red→green evidence, gate results, skipped checks with reason, docs
  changed, secondary findings left open.

## Brain/hand split (when delegating)

| Step | Who |
|---|---|
| 1.1-1.3 reproduce, red test, git history | hand (brief must say "investigation only, no production code") |
| 1.4 root cause verdict, 1.5 report review | brain verifies the hand's evidence - reruns the test, opens the cited lines |
| Phase 2 gate, choosing the option | brain + user |
| 3.2 fix and gate | hand (one fix per hand; brief carries the approved option and the red-test command) |
| 3.3 docs | hand, or brain for spec/plan artifacts |
| 3.4 review and disposition of findings | brain (a hand never reviews its own diff) |

Never forward a hand's root-cause claim as fact; recheck it or label it unverified.
