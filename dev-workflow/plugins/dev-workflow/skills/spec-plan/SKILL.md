---
name: spec-plan
description: Create or update the design (spec), the implementation plan and ADRs from the plugin templates at the paths configured in .claude/dev-workflow.toml, linked to requirement IDs through `implements:` and `covers:`. Keeps only the current design (superseded parts are edited or deleted, never kept side by side), writes every plan task as a Markdown checkbox, ticks a box only after the work is done and verified, deletes skipped tasks or marks them `[-]` struck through, sets the plan status to `completed` when no `[ ]` box is left, and stops for human approval of design/plan on L2 work. Use for any L2 task, whenever a plan or spec must change, or a long-lived technical decision needs recording. Triggers on "tạo spec", "viết spec", "tạo plan", "lập kế hoạch", "viết ADR", "ghi quyết định", "cập nhật plan", "tick plan", "thiết kế tính năng", "design doc".
---

# spec-plan

## Summary

- **Purpose:** turn approved requirements into a design and a task plan the agent can follow and the
  user can approve, and keep both truthful while the work runs.
- **Inputs:** the Triage block (lane, IDs), SRS files (`paths.srs`), existing specs/plans/ADRs, code.
- **Outputs (files):**
  - design: `<paths.specs>/YYYY-MM-DD-<topic>-design.md` from template `design`
  - plan: `<paths.plans>/YYYY-MM-DD-<topic>.md` from template `plan`
  - ADR: `<paths.adr>/ADR-NNNN-<slug>.md` from template `adr` (only for long-lived decisions)
  - CR: `<paths.crs>/CR-YYYYMMDD-NNN.md` from template `cr` when the SRS itself must change
- **Approval gates:** on L2, stop after writing the design and plan and wait for the user to approve
  them. Code starts only after approval. A CR waits for approval before the SRS is edited.
- **Invariants:** only current design in the docs; every plan task is a `- [ ]` checkbox; boxes ticked
  the moment work is done and verified; skipped tasks deleted or marked `- [-] ~~…~~`;
  `status: completed` only when no `[ ]` box is left (`[x]` and `[-]` are both closed).

## 1. Prepare

### 1.1 Config and templates

- Read config with `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --json` (details and defaults:
  `${CLAUDE_PLUGIN_ROOT}/skills/dev-triage/references/config-defaults.md`). Keys used:
  `paths.specs`, `paths.plans`, `paths.adr`, `paths.crs`, `paths.srs`, `paths.templates`,
  `paths.template_aliases`,
  `project.doc_language`, `project.max_file_lines`, `trace.id_types`.
- Template: run `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" template <design|plan|adr|cr>` and copy the file whose path it prints
  (stderr says `source: repo` or `plugin`; a repo `spec.md` serves as the design template). Do not open
  template paths directly. Copy the frontmatter and section headings exactly — the trace script parses
  them.
- No config: write next to the repo's existing specs/plans if any; otherwise ask where before creating
  a new docs tree, and offer to create the config.

### 1.2 Find what already exists

- Search the spec, plan and ADR folders for the topic and for the requirement IDs. Update an existing
  document instead of creating a second one on the same topic: one canonical source per topic.
- Read the SRS rows for each ID, including `Verify by`, error cases `E-…` and success criteria `SC-…`.
  If the SRS is not `approved`, say so; design work on an unapproved SRS is at the user's risk.
- `[NEEDS CLARIFICATION]` or open `OQ-n` items that affect the design: list them and ask before
  designing around a guess.

## 2. Write

### 2.1 Design (spec)

- Frontmatter: `status: draft`, `lane`, `implements: [FR-…, NFR-…]` listing every requirement the design
  satisfies.
- Content: technical decisions only (API, data model, migrations, module boundaries, error handling for
  each `E-…`). Link to the SRS and to canonical docs instead of copying them.
- Long-lived or hard-to-reverse decisions (storage engine, public contract, dependency choice) go into an
  ADR; the design links to the ADR and states the decision in one line.

