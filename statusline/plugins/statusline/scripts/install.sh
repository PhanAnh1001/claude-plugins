#!/bin/bash
# Set up (or remove) the statusline plugin as Claude Code's status line. Idempotent.
#
# Usage: install.sh [--dry-run] [--uninstall]
#   install:   1. back up <CLAUDE_HOME>/statusline-command.sh to .bak-<timestamp> if it exists and
#                 is not already the shim;
#              2. write the shim there (templates/statusline-shim.sh), which runs the installed
#                 plugin version's scripts/statusline.sh on every render;
#              3. point "statusLine" in <CLAUDE_HOME>/settings.json at the shim, keeping every other
#                 key; the file is written atomically and left untouched when already correct.
#   uninstall: restore the newest .bak-<timestamp> over the shim (statusLine then still points at
#              the restored script); without a backup, delete the shim and drop "statusLine" if it
#              points at the shim.
#   --dry-run: print what would change, write nothing.
# CLAUDE_HOME (default: $HOME/.claude) selects the Claude config dir; the tests use a temp dir.
# JSON is edited with jq when present, else with python3 (scripts/settings_json.py);
# STATUSLINE_JSON_BACKEND=python forces the python3 path.

set -u

PLUGIN_NAME="statusline"
MARKETPLACE_NAME="statusline-local"
PLUGIN_KEY="$PLUGIN_NAME@$MARKETPLACE_NAME"
SHIM_NAME="statusline-command.sh"
SETTINGS_NAME="settings.json"
SHIM_MARKER="statusline-plugin-shim"
BACKUP_INFIX=".bak-"
# 14 digits: sortable by name, distinct from hand-made backups such as ".bak-20261013".
BACKUP_TIMESTAMP_FORMAT="%Y%m%d%H%M%S"
BACKUP_TIMESTAMP_GLOB="[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]"
DEFAULT_CLAUDE_HOME="$HOME/.claude"
# Written into settings.json as-is when CLAUDE_HOME is the default, so the entry stays portable.
DEFAULT_STATUSLINE_COMMAND='bash "$HOME/.claude/statusline-command.sh"'
EMPTY_SETTINGS="{}"
# The shim is run with "bash <path>", but keep it executable for direct runs too.
SHIM_MODE="755"
PYTHON="python3"
JSON_BACKEND_ENV_PYTHON="python"
EXIT_OK=0
EXIT_ERROR=1
EXIT_USAGE=2

