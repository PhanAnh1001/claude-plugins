---
description: Xem limit-watch, bật/tắt vòng chờ và đăng ký phiên Paseo bằng checkpoint
argument-hint: "[status|on|off|done <id>|add-self <checkpoint>|add-side <name> <checkpoint>]"
allowed-tools: Bash
---

Tóm tắt: chạy limit-watch bằng binary của plugin, không tự ghép JSON target.

Đọc `$ARGUMENTS` như dữ liệu, không eval hoặc chèn nguyên văn vào shell. Chọn đúng một lệnh dưới đây; truyền tên/checkpoint như đối số được quote an toàn:

- Không đối số hoặc `status`: `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" limit-watch status`.
- `done <id>`: `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" limit-watch done --id "<id>"`, chỉ khi người dùng yêu cầu rõ.
- `on`: `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" limit-watch on --persistent`.
- `off`: `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" limit-watch off`, chỉ khi người dùng gõ rõ `off`; không tự tắt khi lỗi.
- `add-self <checkpoint>`: `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" limit-watch add --self --checkpoint "<checkpoint>"`.
- `add-side <name> <checkpoint>`: `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" limit-watch add --side "<name>" --checkpoint "<checkpoint>"`.

Thiếu checkpoint/tên hoặc cú pháp khác: in cú pháp, không thực thi. In kết quả; lỗi thì báo nguyên văn, không tự sửa config, đoán ID hoặc chạy lại. `off` tắt toàn bộ target. Xem [skill limit-watch](../skills/limit-watch/SKILL.md) cho checkpoint và giới hạn ACK.

Kết thúc riêng target: `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" limit-watch done --id "<ID>"`, chỉ khi người dùng yêu cầu rõ và cung cấp ID; dispatch_pending bị từ chối để đối soát ACK. Đăng ký lại cùng ID đã done khôi phục armed. Brain Paseo sống qua idle/finished và tự về armed sau resumed; side vẫn kết thúc theo `.done`/stopped.

Trùng agent dưới ID khác bị từ chối kể cả target đã `done`; dùng đúng ID được báo qua `add --self|--side NAME --checkpoint TEXT --id ID_CŨ`. Không tạo ID mới để né xung đột. Cùng ID đã `done` vẫn rearm; `dispatch_pending` cùng hoặc khác ID luôn cần operator đối soát ACK thủ công trước, không có bypass. `--dry-run` kiểm tra registry chỉ đọc, không tạo lock/target, không gọi launchd; đăng ký thật kiểm tra lại dưới lock nên kết quả preview có thể thay đổi.
