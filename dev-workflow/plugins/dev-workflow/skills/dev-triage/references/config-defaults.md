# dev-workflow config: lookup and fallback defaults

## Summary

- Every dev-workflow skill reads `.claude/dev-workflow.toml` through the wrapper
  `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config`. The wrapper picks a Python ≥ 3.11 (or `uv`); never run the `.py` scripts with the
  system interpreter, which may be too old to read TOML. The script is the source of truth for keys and
  defaults; this page explains how to read it and what to assume when the config is missing.
- Exit code `2` means the config is missing or invalid, or no suitable Python was found; the stderr
  message says which. Missing:
  continue with the defaults below, say so once in your report, and offer to create the config by
  copying `${CLAUDE_PLUGIN_ROOT}/templates/dev-workflow.example.toml` to `.claude/dev-workflow.toml`.
  Do not create it without the user's go-ahead: it is a committed repo file. Invalid: show the error;
  do not silently fall back.
- Never guess a value that changes what gets written to an external system (Jira project, epic, labels).
  When such a key is missing, ask.

## 1. Reading the config

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --json            # whole config, defaults merged
"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --get gate.commands
"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config --get docs_map --json
"${CLAUDE_PLUGIN_ROOT}/scripts/dw" trace                     # traceability check (see dev-workflow:trace-check)
"${CLAUDE_PLUGIN_ROOT}/scripts/dw" template design           # path of the template to copy (repo override or plugin)
```

Run from the repo root (use an absolute repo path in arguments instead of `cd ... &&`).

| Exit | Meaning | What to do |
|---|---|---|
| 0 | Config found and valid (warnings for unknown keys go to stderr) | Use the values |
| 2 | Config missing, unreadable or invalid; usage error; no Python ≥ 3.11 | Read stderr: missing → fallback table; invalid → report the error; no interpreter → tell the user to install Python 3.11+ or `uv` |

## 2. Fallback values (config missing)

These mirror the script's built-in defaults (`DEFAULTS` in `dw_config.py`); if they ever differ, the
script wins.

| Key | Default | Note |
|---|---|---|
| `project.doc_language` | `vi` | Language of generated docs and reports |
| `project.max_file_lines` | `400` | |
| `gate.commands`, `gate.lint` | empty | Find the repo's own test/lint entry points (Makefile target, `package.json` script, `pytest`) and report that they were inferred |
| `paths.specs` / `plans` / `adr` / `bugs` / `crs` | `docs/specs`, `docs/plans`, `docs/adr`, `docs/bugs`, `docs/cr` | If the repo already keeps such docs elsewhere, use that layout instead and suggest recording it in the config |
| `paths.srs` | `docs/**/srs/*.md`, `docs/specs/**/*.md` | |
| `paths.traceability` | `docs/_shared/traceability.md` | |
| `paths.templates` | empty → plugin templates | Never open a template path directly: `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" template <design\|plan\|bug\|cr\|adr\|traceability>` prints the file to use (stderr `source: repo\|plugin`; exit 2 = unknown name) |
| `paths.template_aliases` | `{design = "spec.md"}` | Extra repo file name tried after `<name>.md` (a repo whose `spec.md` is its design template). A repo value replaces this table entirely |
| `paths.migrations` | empty → auto-detect | See `dev-workflow:db-migration` |
| `frontend.dev_command` | empty → no frontend declared | Fall back to the repo's frontend docs and `package.json` |
| `frontend.checks` | empty | Frontend test/lint/typecheck/build; fall back to the repo's scripts |
| `frontend.ui_language` | empty → `project.doc_language` | |
| `docs_map` | empty | Fall back to the doc-update duties in `AGENTS.md`/rules |
| `trace.require_test_types`, `trace.require_task_types` | `FR` | |
| `trace.waivers` | empty table | `"<ID>" = "<reason>"`; see `dev-workflow:trace-check` |
| `lanes.l0_max_files` | `2` | |
| `jira.project` | empty → Jira sync disabled | Ask; never pick a project key, epic or label by guess |
| `jira.estimate_factor` | `1.1` | 10% buffer |
| `jira.language` | `vi` | |
| `jira.description_sections` | the three sections in the example config | |
| `jira.guide` | empty | No project-specific Jira rules |

`"${CLAUDE_PLUGIN_ROOT}/scripts/dw" trace` needs a config file; without one it exits 2, so skip trace checks and say why.
