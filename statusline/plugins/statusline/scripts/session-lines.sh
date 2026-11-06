#!/bin/bash
# Session-group lines of the statusline plugin, one per main session (root of the side-session tree):
#   "▶ <name>  <alias>  Claude ~X.X% | Go ~Y.Y%" ("· " instead of "▶ " on other lines)
#   Name, alias and numbers are padded to the widest value of the printed lines so the columns
#   line up; the alias column is dropped when no line has one. Cuts end with "…".
#   <name> is the root's name in Claude Code's session registry when the root is live, else the
#   summary's custom title or agent name, else the first 8 chars of the session id, so two
#   sessions with the same auto title (alias) stay distinguishable.
# Usage: session-lines.sh [--color] <session_id>
#   Reads the "groups" of week_split.py's summary in one jq call. The group holding session_id
#   comes first with "▶ "; the others follow by Claude % descending, at most MAX_GROUPS lines.
#   "Go -" when the Go week is unknown.
#   Session registry ($CLAUDE_HOME/sessions/<pid>.json, read in one jq call, liveness by kill -0):
#   when the directory exists only groups with a live member are shown (0.0% included); without
#   it groups at 0.0% on both sides are hidden. Several files with one sessionId: the "user" name
#   wins, then the newest updatedAt. An unreadable registry counts as empty.
# Fail-open: always exits 0; prints nothing without a usable summary. STATUSLINE_WEEK_SPLIT=0
# disables it together with the week-split line.

CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SUMMARY_FILE="$CLAUDE_HOME/.statusline-week-split.json"
REGISTRY_DIR="$CLAUDE_HOME/sessions"
NAME_SOURCE_USER="user"
# ASCII record separator between registry files; cannot occur inside valid JSON text.
RECORD_SEP=$'\x1e'
SUMMARY_VERSION=2
RATE_CALIBRATED="calib"
RATE_PINNED="pin"  # user-pinned USD per 1 %: trusted like a calibrated rate
# Summary older than this gets the "~" mark (same rule as the week-split line).
SUMMARY_STALE_SECONDS=1800
MAX_GROUPS=5
# Kept short so the block fits beside the other columns on a narrow terminal.
NAME_MAX_CHARS=16
ALIAS_MAX_CHARS=16
SESSION_ID_SHORT_CHARS=8
PCT_RED_THRESHOLD=80
PCT_YELLOW_THRESHOLD=50
STALE_MARK="~"
# No line may start with whitespace: Claude Code trims leading spaces of status-line lines, so a
# "  " prefix vanished and the other lines sat 2 columns left of the "▶ " line. "▶" (U+25B6) is
# East Asian Ambiguous width and has an emoji presentation, so it is followed by U+FE0E (text
# presentation selector) and the other lines use "·" (U+00B7), also Ambiguous width, so both
# prefixes take the same number of columns whatever width the terminal gives Ambiguous chars.
# Literal UTF-8 because bash 3.2 (macOS) has no \u escapes in $'...'.
CURRENT_PREFIX="▶︎ "
OTHER_PREFIX="· "
COL_GAP="  "
ELLIPSIS="…"
ABSENT="-"

[ "${STATUSLINE_WEEK_SPLIT:-1}" != "0" ] || exit 0

color=0
if [ "${1:-}" = "--color" ]; then color=1; shift; fi
session_id=${1:-}

if [ "$color" = "1" ]; then
  RESET=$'\033[0m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'
else
  RESET=""; DIM=""; GREEN=""; YELLOW=""; RED=""
fi
SEP=" ${DIM}|${RESET} "
now=$(date +%s)

[ -f "$SUMMARY_FILE" ] || exit 0

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

# pct_text <formatted number>: coloured "<n>%".
pct_text() { printf '%s%s%%%s' "$(col_for_pct "$1")" "$1" "$RESET"; }

