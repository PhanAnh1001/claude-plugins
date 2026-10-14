---
name: documenting-solutions
description: Write, update or delete living solution documents - one file per solution in force at docs/solutions/<group>/<branch>/<solution>.md (or the path the project's AGENTS.md / CLAUDE.md sets), indexed top-down in docs/solutions/README.md. Files describe only what is in force; a changed solution is edited in place, a dropped or replaced one is deleted with every link and the index fixed. Use when a task finishes (spec, feature, dataset, tool, policy or process change), before reporting to the user; when a solution is changed, dropped or replaced; and when a group or branch is added under the solutions folder. Vietnamese triggers - "giải pháp", "ghi lại giải pháp", "cập nhật solutions", "tài liệu giải pháp", "bỏ giải pháp", "thay giải pháp", "xong task", "solutions".
---

# Documenting solutions

## Summary

- **Purpose:** keep a current map of every solution the project applies: one file per solution
  at `docs/solutions/<group>/<branch>/<solution>.md`, indexed in `docs/solutions/README.md`.
- **When:** at the end of every task, before reporting to the user; whenever a solution
  changes, is dropped or is replaced; whenever a group or branch is added.
- **Result required:** each solution of the task has exactly one file in force (created,
  updated in place, or deleted with every link fixed); the index matches the folders; the
  checklist in step 5 passes.
- **Project rules win:** if AGENTS.md / CLAUDE.md sets another folder, language or line limit,
  use it everywhere this skill says `docs/solutions/`.
- **Related skills:** structure every file with `structuring-documents`; cite legal, market and
  vendor claims with `citing-sources`.

## Rules

- **Path:** `<group>` is a major area, `<branch>` a sub-area, `<solution>` one solution; names
  in English kebab-case, no date prefix.
- **Content:** follow [template.md](template.md): summary, cause, solution in force, why chosen,
  rejected alternatives, verification (commands and real results), related files, open issues,
  last-updated date.
- **Language:** the template headings are Vietnamese by default. If the project writes its
  documents in another language, translate the headings (table below) and keep that choice for
  every file in the folder.
- **One topic, one place:** never two folders or two files for the same topic.
- **In force only:** files describe the current state; history lives in version control.
- **Decisions:** if the project keeps a decision log, link the relevant entries from the file
  header (`Liên quan:`) and from the why-chosen section; otherwise the why-chosen section
  carries the full reasoning.

| Vietnamese (default) | English |
|---|---|
| `Cập nhật:` / `Liên quan:` | `Updated:` / `Related:` |
| `## Tóm tắt` | `## Summary` |
| `## Nguyên nhân` | `## Cause` |
| `## Giải pháp đang áp dụng` | `## Solution in force` |
| `## Vì sao chọn` | `## Why chosen` |
| `## Phương án đã loại` | `## Rejected alternatives` |
| `## Kiểm chứng` | `## Verification` |
| `## File liên quan` | `## Related files` |
| `## Việc còn mở` | `## Open issues` |

## Steps

### 1. Identify the solutions of the task

- List each independent solution the task applied, changed or dropped. One solution = one
  file; split a task touching two concerns (for example a parser and a caching policy) in two.
- For each, note the action: create, update or delete (dropped or replaced).

### 2. Place each solution in the tree

- Read `docs/solutions/README.md` first; do not assume a fixed tree, it changes over time. If
  it does not exist yet, list `docs/solutions/` and create the index in step 4.
- Reuse an existing group and branch that covers the topic. Create a new one only when none
  does.
- Check for near-duplicates by meaning, not only by name (`auth` vs `login`, `export` vs
  `reporting`). If two folders overlap, use the existing one.
- Search for an existing file on the topic before creating one:
  `git grep -il "<keyword>" -- docs/solutions` and `ls docs/solutions/<group>/<branch>/`.
  If one exists, update it instead.

### 3. Act on each solution

**Create**

- Copy [template.md](template.md) to `docs/solutions/<group>/<branch>/<solution>.md`.
- Replace every guidance comment with content; keep the section headings (translated if the
  project uses another language).
- Set the updated date to today (ISO `YYYY-MM-DD`).

**Update**

- Edit the file in place so it describes the state now in force. Do not write a log
  ("previously...", "then...", "second fix"); rewrite the affected sections instead.
- Update the date, related links, verification commands/results and related files.

**Delete (dropped or replaced)**

- `git rm docs/solutions/<group>/<branch>/<solution>.md`; remove any folder left empty.
- Find and fix every link to it: `git grep -n "<solution>.md"` (and the folder name if a folder
  was removed). Point each link to the replacement, or remove it.
- Remove its line from `docs/solutions/README.md`.
- If replaced: the new file states the old solution briefly under rejected alternatives (why it
  was dropped) or under cause (why it no longer sufficed). Do not keep the old file.

### 4. Update the index `docs/solutions/README.md`

- Opens with a summary (purpose, how to use, add/update/delete rules, counts of groups, branches
  and files), then the solution tree top-down: one `### <group>: <description>` heading per
  group; inside it one bullet per branch `- **<branch>:** <description>`; under each branch one
  nested bullet per file: link, then the solution in one phrase, then related decision entries
  if the project keeps a decision log.
- Example branch and file lines (copy the format of existing lines when the index exists):

  ```
  - **file-import:** reading files uploaded by users
    - [csv-reader.md](data-ingestion/file-import/csv-reader.md): reads CSV with encoding
      detection and a size cap.
  ```

- Update the counts in the summary when a group, branch or file is added or removed.
- Every file under `docs/solutions/` has exactly one line; every line points to an existing file.

### 5. Checklist before reporting done

- [ ] Every solution file and the index open with a summary (`structuring-documents`).
- [ ] Language and headings consistent across the folder (Vietnamese default or translated).
- [ ] Folder and file names are English kebab-case, no date prefix.
- [ ] Each file within the project's line limit; split by sub-topic into separate solutions if
      larger.
- [ ] Only paths relative to the project root; no developer-machine absolute path:
      `git grep -nE "/User[s]/|/hom[e]/|/privat[e]/|/tm[p]/|/var/folder[s]/|[~]/" -- docs/solutions` is empty.
- [ ] Every relative link points to an existing file (check each target with `ls`).
- [ ] Legal, market and vendor claims cited per `citing-sources`.
- [ ] No link remains to a deleted file: `git grep -n "<deleted-file>.md"` is empty.
- [ ] Index tree matches the folders on disk; no two folders or files cover the same topic.
- [ ] Decision-log entries linked if the project keeps one; otherwise the why-chosen section
      carries the reasoning.

Do this before reporting the task to the user. Do not commit or push unless the user asks.
