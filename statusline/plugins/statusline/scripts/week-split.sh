#!/bin/bash
# Week-split cells of the statusline plugin, consumed by statusline.sh's limit table:
#   "<this machine cell>\x1f<other machines cell>\x1f<usd per 1%>"
#   e.g. "7d:12.2% (T6 2.1% · T7 5.4%)", "7d:2.8%", "$13.74/1%" (the USD moves inside the
#   Claude 7d parentheses; the labels "máy này"/"máy khác" are the table's first column).
# Usage: week-split.sh [--color] <week_pct> <week_reset> <cached_week_reset>
#   (values may be empty; extra arguments are ignored; per-session lines are session-lines.sh)
#   1. records one (epoch, pct, reset) sample per render when the live payload has both values;
#   2. starts week_split.py detached when its summary is missing or old (it scans transcripts);
#   3. prints the cells from the summary when it belongs to the current 7-day window, else nothing.
# Fail-open: always exits 0. STATUSLINE_WEEK_SPLIT=0 disables everything,
# STATUSLINE_WEEK_SPLIT_SPAWN=0 only the background run.

CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SAMPLES_FILE="$CLAUDE_HOME/.statusline-week-samples.tsv"
SUMMARY_FILE="$CLAUDE_HOME/.statusline-week-split.json"
LOCK_DIR="$CLAUDE_HOME/.statusline-week-split.lock"
# A repeated sample (same pct and reset) is still recorded after this long, to mark idle time.
SAMPLE_REPEAT_SECONDS=300
SUMMARY_REFRESH_SECONDS=120
LOCK_STALE_SECONDS=300
# Summary older than this gets the "~" mark.
SUMMARY_STALE_SECONDS=1800
# The summary must describe the current window: its reset within this distance of ours.
SAME_WINDOW_SECONDS=3600
SUMMARY_VERSION=2
RATE_CALIBRATED="calib"
PCT_RED_THRESHOLD=80
PCT_YELLOW_THRESHOLD=50
STALE_MARK="~"

