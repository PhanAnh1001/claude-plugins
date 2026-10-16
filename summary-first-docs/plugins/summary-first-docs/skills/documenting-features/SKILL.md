---
name: documenting-features
description: Create and keep current the end-user feature list of a project - one living document per user group (for example docs/guides/features.md, or the path the project's AGENTS.md / CLAUDE.md sets) that says what users can do, how, with what input and output, and its limits, with every feature marked "Đã có" (available), "Đang làm" (in progress) or "Dự kiến" (planned, with its source spec/plan/issue) so planned work is never mistaken for usable. Built at project start by scanning README, specs, plans and code entry points (CLI, routes, UI buttons, commands, skills); read at the start of every task to state the task in user terms; updated at the end of every task before reporting. Use when a project starts or has no feature list yet, when a task starts or finishes, when a feature is added, changed, dropped or planned, and when the user asks what the product can do. Vietnamese triggers - "danh sách tính năng", "tính năng", "liệt kê tính năng", "làm được gì", "bắt đầu dự án", "task mới", "xong task", "tính năng dự kiến", "hướng dẫn người dùng", "cập nhật tính năng".
---

# Documenting features

## Summary

- **Purpose:** keep one current answer to "what can the user do with this product?": a feature
  list per user group, written for end users, with a clear status on every feature.
- **When:** (1) at project start or when no list exists: build it; (2) at the start of every
  task: read its summary and state the task in user terms; (3) at the end of every task, before
  reporting to the user: update it.
- **Result required:** the list matches what users can do now; planned features are separated
  and sourced; the checklist in step 5 passes.
- **Project rules win:** path, file name, language, statuses and line limit come from the
  project's AGENTS.md / CLAUDE.md. Without a rule, propose one (step 1) and ask before writing it.
- **Related skills:** structure the document with `structuring-documents`; record the technical
  solution behind a feature with `documenting-solutions` (the feature list says what users get,
  the solution file says how and why it is built that way).

## Rules

### Audience and scope

- Write for the end user of one user group (for example accountants, admins, API clients), not
  for developers. One project keeps one feature list per user group; never two lists for the
  same group.
- Do not copy other guides: link to them (installation guide, folder guide, FAQ).

### Status of each feature

| Status (Vietnamese default) | English | Meaning |
|---|---|---|
| `Đã có` | Available | Users can use it now in a released or runnable build |
| `Đang làm` | In progress | Work has started in an open task; not usable yet |
| `Dự kiến` | Planned | Decided in a spec, plan or issue; work not started |

- The summary table has a `Trạng thái` column. `Đang làm` and `Dự kiến` features also appear
  only in the section `Dự kiến và đang làm`, each with its source (spec, plan or issue link), so a
  reader never takes them for usable. Never describe them in the "how to use" sections.
- If the project uses no `Đang làm` status (for example short tasks), skip it.
- A dropped feature is deleted from the list; history stays in version control.

### Writing each feature

- **Names as in the product:** copy button labels, menu items, commands and options exactly as
  the code or UI shows them. No `file:line`, no class or function names.
- **Per feature:** input -> output, how to use it (button, command, menu path), and its limits.
- **Language:** the template is Vietnamese with full diacritics; translate headings and status
  names if the project's user documents use another language, and keep that choice everywhere.
- **Paths:** relative to the project root; never a developer-machine absolute path.

## Steps

### 1. Find the list and the project rule

- Read AGENTS.md / CLAUDE.md (root and the docs folder) for the feature-list path and rules.
- If no rule exists: look for an existing list (`git grep -il "tính năng\|features" -- docs`).
  Then propose a path (default `docs/guides/features.md`, or `docs/guides/<user-group>-features.md`
  when there are several user groups) and the sample rule below, and **ask the user before
  adding the rule to AGENTS.md** and before creating the file.

Sample rule for AGENTS.md (adapt the path and user groups):

```markdown
**Features**

- The end-user feature list lives at `docs/guides/features.md` (one file per user group:
  `docs/guides/<user-group>-features.md`), Vietnamese, opens with `## Tóm tắt`, follows the
  skill `summary-first-docs:documenting-features`.
- Every feature has a status: `Đã có`, `Đang làm` or `Dự kiến`. Planned and in-progress features
  stay in the section `Dự kiến và đang làm` with their source (spec, plan or issue).
- At the start of every task, read the list's summary and state which features the task adds,
  changes or drops (or "no feature change"). At the end, update the list before reporting.
- Button, menu and command names are copied exactly from the product; no `file:line`.
```

### 2. Build the list (project start or first time)

- Scan the sources users meet: README, user guides, specs and plans (for planned work), and
  code entry points: CLI commands and options, web routes and page titles, UI buttons and menus,
  bot commands, Agent Skills, MCP tools, scheduled jobs.
- Group features by what users do (run, review, export...), not by code module.
- Copy [template.md](template.md) to the chosen path and fill every section; mark each feature
  with its status and the source of every planned one.
- Show the summary (group table, key numbers, getting-started steps, top limits) to the user in
  chat and ask them to confirm the grouping.

### 3. At the start of a task

- Read the list's summary (and the sections the task touches).
- State the task in user terms: which features it adds, changes or drops, or "no feature
  change" (for example a refactor or test-only task).
- If the project uses `Đang làm`, move the affected features to it now.

### 4. At the end of a task, before reporting

- Added: describe the feature where its group belongs (input -> output, how to use, limits),
  set `Đã có`, update the summary table and counts.
- Changed: rewrite its entry so it describes the behaviour now; re-check names against the code.
- Dropped: delete it everywhere (summary, sections, getting-started steps).
- Not finished: keep `Đang làm` or move back to `Dự kiến` with its source.
- Update `Chưa làm và giới hạn` and the header date.
- If the app displays this document (help page, guide viewer), check that its link, title and
  anchors still work.

### 5. Checklist before reporting done

- [ ] Opens with the audience line, then `## Tóm tắt` (`structuring-documents`).
- [ ] Every feature in the summary table has a status; sections follow the table's group order.
- [ ] No `Đang làm` / `Dự kiến` feature is described as usable; each has a source link.
- [ ] Button, menu and command names match the code; no `file:line`.
- [ ] Each feature states input -> output, how to use, limits.
- [ ] Other guides are linked, not copied; every relative link points to an existing file.
- [ ] Within the project's line limit; split per group with an index file if larger.
- [ ] No developer-machine absolute path:
      `git grep -nE "/User[s]/|/hom[e]/|/privat[e]/|/tm[p]/|/var/folder[s]/|[~]/" -- <list path>` is empty.
- [ ] The task's feature changes (stated in step 3) are all reflected.

Do this before reporting the task to the user. Do not commit or push unless the user asks.
