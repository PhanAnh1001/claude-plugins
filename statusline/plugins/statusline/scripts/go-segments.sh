#!/bin/bash
# OpenCode Go cells of the statusline plugin, sourced by statusline.sh (not run on its own).
# Uses the colours, STALE_MARK, PLACEHOLDER, col_for_pct, join_cells (table.sh) and
# rate_limit_segment that statusline.sh defines before it calls these functions.

# Machine-wide OpenCode Go usage summary written by hand-ext (never called from here).
GO_STATE_DIR="${HYBRID_HANDS_STATE_DIR:-$HOME/.hybrid-hands}"
GO_SUMMARY_FILE="$GO_STATE_DIR/go_usage_summary.json"
GO_STALE_SECONDS=$((5 * 3600))
# The API rounds to an integer: an estimate is shown only inside [api - 0.5, api + 0.4].
GO_ESTIMATE_BELOW=0.5
GO_ESTIMATE_ABOVE=0.4
# Live OpenCode Go usage fetched from the Zen API by go-usage-fetch.sh (same source as Paseo).
# The status line only reads this cache; the fetch runs detached in the background.
GO_LIVE_CACHE_FILE="$CLAUDE_HOME/.statusline-go-usage.json"
GO_LIVE_LOCK_DIR="$CLAUDE_HOME/.statusline-go-usage.lock"
GO_LIVE_AUTH_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/opencode/auth.json"
GO_LIVE_REFRESH_SECONDS=300
GO_LIVE_STALE_SECONDS=900
# A transient error may keep showing the last ok numbers for this long before falling back to DS.
GO_LIVE_ERROR_KEEP_SECONDS=21600
GO_LIVE_LOCK_STALE_SECONDS=60
GO_LIVE_FETCHED_AT=""
GO_LIVE_STATE=""
GO_LIVE_LAST_OK_AT=""
GO_LIVE_ROLLING_PCT=""
GO_LIVE_ROLLING_STATUS=""
GO_LIVE_ROLLING_RESET=""
GO_LIVE_WEEKLY_PCT=""
GO_LIVE_WEEKLY_STATUS=""
GO_LIVE_WEEKLY_RESET=""
GO_LIVE_MONTHLY_PCT=""
GO_LIVE_MONTHLY_STATUS=""
GO_LIVE_MONTHLY_RESET=""
GO_LIVE_STALE=0

