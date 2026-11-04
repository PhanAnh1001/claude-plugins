---
name: ext-hand
description: Giao một việc code hoặc tài liệu tự chứa cho hand ngoài chạy trên gói subscription thứ hai (mặc định DeepSeek V4.1 Flash qua DeepSeek Harness dsh hoặc OpenCode Go; Codex/Claude gọi tường minh) bằng lệnh hand-ext - viết brief vào file, run nền với --backend auto, đọc report, brain tự review diff, báo backend, token, % hạn mức; xử lý exit 7, quota, capped, timeout, not_logged_in; cài đặt lần đầu từng backend; tuỳ chọn --browser cho dsh qua Playwright MCP cô lập, chỉ trang công khai, không TikTok. Không dùng API key, không tính USD. Từ khoá kích hoạt - "hand ngoài", "hand-ext", "gói thứ hai", "Codex", "OpenCode Go", "DeepSeek Harness", "dsh", "trình duyệt", "Playwright", "hand rẻ", "hạn mức hand", "giao hand".
---

# Hand ngoài (hand-ext)

## Tóm tắt

- **Dùng khi (mặc định):** việc code/tài liệu tự chứa, phạm vi file rõ: sửa hay viết script, viết test, refactor trong vài file, soát hay sửa tài liệu, đọc code trả lời câu hỏi. Chạy trên gói subscription thứ hai để giữ hạn mức gói Claude chính cho brain.
- **Không dùng khi:** cần tool riêng của Claude Code (Chrome, MCP, Skill, đọc ảnh, SendMessage), chạy lệnh trả phí của dự án → `hybrid-hands:hand`; `hand-ext` thoát 7 hoặc lỗi → cũng `hybrid-hands:hand`.
- **Chuỗi bước:** brief vào file → `hand-ext run --backend auto` chạy nền → đọc report → brain review diff → báo backend, token, % hạn mức, thời điểm reset.
- **Luật cứng:** không bao giờ dùng hay tạo API key, không chuyển sang API khi hết hạn mức; Codex, DeepSeek Harness và OpenCode không chịu hook của Claude Code nên brief chép nguyên văn luật cấm (nhất là cấm đọc `.env`) và PHẠM VI GHI hẹp.
- **Backend:** mặc định `order` chỉ có `dsh` (DeepSeek Harness trên key OpenCode Go, DeepSeek V4.1 Flash reasoning `max`) rồi `opencode` (OpenCode Go, cùng model, biến thể max). `codex` (ChatGPT), `claude` (Claude tài khoản thứ hai) và `gemini` (dự kiến) vẫn khai báo trong `backends` nhưng không nằm trong `order`; gọi tường minh `--backend codex|claude|gemini` khi cần. `--browser` chỉ dùng với `dsh`.

## 1. Cài đặt lần đầu (mỗi máy, mỗi backend)

Lệnh chung: `hand-ext setup [--backend B|all] [--cwd D]` ghi cấu hình CLI và in lệnh đăng nhập; người dùng tự đăng nhập trong terminal riêng (agent không chạy, không thấy credential); rồi `hand-ext doctor [--backend B|all]` tới khi đạt. Nếu `hand-ext` không có trong PATH, gọi `${CLAUDE_PLUGIN_ROOT}/bin/hand-ext`.

| Backend | Gói | Người dùng tự đăng nhập |
|---|---|---|
| `codex` | ChatGPT, thư mục riêng `~/.codex-hand` | `CODEX_HOME=~/.codex-hand codex login --device-auth` |
| `claude` | Claude tài khoản THỨ HAI, thư mục riêng `~/.claude-hand` | `CLAUDE_CONFIG_DIR=~/.claude-hand claude` rồi `/login` tài khoản thứ hai |
| `dsh` | OpenCode Go qua DeepSeek Harness, thư mục riêng `~/.dsh-hand`; tuỳ chọn `--browser` | cài `npm install -g @deepseek-ai/dsh@latest`; chép API key Go từ OpenCode Console vào `~/.dsh-hand/go.key`, `chmod 600`; TẮT Extra Usage, credit Console 0; cài trình duyệt theo mục 1.1 nếu dùng `--browser` |
| `opencode` | OpenCode Go | `opencode auth login` chọn OpenCode Go; trên Console TẮT Extra Usage, để credit Console 0 |
| `gemini` | dự kiến | chưa dùng được (xem mục 3) |

### 1.1 Cài trình duyệt cho `dsh` (tuỳ chọn `--browser`)

Thư mục mặc định `~/.dsh-hand/browser` (đổi bằng `backends.dsh.browser_dir` trong `.claude/hybrid-hands.json`):

```sh
npm install --prefix ~/.dsh-hand/browser @playwright/mcp@0.0.83
PLAYWRIGHT_BROWSERS_PATH=~/.dsh-hand/browser/ms-playwright \
  ~/.dsh-hand/browser/node_modules/.bin/playwright install chromium
```

`hand-ext doctor --backend dsh` kiểm `node_modules/@playwright/mcp/cli.js` và `ms-playwright`; thiếu thì báo "thiếu (tuỳ chọn)" và không làm doctor fail. Chỉ cần cài khi dùng `--browser`.

Cấu hình dự án ở `.claude/hybrid-hands.json`, mục `ext_hand`: `order` (mặc định `dsh`, `opencode`), `backends.<tên>` (dsh có thêm `browser_dir`, mặc định `~/.dsh-hand/browser`), `timeout_min` (60), `max_tokens`, `sandbox` (`workspace-write`), sổ `ledger` `output/llm/hand_usage.json` (token, không USD), `quota_state` `output/llm/hand_quota.json`, `runs_dir` `output/llm/hand-ext`.

