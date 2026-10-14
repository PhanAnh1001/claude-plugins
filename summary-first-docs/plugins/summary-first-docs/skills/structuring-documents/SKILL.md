---
name: structuring-documents
description: Structure any document summary-first and top-down - README, spec, plan, report, solution doc, research report, AGENTS.md, CLAUDE.md or SKILL.md. The document opens with a summary (purpose, key conclusions or decisions, key numbers, what the reader must do), then presents major groups before the branches inside them, and the detailed sections follow the same group -> branch order as the summary. Use whenever writing, restructuring or extending any Markdown document in any project, including docs produced by other skills. Vietnamese triggers - "tóm tắt", "viết tài liệu", "sửa tài liệu", "README", "báo cáo", "spec", "kế hoạch", "plan", "cấu trúc tài liệu", "tài liệu top-down".
---

# Structuring documents

## Summary

- **Purpose:** every document lets a reader stop after the summary and still know what it is
  for, what was decided or concluded, the numbers that matter and what to do next.
- **Rule:** open with a summary, then go top-down: major groups first, then the branches inside
  each group; detailed sections come after the summary in the same group -> branch order.
- **Applies to:** README, spec, plan, report, solution doc, research report, agent instructions
  (AGENTS.md, CLAUDE.md), SKILL.md and any other Markdown document, new or edited.
- **Project rules win:** language, summary heading, file-length limit and paths come from the
  project's AGENTS.md / CLAUDE.md when it states them; the defaults below apply otherwise.
- **Before reporting done:** run the checklist at the end of this skill.

## Project rules first

Read the project's AGENTS.md / CLAUDE.md (root and the folder of the document) before writing.

- **Language:** use the language the project sets for this kind of document. If it says
  nothing, keep the language of the existing document or of the neighbouring documents.
- **Summary heading:** use the project's heading (for example `## Summary` or `## Tóm tắt`).
  If none is set, use `## Summary` in English documents and the equivalent heading in the
  document's language.
- **File length:** respect the project's line limit. If none is set and a document grows past
  roughly 400 lines, propose splitting it by responsibility (one file per group) with an index
  file that keeps the summary.
- **Paths:** refer to files by paths relative to the project root; never write an absolute
  path of a developer machine.

## The summary

### Required content

A summary has these four elements, as short bullets or 2-6 sentences:

1. **Purpose:** what the document is for and who should read it.
2. **Key conclusions or decisions:** the answer, the choice made or the state in force.
3. **Key numbers:** counts, sizes, dates, costs, test results, limits; with sources when the
   numbers are external claims (see the `citing-sources` skill).
4. **What the reader must do:** the action, approval, command or next step; write "nothing to
   do" (in the document's language) if there is none.

Leave an element out only when it truly does not apply (a README may have no decision); never
replace content with filler.

### Short template

```markdown
# <Title>

## Summary

- **Purpose:** <what this document is for, for whom>.
- **Key points:** <decision / conclusion / state in force>.
- **Numbers:** <the 2-5 figures that matter>.
- **Reader action:** <what to do next, or "nothing to do">.
- **Contents:** <group A> -> <group B> -> <group C> (same order as the sections below).
```

### Per document type

| Type | Summary must say |
|---|---|
| README | what the project/folder is, how to install or run it, where to go next |
| Spec | problem, scope, key design decisions, acceptance criteria count, open questions |
| Plan | goal, phases and their status, dates or effort, blockers, next step |
| Report / research | question, 3-5 conclusions, key figures with sources, recommendation |
| Solution doc | solution in force, cause, key numbers, what the reader must do |
| Agent instructions | purpose of the repo, commands, rules that apply on every change |

## Top-down order

### Groups before branches

- Decide the major groups first (for example *Install*, *Use*, *Develop*) and introduce all of
  them, in the summary or a short contents line, before going into any of them.
- Inside each group, present its branches; inside a branch, its details. Do not jump into a
  branch of group B while group A is still open.
- Do not mix levels: siblings under one heading are of the same kind and granularity.

### Sections follow the summary

- Detailed sections appear in the same order as the items in the summary, and use matching
  names, so a reader can jump from a summary bullet to its section.
- Heading levels mirror the tree: `##` for groups, `###` for branches, `####` only when needed.
- Put reference material (tables of options, long examples, history) after the main content or
  in a separate file linked from it.

### Editing an existing document

- When adding content, place it in the group and branch it belongs to; create a new group only
  when none fits, and add it to the summary.
- When the change alters a conclusion, number or reader action, update the summary in the same
  edit. A summary that contradicts the body is a defect.
- Describe the state in force; history belongs in version control, not in "previously..."
  paragraphs, unless the document is explicitly a log.

## Checklist

- [ ] The document opens (after the title) with a summary under the project's summary heading.
- [ ] The summary states purpose, key conclusions/decisions, key numbers and reader action.
- [ ] All major groups are introduced before any branch is detailed.
- [ ] Detailed sections follow the summary's order; heading levels mirror group -> branch.
- [ ] No sibling headings at mixed levels of detail.
- [ ] Language, summary heading and line limit follow the project's rules (or the defaults).
- [ ] Paths are relative to the project root; no developer-machine absolute path.
- [ ] External figures and claims carry sources per the `citing-sources` skill.
- [ ] The summary still matches the body after the last edit.
