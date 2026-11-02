#!/bin/bash
# Đặt lịch launchd chạy run_followup.sh --once một lần vào ngày/giờ local cho trước.
# Ported from session scratchpad 2026-11-02.
# Dùng: install_schedule.sh [YYYY-MM-DD] [HH:MM]   (mặc định 2026-11-16 09:07)
#       install_schedule.sh --uninstall
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"

DEFAULT_DATE="2026-11-16"
DEFAULT_TIME="09:07"

uninstall() {
  launchctl bootout "$GUI_DOMAIN/$LABEL" 2>/dev/null || true
  rm -f "$PLIST"
  echo "Đã gỡ $LABEL"
}

if [[ "${1:-}" == "--uninstall" ]]; then uninstall; exit 0; fi

DATE="${1:-$DEFAULT_DATE}"
TIME="${2:-$DEFAULT_TIME}"
[[ "$DATE" =~ ^[0-9]{4}-([0-9]{2})-([0-9]{2})$ ]] || { echo "Ngày sai dạng YYYY-MM-DD: $DATE" >&2; exit 2; }
MONTH=$((10#${BASH_REMATCH[1]})); DAY=$((10#${BASH_REMATCH[2]}))
[[ "$TIME" =~ ^([0-9]{2}):([0-9]{2})$ ]] || { echo "Giờ sai dạng HH:MM: $TIME" >&2; exit 2; }
HOUR=$((10#${BASH_REMATCH[1]})); MINUTE=$((10#${BASH_REMATCH[2]}))

mkdir -p "$OUT_DIR" "$(dirname "$PLIST")"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$TOOL_DIR/run_followup.sh</string>
    <string>--once</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Month</key><integer>$MONTH</integer>
    <key>Day</key><integer>$DAY</integer>
    <key>Hour</key><integer>$HOUR</integer>
    <key>Minute</key><integer>$MINUTE</integer>
  </dict>
  <key>StandardOutPath</key><string>$OUT_DIR/launchd.out.log</string>
  <key>StandardErrorPath</key><string>$OUT_DIR/launchd.err.log</string>
</dict>
</plist>
PLIST
plutil -lint "$PLIST"
launchctl bootout "$GUI_DOMAIN/$LABEL" 2>/dev/null || true   # nạp lại nếu đã có
launchctl bootstrap "$GUI_DOMAIN" "$PLIST"
echo "Đã đặt lịch $LABEL lúc $DATE $TIME (giờ local; launchd không xét năm). Plist: $PLIST"
