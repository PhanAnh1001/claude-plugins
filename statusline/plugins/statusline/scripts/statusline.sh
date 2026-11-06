#!/bin/bash
# Claude Code status line (statusline plugin). Prints three lines, then optional skill lines:
#   1. user@host  current-dir (basename, ~ for $HOME)  (git-branch in green)
#      - mirrors the zsh PROMPT "%n@%m %1~%F{green}$(parse_git_branch)%f %# "
#   2. model name (+ reasoning effort) | cumulative session tokens | context-window used %
#   3. an aligned limit table: row "Claude" (5h / 7d + reset times; 5h only from the live payload,
#      "5h:-" without it; 7d estimated to 0.1, "~4.3%", from week_split.py's summary when valid;
#      this machine's USD per 1% inside the 7d parentheses)
#   3b. rows "· máy này" and "· máy khác": 7-day usage split by machine (per weekday for this
#      one), from "week-split.sh --color"; none until its summary exists for this window
#   3c. row "Go": live OpenCode Go usage (5h / wk / mo) when its cache has usable numbers, else
#      the estimated DS cells from hand-ext
#   3d. one line per main-session group (session-lines.sh): Claude and Go % of the group
#   4+. "🔧 <skill> (main)" for the main agent, then '🔧 <skill> (<agent>: "<description start>")'
#      per recent subagent, from "last-skill.sh --color" next to this script (skill in Claude Code's
#      inline-code colour, note in parentheses dimmed like "(high)" on line 2); none when no skill.
#
# Reads the session JSON from stdin per the statusLine contract; cwd always comes from that JSON,
# never from the process's own $PWD. Requires jq. Paths under the Claude config dir use
# CLAUDE_HOME (default: $HOME/.claude), which the installed shim exports.
#
# NOTE: the documented statusLine payload only exposes rate_limits.five_hour and
# rate_limits.seven_day. If the CLI starts sending another weekly limit, add it as its own
# segment instead of overloading seven_day.

CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
# Last known rate-limit percentages/reset times, so line 3 shows real numbers on CLI startup
# (before the first API response, when rate_limits is absent). Cached values are marked "~".
CACHE_FILE="$CLAUDE_HOME/.statusline-cache.json"