case "${BASH_SOURCE[0]}" in
  */*) SCRIPTS_DIR="${BASH_SOURCE[0]%/*}" ;;
  *) SCRIPTS_DIR="." ;;
esac
PLUGIN_ROOT="$SCRIPTS_DIR/.."
SHIM_TEMPLATE="$PLUGIN_ROOT/templates/statusline-shim.sh"
SETTINGS_HELPER="$SCRIPTS_DIR/settings_json.py"

CLAUDE_HOME="${CLAUDE_HOME:-$DEFAULT_CLAUDE_HOME}"
SHIM_PATH="$CLAUDE_HOME/$SHIM_NAME"
SETTINGS_PATH="$CLAUDE_HOME/$SETTINGS_NAME"
DRY_RUN=0
MODE="install"
CHANGES=0

say() { printf 'statusline: %s\n' "$*"; }
die() { printf 'statusline: error: %s\n' "$*" >&2; exit "$EXIT_ERROR"; }

# Run "$@" unless --dry-run; always report it as a change.
act() {
  local description=$1
  shift
  CHANGES=$((CHANGES + 1))
  if [ "$DRY_RUN" -eq 1 ]; then
    say "would $description"
    return 0
  fi
  "$@" || die "failed to $description"
  say "$description"
}

statusline_command() {
  if [ "$CLAUDE_HOME" = "$DEFAULT_CLAUDE_HOME" ]; then
    printf '%s' "$DEFAULT_STATUSLINE_COMMAND"
  else
    printf 'bash "%s"' "$SHIM_PATH"
  fi
}

use_jq() {
  [ "${STATUSLINE_JSON_BACKEND:-}" != "$JSON_BACKEND_ENV_PYTHON" ] && command -v jq >/dev/null 2>&1
}

# --- settings.json -------------------------------------------------------------------------

settings_document() {
  if [ -f "$SETTINGS_PATH" ]; then cat "$SETTINGS_PATH"; else printf '%s' "$EMPTY_SETTINGS"; fi
}

# json_edit get-command | set-command <cmd> | delete  (document on stdin)
json_edit() {
  local action=$1
  if use_jq; then
    case "$action" in
      get-command) jq -er 'if type == "object" then
          (if .statusLine.type? == "command" then .statusLine.command // "" else "" end)
          else error("settings JSON is not an object") end' ;;
      set-command) jq -e --arg cmd "$2" 'if type == "object" then
          .statusLine = ((.statusLine | objects) // {}) + {type: "command", command: $cmd}
          else error("settings JSON is not an object") end' ;;
      delete) jq -e 'if type == "object" then del(.statusLine)
          else error("settings JSON is not an object") end' ;;
    esac
  else
    command -v "$PYTHON" >/dev/null 2>&1 || die "need jq or $PYTHON to edit $SETTINGS_PATH"
    "$PYTHON" "$SETTINGS_HELPER" "$@"
  fi
}

current_command() {
  settings_document | json_edit get-command || die "$SETTINGS_PATH is not a valid JSON object"
}

file_mode() {
  stat -f '%Lp' "$1" 2>/dev/null || stat -c '%a' "$1" 2>/dev/null
}

real_path() {
  # Follow symlinks (a dotfiles-managed settings.json) so the link itself is not replaced.
  local path=$1 link
  while [ -L "$path" ]; do
    link=$(readlink "$path")
    case "$link" in
      /*) path="$link" ;;
      *) path="$(dirname "$path")/$link" ;;
    esac
  done
  printf '%s' "$path"
}

# write_settings <json_edit args...>: edit into a temp file next to the target, then rename.
write_settings() {
  local target tmp mode
  target=$(real_path "$SETTINGS_PATH")
  mkdir -p "$(dirname "$target")" || return 1
  tmp=$(mktemp "$(dirname "$target")/.$SETTINGS_NAME.XXXXXX") || return 1
  if ! settings_document | json_edit "$@" > "$tmp"; then
    rm -f "$tmp"
    return 1
  fi
  mode=$(file_mode "$target")
  [ -n "$mode" ] && chmod "$mode" "$tmp"
  mv -f "$tmp" "$target"
}

# --- shim and backups ----------------------------------------------------------------------

is_shim() {
  [ -f "$1" ] && grep -q "$SHIM_MARKER" "$1"
}

render_shim() {
  sed -e "s|@PLUGIN_NAME@|$PLUGIN_NAME|g" -e "s|@PLUGIN_KEY@|$PLUGIN_KEY|g" "$SHIM_TEMPLATE"
}

write_shim() {
  local tmp
  tmp=$(mktemp "$CLAUDE_HOME/.$SHIM_NAME.XXXXXX") || return 1
  render_shim > "$tmp" && chmod "$SHIM_MODE" "$tmp" && mv -f "$tmp" "$SHIM_PATH"
}

new_backup_path() {
  local path
  path="$SHIM_PATH$BACKUP_INFIX$(date "+$BACKUP_TIMESTAMP_FORMAT")"
  [ -e "$path" ] && path="$path-$$"
  printf '%s' "$path"
}

newest_backup() {
  local candidate newest=""
  for candidate in "$SHIM_PATH$BACKUP_INFIX"$BACKUP_TIMESTAMP_GLOB*; do
    [ -f "$candidate" ] && newest="$candidate"
  done
  printf '%s' "$newest"
}

# --- modes ---------------------------------------------------------------------------------

check_requirements() {
  [ -f "$SHIM_TEMPLATE" ] || die "missing $SHIM_TEMPLATE"
  command -v jq >/dev/null 2>&1 || say "warning: jq not found; the status line needs jq to render"
  local installed="$CLAUDE_HOME/plugins/installed_plugins.json"
  if [ ! -f "$installed" ] || ! grep -q "\"$PLUGIN_NAME@" "$installed"; then
    say "warning: $PLUGIN_NAME is not in $installed yet; the shim prints a hint until it is installed"
  fi
}

do_install() {
  check_requirements
  if [ ! -d "$CLAUDE_HOME" ]; then
    act "create $CLAUDE_HOME" mkdir -p "$CLAUDE_HOME"
  fi
  if [ -e "$SHIM_PATH" ] && ! is_shim "$SHIM_PATH"; then
    local backup
    backup=$(new_backup_path)
    act "back up $SHIM_PATH to $backup" cp "$SHIM_PATH" "$backup"
  fi
  if ! is_shim "$SHIM_PATH" || [ "$(render_shim)" != "$(cat "$SHIM_PATH")" ]; then
    act "write shim $SHIM_PATH" write_shim
  fi
  local wanted current
  wanted=$(statusline_command)
  current=$(current_command) || exit "$EXIT_ERROR"
  if [ "$current" != "$wanted" ]; then
    act "set statusLine in $SETTINGS_PATH to: $wanted" write_settings set-command "$wanted"
  fi
}

do_uninstall() {
  local backup
  backup=$(newest_backup)
  if [ -n "$backup" ] && { is_shim "$SHIM_PATH" || [ ! -e "$SHIM_PATH" ]; }; then
    act "restore $backup to $SHIM_PATH" mv -f "$backup" "$SHIM_PATH"
  elif is_shim "$SHIM_PATH"; then
    act "remove shim $SHIM_PATH (no backup found)" rm -f "$SHIM_PATH"
  else
    say "$SHIM_PATH is not the plugin shim; leaving it alone"
  fi
  local restored=0
  [ -n "$backup" ] && restored=1
  [ -e "$SHIM_PATH" ] && ! is_shim "$SHIM_PATH" && restored=1
  local current
  current=$(current_command) || exit "$EXIT_ERROR"
  if [ "$restored" -eq 0 ] && [ "$current" = "$(statusline_command)" ]; then
    act "remove statusLine from $SETTINGS_PATH" write_settings delete
  fi
}

usage() {
  # The header comment block (after the shebang) is the help text.
  awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"
}

parse_args() {
  local arg
  for arg in "$@"; do
    case "$arg" in
      --dry-run) DRY_RUN=1 ;;
      --uninstall) MODE="uninstall" ;;
      -h|--help) usage; exit "$EXIT_OK" ;;
      *) usage >&2; exit "$EXIT_USAGE" ;;
    esac
  done
}

main() {
  parse_args "$@"
  if [ "$MODE" = "uninstall" ]; then do_uninstall; else do_install; fi
  if [ "$CHANGES" -eq 0 ]; then
    say "nothing to do ($MODE is already in place)"
  elif [ "$DRY_RUN" -eq 1 ]; then
    say "dry run: $CHANGES change(s) planned, nothing written"
  fi
  exit "$EXIT_OK"
}

main "$@"
