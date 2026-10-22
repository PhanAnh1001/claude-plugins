---
name: project-bootstrap
description: Take a new project from an empty repo to the per-task development loop in a fixed order of phases - (0) repo rules (AGENTS.md, document governance, .claude/dev-workflow.toml), (1) requirements (SRS with FR IDs, open-question register, prototype-to-FR mapping), (2) architecture and one ADR per long-lived decision, (3) Jira epics plus the jira.guide backlog map and branch/merge-request rules, (4) an approved MVP roadmap whose task lines cover every FR, (5) the scaffold and gate for milestone M0, then (6) hand over to dev-triage for each task. Keeps a bootstrap plan with one checkbox per exit criterion, detects the current phase from the artifacts already in the repo, and stops at each human approval gate. Use when a project or repo is new or half set up, when the user asks what comes next before coding starts, or how a project goes from start to development. Vietnamese triggers - "dự án mới", "bắt đầu dự án", "khởi tạo dự án", "khởi tạo repo", "dựng dự án từ đầu", "quy trình dự án mới", "từ đầu đến dev", "các bước trước khi code", "bootstrap dự án".
---

# project-bootstrap

## Summary

- **Purpose:** give every new project the same path from an empty repo to coding, so requirements,
  decisions and the backlog exist before code, and each later task can run through `dev-triage`.
- **Phases (in order):** 0 repo rules → 1 requirements → 2 architecture and ADRs → 3 backlog in Jira →
  4 MVP roadmap → 5 scaffold and gate (milestone M0) → 6 per-task loop. Phases 0–4 write only docs and
  decisions; code starts in phase 5.
- **Output:** the artifacts of each phase plus one bootstrap plan
  `<paths.plans>/YYYY-MM-DD-project-bootstrap.md` copied from
  [references/bootstrap-plan.md](references/bootstrap-plan.md); every exit criterion is a checkbox,
  ticked only when its artifact exists and was checked.
- **Approval gates (human):** AGENTS.md rules and config (phase 0); SRS draft and each open-question
  answer (phase 1); each ADR (phase 2); epic list before creating it in Jira (phase 3); the roadmap
  (phase 4). Stop at each gate and wait.
- **Never:** copy the product source documents into the repo; write feature code before the roadmap is
  approved; create Jira issues without a dry-run and confirmation; guess a Jira project, epic or label.
- **Lessons built in:** write the roadmap before the scaffold so M0 builds only what the first
  milestones need; calibrate estimates against the first logged tasks (first guesses ran ~10× high);
  keep open questions in one register and answer the ones blocking the next milestone first.

## 1. Start: find the current phase

### 1.1 Detect

Look at what exists; the first phase whose exit criteria are not met is the current one. Report the
table in chat, then continue with that phase.

| Phase | Done when these exist |
|---|---|
| 0 | `AGENTS.md` (+ `CLAUDE.md` with `@AGENTS.md`), `README.md`, `.gitignore`, docs index, document governance, `.claude/dev-workflow.toml` |
| 1 | SRS files under `paths.srs` with `FR-<feature>-NNN` IDs, an open-question register, prototype mapping (if a prototype exists) |
| 2 | Architecture overview and at least the repo-layout and stack ADRs in `paths.adr`, all `accepted` |
| 3 | Epics in Jira, `jira.guide` doc, branch and merge-request rules in AGENTS.md |
| 4 | Roadmap plan `status: approved`; `dw trace` shows no FR without a task; tasks of the first milestones in Jira |
| 5 | Scaffold merged to the integration branch; `gate.commands` filled in config and green |

### 1.2 Inputs to ask for (once, together)

Ask only for what the repo cannot tell you: where the product source documents live (outside the repo),
the Jira project key, the integration branch (for example `dev`), who approves direction and review
tasks and who takes regular tasks, deployment constraints (cloud, on-premise, offline), reference
projects to reuse. Record the answers in AGENTS.md (phase 0), not only in chat.

## 2. Phase 0 — repo rules

1. Write `AGENTS.md` from the outline in
   [references/agents-md-outline.md](references/agents-md-outline.md): summary first, documentation
   language, product source documents outside the repo (path as `~/...`), reference projects, role
   separation, working rules (git, shell, paths, secrets, file size), bug workflow, commit and
   merge-request rules. `CLAUDE.md` holds only `@AGENTS.md`.
2. `README.md` (human language), `.gitignore` (secrets, `.env`, local data, build output).
3. Docs tree: `docs/index.md` and `docs/document-governance.md` separating living docs (requirements,
   architecture, decisions) from work in progress (specs, plans, backlog, bugs, CRs).
4. Config: copy `${CLAUDE_PLUGIN_ROOT}/templates/dev-workflow.example.toml` to
   `.claude/dev-workflow.toml`; set `paths.*` to the docs tree, `[jira]` (project, language,
   `description_sections`), `project.max_file_lines`. Leave `gate.commands` empty until phase 5.
