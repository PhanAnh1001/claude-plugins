#!/bin/bash
# Claude Code status line (statusline plugin). Prints three lines, then optional skill lines:
#   1. user@host  current-dir (basename, ~ for $HOME)  (git-branch in green)
#      - mirrors the zsh PROMPT "%n@%m %1~%F{green}$(parse_git_branch)%f %# "
#   2. model name (+ reasoning effort) | cumulative session tokens | context-window used %
#   3. Claude.ai rate-limit usage (5-hour / 7-day) + reset times
#   4+. "🔧 <skill> (main)" for the main agent, then '🔧 <skill> (<agent>: "<description start>")'
#      per recent subagent, from "last-skill.sh --color" next to this script (the note in
#      parentheses is dimmed like "(high)" on line 2); none when no skill was loaded.
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

RESET="\033[0m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
MAGENTA="\033[35m"
DIM="\033[2m"
SEP=" ${DIM}|${RESET} "
PLACEHOLDER="--"
STALE_MARK="~"
# Usage % at or above which a value turns red / yellow.
PCT_RED_THRESHOLD=80
PCT_YELLOW_THRESHOLD=50
RESET_TIME_FORMAT="+%d/%m %H:%M"

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

# --- Line 3: rate limits ---
rate_limit_segment() {
  # Args: label live_pct live_reset cached_pct cached_reset. Live values win; cached ones get "~".
  local label=$1 pct=$2 reset=$3 mark=""
  if [ -z "$pct" ]; then
    pct=$4
    reset=$5
    mark="$STALE_MARK"
  fi
  if [ -z "$pct" ]; then
    printf '%s' "${DIM}${label}:${PLACEHOLDER}${RESET}"
    return 0
  fi
  local seg reset_fmt
  seg="${DIM}${label}:${mark}${RESET}$(col_for_pct "$pct")$(printf '%.0f' "$pct")%${RESET}"
  if [ -n "$reset" ]; then
    reset_fmt=$(fmt_reset "$reset")
    [ -n "$reset_fmt" ] && seg="${seg}${DIM}(reset ${reset_fmt})${RESET}"
  fi
  printf '%s' "$seg"
}

save_cache() {
  # Persist the newest values so the next render (even the first one after CLI startup) has a
  # fallback. jq yields nothing when any field is empty, and then the cache is left as it is.
  local new_cache
  new_cache=$(jq -n \
    --arg five "${five:-$cached_five}" \
    --arg five_reset "${five_reset:-$cached_five_reset}" \
    --arg week "${week:-$cached_week}" \
    --arg week_reset "${week_reset:-$cached_week_reset}" \
    '{five: ($five | select(. != "")), five_reset: ($five_reset | select(. != "")),
      week: ($week | select(. != "")), week_reset: ($week_reset | select(. != ""))}' 2>/dev/null)
  [ -n "$new_cache" ] && echo "$new_cache" > "$CACHE_FILE" 2>/dev/null
}

build_line3() {
  join_segments \
    "$(rate_limit_segment 5h "$five" "$five_reset" "$cached_five" "$cached_five_reset")" \
    "$(rate_limit_segment 7d "$week" "$week_reset" "$cached_week" "$cached_week_reset")"
}

line1=$(build_line1)
line2=$(build_line2)
line3=$(build_line3)
# --- Skill block (lines 4+) ---
build_skill_block() {
  # Lines from last-skill.sh: "🔧 <skill> (main)", '🔧 <skill> (<agent>: "<desc>")'; or nothing.
  [ -n "$transcript_path" ] && [ -f "$LAST_SKILL_SCRIPT" ] || return 0
  bash "$LAST_SKILL_SCRIPT" --color "$transcript_path" 2>/dev/null
}

save_cache
skill_block=$(build_skill_block)

out="$line1"
[ -n "$line2" ] && out="${out}\n${line2}"
[ -n "$line3" ] && out="${out}\n${line3}"
printf "%b" "$out"
# printf %s, not %b: skill names and subagent descriptions are data, so "\" must stay literal.
[ -n "$skill_block" ] && printf '\n%s' "$skill_block"
exit 0