# --- Go usage (last row of the limit table; cached summary file only) ---
load_go_summary() {
  # One jq read of go_usage_summary.json; sets go_updated/go_five/... or leaves them empty.
  [ -f "$GO_SUMMARY_FILE" ] || return 0
  local row
  row=$(jq -r '
    (.models // {}) as $models
    | ([$models | to_entries[]
        | select((.key | type) == "string" and (.key | test("deepseek"; "i")))]
       | .[0].value // {}) as $m
    | (if ($m | type) == "object" then $m else {} end) as $w
    | [ ((.updated_at // 0) | numbers // 0),
        (($w["5h"].percent | numbers) // ""),
        ($w["5h"].estimated == true),
        (($w["7d"].percent | numbers) // ""),
        ($w["7d"].estimated == true),
        (($w["30d"].percent | numbers) // ""),
        ($w["30d"].estimated == true) ]
    | @tsv
  ' "$GO_SUMMARY_FILE" 2>/dev/null) || return 0
  [ -n "$row" ] || return 0
  IFS=$'\t' read -r go_updated go_five go_five_est go_week go_week_est go_month go_month_est \
    <<< "$row"
}

go_pct_segment() {
  # Args: label percent mark. Same colour thresholds as the Claude part; "--" when absent.
  local label=$1 pct=$2 mark=$3
  if [ -z "$pct" ]; then
    printf '%s %s%s%s' "${DIM}${label}${RESET}" "$DIM" "$PLACEHOLDER" "$RESET"
    return 0
  fi
  printf '%s %s%s%s%s%.1f%%%s' "${DIM}${label}${RESET}" "$DIM" "$mark" "$RESET" \
    "$(col_for_pct "$pct")" "$pct" "$RESET"
}

go_usage_cells() {
  # "DS 5h ~12.3%" and "tuần ~31.0%" cells; "~" when any value is estimated or >5h old.
  [ -n "$go_five" ] || [ -n "$go_week" ] || return 0
  local now stale="" mark5="" mark7=""
  now=$(date +%s)
  if ! [[ "$go_updated" =~ ^[0-9]+$ ]] || [ "$go_updated" -le 0 ] \
      || [ $((now - go_updated)) -ge "$GO_STALE_SECONDS" ]; then
    stale="$STALE_MARK"
  fi
  [ "$go_five_est" = "true" ] && mark5="$STALE_MARK"
  [ "$go_week_est" = "true" ] && mark7="$STALE_MARK"
  [ -n "$stale" ] && { mark5="$STALE_MARK"; mark7="$STALE_MARK"; }
  join_cells "$(go_pct_segment "DS 5h" "$go_five" "$mark5")" \
    "$(go_pct_segment tuần "$go_week" "$mark7")"
}

# --- Go live usage (cache written by go-usage-fetch.sh) ---
load_go_live_cache() {
  # One jq read of the live cache; sets GO_LIVE_* or leaves them empty. A corrupt/missing cache
  # is silent so the estimated DS cells below still work.
  [ -f "$GO_LIVE_CACHE_FILE" ] || return 0
  local row now
  row=$(jq -r '
    [ (.fetched_at // ""), (.state // ""), (.last_ok_at // ""),
      (.windows.rolling.percent // ""), (.windows.rolling.status // ""),
      (.windows.rolling.resets_at // ""),
      (.windows.weekly.percent // ""), (.windows.weekly.status // ""),
      (.windows.weekly.resets_at // ""),
      (.windows.monthly.percent // ""), (.windows.monthly.status // ""),
      (.windows.monthly.resets_at // "") ]
    | map(tostring) | join("\u001f")
  ' "$GO_LIVE_CACHE_FILE" 2>/dev/null) || return 0
  [ -n "$row" ] || return 0
  IFS=$'\x1f' read -r GO_LIVE_FETCHED_AT GO_LIVE_STATE GO_LIVE_LAST_OK_AT \
    GO_LIVE_ROLLING_PCT GO_LIVE_ROLLING_STATUS GO_LIVE_ROLLING_RESET \
    GO_LIVE_WEEKLY_PCT GO_LIVE_WEEKLY_STATUS GO_LIVE_WEEKLY_RESET \
    GO_LIVE_MONTHLY_PCT GO_LIVE_MONTHLY_STATUS GO_LIVE_MONTHLY_RESET <<< "$row"
  local age_from=$GO_LIVE_LAST_OK_AT
  [[ "$age_from" =~ ^[0-9]+$ ]] || age_from=$GO_LIVE_FETCHED_AT
  now=$(date +%s)
  [ "$GO_LIVE_STATE" = "error" ] && GO_LIVE_STALE=1
  if [[ "$age_from" =~ ^[0-9]+$ ]] \
      && [ $((now - age_from)) -ge "$GO_LIVE_STALE_SECONDS" ]; then
    GO_LIVE_STALE=1
  fi
}

go_live_windows_complete() {
  [ -n "$GO_LIVE_ROLLING_PCT" ] && [ -n "$GO_LIVE_ROLLING_STATUS" ] \
    && [ -n "$GO_LIVE_WEEKLY_PCT" ] && [ -n "$GO_LIVE_WEEKLY_STATUS" ] \
    && [ -n "$GO_LIVE_MONTHLY_PCT" ] && [ -n "$GO_LIVE_MONTHLY_STATUS" ]
}

go_live_ok() {
  # An "ok" cache renders; an "error" cache keeps rendering only while its last ok fetch is
  # recent, so a long outage eventually falls back to the estimated DS numbers.
  go_live_windows_complete || return 1
  case "$GO_LIVE_STATE" in
    ok)
      [[ "$GO_LIVE_FETCHED_AT" =~ ^[0-9]+$ ]] || return 1
      return 0
      ;;
    error)
      [[ "$GO_LIVE_LAST_OK_AT" =~ ^[0-9]+$ ]] || return 1
      [ $(( $(date +%s) - GO_LIVE_LAST_OK_AT )) -lt "$GO_LIVE_ERROR_KEEP_SECONDS" ]
      ;;
    *)
      return 1
      ;;
  esac
}

go_summary_fresh() {
  [[ "${go_updated:-}" =~ ^[0-9]+$ ]] && [ "$go_updated" -gt 0 ] \
    && [ $(( $(date +%s) - go_updated )) -le "$GO_STALE_SECONDS" ]
}

go_estimate() {
  # Args: percent estimated_flag. Prints the hand-ext estimate when fresh and estimated.
  [ -n "$1" ] && [ "$2" = "true" ] && go_summary_fresh && printf '%s' "$1"
}

go_clamp_estimate() {
  # Args: api_percent estimate -> estimate clamped to [max(0, api - 0.5), api + 0.4].
  awk -v a="$1" -v e="$2" -v below="$GO_ESTIMATE_BELOW" -v above="$GO_ESTIMATE_ABOVE" 'BEGIN {
    lo = a - below; if (lo < 0) lo = 0; hi = a + above;
    if (e < lo) e = lo; if (e > hi) e = hi; printf "%.1f", e;
  }'
}

go_live_window_segment() {
  # Args: label percent status resets_at [estimate]. An expired reset means the window already
  # reset: print "~0%" and drop the time until the next fetch. Otherwise an estimate is clamped
  # around the API integer and printed with one decimal; colour and status follow the API.
  local label=$1 pct=$2 status=$3 reset=$4 est="${5:-}" shown="" mark="" color now
  now=$(date +%s)
  if [ -n "$reset" ] && [[ "$reset" =~ ^[0-9]+$ ]] && [ "$reset" -le "$now" ]; then
    pct=0
    reset=""
    mark="$STALE_MARK"
    est=""
  elif [ "$GO_LIVE_STALE" = "1" ]; then
    mark="$STALE_MARK"
  fi
  [ -n "$est" ] && shown=$(go_clamp_estimate "$pct" "$est")
  color=$(col_for_pct "$pct")
  [ "$status" = "rate-limited" ] && color="$RED"
  rate_limit_segment "$label" "$pct" "$reset" "" "" "$color" "$mark" "$shown"
}

go_live_cells() {
  # The three Go cells (5h, wk, mo) for the limit table; the row label is added by build_go_row.
  # Pairs: rolling <-> 5h, weekly <-> 7d, monthly <-> 30d of the hand-ext summary.
  join_cells "$(go_live_window_segment 5h "$GO_LIVE_ROLLING_PCT" \
    "$GO_LIVE_ROLLING_STATUS" "$GO_LIVE_ROLLING_RESET" "$(go_estimate "$go_five" "$go_five_est")")" \
    "$(go_live_window_segment wk "$GO_LIVE_WEEKLY_PCT" \
    "$GO_LIVE_WEEKLY_STATUS" "$GO_LIVE_WEEKLY_RESET" "$(go_estimate "$go_week" "$go_week_est")")" \
    "$(go_live_window_segment mo "$GO_LIVE_MONTHLY_PCT" \
    "$GO_LIVE_MONTHLY_STATUS" "$GO_LIVE_MONTHLY_RESET" "$(go_estimate "$go_month" "$go_month_est")")"
}

build_go_row() {
  # Go cells for the limit table: live 5h/wk/mo with reset times, else the DS estimate cells
  # (no reset time) from go_usage_summary.json, else nothing (no row).
  if go_live_ok; then
    go_live_cells
    return 0
  fi
  local go_cells
  go_cells=$(go_usage_cells)
  [ -n "$go_cells" ] || return 0
  [ "$GO_LIVE_STATE" = "rejected" ] \
    && go_cells="${go_cells} ${DIM}(khoá Go bị từ chối)${RESET}"
  printf '%s' "$go_cells"
}

go_auth_has_key() {
  # Only the presence of a non-empty opencode-go key; the value is never printed.
  [ -f "$GO_LIVE_AUTH_FILE" ] || return 1
  jq -e '.["opencode-go"].key | strings | length > 0' "$GO_LIVE_AUTH_FILE" >/dev/null 2>&1
}

go_live_lock_is_fresh() {
  # A lock younger than 60 s means a fetch is already running; leave it alone.
  local mtime now
  [ -d "$GO_LIVE_LOCK_DIR" ] || return 1
  mtime=$(stat -c '%Y' "$GO_LIVE_LOCK_DIR" 2>/dev/null \
    || stat -f '%m' "$GO_LIVE_LOCK_DIR" 2>/dev/null) || return 1
  now=$(date +%s)
  [ $((now - mtime)) -lt "$GO_LIVE_LOCK_STALE_SECONDS" ]
}

maybe_start_go_live_fetch() {
  # Never wait for the network: spawn the fetch detached and keep rendering the current cache.
  [ "${STATUSLINE_GO_LIVE:-1}" != "0" ] || return 0
  local now fetched
  now=$(date +%s)
  fetched=$GO_LIVE_FETCHED_AT
  if [[ "$fetched" =~ ^[0-9]+$ ]] \
      && [ $((now - fetched)) -lt "$GO_LIVE_REFRESH_SECONDS" ]; then
    return 0
  fi
  [ -f "$GO_FETCH_SCRIPT" ] || return 0
  go_auth_has_key || return 0
  go_live_lock_is_fresh && return 0
  nohup bash "$GO_FETCH_SCRIPT" </dev/null >/dev/null 2>&1 &
  disown 2>/dev/null || true
}
