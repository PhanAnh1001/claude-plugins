---
name: setup
description: Set up, check or remove the statusline plugin as Claude Code's status line - runs the plugin's install.sh, which backs up the current status-line script, writes a stable shim in the Claude config dir that always runs the installed plugin version, and points "statusLine" in settings.json at it (every other key kept). Dry-run first, then the real run, then verify. Use after installing or moving to a new machine, when the status line shows "statusline plugin not found", or to uninstall it. Vietnamese triggers - "cài statusline", "thanh trạng thái", "status line", "cài thanh trạng thái", "gỡ statusline", "statusline không hiện".
---

# statusline:setup

## Summary

- **Purpose:** make the statusline plugin Claude Code's status line on this machine, idempotently.
- **Order:** dry-run, show the plan to the user, real run, verify. Uninstall uses the same order.
- **Never** edit settings.json or the shim by hand; only `install.sh` touches them.

## Steps

1. Dry-run and show the output to the user:

   ```sh
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/install.sh" --dry-run
   ```

   It prints `would back up ...`, `would write shim ...`, `would set statusLine ...`, or
   `nothing to do`. A warning that `jq` is missing means the status line will not render until
   the user installs `jq`; say so.

2. Run it for real (skip when the dry-run said `nothing to do`):

   ```sh
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/install.sh"
   ```

3. Verify:

   ```sh
   jq .statusLine "${CLAUDE_HOME:-$HOME/.claude}/settings.json"
   echo '{"model":{"display_name":"test"},"cwd":"/"}' | bash "${CLAUDE_HOME:-$HOME/.claude}/statusline-command.sh"
   ```

   The first shows `bash "$HOME/.claude/statusline-command.sh"`; the second prints three or more lines.
   When the hand-ext Codex ledger
   `${HYBRID_HANDS_STATE_DIR:-$HOME/.hybrid-hands}/codex_usage.jsonl` has a schema-1 `.codex-hand`
   sample ended within 24 hours, a `GPT` row ends the limit table with the newest 5h/7d percentages and
   today's estimated USD (`hôm nay ~$...`); otherwise there is no GPT row.
   If it prints `statusline plugin not found`, the plugin is not in `installed_plugins.json`:
   install it with `claude plugin install statusline@statusline-local`.

4. Tell the user the backup file name (if one was made) and that the status line refreshes on the
   next render; plugin updates need no new setup because the shim follows the installed version.

## Uninstall

Same order with `--uninstall`: `--uninstall --dry-run`, then `--uninstall`. It restores the newest
`statusline-command.sh.bak-<timestamp>`; without a backup it removes the shim and drops
`statusLine` when it points at the shim.

## Notes

- `CLAUDE_HOME` overrides the config dir (default `$HOME/.claude`); only set it when the user
  runs Claude Code with a non-default config dir.
- The `GPT` row is read-only: `scripts/gpt_usage.py` reads Codex rollouts in `~/.codex` and `~/.codex-hand` and never
  writes it, calls the network or needs a setup step. Missing, broken or older-than-24h data hides
  the row; an expired reset hides only that percentage.
- Requirements: `jq` (rendering), `python3` >= 3.9 (skill
  segment; JSON fallback when `jq` is missing during setup).
