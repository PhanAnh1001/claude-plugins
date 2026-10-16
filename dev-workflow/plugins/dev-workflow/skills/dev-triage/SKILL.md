---
name: dev-triage
description: Classify a piece of development work into lane L0 (quick fix), L1 (standard), L2 (large, needs spec/plan) or L3 (investigation) using measurable criteria, then output a short Triage block listing the lane, reasons, artifacts to create, skills to load, gate commands and approval gates. Use at the start of any coding task — bug fix, feature, refactor, change request — before editing code, and again when the scope grows mid-task. Triggers on "làm task", "sửa", "sửa lỗi", "fix", "thêm tính năng", "triage", "bắt đầu việc", "làm việc này", "implement", "có cần spec không", "làm theo workflow". Do not use for requests that only update Jira, log work, close the session or run the traceability check — those go directly to jira-workflow, session-closeout or trace-check.
---

# dev-triage

## Summary

- **Purpose:** pick the smallest process that is still safe for this task, so quick fixes stay quick and
  large changes get a design, a plan and approval gates.
- **Input:** the user's request, the repo, `.claude/dev-workflow.toml` (`[lanes]`, `[gate]`, `[paths]`).
- **Output:** a `Triage` block in the chat (no file). It decides which skills run next.
- **Rule of thumb:** when the evidence sits between two lanes, take the higher lane, or ask **one**
  question whose answer decides the lane. A bug is never L0.
- **Brain/hand:** the brain triages once and copies the block's `SKILL CẦN NẠP` line into every hand
  brief; hands do not re-triage unless the brief says so. Reviews always stay with the brain.

## 1. Gather the facts (measure, do not guess)

### 1.1 Config

Read the config with `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --json` (details and defaults:
[references/config-defaults.md](references/config-defaults.md)):
`lanes.l0_max_files`, `gate.commands`, `gate.lint`, `paths.srs`. No config: use the fallbacks there and
mention it in the block.

### 1.2 Criteria

Answer each question with something you looked at (file list, grep hit, test run), not with intuition.

| # | Criterion | How to measure |
|---|---|---|
| C1 | Files likely touched | Search for the symbols/strings involved; list the files |
| C2 | Modules touched | Top-level package or app directory of each file in C1 |
| C3 | Changes a public API, DB schema, migration, file/wire format, config key or cross-module contract | Look for route/handler signatures, schema/migration files, exported types used by other modules |
| C4 | Changes observable behaviour | Would any existing test or user-visible output change? |
| C5 | It is a defect | User reports wrong behaviour, an error, a regression |
| C6 | Reproducible deterministically | You can name a command or input that shows the problem every time |
| C7 | Root cause or design known | You can point at the line/component responsible, or the design is obvious |
| C8 | Non-deterministic, performance, capacity or infrastructure question | Timing, GPU, network, flaky output, environment |
| C9 | Related requirement IDs | Grep `paths.srs` for `FR-`/`NFR-`/`BR-`/`E-`/`SC-` IDs on the feature; list hits |

## 2. Choose the lane

### 2.1 Decision order (first match wins)

1. **L3 investigation** — C8 is true, or C5 with C6/C7 false (cannot reproduce, cause unknown).
2. **L2 large** — C2 > 1 module, or C3 true, or the work adds/changes FRs that need a design.
3. **L1 standard** — C5 true (any bug), or C4 true inside one module.
4. **L0 quick fix** — C1 ≤ `lanes.l0_max_files`, C3 false, C4 false (typo, comment, docs wording,
   dead code with proof it is dead, a constant with no behaviour impact).

### 2.2 Borderline cases

- Between two lanes: choose the higher one. Ask a single question instead only when the answer flips the
  lane **and** the higher lane would add an approval stop the user probably does not want.
- Unknown C1 because the search is inconclusive: treat as > `l0_max_files`.
- User says "sửa nhanh" but criteria say L2: state the conflict in one line and let the user choose;
  record the choice in the block.

### 2.3 Re-triage during the work

Raise the lane and announce it as soon as a higher-lane fact appears: a schema/API change surfaces, a
second module is needed, the fix fails to make the reproduction pass, or L3 measurements point at a
concrete defect (then move to L1/L2). Never lower a lane silently.

## 3. What each lane requires

| Lane | Steps | Artifacts | Skills (as `dev-workflow:<name>`) | Approval gates |
|---|---|---|---|---|
| L0 | Edit → gate → report | none | `session-closeout` | none |
| L1 | Red test → fix → living docs (`docs_map`) → gate → self-review | bug report for bugs (`paths.bugs`) | `bug-investigation` (bugs), `self-review`, `session-closeout` | bug: root-cause report before the fix, when the bug skill asks |
| L2 | Design + plan (+ ADR) → approval → implement task by task, ticking boxes → review | design, plan, ADR if a long-lived decision, CR if the SRS must change | `spec-plan`, `trace-check`, `self-review`, `session-closeout`; `db-migration` if schema | design/plan approved before code; review diff before done |
| L3 | Hypotheses → measure one variable at a time → report → **stop** → re-triage to L1/L2 | measurement report | `measurement-evidence`, `bug-investigation` if a defect is suspected | report approved before any fix |

Add when relevant at any lane: `ui-review-iterate` (frontend change), `port-between-repos` (moving code or
docs between repos), `resume-work` (resuming after lost context), `jira-workflow` (via closeout when
`[jira].project` is set).

## 4. Output: the Triage block

Write it in `project.doc_language`, keep it under ~15 lines, put the lane first.

```markdown
### Triage
- **Lane:** L1 — standard
- **Why:** 1 module (`<module>`), 3 files; behaviour changes; bug reproducible with `<command>`; no API/schema change
- **Requirement IDs:** FR-<feature>-003 (or: none found in `paths.srs`)
- **Artifacts:** bug report in `<paths.bugs>/<date>-<slug>.md`
- **Skills:** dev-workflow:bug-investigation → dev-workflow:self-review → dev-workflow:session-closeout
- **Gate:** `<gate.commands>` + `<gate.lint>` (or: no config — inferred `<command>`)
- **Approval gates:** root-cause report before the fix
- **SKILL CẦN NẠP:** dev-workflow:bug-investigation
- **Open question:** (only if one decides the lane)
```

- `SKILL CẦN NẠP` lists the skills a hand doing the implementation must load with its Skill tool; the
  brain pastes this line verbatim into the hand brief. Leave out brain-only skills (`self-review`,
  `session-closeout`, `jira-workflow`) when the brain/hand policy is active.
- Then continue straight into the first step of the lane, unless the block ends with an approval gate or
  an open question — then stop and wait.
