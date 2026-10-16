---
name: jira-workflow
description: Keep Jira in step with the development work using the jira-cli shipped by the jira-tools plugin, driven by the [jira] section of .claude/dev-workflow.toml — search for an existing issue before creating one, create issues under the configured epic/label structure with a description in the configured language and sections, estimate as (AI research + AI coding/testing + human reading/deciding, minimum) × estimate_factor with the breakdown in the description, and on Done log the real time spent and set remaining to 0. Always dry-runs and shows the list before bulk changes; never prints a PAT. Use for any Jira action tied to dev work, including from session-closeout. Triggers on "jira", "tạo task", "tạo issue", "log work", "log giờ", "đóng task", "chuyển Done", "estimate", "ước lượng", "cập nhật jira", "update jira theo kết quả", "log work hôm nay", "cập nhật jira rồi log work", "báo cáo tuần", "weekly report". Prefer this over jira-tools:jira when the repo has .claude/dev-workflow.toml.
---

# jira-workflow

## Summary

- **Purpose:** apply one consistent set of Jira rules in every repo, parameterised by `[jira]` in
  `.claude/dev-workflow.toml`, so the user stops correcting estimates, structure and language by hand.
- **Tool:** the `jira-cli` command of the `jira-tools` plugin. Load skill `jira-tools:jira` for the
  command reference. Its SessionStart hook prints the CLI's location and the matched project; use that
  path. Never write the install path into repo files, and never call the REST API by hand with the PAT.
- **Config keys:** `jira.project`, `jira.estimate_factor`, `jira.language`,
  `jira.description_sections`, `jira.guide` (repo doc describing epics, labels, issue types).
- **Safety:** read-only commands freely; every write is shown first (`--dry-run`), and bulk writes (more
  than one issue) need the user's confirmation of the list. Secrets never appear in output.
- **Missing config:** without `jira.project`, ask which project to use; never guess a project, epic or
  label. Offer to add a `[jira]` section from the example config.

## 1. Before any write

### 1.1 Context

1. Read config with `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --get jira --json` (defaults:
   `${CLAUDE_PLUGIN_ROOT}/skills/dev-triage/references/config-defaults.md`).
2. Read `jira.guide` if set: it decides epics, labels, issue types and any project-specific rule. Project
   rules there win over the defaults in this skill.
3. Confirm the CLI is available: run `jira-cli whoami` (via the hook-provided path). Not available:
   tell the user the `jira-tools` plugin is missing or not configured, and stop.
4. Unsure which fields a type requires: `jira-cli meta --type <Type>`.

### 1.2 What belongs in Jira

Jira tracks the product work. Tooling work on the agent setup itself does not become an issue unless the
user asks. A defect gets the issue type for bugs, not a task with a "bug" label.

## 2. Find or create

### 2.1 Search first

Search before creating, by keywords from the work and by requirement/plan IDs:

```bash
jira-cli search --jql 'project = <KEY> AND text ~ "<keyword>" ORDER BY updated DESC' --limit 20
```

An open issue that matches the work: reuse it (update/comment) instead of creating a duplicate. Several
plausible matches: list them and ask.

### 2.2 Create

- Structure from `jira.guide`: epic link/parent, labels, issue type. Exactly the labels the guide
  requires — no extra ad-hoc labels.
- Leave the assignee empty unless the user named a person in this request.
- Title and body in `jira.language`, with full diacritics where the language has them; identifiers,
  commands and paths verbatim.
- Description body: one heading per entry of `jira.description_sections`, in that order.
- Formatting: Jira Server renders **wiki markup, not Markdown** — use `h3.`, `*bold*`, `{{code}}`, `*`
  bullets. Markdown arrives as raw characters.
- Epics/parent issues carry no estimate.

```bash
jira-cli create --summary '<title>' --type Task --label <label> --description '<wiki markup body>' --field timetracking='{"originalEstimate":"<N>h"}' --dry-run
```

Run without `--dry-run` once the payload is right. Check the field format with `meta` if the project
uses a custom estimate field.

## 3. Estimate

### 3.1 Formula

`estimate = (AI research + AI coding/testing + human reading/deciding) × jira.estimate_factor`

- Each component is the **minimum** realistic time for agent-driven work, not the time a person would
  take to type it. Only machine-bound work (long runs, real data re-processing) stays large.
- Round **up** to the next half hour.
- Write the breakdown (three components, factor, result) into the description's details section so the
  number can be audited. Keep the method out of the summary line.

### 3.2 Example

Research 0.5h + coding/testing 1.5h + human review 0.5h = 2.5h × 1.1 = 2.75h → **3h**.

## 4. Progress and Done

### 4.1 Progress

Comment results with `jira-cli comment <KEY> --body '<wiki markup>'`: what changed, gate result,
links to plan/report paths (relative), open items. Transition with `jira-cli transitions <KEY>` then
`jira-cli transition <KEY> --to '<status>'`.

### 4.2 Done

Only when the gate is green and the issue's scope is finished:

1. **Measure real time** from the session transcript if available: sum the active intervals between the
   first and last message of this work, treating gaps longer than 30 minutes as idle (a pause, not work).
   Add human review time the user reports. State the method in one line in your report.
2. **Log work and zero the remaining estimate in one call**, dated on the day the work was done:

   ```bash
   jira-cli worklog <KEY> --time 1h30m --started '<YYYY-MM-DD>T09:00:00.000+0700' --comment '<one line>' --remaining 0m --dry-run
   ```

   Drop `--dry-run` once the payload is right (always show the dry-run first for bulk closes). The
   command reads time tracking back and exits non-zero when it does not match — report that, do not retry
   blindly.
3. Transition to Done, then comment the summary.

**Fallback:** if `jira-cli --help` lists no `worklog` command (older `jira-tools`), do not improvise a
REST call. Set remaining to 0 with `update <KEY> --field timetracking='{"remainingEstimate":"0m"}'`,
report the exact worklog values (issue, date, duration) for the user to log, and suggest updating the
plugin.

## 5. Bulk changes

Creating, updating or closing more than one issue:

1. Build the full list (key or "new", action, title, estimate or worklog time).
2. Run each command with `--dry-run` and show the list as a table.
3. Wait for the user's confirmation, then execute, and report each result (key + URL or error).
4. Exit code `3` (transition name not found): run `transitions <KEY>` and pick the real name; exit `2`:
   config/PAT problem — tell the user, do not retry blindly.

## 6. Weekly report

1. Query the week:
   `jira-cli search --jql 'project = <KEY> AND updated >= -7d ORDER BY status, updated DESC' --limit 100`
2. Group by status: done this week, in progress, blocked/waiting (labels from `jira.guide`), new.
3. For each done issue: key, title, estimate vs logged time when available.
4. Write the report in `jira.language`, summary first (counts, key outcomes, blockers), then the groups.
   Do not write it into Jira unless the user asks.

## 7. Output hygiene

- Never print, echo or paste the PAT, keychain contents or `secrets` files; never pass a token on the
  command line.
- Pass description/comment text as single-quoted shell strings (escape embedded single quotes); do not
  save Jira drafts as files in the repo.
- In the final report list each issue touched: key, action, result.