### 2.2 Plan

- Frontmatter: `status: draft`, `lane`, `covers: [FR-…]` (union of the task lines); link to the design.
- Every task and every Verification step is a checkbox line — never a plain bullet or a paragraph. One
  task per reviewable unit, in the template's exact line format (the trace script parses it):
  `- [ ] T-<feature>-NN <description> — covers: FR-<feature>-001, E-<feature>-002 — estimate: 2h`.
  Plain bullets are allowed only for notes and decisions, which are not work.
  Every ID in the design's `implements` is covered by at least one task.
- Include a test task (or test sub-item) for every ID whose `Verify by` names a test, and for every
  `E-…` case. Add a "Verification" section with the gate commands from `gate.commands`.
- Order tasks so each one leaves the build green.

### 2.3 ADR

- Number: next free `NNNN` in `paths.adr`; never reuse a number.
- `status: draft` until the user accepts it. Signing an ADR is a human decision.
- A superseding ADR fills `supersedes:`; the old ADR keeps its content and gets a pointer to the new one.

### 2.4 CR (requirement change discovered during design)

Do not edit an approved SRS directly. Create a CR with the impact report (affected IDs, design, plan,
tests, estimate delta) and stop for approval. After approval, update the SRS, then the design and plan.

### 2.5 Writing rules

- Language: `project.doc_language`; identifiers, commands and paths stay verbatim.
- Every document opens with a summary (purpose, key decisions, what the reader must do), then sections
  top-down: groups first, branches inside each group.
- Relative links only; no machine absolute paths; no secrets.
- Stay under `project.max_file_lines`; split by topic before crossing it.

## 3. Approval gate (L2)

Present in chat: file paths, a five-line summary of the design, the task list with IDs and estimates,
open questions. Then stop. On approval set `status: approved` in the approved files (record who/when if
the template has fields). Requested changes: edit, re-present, stop again. L1 work that asked for a plan
only does not need this stop unless the user requests it.

## 4. Keep it current while working

### 4.1 Ticking and status

- Tick `- [x]` as soon as a task's code, test and docs are done and its check passed — not in a batch at
  the end, and never before the gate or check has finished running. Status flow: `draft` → `approved`
  (gate) → `in-progress` (first task starts) → `completed`; a replaced document becomes `superseded`.
- Set `status: completed` only when no `[ ]` box is left, including Verification (`[x]` done, `[-]`
  skipped). A design moves to `completed` with its plan. After completion, reflect changed behaviour
  into the living docs (`docs_map`, see `session-closeout`).

### 4.2 Superseded designs and decisions

When a decision changes, edit or delete the old text in the design/plan in the same edit — never keep old
and new side by side or append "UPDATE:" notes. History lives in ADRs and git. Add newly discovered
tasks with new IDs (never renumber existing ones, other files reference them).

### 4.3 Skipped tasks

A task that will not be done is never ticked as if it were done. Pick one:

- **Delete the line** when the task no longer means anything (default; only current design stays).
- **Mark it skipped** when the decision to skip must stay visible:
  `- [-] ~~T-<feature>-NN <description>~~ — bỏ qua: <reason>`.
  `covers:` and `estimate:` may stay for the record: the trace script ignores any line with a `[-]` box
  or a struck-through task ID, so a skipped task never counts as covering a requirement. `dw trace` then
  reports each ID left without a task; re-cover it with another task, or raise a CR if the requirement
  itself is dropped.

### 4.4 Scope growth

New requirement or a second module discovered mid-work: update the plan, tell the user in one line, and
re-run `dev-workflow:dev-triage` if the lane changes. Changes to approved design decisions need a fresh
approval.

## 5. Check before handing back

- `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" trace` when `paths.srs` is configured: every `implements`
  ID is covered by a task (see `dev-workflow:trace-check`).
- Frontmatter has the template's required keys; links resolve; file length within the ceiling.
