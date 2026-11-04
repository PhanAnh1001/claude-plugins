#!/bin/bash
# Test double for curl, installed as "curl" first on PATH by test_go_usage.py.
#
# Records its argv and stdin (the curl config that carries the Authorization header) to
# $FAKE_CURL_LOG / $FAKE_CURL_STDIN_LOG, then prints $FAKE_CURL_BODY to the -o target and
# $FAKE_CURL_HTTP_CODE to stdout (the script asks for -w '%{http_code}').
# It never touches the network.
set -u

log=${FAKE_CURL_LOG:?FAKE_CURL_LOG is required}
stdin_log=${FAKE_CURL_STDIN_LOG:-$log.stdin}

{
  printf 'argv\n'
  printf '%s\n' "$@"
} >> "$log"
cat > "$stdin_log"

body=${FAKE_CURL_BODY:-}
http_code=${FAKE_CURL_HTTP_CODE:-200}
sleep_seconds=${FAKE_CURL_SLEEP:-}
out=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    -o)
      out=${2:-}
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

[ -n "$sleep_seconds" ] && sleep "$sleep_seconds"
if [ -n "$out" ]; then
  printf '%s' "$body" > "$out"
  printf '%s' "$http_code"
else
  # statusline.sh asks for "\n%{http_code}"; keep body and code on separate lines.
  printf '%s\n%s' "$body" "$http_code"
fi
exit "${FAKE_CURL_EXIT:-0}"
