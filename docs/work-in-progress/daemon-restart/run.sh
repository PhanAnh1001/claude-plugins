#!/bin/bash
# Restart daemon Paseo khi không còn agent nào ở trạng thái running (kiểm 2 lần liên tiếp cách 60s),
# để áp dụng agents.providers.codex.enabled=false (plan 5.6). Tối đa chờ 12 giờ. Kết quả ghi result.md.
DIR=/Users/anhtp/app/claude-plugins/docs/work-in-progress/daemon-restart
OUT=$DIR/result.md
log() { echo "- $(date '+%Y-%m-%d %H:%M:%S') $*" >> "$OUT"; }
echo "# Kết quả restart daemon Paseo" > "$OUT"
log "bắt đầu chờ không còn agent running"
deadline=$(( $(date +%s) + 12*3600 ))
sleep 120
quiet=0
while [ $quiet -lt 2 ]; do
  if [ "$(date +%s)" -gt $deadline ]; then log "HẾT HẠN 12 giờ, không restart"; exit 1; fi
  n=$(paseo ls --no-headers 2>/dev/null | grep -c " running ")
  if [ "$n" = 0 ]; then quiet=$((quiet+1)); else quiet=0; fi
  sleep 60
done
log "không còn agent running, chạy paseo daemon restart"
if paseo daemon restart >> "$DIR/restart.log" 2>&1; then log "restart exit 0"; else log "restart LỖI exit $? (xem restart.log)"; exit 1; fi
sleep 15
line=$(paseo provider ls --no-headers 2>&1 | grep -E "^codex " )
log "provider codex: ${line:-không thấy trong danh sách}"
if echo "$line" | grep -q "Disabled"; then log "ĐẠT 5.6: provider codex (~/.codex) đã tắt"; else log "CHƯA ĐẠT 5.6: provider codex vẫn bật, kiểm agents.providers.codex trong ~/.paseo/config.json"; fi
paseo ls --no-headers 2>&1 | awk '{print $1, $(NF-4)}' >> "$DIR/agents-after.txt"