5. Create the bootstrap plan (section Summary, Output).
6. **Gate:** show the rules and config; wait for approval.

## 3. Phase 1 — requirements

1. Read the source documents with a converter (`textutil -convert txt`, `libreoffice --headless
   --convert-to txt`); quote paths with spaces. Never commit them or paste large parts into the repo.
2. SRS under `paths.srs`: one file per feature group, IDs `FR-<feature>-NNN`, plus `NFR-…`, error cases
   `E-…` and success criteria `SC-…` where they are known. Status `draft`.
3. Open-question register: one row per `Q-NN` (question, options, who decides, which milestone or FR it
   blocks, status). An answered question moves to a "decided on <date>" section and its answer is
   written into the affected FR in the same edit.
4. UI prototype present: map each screen to FR IDs; screens without an FR become new FRs or questions.
5. Sizing or market/vendor research across several sources: save it with
   `summary-first-docs:saving-research` (if installed) and cite sources.
6. **Gate:** the user reviews the SRS draft and answers the blocking questions. Iterate; set the SRS to
   `approved` when the user says so.

## 4. Phase 2 — architecture and decisions

1. Architecture overview and flow diagrams in the living architecture folder; diagrams as Mermaid in
   the Markdown, not image files.
2. One ADR per long-lived decision, through `dev-workflow:spec-plan` §2.3: repo layout, stack and
   versions, integration patterns (plug-in contracts, provider interfaces), data stores, CI policy.
   Each ADR is a separate approval; a changed decision gets a superseding ADR.
3. Copy each accepted decision into the AGENTS.md summary in one line with its ADR path, so agents see
   it every turn.

## 5. Phase 3 — backlog in Jira

1. Write the `jira.guide` doc (for example `docs/work-in-progress/backlog/epic-reuse-map.md`): one epic
   per feature group, required labels, issue types, the reuse source for each epic (reference project,
   shared package), a suggested order and porting risks. Set `jira.guide` in the config.
2. Create the epics through `dev-workflow:jira-workflow` (dry-run, show the list, confirm). Epics carry
   no estimate.
3. Add branch and merge-request rules to AGENTS.md: branch from the integration branch, named after the
   Jira key (`feat/<key>-<meaning>`), merge requests target the integration branch, and what to do when
   the server ignores push options (give the user the prefilled merge-request link).
4. Long or uncertain groundwork (measurements, API surveys) becomes its own Jira task now so it runs in
   parallel with phase 4.

## 6. Phase 4 — MVP roadmap

1. One L2 plan `<paths.plans>/YYYY-MM-DD-mvp-roadmap.md` via `dev-workflow:spec-plan`: milestones
   M0..Mn, each with acceptance checkboxes; task lines `T-mvp-NN … — covers: FR-… — estimate: …`.
   M0 is the scaffold and core foundation only.
2. Each milestone lists the open questions that block it; answer those of M0–M1 before approval.
3. Run `dev-workflow:trace-check` until no FR is without a task ("no test" errors are expected before
   code).
4. Estimates: use the formula of `jira-workflow` §3; once the first tasks are logged, recalibrate the
   rest from actual time and note it in the plan.
5. **Gate:** the user approves the roadmap. Then create the Jira tasks of the first milestones as one
   bulk change (dry-run, table, confirmation), assigned by the rule recorded in phase 0, and write the
   Jira keys into the roadmap lines.

## 7. Phase 5 — scaffold and gate (M0)

1. Run as normal tasks (`dev-workflow:dev-triage`, usually L2): folder layout per the repo-layout ADR,
   local dev environment, CI per the CI ADR, test runner and linter per language, deployment skeleton.
   Reused code goes through `dev-workflow:port-between-repos`.
2. Fill `gate.commands` and `gate.lint` in the config with the real commands and run them green; from
   now on the gate is mandatory before every commit.
3. Update AGENTS.md "current state" (how to run locally, ports, gate) in the same change.

## 8. Phase 6 — per-task loop

Every task from here: Jira task → branch from the integration branch → `dev-triage` → `spec-plan` (L2)
or `bug-investigation` (bugs) → code and tests → gate → `self-review` and `trace-check` → commit only
when asked → merge request → review and merge → `session-closeout` (logs real time, closes Jira). Close
the bootstrap plan (`status: completed`) when the M0 scaffold is merged and its gate is green.

## 9. Rules while bootstrapping

- Documents: summary first, top-down; human docs in `project.doc_language`, agent files in English;
  relative links; no machine absolute paths; no secrets; stay under `project.max_file_lines`.
- Commit only when the user asks, staging only the files of that step; no history-rewriting git
  commands.
- One canonical source per topic: update an existing SRS, ADR or plan instead of adding a parallel one.
