# Hằng số dùng chung cho run_followup.sh và install_schedule.sh (source, không chạy trực tiếp).
# Ported from session scratchpad 2026-11-02.
TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$TOOL_DIR/out"
LABEL="com.parallel-subagents.cache-metrics-followup"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
GUI_DOMAIN="gui/$(id -u)"
# launchd chạy với PATH tối giản; đặt PATH đầy đủ để tìm python3/osascript/launchctl.
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
