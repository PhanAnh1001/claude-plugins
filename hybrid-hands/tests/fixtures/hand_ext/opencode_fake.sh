#!/bin/sh
# Fake opencode for doctor tests: never prints secrets, mimics 1.18.14 output.
case "$1 $2 $3" in
  "--version  ") echo "1.18.14" ;;
  "auth list ") printf 'Credentials ~/.local/share/opencode/auth.json\n OpenCode Go api\n 1 credentials\n' ;;
  "models opencode-go --verbose") printf 'opencode-go/deepseek-v4.1-flash\n{\n  "release_date": "2026-09-10"\n}\n' ;;
  "models opencode-go ") printf 'opencode-go/deepseek-v4-pro\nopencode-go/deepseek-v4.1-flash\n' ;;
  *) echo "unexpected: $*" >&2; exit 2 ;;
esac
