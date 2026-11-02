#!/bin/bash
# Đo lại prompt cache của subagent: chạy compare_periods.py, compact_cache.py, resume_miss.py,
# ghi out/followup-<YYYY-MM-DD>.md rồi gửi thông báo macOS.
# Ported from session scratchpad 2026-11-02.
# Dùng: run_followup.sh [--once]
#   --once  chạy xong thì gỡ launchd agent và xóa plist (StartCalendarInterval lặp hằng năm).
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

ONCE=0
case "${1:-}" in
  --once) ONCE=1 ;;
  "") ;;
  *) echo "Tham số không hợp lệ: $1 (chỉ nhận --once)" >&2; exit 2 ;;
esac

if [[ -x /usr/bin/python3 ]]; then PY=/usr/bin/python3; else PY="$(command -v python3)"; fi
mkdir -p "$OUT_DIR"
REPORT="$OUT_DIR/followup-$(date +%Y-%m-%d).md"
START=$(date +%s)

section() { # $1 = tiêu đề, phần còn lại = lệnh
  local title="$1"; shift
  printf '\n# %s\n\n```text\n' "$title"
  "$@"
  printf '```\n'
}

{
  "$PY" -I "$TOOL_DIR/compare_periods.py"
  section "compact_cache.py (toàn bộ lịch sử)" "$PY" -I "$TOOL_DIR/compact_cache.py"
  section "resume_miss.py (toàn bộ lịch sử)" "$PY" -I "$TOOL_DIR/resume_miss.py"
} > "$REPORT"

echo "Xong sau $(( $(date +%s) - START ))s: $REPORT"
MSG="Đo lại cache subagent xong: $REPORT; mở Claude Code và yêu cầu viết báo cáo nghiên cứu tiếp nối"
osascript -e 'on run argv' -e 'display notification (item 1 of argv) with title "cache-metrics"' \
  -e 'end run' "$MSG" || echo "Không gửi được thông báo macOS" >&2

if (( ONCE )); then
  launchctl bootout "$GUI_DOMAIN/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Đã gỡ launchd agent $LABEL"
fi