case "${BASH_SOURCE[0]}" in
  */*) SCRIPTS_DIR="${BASH_SOURCE[0]%/*}" ;;
  *) SCRIPTS_DIR="." ;;
esac
LAST_SKILL_SCRIPT="$SCRIPTS_DIR/last-skill.sh"
GO_FETCH_SCRIPT="$SCRIPTS_DIR/go-usage-fetch.sh"
WEEK_SPLIT_SCRIPT="$SCRIPTS_DIR/week-split.sh"
SESSION_LINES_SCRIPT="$SCRIPTS_DIR/session-lines.sh"
# Summary of week_split.py: the 7-day estimate is used only when it is recent and matches the
# integer % and the reset shown.
WEEK_SPLIT_SUMMARY="$CLAUDE_HOME/.statusline-week-split.json"
WEEK_SPLIT_SUMMARY_VERSION=2
ESTIMATE_FRESH_SECONDS=1800
ESTIMATE_SAME_WINDOW_SECONDS=3600
# Shown when the live payload has no 5-hour data (cached 5h values are never shown).
FIVE_ABSENT="-"
# shellcheck source=go-segments.sh
. "$SCRIPTS_DIR/go-segments.sh"

RESET=$'\033[0m'
GREEN=$'\033[32m'
YELLOW=$'\033[33m'
RED=$'\033[31m'
MAGENTA=$'\033[35m'
DIM=$'\033[2m'
SEP=" ${DIM}|${RESET} "
PLACEHOLDER="--"
STALE_MARK="~"
# Usage % at or above which a value turns red / yellow.
PCT_RED_THRESHOLD=80
PCT_YELLOW_THRESHOLD=50
RESET_TIME_FORMAT="+%d/%m %H:%M"
# shellcheck source=table.sh
. "$SCRIPTS_DIR/table.sh"

input=$(cat)

json_field() {
  # Print one jq path from the stdin payload, or nothing.
  echo "$input" | jq -r "$1 // empty"
}

cache_field() {
  jq -r ".$1 // empty" "$CACHE_FILE" 2>/dev/null
}

[ -f "$CACHE_FILE" ] || echo '{}' > "$CACHE_FILE"
cached_five=$(cache_field five)
cached_five_reset=$(cache_field five_reset)
cached_week=$(cache_field week)
cached_week_reset=$(cache_field week_reset)

cwd=$(json_field '.workspace.current_dir // .cwd')
transcript_path=$(json_field '.transcript_path')
model_name=$(json_field '.model.display_name // .model.id')
effort_level=$(json_field '.effort.level')
context_pct=$(json_field '.context_window.used_percentage')
five=$(json_field '.rate_limits.five_hour.used_percentage')
five_reset=$(json_field '.rate_limits.five_hour.resets_at')
week=$(json_field '.rate_limits.seven_day.used_percentage')
week_reset=$(json_field '.rate_limits.seven_day.resets_at')
session_id=$(json_field '.session_id')
session_name=$(json_field '.session_name')

col_for_pct() {
  # Colour escape for a usage percentage (awk compares decimals; bash cannot).
  local level
  level=$(awk -v p="$1" -v red="$PCT_RED_THRESHOLD" -v yellow="$PCT_YELLOW_THRESHOLD" 'BEGIN {
    if (p >= red) print "red";
    else if (p >= yellow) print "yellow";
    else print "green";
  }')
  case "$level" in
    red) printf '%s' "$RED" ;;
    yellow) printf '%s' "$YELLOW" ;;
    *) printf '%s' "$GREEN" ;;
  esac
}

fmt_reset() {
  # Unix epoch seconds -> local "dd/mm HH:MM" (BSD date first, then GNU date).
  date -r "$1" "$RESET_TIME_FORMAT" 2>/dev/null || date -d "@$1" "$RESET_TIME_FORMAT" 2>/dev/null
}

fmt_tokens() {
  # Human-readable token count (e.g. 950, 12.3k, 1.2M).
  awk -v n="$1" 'BEGIN {
    if (n >= 1000000) printf "%.1fM", n/1000000;
    else if (n >= 1000) printf "%.1fk", n/1000;
    else printf "%d", n;
  }'
}

join_segments() {
  # Join the arguments with SEP.
  local joined="" seg
  for seg in "$@"; do
    if [ -z "$joined" ]; then joined="$seg"; else joined="${joined}${SEP}${seg}"; fi
  done
  printf '%s' "$joined"
}

# --- Line 1: user@host  dir  (git-branch) ---
build_line1() {
  local line dir_disp="" branch=""
  line="$(whoami)@$(hostname -s 2>/dev/null || hostname)"
  if [ -n "$cwd" ]; then
    if [ "$cwd" = "$HOME" ]; then dir_disp="~"; else dir_disp=$(basename "$cwd"); fi
  fi
  if [ -n "$cwd" ] && git --no-optional-locks -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    branch=$(git --no-optional-locks -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
  fi
  [ -n "$dir_disp" ] && line="$line $dir_disp"
  [ -n "$branch" ] && line="$line (${GREEN}${branch}${RESET})"
  printf '%s' "$line"
}

# --- Line 2 segments ---
model_segment() {
  [ -n "$model_name" ] || return 0
  local seg="${MAGENTA}${model_name}${RESET}"
  [ -n "$effort_level" ] && seg="${seg}${DIM}(${effort_level})${RESET}"
  printf '%s' "$seg"
}

tokens_segment() {
  # Cumulative tokens of every API usage record in the transcript: only ever grows, and is NOT
  # reduced by context compaction (unlike context_window.*).
  local total_tok=""
  if [ -n "$transcript_path" ] && [ -f "$transcript_path" ]; then
    total_tok=$(jq -s '
      [ .[]
        | select(.type == "assistant")
        | .message.usage? // empty
        | ((.input_tokens // 0) + (.output_tokens // 0)
           + (.cache_creation_input_tokens // 0) + (.cache_read_input_tokens // 0))
      ] | add // 0
    ' "$transcript_path" 2>/dev/null)
  fi
  if [ -n "$total_tok" ] && [ "$total_tok" != "0" ]; then
    printf '%s' "${MAGENTA}tokens:${RESET}$(fmt_tokens "$total_tok")"
  else
    printf '%s' "${MAGENTA}tokens:${RESET}${DIM}${PLACEHOLDER}${RESET}"
  fi
}

context_segment() {
  if [ -n "$context_pct" ]; then
    printf '%s' "${DIM}ctx:${RESET}$(col_for_pct "$context_pct")$(printf '%.0f' "$context_pct")%${RESET}"
  else
    printf '%s' "${DIM}ctx:${PLACEHOLDER}${RESET}"
  fi
}

build_line2() {
  local segments=() seg
  seg=$(model_segment); [ -n "$seg" ] && segments+=("$seg")
  segments+=("$(tokens_segment)")
  segments+=("$(context_segment)")
  join_segments "${segments[@]}"
}

# --- Line 3: Claude rate limits ---
rate_limit_segment() {
  # Args: label live_pct live_reset cached_pct cached_reset [color] [mark] [estimate] [extra].
  # Live values win; cached ones get "~". Callers may force a colour (rate-limited Go windows)
  # and a stale mark (Go windows with an expired reset) without changing the Claude behaviour.
  # An estimate is printed with one decimal and "~"; the colour still follows the integer %.
  # "extra" goes inside the parentheses after the reset ("reset X · extra") or alone there.
  local label=$1 pct=$2 reset=$3 mark="" color="${6:-}" shown="${8:-}" extra="${9:-}" text
  if [ -z "$pct" ]; then
    pct=$4
    reset=$5
    mark="$STALE_MARK"
  fi
  [ -n "${7:-}" ] && mark="${7:-}"
  [ -n "$shown" ] && mark="$STALE_MARK"
  if [ -z "$pct" ]; then
    printf '%s' "${DIM}${label}:${PLACEHOLDER}${RESET}"
    return 0
  fi
  local seg reset_fmt
  [ -z "$color" ] && color=$(col_for_pct "$pct")
  if [ -n "$shown" ]; then text=$(printf '%.1f' "$shown"); else text=$(printf '%.0f' "$pct"); fi
  seg="${DIM}${label}:${mark}${RESET}${color}${text}%${RESET}"
  reset_fmt=""
  [ -n "$reset" ] && reset_fmt=$(fmt_reset "$reset")
  if [ -n "$reset_fmt" ] && [ -n "$extra" ]; then
    seg="${seg}${DIM} (reset ${reset_fmt} · ${extra})${RESET}"
  elif [ -n "$reset_fmt" ]; then
    seg="${seg}${DIM} (reset ${reset_fmt})${RESET}"
  elif [ -n "$extra" ]; then
    seg="${seg}${DIM} (${extra})${RESET}"
  fi
  printf '%s' "$seg"
}

save_cache() {
  # Persist the newest values so the next render (even the first one after CLI startup) has a
  # fallback. Empty fields are dropped (5h data may be absent), so the 7d values still persist.
  local new_cache
  new_cache=$(jq -n \
    --arg five "${five:-$cached_five}" \
    --arg five_reset "${five_reset:-$cached_five_reset}" \
    --arg week "${week:-$cached_week}" \
    --arg week_reset "${week_reset:-$cached_week_reset}" \
    '{five: $five, five_reset: $five_reset, week: $week, week_reset: $week_reset}
      | with_entries(select(.value != ""))' 2>/dev/null)
  [ -n "$new_cache" ] && [ "$new_cache" != "{}" ] && echo "$new_cache" > "$CACHE_FILE" 2>/dev/null
}

load_week_estimate() {
  # One jq read of the week-split summary: version, computed_at and the 7-day estimate.
  [ -f "$WEEK_SPLIT_SUMMARY" ] || return 0
  local row
  row=$(jq -r '[((.version | numbers) // ""), ((.computed_at | numbers) // ""),
      ((.claude_estimates.week.pct | numbers) // ""), ((.claude_estimates.week.base | numbers) // ""),
      ((.claude_estimates.week.reset | numbers) // "")] | map(tostring) | join("\u001f")
    ' "$WEEK_SPLIT_SUMMARY" 2>/dev/null) || return 0
  IFS=$'\x1f' read -r ws_version ws_computed est_week est_week_base est_week_reset <<< "$row"
}

week_estimate() {
  # Args: shown_pct shown_reset. Prints the estimate when it describes exactly what is shown.
  local shown=$1 reset=$2 now
  [ "${ws_version:-}" = "$WEEK_SPLIT_SUMMARY_VERSION" ] && [ -n "${est_week:-}" ] || return 0
  [[ "$ws_computed" =~ ^[0-9]+$ ]] && [ -n "$shown" ] && [ -n "$reset" ] || return 0
  now=$(date +%s)
  [ $((now - ws_computed)) -le "$ESTIMATE_FRESH_SECONDS" ] || return 0
  awk -v s="$shown" -v r="$reset" -v e="$est_week" -v b="$est_week_base" -v er="$est_week_reset" \
    -v gap="$ESTIMATE_SAME_WINDOW_SECONDS" 'BEGIN {
      d = r - er; if (d < 0) d = -d;
      if (int(b) == int(s) && d <= gap) print e;
    }'
}

build_claude_row() {
  # Args: usd per 1% text (inside the 7d parentheses). Prints the 5h cell, 0x1f, the 7d cell.
  local usd=$1 est five_cell week_cell
  if [ -n "$five" ]; then
    five_cell=$(rate_limit_segment 5h "$five" "$five_reset" "" "")
  else
    five_cell="${DIM}5h:${FIVE_ABSENT}${RESET}"
  fi
  est=$(week_estimate "${week:-$cached_week}" "${week_reset:-$cached_week_reset}")
  week_cell=$(rate_limit_segment 7d "$week" "$week_reset" "$cached_week" "$cached_week_reset" \
    "" "" "$est" "$usd")
  printf '%s%s%s' "$five_cell" "$TABLE_US" "$week_cell"
}

build_limit_table() {
  # Args: claude_cells local_cell other_cell go_cells. Builds the aligned rows and prints them;
  # labels never start with a space because Claude Code trims leading whitespace of each line.
  local claude_cells=$1 local_cell=$2 other_cell=$3 go_cells=$4 rows=""
  rows="Claude${TABLE_US}${claude_cells}"
  [ -n "$local_cell" ] && rows="${rows}"$'\n'"${DIM}· máy này${RESET}${TABLE_US}${TABLE_US}${local_cell}"
  [ -n "$other_cell" ] && rows="${rows}"$'\n'"${DIM}· máy khác${RESET}${TABLE_US}${TABLE_US}${other_cell}"
  [ -n "$go_cells" ] && rows="${rows}"$'\n'"${DIM}Go${RESET}${TABLE_US}${go_cells}"
  printf '%s\n' "$rows" | table_print
}


line1=$(build_line1)
line2=$(build_line2)
load_go_summary
load_go_live_cache
load_week_estimate
week_split_row=""
[ -f "$WEEK_SPLIT_SCRIPT" ] && week_split_row=$(bash "$WEEK_SPLIT_SCRIPT" --color \
  "$week" "$week_reset" "$cached_week_reset" 2>/dev/null)
local_cell=""; other_cell=""; usd_text=""
IFS=$TABLE_US read -r local_cell other_cell usd_text <<< "$week_split_row"
claude_row=$(build_claude_row "$usd_text")
go_row=$(build_go_row)
limit_table=$(build_limit_table "$claude_row" "$local_cell" "$other_cell" "$go_row")
line_sessions=""
[ -f "$SESSION_LINES_SCRIPT" ] && line_sessions=$(bash "$SESSION_LINES_SCRIPT" --color \
  "$session_id" 2>/dev/null)
maybe_start_go_live_fetch
# --- Skill block (after the rate-limit lines) ---
build_skill_block() {
  # Lines from last-skill.sh: "🔧 <skill> (main)", '🔧 <skill> (<agent>: "<desc>")'; or nothing.
  [ -n "$transcript_path" ] && [ -f "$LAST_SKILL_SCRIPT" ] || return 0
  bash "$LAST_SKILL_SCRIPT" --color "$transcript_path" 2>/dev/null
}

save_cache
skill_block=$(build_skill_block)

out="$line1"
[ -n "$line2" ] && out="${out}\n${line2}"
printf "%b" "$out"
[ -n "$limit_table" ] && printf '\n%s' "$limit_table"
# printf %s, not %b: session names and aliases are data.
[ -n "$line_sessions" ] && printf '\n%s' "$line_sessions"
# printf %s, not %b: skill names and subagent descriptions are data, so "\" must stay literal.
[ -n "$skill_block" ] && printf '\n%s' "$skill_block"
exit 0
