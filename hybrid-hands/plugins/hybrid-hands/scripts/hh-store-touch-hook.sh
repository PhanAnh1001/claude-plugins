#!/bin/sh
# Claude Code hook: tell the hh-store indexer a transcript changed.
# Returns at once: python runs detached with the hook's stdin; never prints, always exit 0.
case "$HYBRID_HANDS_STORE:$HYBRID_HANDS_INDEXER" in
  off:*|OFF:*|*:off|*:OFF) exit 0 ;;
esac
PL=$(CDPATH= cd -- "$(dirname -- "$0")/.." 2>/dev/null && pwd) || exit 0
"$PL/bin/hh-store" touch --hook-stdin <&0 >/dev/null 2>&1 &
exit 0