## 2. Một lượt giao việc

1. **Brief:** khuôn 7 mục (MỤC TIÊU, NGỮ CẢNH, PHẠM VI GHI, KHÔNG ĐƯỢC ĐỤNG, LUẬT BẮT BUỘC, KIỂM CHỨNG, TRẢ VỀ) vào file tạm trong scratchpad, ví dụ `<scratchpad>/brief-<nhãn>.md`. LUẬT BẮT BUỘC chép nguyên văn từ AGENTS.md/CLAUDE.md của repo, luôn có câu cấm đọc `.env`; PHẠM VI GHI liệt kê từng file.
2. **Run nền:** tool Bash với `run_in_background`:
   `hand-ext run --brief <file> --backend auto --label <nhãn> [--browser] [--cwd D] [--model M] [--effort E] [--timeout-min M] [--max-tokens N] [--sandbox S]`
   Chờ thông báo khi lệnh thoát; không viết vòng chờ riêng. `auto` thử backend theo `order`, gặp hết hạn mức hoặc chưa đăng nhập thì sang backend kế tiếp. `--browser` chỉ dùng với `dsh`: `auto --browser` chỉ xét `dsh`; `--backend` khác `dsh` kèm `--browser` thoát 2. Khi bật, prompt có thêm luật trình duyệt và dsh nạp MCP Playwright cô lập cho riêng lượt chạy (không sửa patch chung).
3. **Đọc kết quả:** khối tóm tắt cuối output (backend, token, `used_percent`, `resets_at`) và `report.md` theo đường dẫn được in.
4. **Review:** brain tự `git diff` các file hand đã đổi; lỗi thì một lượt `run` mới với brief gọn chép sẵn phát hiện (hand ngoài không nhận SendMessage).
5. **Báo hạn mức:** backend, token, % hạn mức, thời điểm reset; không cần bảng USD vì gói không tính theo lượt. Xem trạng thái các gói: `hand-ext status`; tổng lượt và token: `hand-ext report [--since D] [--backend B] [--label L]`.

## 3. Xử lý lỗi và rủi ro

- **Mã thoát:** 0 ok, 1 failed, 2 sai cách dùng, 4 capped, 6 timeout, 7 mọi backend hết hạn mức hoặc chưa đăng nhập.
- **Exit 7 (`quota`, `not_logged_in` ở mọi backend):** giao lại việc cho `hybrid-hands:hand`; `not_logged_in` thì nhắc người dùng lệnh đăng nhập ở mục 1. Không dùng API key thay thế.
- **`capped` (exit 4, chạm `--max-tokens`):** đọc report xem phần đã xong; lượt tiếp là `run` mới với brief phần còn lại.
- **`timeout` (exit 6):** đọc report; việc dài thì chia nhỏ hoặc tăng `--timeout-min` có lý do.
- **Lỗi khác hoặc `doctor` không đạt:** `hybrid-hands:hand` làm dự phòng, báo người dùng kèm output thật.
- **OpenCode Go:** hết hạn mức mà Extra Usage còn bật hoặc Console còn credit thì bị tính tiền theo token, nên người dùng phải TẮT Extra Usage và để credit 0. Metadata models.dev vẫn ghi `release_date` 2026-09-10, nhưng OpenCode báo Go đã phục vụ bản 1017 dưới cùng id `deepseek-v4.1-flash` (khoảng 20/10/2026); `doctor` chỉ ghi chú, không coi là lỗi.
- **DeepSeek Harness (`dsh`):** dsh luôn đọc `<thư mục khởi chạy>/.env` (đã đọc mã nguồn bản 0.2.1-rc.5), nên `hand-ext` khởi chạy dsh từ `~/.dsh-hand/launch` (không có `.env`) và trỏ workspace sang repo bằng patch; không tạo `~/.dsh-hand/.env`. dsh không có luật chặn tool đọc `.env` theo mẫu file, nên brief vẫn phải chép luật cấm. Hết hạn mức (`QUOTA`, `RATE_LIMIT`) thì `auto` sang `opencode`. Bản dsh khác 0.2.1-rc.5 thì `doctor` không đạt tới khi đọc lại mã nguồn. `doctor` có dòng `browser`: thiếu `cli.js`/`ms-playwright` chỉ là ghi chú tuỳ chọn, không làm fail; nhưng `run --browser` sẽ báo lỗi rõ nếu thiếu.
- **Trình duyệt (`--browser`):** chỉ backend `dsh`, MCP server stdio `@deepseek-ai/dsh-mcp-client` tên `playwright` chạy `node <browser_dir>/node_modules/@playwright/mcp/cli.js --headless --isolated --browser chromium --blocked-origins "<5 origin TikTok>" --output-dir <run>/browser`, env chỉ `PLAYWRIGHT_BROWSERS_PATH=<browser_dir>/ms-playwright`. Chỉ duyệt trang công khai; không đăng nhập, không tạo tài khoản, không điền form, không mua, không vượt captcha; không mở TikTok; không tải hay chạy file tải về. `--blocked-origins` không phải ranh giới bảo mật và không chặn redirect, nên luật prompt là lớp chính. Không dùng API key hay key Go cho MCP; dsh lọc biến dạng key/token khỏi env con.
- **Gemini (dự kiến):** Gemini 4 Carbon chưa mở cho gói nào (chỉ Fairwind Program, 28/10/2026); gói AI Pro/Ultra đã chuyển sang Antigravity CLI. `backends.gemini` giữ khai báo nhưng không nằm trong `order`.
