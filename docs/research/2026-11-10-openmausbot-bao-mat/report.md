# Đánh giá bảo mật OpenMausBot và so sánh với hybrid-hands + Paseo

## Tóm tắt

- **Câu hỏi:** có nên cài OpenMausBot (OMB) lên user macOS đang chạy hybrid-hands + Paseo không, và nó khác gì công cụ hiện có?
- **Kết luận chính:**
  1. **Không cài OMB lên user macOS đang chạy hybrid-hands + Paseo.** Giữ hybrid-hands + Paseo cho điều phối agent code (suy luận từ các phát hiện dưới, [notes](notes/bao-mat-openmausbot.md)).
  2. Không thấy mã độc/obfuscation ở phần đã rà; code có ý thức bảo mật: bind 127.0.0.1, config 0600, thẻ duyệt, kiểm SHA-512 khi cập nhật [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/electron/elevated-install.mjs#L9-L27) (11/2026).
  3. Rủi ro là bề mặt quyền rộng: chế độ full bỏ sandbox/duyệt [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex.ts#L163-L168), điều khiển desktop GUI [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/electron/cua.mjs#L235), đọc token OAuth Claude từ Keychain [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/plan-usage.ts#L736-L790), và một lỗ tác giả đã biết chưa vá [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/SECURITY.md#L24-L27) (11/2026).
  4. Repo còn non: v0.1.151, ~1.430 commit từ 2026-10-16, ~6.000 file, server/index.ts ~15.500 dòng (chưa kiểm chéo) [nguồn](https://github.com/milind-soni/OpenMausBot) (11/2026).
  5. Chỉ dùng OMB khi cần tính năng riêng (desktop GUI, Composio Gmail/Slack/GitHub, chat trợ lý, routines) và phải chạy trong VM hoặc user macOS riêng với tài khoản Claude/ChatGPT phụ.
- **Số chính:** 4 High, 4 Medium, 3 Low; 57 dep trực tiếp; commit rà `f55d45c6` (2026-11-10).
- **Người đọc phải làm:** không cài trên máy chính; nếu thật cần, theo [Phương án 2](#3-phương-án); nếu chỉ thiếu routine theo lịch, kiểm schedule/heartbeat của Paseo trước.

## 1. Phát hiện bảo mật OMB

Chi tiết từng dòng code ở [notes/bao-mat-openmausbot.md](notes/bao-mat-openmausbot.md). Mọi link trỏ commit f55d45c6 (11/2026).

### 1.1 High

- **H1 chế độ full:** codex `approvalPolicy never` + `danger-full-access` [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex.ts#L163-L168); claude `bypassPermissions` [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/claude.ts#L985); qwen/gemini `--yolo` [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/acp/qwen.ts#L202). Rủi ro prompt injection qua Composio/web/file team (suy luận).
- **H2 điều khiển desktop:** cua-driver cần Accessibility + Screen Recording [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/electron/privacy-settings.mjs#L5-L7); opt-in [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/README.md#L83-L86).
- **H3 lỗ đã biết chưa vá:** shell của bot gọi route guarded của Slack worker, làm việc Full-access không cần thẻ duyệt (workspace hosted/shared) [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/SECURITY.md#L24-L27).
- **H4 đọc token OAuth Claude từ Keychain** bằng `security find-generic-password -w` [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/plan-usage.ts#L736-L790).

### 1.2 Medium

- **M1** route loopback ẩn danh đọc được bot và tin nhắn thread [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/request-auth.ts#L40-L45); chưa xác minh phạm vi trong bản packaged.
- **M2** analytics PostHog bật mặc định, có cờ opt-out, autocapture tắt [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/src/lib/analytics.ts#L91-L92).
- **M3** entitlements macOS nới (allow-jit, unsigned-executable-memory, dyld env vars, disable-library-validation, audio-input) [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/build/entitlements.mac.plist).
- **M4** gợi ý cài bằng curl|bash [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/muse-code.ts#L256-L257).

### 1.3 Low và supply chain

- **L1** tự cập nhật có kiểm SHA-512 [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/electron/updater.mjs); **L2** một số dep `^`, có lockfile [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/pnpm-lock.yaml); **L3** `OMB_LAN=1` bind 0.0.0.0 chỉ nhận IP private [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/lan-address.ts#L53-L59).
- Gói nhạy cảm @trycua/cua-driver, @1password/sdk, imapflow/nodemailer, posthog-js; nhiều endpoint ngoài gồm us.i.posthog.com và cloud.openmausbot.com [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/package.json) (11/2026).
- README cảnh báo token crypto mạo danh, chỉ tải từ [releases](https://github.com/milind-soni/OpenMausBot/releases) [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/README.md#L62) (11/2026).

## 2. So sánh với hybrid-hands + Paseo

Không có nguồn internet, nguồn nội bộ: [notes/hybrid-hands-paseo.md](notes/hybrid-hands-paseo.md).

### 2.1 Trùng và khác

- **Trùng:** chạy nhiều agent CLI dùng subscription sẵn có, điều khiển từ điện thoại.
- **OMB có thêm:** điều khiển desktop GUI, Composio, routines, UX chat trợ lý [nguồn](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/README.md) (11/2026).
- **OMB thiếu:** mô hình brain/hand, luật dữ liệu, ledger USD~/quota, guard v1 5%/ngày (không có nguồn internet, nguồn nội bộ).
- Schedule/heartbeat của Paseo chưa xác minh trong tài liệu hybrid-hands.

### 2.2 Xung đột nếu cài chung user (suy luận)

Suy luận từ [H1](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex.ts#L163-L168), [M1](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/request-auth.ts#L40-L45) và nguồn nội bộ:

- Bot chế độ full đọc được ~/.codex-hand, ~/.claude-hand, ~/.dsh-hand/go.key.
- Hand ngoài đọc được transcript bot qua route ẩn danh, vi phạm luật dữ liệu nếu có dữ liệu khách hàng.
- Bot tiêu quota v1 ngoài ledger hybrid-hands nên guard 5%/ngày có thể lệch.

## 3. Phương án

1. **Mặc định:** giữ hybrid-hands + Paseo, không cài OMB.
2. **Nếu cần OMB:** VM hoặc user macOS riêng + tài khoản Claude/ChatGPT phụ; không cấp Accessibility/Screen Recording, không dùng "this Mac"; giữ duyệt ask, không full; cẩn thận Composio, không import team lạ; tắt analytics, không bật OMB_LAN, cân nhắc chặn outbound posthog/cloud.openmausbot.com (LuLu/Little Snitch); tải .dmg đúng [releases](https://github.com/milind-soni/OpenMausBot/releases), kiểm Team ID bằng `codesign -dv`, tắt auto-update/pin version; build thì pin commit f55d45c6 trong VM.
3. **Nếu chỉ thiếu routine theo lịch:** kiểm schedule/heartbeat của Paseo trước.

## 4. Phương pháp và giới hạn

- Rà tĩnh chọn lọc bản clone shallow HEAD `f55d45c6e0764ec78e5ba8b0427150656dc94c92` (2026-11-10); không chạy script/build/install nào của repo.
- Chưa đọc hết server/index.ts, relay/, third_party/ (43 file), enterprise/, cloudflare/.
- Không chạy semgrep/bandit/pip-audit (không có trên máy) và npm/pnpm audit.

## 5. Câu hỏi mở

- Phạm vi route ẩn danh (M1) trong bản packaged.
- Paseo có schedule/heartbeat đủ thay routines của OMB không.
