---
name: limit-watch
description: Đăng ký phiên Paseo và bật vòng chờ hạn mức khi hết limit, chờ hạn mức, limit-watch, tự chạy tiếp, bật vòng lặp; dùng trước khi hết quota hoặc sau khi mở side-session dài.
---

Tóm tắt: đăng ký đúng phiên bằng metadata public, chờ quota bằng code và tiếp tục từ checkpoint; không đổi tài khoản để né hạn mức.

1. Xem `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" limit-watch status`.
2. Cho chính phiên đang gọi, dùng `limit-watch add --self --checkpoint "Đã xong A; còn B" --next-step "Kiểm chứng B, tạo file .done khi hoàn tất" --dry-run`. Với Sol vừa mở bằng `side-session start`, dùng `add --side NAME` thay `--self`. Luôn gọi binary trên; bỏ `--dry-run` để đăng ký khi metadata đầy đủ.
3. `add` tự lấy agent/workspace/native/endpoint và account home, ghi target rồi bật watcher nếu đang tắt; giữ nguyên chế độ persistent. Muốn bật vòng lặp liên tục, chạy `limit-watch on --persistent` theo yêu cầu người dùng, trước khi thêm target. Thiếu trường thì báo lỗi, không đoán ID hoặc tự ghép JSON.
4. Checkpoint ghi đã xong gì, phần còn dở và phạm vi đã duyệt; next-step ghi bước kế cụ thể và đường dẫn file `.done` nếu có. Không ghi secret hoặc dữ liệu khách hàng. Đăng ký trước khi hết limit để phiên ở trạng thái armed.

In kết quả lệnh; lỗi thì báo nguyên văn, không đổi ID hoặc off/on để thử lại. ACK mơ hồ giữ dispatch_pending, cần operator reconcile, không gửi trùng. `off` tắt toàn bộ watcher, chỉ chạy khi người dùng yêu cầu rõ. Tmux/CLI ngoài Paseo chưa hỗ trợ. Guard v1 8%/ngày vẫn giữ nguyên; không gọi model để poll, không mua credits hay bật extra usage.

Chi tiết: [README limit-watch](../../README.md). Slash command: `/hybrid-hands:limit-watch`.

Kết thúc riêng target: `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" limit-watch done --id "<ID>"`, chỉ khi người dùng yêu cầu rõ và cung cấp ID; dispatch_pending bị từ chối để đối soát ACK. Đăng ký lại cùng ID đã done khôi phục armed. Brain Paseo sống qua idle/finished và tự về armed sau resumed; side vẫn kết thúc theo `.done`/stopped.
