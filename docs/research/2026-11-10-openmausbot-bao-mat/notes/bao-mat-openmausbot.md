# Ghi chú nguồn: bảo mật OpenMausBot

## Tóm tắt

- **Mục đích:** ghi từng sự kiện rà tĩnh từ mã nguồn OpenMausBot, mỗi dòng có link file:dòng và ngày dữ liệu.
- **Phiên bản rà:** commit `f55d45c6e0764ec78e5ba8b0427150656dc94c92` (2026-11-10), bản clone shallow, chỉ đọc tĩnh.
- **Kết quả:** 4 High, 4 Medium, 3 Low; không thấy mã độc/obfuscation ở phần đã rà.
- **Đã kiểm lại khi lưu:** codex.ts:163-168, SECURITY.md:24-27, plan-usage.ts:~751 khớp bản clone.

## Chức năng và kiến trúc

- App Electron chat kiểu Telegram; mỗi bot là agent CLI thật (claude, codex, grok, gemini, qwen, cursor…) dùng login sẵn có; bot có "máy tính" riêng (VM cloud, VM cục bộ hoặc chính Mac); channel/room, router, routines, Composio, import team từ Markdown, ghép điện thoại, Team Cloud. [README](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/README.md) (11/2026)
- Thư mục: electron/ (main=[electron/main.mjs](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/electron/main.mjs)), server/ (listen ở [server/index.ts#L15499](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/index.ts#L15499)), src/, relay/, cloudflare/, companion/, enterprise/. (11/2026)
- Dữ liệu ở `~/.openmausbot/config.json` (quyền 0600); server bind 127.0.0.1. [server/index.ts](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/index.ts) (11/2026)
- Cài .dmg notarize từ GitHub Releases hoặc build pnpm; [package.json](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/package.json) gốc không có pre/postinstall. (11/2026)

## Phát hiện High

- H1 chế độ full: codex `approvalPolicy: "never"`, `sandbox: "danger-full-access"` [codex.ts#L163-L168](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/codex.ts#L163-L168); claude `bypassPermissions` [claude.ts#L985](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/claude.ts#L985); `--yolo` [qwen.ts#L202](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/acp/qwen.ts#L202), [gemini.ts#L46](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/acp/gemini.ts#L46). (11/2026)
- H2 điều khiển desktop qua cua-driver (Accessibility + Screen Recording): [cua.mjs#L235](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/electron/cua.mjs#L235), [cua.mjs#L276](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/electron/cua.mjs#L276), [privacy-settings.mjs#L5-L7](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/electron/privacy-settings.mjs#L5-L7); opt-in theo [README#L83-L86](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/README.md#L83-L86). (11/2026)
- H3 lỗ đã biết chưa vá: shell của bot gọi route guarded của Slack worker, làm việc Full-access không cần thẻ duyệt; dự kiến vá bằng relay token riêng worker. [SECURITY.md#L24-L27](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/SECURITY.md#L24-L27) (11/2026)
- H4 đọc token OAuth Claude từ Keychain bằng `security find-generic-password -w`: [plan-usage.ts#L736-L790](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/plan-usage.ts#L736-L790) (11/2026)

## Phát hiện Medium

- M1 route loopback ẩn danh đọc được (GET /api/bots, /api/threads/*/messages): [request-auth.ts#L40-L45](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/request-auth.ts#L40-L45), [SECURITY.md#L16](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/SECURITY.md#L16) (11/2026). Chưa xác minh phạm vi trong bản packaged.
- M2 analytics PostHog bật mặc định, opt-out cờ `omb-analytics-opt-out`, autocapture tắt: [analytics.ts#L7](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/src/lib/analytics.ts#L7), [#L26](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/src/lib/analytics.ts#L26), [#L91-L92](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/src/lib/analytics.ts#L91-L92) (11/2026)
- M3 entitlements nới: allow-jit, allow-unsigned-executable-memory, allow-dyld-environment-variables, disable-library-validation, audio-input. [entitlements.mac.plist](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/build/entitlements.mac.plist) (11/2026)
- M4 gợi ý cài bằng curl|bash: [muse-code.ts#L256-L257](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/muse-code.ts#L256-L257), [cursor.ts#L488-L489](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/drivers/acp/cursor.ts#L488-L489) (11/2026)

## Phát hiện Low và khác

- L1 tự cập nhật, kiểm SHA-512, pkexec trên Linux: [updater.mjs](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/electron/updater.mjs), [elevated-install.mjs#L9-L27](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/electron/elevated-install.mjs#L9-L27) (11/2026)
- L2 một số dep dùng `^` (posthog-js, react, mermaid, shiki), có [pnpm-lock.yaml](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/pnpm-lock.yaml). (11/2026)
- L3 `OMB_LAN=1` bind 0.0.0.0, chỉ nhận IP private: [lan-address.ts#L53-L59](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/lan-address.ts#L53-L59) (11/2026)
- Khác: webhook ingress [webhook-ingress.ts#L189](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/webhook-ingress.ts#L189); OAuth callback loopback [mcp-oauth.ts#L145](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/server/mcp-oauth.ts#L145); key tuỳ chọn [credential-patch.mjs#L2-L16](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/electron/credential-patch.mjs#L2-L16). (11/2026)

## Supply chain

- 57 dep trực tiếp; lockfile [pnpm-lock.yaml](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/pnpm-lock.yaml), [relay/pnpm-lock.yaml](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/relay/pnpm-lock.yaml); gói nhạy cảm @trycua/cua-driver 0.45.4, @1password/sdk, imapflow/nodemailer, @muse-code/sdk, posthog-js. [package.json](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/package.json) (11/2026)
- Script cài: [build/linux-after-install.sh](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/build/linux-after-install.sh), [maus.ps1](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/maus.ps1). (11/2026)
- Endpoint thấy trong mã: api.anthropic.com, api.openai.com, api.x.ai, openrouter.ai, generativelanguage.googleapis.com, api.groq.com, minimax, meta.ai, us.i.posthog.com, cloud.openmausbot.com, Composio, raw.githubusercontent.com, github.com, WSS elevenlabs/openai. (11/2026)
- Không chạy semgrep/bandit/pip-audit (không có trên máy) và npm/pnpm audit (cấm chạy trong repo clone).

## Tín hiệu repo

- v0.1.151, ~1.430 commit từ 2026-10-16, ~6.000 file, server/index.ts ~15.500 dòng; PR ~#5211; contributor milind-soni ~833, Sebastian B 157, AdityaUmale ~144 (chưa kiểm chéo). [repo](https://github.com/milind-soni/OpenMausBot) (11/2026)
- Apache-2.0, enterprise/ source-available [LICENSING.md](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/LICENSING.md); có CLA, [SECURITY.md](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/SECURITY.md). (11/2026)
- Cảnh báo token crypto mạo danh, chỉ tải từ [releases](https://github.com/milind-soni/OpenMausBot/releases): [README#L62](https://github.com/milind-soni/OpenMausBot/blob/f55d45c6e0764ec78e5ba8b0427150656dc94c92/README.md#L62) (11/2026)