# Live registry entries as a JSON array of {sid, name, user, ts}; registry_on=false keeps the old
# behaviour (no liveness filter) when the registry directory is absent.
registry_on=false
live="[]"
if [ -d "$REGISTRY_DIR" ]; then
  registry_on=true
  entries=()
  # Files joined with a record separator and parsed one by one (fromjson?), so one corrupt file
  # does not drop the others.
  while IFS=$'\t' read -r pid entry; do
    [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" 2>/dev/null && entries+=("$entry")
  done < <(shopt -s nullglob
    for file in "$REGISTRY_DIR"/*.json; do printf '%s%s' "$(<"$file")" "$RECORD_SEP"; done \
      | jq -Rsr --arg user "$NAME_SOURCE_USER" --arg rs "$RECORD_SEP" '
      split($rs)[] | (fromjson? // null) | objects
      | select((.pid | type) == "number" and (.sessionId | type) == "string")
      | [(.pid | tostring),
         ({sid: .sessionId, name: ((.name | strings) // ""), user: (.nameSource == $user),
           ts: ((.updatedAt | numbers) // 0)} | tojson)]
      | join("\t")' 2>/dev/null)
  if [ ${#entries[@]} -gt 0 ]; then
    live="[$(IFS=,; printf '%s' "${entries[*]}")]"
  fi
fi

# First row: version, computed_at, rate_label, alias column width (0 = no alias column). Then one
# row per group to print: current flag, name and alias already padded to their column width,
# claude %, go % (empty when unknown). Padding is done in jq because jq counts codepoints while
# bash 3.2 printf counts bytes; strings are assumed NFC (one codepoint per column).
rows=$(jq -r --arg sid "$session_id" --argjson max "$MAX_GROUPS" \
  --argjson nmax "$NAME_MAX_CHARS" --argjson amax "$ALIAS_MAX_CHARS" \
  --argjson short "$SESSION_ID_SHORT_CHARS" --arg ellipsis "$ELLIPSIS" \
  --argjson registry "$registry_on" --argjson live "$live" '
  def clean: tostring | gsub("[[:cntrl:]]"; " ") | gsub("\\s+"; " ") | sub("^ "; "") | sub(" $"; "");
  def cut($n): if length > $n then .[0:($n - 1)] + $ellipsis else . end;
  def pad($w): . + ([range(0; $w - length)] | map(" ") | join(""));
  def shown: ((. // 0) * 10 | round) > 0;
  ($live | group_by(.sid) | map(max_by([.user, .ts])) | map({key: .sid, value: .name})
   | from_entries) as $names
  | def alive: ([.root] + (.members // [])) | any(. as $m | $names | has($m | tostring));
  def visible: if $registry then alive else (.claude_pct | shown) or (.go_pct | shown) end;
  (.go_week != null) as $gw
  | ([(.groups // [])[] | select(type == "object")]) as $groups
  | (if $sid == "" then null
     else ([$groups[] | select((.members // []) | any(. == $sid))] | .[0]
           // {root: $sid, members: [$sid], claude_pct: 0,
               go_pct: (if $gw then 0 else null end)}) end) as $cur
  | ([$groups[] | select(.root != ($cur.root // null))
      | select(visible)]
     | sort_by(-(.claude_pct // 0))) as $others
  | [([$cur // empty] + $others)[0:$max][]
     | (($names[.root | tostring] // "") | clean) as $live_name
     | (if $live_name != "" then $live_name else ((.name // "") | clean) end) as $n0
     | ((.alias // "") | clean) as $a0
     | {cur: (if $cur != null and .root == $cur.root then "1" else "" end),
        name: (if $n0 == "" then (.root | tostring)[0:$short] else ($n0 | cut($nmax)) end),
        alias: (if $a0 == $n0 then "" else ($a0 | cut($amax)) end),
        claude: ((.claude_pct | numbers) // 0), go: ((.go_pct | numbers) // "")}] as $rows
  | ([$rows[].name | length] | max // 0) as $nw
  | ([$rows[].alias | length] | max // 0) as $aw
  | [((.version | numbers) // ""), ((.computed_at | numbers) // ""), (.rate_label // ""), $aw]
    , ($rows[] | [.cur, (.name | pad($nw)), (.alias | pad($aw)), .claude, .go])
  | map(tostring) | join("\u001f")
' "$SUMMARY_FILE" 2>/dev/null) || exit 0

# Left-pad an ASCII string to a width (bytes == columns here, so printf is safe).
lpad() { printf '%*s' "$2" "$1"; }

flags=(); names=(); aliases=(); claude_txt=(); go_txt=()
header=1
alias_width=0
while IFS=$'\x1f' read -r f1 f2 f3 f4 f5; do
  if [ "$header" = "1" ]; then
    header=0
    [ "$f1" = "$SUMMARY_VERSION" ] || exit 0
    mark=""
    if { [ "$f3" != "$RATE_CALIBRATED" ] && [ "$f3" != "$RATE_PINNED" ]; } || ! [[ "$f2" =~ ^[0-9]+$ ]] \
        || [ $((now - f2)) -ge "$SUMMARY_STALE_SECONDS" ]; then
      mark="$STALE_MARK"
    fi
    alias_width=${f4:-0}
    continue
  fi
  flags+=("$f1"); names+=("$f2"); aliases+=("$f3")
  claude_txt+=("$(printf '%.1f' "$f4")")
  if [ -n "$f5" ]; then go_txt+=("$(printf '%.1f' "$f5")"); else go_txt+=(""); fi
done <<< "$rows"
[ ${#names[@]} -gt 0 ] || exit 0

# Column widths of the numbers ("%" excluded; "Go -" uses the Go column width plus the "%").
claude_width=0; go_width=${#ABSENT}
for i in "${!names[@]}"; do
  [ ${#claude_txt[$i]} -gt "$claude_width" ] && claude_width=${#claude_txt[$i]}
  [ $((${#go_txt[$i]} + 1)) -gt "$go_width" ] && go_width=$((${#go_txt[$i]} + 1))
done

for i in "${!names[@]}"; do
  prefix="$OTHER_PREFIX"
  [ "${flags[$i]}" = "1" ] && prefix="$CURRENT_PREFIX"
  label="${names[$i]}${COL_GAP}"
  [ "$alias_width" -gt 0 ] && label="${label}${DIM}${aliases[$i]}${RESET}${COL_GAP}"
  claude_part="${DIM}Claude ${mark}${RESET}$(lpad "" $((claude_width - ${#claude_txt[$i]})))$(pct_text "${claude_txt[$i]}")"
  if [ -n "${go_txt[$i]}" ]; then
    go_part="${DIM}Go ${mark}${RESET}$(lpad "" $((go_width - ${#go_txt[$i]} - 1)))$(pct_text "${go_txt[$i]}")"
  else
    go_part="${DIM}Go ${mark}$(lpad "$ABSENT" "$go_width")${RESET}"
  fi
  printf '%s\n' "${prefix}${label}${claude_part}${SEP}${go_part}"
done
exit 0
