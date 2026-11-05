#!/bin/bash
# Fetch the real OpenCode Go usage windows from the OpenCode Zen API and cache them for the
# status line. Mirrors the opencode-go-usage-source builtin plugin in Paseo 0.15.0.
#
# The key is read from ${XDG_DATA_HOME:-$HOME/.local/share}/opencode/auth.json
# (["opencode-go"].key), passed to curl through stdin (-K -) so it never appears in argv, and is
# never written to the cache, a log or stderr. Cache:
#   $CLAUDE_HOME/.statusline-go-usage.json   (default $HOME/.claude), mode 600, atomic rename
#   {"fetched_at": <epoch>, "state": "ok"|"rejected"|"error"|"no_key",
#    "last_ok_at": <epoch of the last ok fetch, absent for rejected/no_key>,
#    "windows": {"rolling"|"weekly"|"monthly": {"percent", "status", "resets_at"}}}
# A transient error (network, 5xx, malformed JSON) reuses the windows and last_ok_at of the last
# ok cache so the Go line can keep showing real numbers with "~"; rejected/no_key drop them.
# A directory lock stops overlapping fetches; a lock older than 60 s is considered stale.
# Run from statusline.sh in the background; safe to run by hand too.

set -u
umask 077

CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
CACHE_FILE="$CLAUDE_HOME/.statusline-go-usage.json"
LOCK_DIR="$CLAUDE_HOME/.statusline-go-usage.lock"
AUTH_FILE="${XDG_DATA_HOME:-$HOME/.local/share}/opencode/auth.json"
USAGE_URL="https://opencode.ai/zen/go/v1/usage"
REQUEST_TIMEOUT_SECONDS=15
LOCK_STALE_SECONDS=60
LOCK_HELD=0

now_epoch() {
  date +%s
}

file_mtime() {
  # GNU stat first, then BSD (macOS).
  stat -c '%Y' "$1" 2>/dev/null || stat -f '%m' "$1" 2>/dev/null
}

release_lock() {
  if [ "$LOCK_HELD" -eq 1 ]; then
    rmdir "$LOCK_DIR" 2>/dev/null || true
    LOCK_HELD=0
  fi
}

cleanup() {
  release_lock
}

acquire_lock() {
  local mtime now age
  mkdir -p "$CLAUDE_HOME" 2>/dev/null || return 1
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    LOCK_HELD=1
    return 0
  fi
  mtime=$(file_mtime "$LOCK_DIR") || return 1
  now=$(now_epoch)
  age=$((now - mtime))
  [ "$age" -ge "$LOCK_STALE_SECONDS" ] || return 1
  rmdir "$LOCK_DIR" 2>/dev/null || return 1
  if mkdir "$LOCK_DIR" 2>/dev/null; then
    LOCK_HELD=1
    return 0
  fi
  return 1
}

write_cache_document() {
  # $1: JSON document. Write a temp file next to the cache, chmod 600, then rename.
  local document=$1 tmp
  tmp=$(mktemp "$CLAUDE_HOME/.statusline-go-usage.XXXXXX") || return 1
  if ! printf '%s\n' "$document" > "$tmp"; then
    rm -f "$tmp"
    return 1
  fi
  if ! chmod 600 "$tmp"; then
    rm -f "$tmp"
    return 1
  fi
  if ! mv -f "$tmp" "$CACHE_FILE"; then
    rm -f "$tmp"
    return 1
  fi
}

