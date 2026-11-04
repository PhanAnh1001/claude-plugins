---
name: ext-hand
description: Giao một việc code hoặc tài liệu tự chứa cho hand ngoài chạy trên gói subscription thứ hai (Codex gói ChatGPT, Claude tài khoản thứ hai, OpenCode Go) bằng lệnh hand-ext - viết brief vào file, run nền với --backend auto, đọc report, brain tự review diff, báo backend, token, % hạn mức; xử lý exit 7, quota, capped, timeout, not_logged_in; cài đặt lần đầu từng backend. Không dùng API key, không tính USD. Từ khoá kích hoạt - "hand ngoài", "hand-ext", "gói thứ hai", "Codex", "OpenCode Go", "hand rẻ", "hạn mức hand", "giao hand".
---

# Hand ngoài (hand-ext)

## Tóm tắt

- **Dùng khi (mặc định):** việc code/tài liệu tự chứa, phạm vi file rõ: sửa hay viết script, viết test, refactor trong vài file, soát hay sửa tài liệu, đọc code trả lời câu hỏi. Chạy trên gói subscription thứ hai để giữ hạn mức gói Claude chính cho brain.
- **Không dùng khi:** cần tool riêng của Claude Code (Chrome, MCP, Skill, đọc ảnh, SendMessage), chạy lệnh trả phí của dự án → `hybrid-hands:hand`; `hand-ext` thoát 7 hoặc lỗi → cũng `hybrid-hands:hand`.
- **Chuỗi bước:** brief vào file → `hand-ext run --backend auto` chạy nền → đọc report → brain review diff → báo backend, token, % hạn mức, thời điểm reset.
- **Luật cứng:** không bao giờ dùng hay tạo API key, không chuyển sang API khi hết hạn mức; Codex và OpenCode không chịu hook của Claude Code nên brief chép nguyên văn luật cấm (nhất là cấm đọc `.env`) và PHẠM VI GHI hẹp.
- **Backend:** `codex` (gói ChatGPT), `claude` (gói Claude thứ hai), `opencode` (OpenCode Go, DeepSeek V4.1 Flash biến thể max); `gemini` dự kiến, chưa nằm trong `order`.

## 1. Cài đặt lần đầu (mỗi máy, mỗi backend)

Lệnh chung: `hand-ext setup [--backend B|all] [--cwd D]` ghi cấu hình CLI và in lệnh đăng nhập; người dùng tự đăng nhập trong terminal riêng (agent không chạy, không thấy credential); rồi `hand-ext doctor [--backend B|all]` tới khi đạt. Nếu `hand-ext` không có trong PATH, gọi `${CLAUDE_PLUGIN_ROOT}/bin/hand-ext`.

| Backend | Gói | Người dùng tự đăng nhập |
|---|---|---|
| `codex` | ChatGPT, thư mục riêng `~/.codex-hand` | `CODEX_HOME=~/.codex-hand codex login --device-auth` |
| `claude` | Claude tài khoản THỨ HAI, thư mục riêng `~/.claude-hand` | `CLAUDE_CONFIG_DIR=~/.claude-hand claude` rồi `/login` tài khoản thứ hai |
| `opencode` | OpenCode Go | `opencode auth login` chọn OpenCode Go; trên Console TẮT Extra Usage, để credit Console 0 |
| `gemini` | dự kiến | chưa dùng được (xem mục 3) |

Cấu hình dự án ở `.claude/hybrid-hands.json`, mục `ext_hand`: `order` (mặc định `codex`, `claude`, `opencode`), `backends.<tên>`, `timeout_min` (60), `max_tokens`, `sandbox` (`workspace-write`), sổ `ledger` `output/llm/hand_usage.json` (token, không USD), `quota_state` `output/llm/hand_quota.json`, `runs_dir` `output/llm/hand-ext`.

## 2. Một lượt giao việc

1. **Brief:** khuôn 7 mục (MỤC TIÊU, NGỮ CẢNH, PHẠM VI GHI, KHÔNG ĐƯỢC ĐỤNG, LUẬT BẮT BUỘC, KIỂM CHỨNG, TRẢ VỀ) vào file tạm trong scratchpad, ví dụ `<scratchpad>/brief-<nhãn>.md`. LUẬT BẮT BUỘC chép nguyên văn từ AGENTS.md/CLAUDE.md của repo, luôn có câu cấm đọc `.env`; PHẠM VI GHI liệt kê từng file.
2. **Run nền:** tool Bash với `run_in_background`:
   `hand-ext run --brief <file> --backend auto --label <nhãn> [--cwd D] [--model M] [--effort E] [--timeout-min M] [--max-tokens N] [--sandbox S]`
   Chờ thông báo khi lệnh thoát; không viết vòng chờ riêng. `auto` thử backend theo `order`, gặp hết hạn mức hoặc chưa đăng nhập thì sang backend kế tiếp.
3. **Đọc kết quả:** khối tóm tắt cuối output (backend, token, `used_percent`, `resets_at`) và `report.md` theo đường dẫn được in.
4. **Review:** brain tự `git diff` các file hand đã đổi; lỗi thì một lượt `run` mới với brief gọn chép sẵn phát hiện (hand ngoài không nhận SendMessage).
5. **Báo hạn mức:** backend, token, % hạn mức, thời điểm reset; không cần bảng USD vì gói không tính theo lượt. Xem trạng thái các gói: `hand-ext status`; tổng lượt và token: `hand-ext report [--since D] [--backend B] [--label L]`.

## 3. Xử lý lỗi và rủi ro

- **Mã thoát:** 0 ok, 1 failed, 2 sai cách dùng, 4 capped, 6 timeout, 7 mọi backend hết hạn mức hoặc chưa đăng nhập.
- **Exit 7 (`quota`, `not_logged_in` ở mọi backend):** giao lại việc cho `hybrid-hands:hand`; `not_logged_in` thì nhắc người dùng lệnh đăng nhập ở mục 1. Không dùng API key thay thế.
- **`capped` (exit 4, chạm `--max-tokens`):** đọc report xem phần đã xong; lượt tiếp là `run` mới với brief phần còn lại.
- **`timeout` (exit 6):** đọc report; việc dài thì chia nhỏ hoặc tăng `--timeout-min` có lý do.
- **Lỗi khác hoặc `doctor` không đạt:** `hybrid-hands:hand` làm dự phòng, báo người dùng kèm output thật.
- **OpenCode Go:** hết hạn mức mà Extra Usage còn bật hoặc Console còn credit thì bị tính tiền theo token, nên người dùng phải TẮT Extra Usage và để credit 0. Go hiện phục vụ DeepSeek V4.1 Flash bản 0910, chưa phải 1017; `doctor` cảnh báo khi lệch.
- **Gemini (dự kiến):** Gemini 4 Carbon chưa mở cho gói nào (chỉ Fairwind Program, 28/10/2026); gói AI Pro/Ultra đã chuyển sang Antigravity CLI. `backends.gemini` giữ khai báo nhưng không nằm trong `order`.
