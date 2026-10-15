#!/bin/bash
# statusline-plugin-shim - written by the statusline Claude Code plugin (scripts/install.sh).
# Do not edit: the next setup run overwrites it; "install.sh --uninstall" restores the backup.
# Runs scripts/statusline.sh of the statusline plugin version currently installed, found through
# plugins/installed_plugins.json next to this file, so plugin updates need no new setup.
# Fail-open: when the plugin cannot be found it prints one hint line and exits 0.

PLUGIN_NAME="@PLUGIN_NAME@"
PLUGIN_KEY="@PLUGIN_KEY@"
STATUSLINE_SCRIPT="scripts/statusline.sh"
NOT_FOUND_LINE="statusline plugin not found - install it, then run the statusline:setup skill"

case "${BASH_SOURCE[0]}" in
  */*) shim_dir="${BASH_SOURCE[0]%/*}" ;;
  *) shim_dir="." ;;
esac
installed="$shim_dir/plugins/installed_plugins.json"

install_path() {
  # installPath of PLUGIN_KEY, else of the first "<PLUGIN_NAME>@..." entry (other marketplace name).
  [ -f "$installed" ] || return 0
  if command -v jq >/dev/null 2>&1; then
    jq -r --arg key "$PLUGIN_KEY" --arg prefix "$PLUGIN_NAME@" '
      .plugins[$key][0].installPath
      // ([.plugins | to_entries[] | select(.key | startswith($prefix)) | .value[0].installPath]
          | map(select(. != null)) | first)
      // empty' "$installed" 2>/dev/null
  elif command -v python3 >/dev/null 2>&1; then
    python3 -c '
import json, sys
plugins = json.load(open(sys.argv[1])).get("plugins", {})
keys = [sys.argv[2]] + [k for k in plugins if k.startswith(sys.argv[3] + "@")]
paths = [(plugins.get(k) or [{}])[0].get("installPath") for k in keys]
print(next((p for p in paths if p), ""), end="")
' "$installed" "$PLUGIN_KEY" "$PLUGIN_NAME" 2>/dev/null
  fi
}

plugin_root=$(install_path)
if [ -z "$plugin_root" ] || [ ! -f "$plugin_root/$STATUSLINE_SCRIPT" ]; then
  printf '%s' "$NOT_FOUND_LINE"
  exit 0
fi
export CLAUDE_HOME="$shim_dir"
exec bash "$plugin_root/$STATUSLINE_SCRIPT"
