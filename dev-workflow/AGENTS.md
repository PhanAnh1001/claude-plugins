# AGENTS.md

## Summary

- **Purpose:** this folder (`dev-workflow/` in the `claude-plugins` repo) is a self-hosted Claude Code marketplace,
  `dev-workflow-local`, that ships one plugin, `dev-workflow`: an AI-assisted SDLC workflow (lane triage L0-L3,
  spec/plan/ADR, bug and CR reports, traceability, closeout). Paths below are relative to this folder.
- **Test command** (from the `claude-plugins` repo root): `python3.11 -m unittest discover -s dev-workflow/tests`
  (any Python >= 3.11, stdlib only).
- **Must do on every change:** keep files <= 400 lines, bump `version` in
  `plugins/dev-workflow/.claude-plugin/plugin.json` when anything under `plugins/` changes, run the tests.

## Layout

```text
.claude-plugin/marketplace.json           # marketplace "dev-workflow-local" -> ./plugins/dev-workflow
plugins/dev-workflow/
  .claude-plugin/plugin.json              # plugin manifest (name, version, description)
  skills/<name>/SKILL.md                  # workflow skills
  templates/                              # design, plan, traceability, cr, bug, adr, example config
  scripts/
    dw                                    # entry point: dw config | trace | template | python
    _pick_python.sh                       # picks Python >= 3.11 (or uv), sourced by dw and the hook
    dw_config.py                          # merged .claude/dev-workflow.toml
    dw_template.py                        # which template file to use (repo override or plugin)
    trace_check.py                        # traceability CLI; trace_scan.py, trace_report.py, trace_render.py
    session-start.sh                      # SessionStart hook
    skill-notice.sh, skill_notice.py      # PreToolUse(Skill) hook: systemMessage "Skill: <name>"
  hooks/hooks.json                        # SessionStart + PreToolUse(Skill) hooks
tests/                                    # unittest suite for scripts and hook
docs/                                     # proposal, workflow, plans (Vietnamese)
```

## Rules

### Language

- Skills, scripts, hook output and config comments are written for agents: **English**.
  Skill descriptions may add the Vietnamese phrases users actually type.
- Documents that skills generate for people (templates, specs, plans, reports): **Vietnamese with diacritics**.

### Documents

- Every document opens with a summary (`## Summary` / `## Tóm tắt`): overview, key decisions, key numbers,
  and what the reader must do, before any detail.
- Present top-down: major groups first, then the branches inside each group. Detailed sections follow
  the same group -> branch order as the summary.

### Code and files

- Every file <= 400 lines; split into modules by responsibility when larger.
- No magic numbers or strings: name constants in one place.
- Scripts use only the Python standard library (3.11+, `tomllib`). Skills call them through
  `"${CLAUDE_PLUGIN_ROOT}/scripts/dw" config|trace|template|python`, never `python3 ...` directly
  (system `python3` may be older than 3.11).
- Never reference absolute paths of a developer machine (home directories, temp directories) in committed
  files: code, config, docs, rules. Use paths relative to the repo or `${CLAUDE_PLUGIN_ROOT}`.
- Never put secrets in the repo.
- No `cd` inside compound shell commands; use absolute paths or `make -C`/`git -C` style flags.

### Releases

- Any change under `plugins/dev-workflow/` bumps `version` in its `plugin.json` (semver).
- Validate before release (from the `claude-plugins` repo root): `claude plugin validate dev-workflow` and
  `claude plugin validate dev-workflow/plugins/dev-workflow`.