case "${BASH_SOURCE[0]}" in
  */*) SCRIPTS_DIR="${BASH_SOURCE[0]%/*}" ;;
  *) SCRIPTS_DIR="." ;;
esac
PY_SCRIPT="$SCRIPTS_DIR/week_split.py"

[ "${STATUSLINE_WEEK_SPLIT:-1}" != "0" ] || exit 0

color=0
if [ "${1:-}" = "--color" ]; then color=1; shift; fi
week_live=${1:-}
reset_live=${2:-}
reset_cached=${3:-}

if [ "$color" = "1" ]; then
  RESET=$'\033[0m'
  DIM=$'\033[2m'
  GREEN=$'\033[32m'
  YELLOW=$'\033[33m'
  RED=$'\033[31m'
else
  RESET=""; DIM=""; GREEN=""; YELLOW=""; RED=""
fi
CELL_SEP=$'\x1f'
now=$(date +%s)

is_int() { [[ "$1" =~ ^[0-9]+$ ]]; }

record_sample() {
  # Append "epoch<TAB>pct<TAB>reset" unless the last line has the same values and is recent.
  [ -n "$week_live" ] && [ -n "$reset_live" ] || return 0
  local last last_t last_pct last_reset
  if [ -f "$SAMPLES_FILE" ]; then
    last=$(tail -n 1 "$SAMPLES_FILE" 2>/dev/null)
    IFS=$'\t' read -r last_t last_pct last_reset <<< "$last"
    if [ "$last_pct" = "$week_live" ] && [ "$last_reset" = "$reset_live" ] && is_int "$last_t" \
        && [ $((now - last_t)) -le "$SAMPLE_REPEAT_SECONDS" ]; then
      return 0
    fi
  fi
  printf '%s\t%s\t%s\n' "$now" "$week_live" "$reset_live" >> "$SAMPLES_FILE" 2>/dev/null
}

lock_is_fresh() {
  local mtime
  [ -d "$LOCK_DIR" ] || return 1
  mtime=$(stat -c '%Y' "$LOCK_DIR" 2>/dev/null || stat -f '%m' "$LOCK_DIR" 2>/dev/null) || return 1
  [ $((now - mtime)) -lt "$LOCK_STALE_SECONDS" ]
}

maybe_spawn() {
  # Arg: computed_at of the summary (may be empty). Never waits for the scan.
  [ "${STATUSLINE_WEEK_SPLIT_SPAWN:-1}" != "0" ] || return 0
  if is_int "$1" && [ $((now - $1)) -lt "$SUMMARY_REFRESH_SECONDS" ]; then return 0; fi
  [ -f "$PY_SCRIPT" ] || return 0
  lock_is_fresh && return 0
  CLAUDE_HOME="$CLAUDE_HOME" nohup python3 "$PY_SCRIPT" </dev/null >/dev/null 2>&1 &
  disown 2>/dev/null || true
}

col_for_pct() {
  [ "$color" = "1" ] || return 0
  local level
  level=$(awk -v p="$1" -v red="$PCT_RED_THRESHOLD" -v yellow="$PCT_YELLOW_THRESHOLD" 'BEGIN {
    if (p >= red) print "red"; else if (p >= yellow) print "yellow"; else print "green";
  }')
  case "$level" in
    red) printf '%s' "$RED" ;;
    yellow) printf '%s' "$YELLOW" ;;
    *) printf '%s' "$GREEN" ;;
  esac
}

pct_text() { printf '%s%.1f%%%s' "$(col_for_pct "$1")" "$1" "$RESET"; }

days_text() {
  # Arg: "T6=2.1;T7=5;..." -> "T6 2% · T7 5% · ..."
  local joined="" item wd pct
  local IFS=';'
  for item in $1; do
    wd=${item%%=*}; pct=${item#*=}
    [ -n "$wd" ] || continue
    item=$(printf '%s %.1f%%' "$wd" "$pct")
    if [ -z "$joined" ]; then joined=$item; else joined="$joined · $item"; fi
  done
  printf '%s' "$joined"
}

record_sample

row=""
[ -f "$SUMMARY_FILE" ] && row=$(jq -r '
  [ ((.version | numbers) // ""), ((.computed_at | numbers) // ""), ((.reset | numbers) // ""),
      (.rate_label // ""), ((.local | numbers) // ""), ((.other | numbers) // ""),
      ((.usd_per_pct | numbers) // ""),
      ([(.days // [])[] | "\(.wd)=\(.pct)"] | join(";")) ]
  | map(tostring) | join("\u001f")
' "$SUMMARY_FILE" 2>/dev/null)
IFS=$'\x1f' read -r version computed_at summary_reset rate_label local_pct other_pct usd_per_pct \
  days <<< "$row"

maybe_spawn "$computed_at"

[ "$version" = "$SUMMARY_VERSION" ] || exit 0
current_reset=${reset_live:-$reset_cached}
current_reset=${current_reset%%.*}
is_int "$current_reset" && is_int "$summary_reset" || exit 0
[ -n "$local_pct" ] && [ -n "$other_pct" ] && [ -n "$usd_per_pct" ] || exit 0
distance=$((current_reset - summary_reset))
[ "${distance#-}" -le "$SAME_WINDOW_SECONDS" ] || exit 0

mark=""
if [ "$rate_label" != "$RATE_CALIBRATED" ] || ! is_int "$computed_at" \
    || [ $((now - computed_at)) -ge "$SUMMARY_STALE_SECONDS" ]; then
  mark="$STALE_MARK"
fi
local_cell="${DIM}7d:${mark}${RESET}$(pct_text "$local_pct")"
day_part=$(days_text "$days")
[ -n "$day_part" ] && local_cell="$local_cell ${DIM}(${day_part})${RESET}"
other_cell="${DIM}7d:${mark}${RESET}$(pct_text "$other_pct")"
usd_text="${mark}$(printf '$%.2f/1%%' "$usd_per_pct")"
printf '%s%s%s%s%s\n' "$local_cell" "$CELL_SEP" "$other_cell" "$CELL_SEP" "$usd_text"
exit 0