read_previous_windows() {
  # Print {"last_ok_at", "windows"} from a cache that still holds all three windows of a
  # successful fetch; print nothing when the cache is missing, corrupt or incomplete. An error
  # cache written by an earlier error keeps last_ok_at instead of pretending it fetched ok.
  [ -f "$CACHE_FILE" ] || return 0
  jq -c '
    def valid_window:
      (type == "object")
      and ((.percent | type) == "number")
      and ((.status | type) == "string")
      and ((.resets_at | type) == "number");
    (.windows // {}) as $windows
    | select(($windows | type) == "object"
        and ($windows.rolling | valid_window)
        and ($windows.weekly | valid_window)
        and ($windows.monthly | valid_window))
    | (if (.state == "ok") and ((.fetched_at | type) == "number") then .fetched_at
       elif (.last_ok_at | type) == "number" then .last_ok_at
       else null end) as $last_ok_at
    | select($last_ok_at != null)
    | {last_ok_at: $last_ok_at, windows: $windows}
  ' "$CACHE_FILE" 2>/dev/null
}

write_state() {
  # $1: non-ok state (rejected/error/no_key). Never stores a response body.
  local state=$1 document previous
  if [ "$state" = "error" ]; then
    previous=$(read_previous_windows)
    if [ -n "$previous" ]; then
      document=$(jq -n --argjson fetched_at "$(now_epoch)" --argjson previous "$previous" \
        '{fetched_at: $fetched_at, state: "error",
          last_ok_at: $previous.last_ok_at, windows: $previous.windows}') || return 1
      write_cache_document "$document"
      return
    fi
  fi
  document=$(jq -n --argjson fetched_at "$(now_epoch)" --arg state "$state" \
    '{fetched_at: $fetched_at, state: $state}') || return 1
  write_cache_document "$document"
}

write_ok_cache() {
  # $1: response body (JSON). Reject malformed bodies instead of caching partial windows.
  local body=$1 document
  document=$(jq --argjson fetched_at "$(now_epoch)" '
    def window($w):
      if (($w | type) == "object")
         and (($w.percent | type) == "number")
         and (($w.status | type) == "string")
         and (($w.resetsAt | type) == "string")
      then {
        percent: $w.percent,
        status: $w.status,
        resets_at: ($w.resetsAt | sub("\\.[0-9]+Z$"; "Z") | fromdateiso8601)
      }
      else error("invalid usage window") end;
    if (.usage | type) == "object" then
      {
        fetched_at: $fetched_at,
        state: "ok",
        last_ok_at: $fetched_at,
        windows: {
          rolling: window(.usage.rolling),
          weekly: window(.usage.weekly),
          monthly: window(.usage.monthly)
        }
      }
    else error("missing usage") end
  ' <<< "$body" 2>/dev/null) || return 1
  write_cache_document "$document"
}

read_key() {
  # Print the opencode-go API key, or nothing. The key is never echoed to a log or argv.
  [ -f "$AUTH_FILE" ] || return 0
  jq -r '.["opencode-go"].key // empty | strings' "$AUTH_FILE" 2>/dev/null | head -n 1
}

escape_curl_config() {
  # Escape backslashes and double quotes for a quoted curl config value.
  local value=$1
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  printf '%s' "$value"
}

main() {
  local key config response http_code body curl_status

  acquire_lock || exit 0
  trap cleanup EXIT

  key=$(read_key)
  if [ -z "$key" ]; then
    write_state no_key || true
    exit 0
  fi

  config=$(printf 'header = "Authorization: Bearer %s"\n' "$(escape_curl_config "$key")")

  # -K - reads the Authorization header from stdin; only the URL/options are in argv. The body
  # stays in memory: it is never written to the cache, a temp file or stderr.
  response=$(printf '%s' "$config" | curl -K - -sS --max-time "$REQUEST_TIMEOUT_SECONDS" \
    -H "Accept: application/json" -w '\n%{http_code}' "$USAGE_URL" 2>/dev/null)
  curl_status=$?

  if [ "$curl_status" -ne 0 ]; then
    write_state error || true
    exit 0
  fi
  # curl -w puts the code on the last line; a test double may append it without a newline.
  response=${response%$'\n'}
  case "$response" in
    *$'\n'*)
      http_code=${response##*$'\n'}
      body=${response%$'\n'*}
      ;;
    *)
      if [ "${#response}" -ge 3 ]; then
        http_code=${response: -3}
        body=${response:0:${#response}-3}
      else
        http_code=""
        body=$response
      fi
      ;;
  esac
  http_code=${http_code//[!0-9]/}
  case "$http_code" in
    2??)
      if ! write_ok_cache "$body"; then
        write_state error || true
      fi
      ;;
    401|403)
      write_state rejected || true
      ;;
    *)
      write_state error || true
      ;;
  esac
  exit 0
}

main "$@"
