# AGENTS.md outline for a new project

## Summary

- **Use:** the section list for a new repo's `AGENTS.md`, written in English (agent-only file). Fill
  each section with the project's facts; drop a section only when it truly does not apply.
- **Order:** summary first (what the repo is, current state, key decisions with ADR paths, rules that
  apply every turn), then the detailed sections in the order below.
- **Keep it current:** phase 2 adds one line per accepted ADR to the summary; phase 3 adds branch and
  merge-request rules; phase 5 fills "current state" with how to run and the gate.

## 1. Summary

- What this repo is (product, users, deployment model).
- Current state (empty → scaffold → features); how to run locally once a scaffold exists.
- Key decisions, one line each, with the ADR path.
- Rules that apply to every turn (language, source documents outside the repo, no commit without
  request, no destructive git, no secrets, no `cd` in compound commands, file-size limit).

## 2. Documentation language

- Agent-only files in English; human-facing files (`README.md`, `docs/`) in the team's language with
  full diacritics; identifiers, commands and paths unchanged.
- File and directory names in English kebab-case.
- Every document opens with a summary, then groups before branches.

## 3. Product source documents outside the repository

- Local copy path as `~/...`, shared original link, which file holds what.
- Never copy them into the repo or commit them; how to read them (converters, quoting).

## 4. Reference projects

- Sibling projects to learn from or reuse, written as `~/app/<project>`; shared packages to prefer.
- Ported code cites its source in the file header.

## 5. Role separation

- Who plans, decides and reviews; who executes; what an executing sub-agent must be given in its brief.

## 6. Working rules

- Git: commit only when asked, `git add <path>` only; list of forbidden history/tree-rewriting commands.
- Shell: no `cd` chained with `&&`, `;` or `|`; use `make -C`, `npm --prefix`, `env -C`, `git -C`.
- Paths in committed files: repo-relative or `~/...`, never machine absolute paths.
- Secrets: never commit `.env` or credentials; `.env.example` holds names only; never log passwords.
- File size: hard limit per file; split before crossing it.
- Product constraints that shape every change (deployment model, offline, customisation by
  configuration, scale profiles, feature toggles).

## 7. Bug investigation and repair

1. Reproduce and trace without touching production code; smallest test that fails for the real reason.
2. Check git history of the affected path.
3. Report root cause, evidence and options; stop for approval.
4. After approval: fix, targeted test, gate, living docs in the same change.

## 8. Commit and merge-request guidelines

- Conventional Commits with scope; imperative, scoped commits.
- Merge-request description: problem, solution, verification commands, linked issues/specs, screenshots
  for UI.
- Branches from the integration branch named after the Jira key; merge requests target it; the main
  branch is updated only from the integration branch.
- How merge requests are created (push options) and the fallback when the server ignores them.
