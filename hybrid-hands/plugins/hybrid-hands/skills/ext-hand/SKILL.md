---
name: ext-hand
description: Giao một việc code hoặc tài liệu tự chứa cho hand ngoài chạy trên gói subscription thứ hai (mặc định DeepSeek V4.1 Flash qua DeepSeek Harness dsh hoặc OpenCode Go; Codex/Claude gọi tường minh) bằng lệnh hand-ext - viết brief vào file, run nền với --backend auto, đọc report, brain tự review diff, báo backend, token, % hạn mức và USD Go ước tính; xử lý exit 7, quota, capped, timeout, not_logged_in; cài đặt lần đầu từng backend; tuỳ chọn --browser cho dsh qua Playwright MCP cô lập, chỉ trang công khai, không TikTok. Không dùng API key; USD Go chỉ là ước tính từ token, Console là nguồn chuẩn. Từ khoá kích hoạt - "hand ngoài", "hand-ext", "gói thứ hai", "Codex", "OpenCode Go", "DeepSeek Harness", "dsh", "trình duyệt", "Playwright", "hand rẻ", "hạn mức hand", "mức đã dùng Go", "giao hand".
---

# Hand ngoài (hand-ext)

## Tóm tắt

- **Dùng khi (mặc định):** việc code/tài liệu tự chứa, phạm vi file rõ: sửa hay viết script, viết test, refactor trong vài file, soát hay sửa tài liệu, đọc code trả lời câu hỏi. Chạy trên gói subscription thứ hai để giữ hạn mức gói Claude chính cho brain.
- **Không dùng khi:** cần tool riêng của Claude Code (Chrome, MCP, Skill, đọc ảnh, SendMessage), chạy lệnh trả phí của dự án → `hybrid-hands:hand`; `hand-ext` thoát 7 hoặc lỗi → cũng `hybrid-hands:hand`.
- **Chuỗi bước:** brief vào file → `hand-ext run --backend auto` chạy nền → đọc report → brain review diff → báo backend, token, % hạn mức (Claude/Codex) hoặc % Go 5h/tuần kèm USD ước tính, thời điểm reset.
- **Luật cứng:** không bao giờ dùng hay tạo API key, không chuyển sang API khi hết hạn mức; Codex, DeepSeek Harness và OpenCode không chịu hook của Claude Code nên brief chép nguyên văn luật cấm (nhất là cấm đọc `.env`) và PHẠM VI GHI hẹp.
- **Luật dữ liệu:** không giao hand ngoài (dsh, opencode, codex, gemini — dữ liệu đi lên dịch vụ ngoài) việc phải đọc hoặc gửi secret (`.env`, token, mật khẩu, URL DB có mật khẩu) hay dữ liệu khách hàng (tài liệu, nội dung DB, log có dữ liệu khách hàng, tên/thông tin cá nhân); việc đó dùng hand Claude (`hybrid-hands:hand`). Được giao code, test, tài liệu kỹ thuật; tài liệu hay dữ liệu mẫu đã bỏ thông tin khách hàng và công khai được.
- **Cách ly:** `hand-ext run` mặc định tạo git worktree sạch (chỉ file tracked + thay đổi chưa commit/untracked không bị ignore, nên `.env` bị ignore không có trong workspace), chạy hand ở đó rồi lưu `changes.patch` và áp về repo; xem mục 2.
- **Mức Go:** hạn mức OpenCode Go tính bằng USD theo tháng cho từng model (DeepSeek V4.1 Flash: $100; 5 giờ = 20%, tuần = 50%, tháng = 100%). `dsh`/`opencode` ghi sổ toàn máy `~/.hybrid-hands/go_usage.jsonl`; `hand-ext usage [--json]` và `hand-ext status` đọc bản tóm tắt. Số từ sổ là **ước tính** dự phòng (OpenCode chưa công bố mốc reset, CLI không giữ `opencode.allowance`), Console là nguồn chuẩn; không bịa số khi thiếu đơn giá.
- **Số Go thật:** ngay sau mỗi lượt `dsh`/`opencode`, `hand-ext` chạy script fetch của plugin statusline rồi đọc cache chung `$CLAUDE_HOME/.statusline-go-usage.json` (cùng cache với status line) để in % Go thật 5h/tuần/tháng kèm giờ reset; `hand-ext status` chỉ đọc cache, `hand-ext usage` làm mới rồi in trước bảng ước tính. Tắt bằng `go_usage.live: false` trong `.claude/hybrid-hands.json` hoặc `HYBRID_HANDS_GO_LIVE=0`; đặt `HYBRID_HANDS_GO_FETCH` khi script không nằm trong plugin đã cài. Số ước tính từ sổ chỉ là dự phòng; khi báo người dùng thì báo số thật.
- **Backend:** mặc định `order` chỉ có `dsh` (DeepSeek Harness trên key OpenCode Go, DeepSeek V4.1 Flash reasoning `high`; việc thiết kế nhiều phần thì `--effort max`) rồi `opencode` (OpenCode Go, cùng model, biến thể max). `codex` (ChatGPT), `claude` (Claude tài khoản thứ hai) và `gemini` (dự kiến) vẫn khai báo trong `backends` nhưng không nằm trong `order`; gọi tường minh `--backend codex|claude|gemini` khi cần. `--browser` chỉ dùng với `dsh`.

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

Cấu hình dự án ở `.claude/hybrid-hands.json`, mục `ext_hand`: `order` (mặc định `dsh`, `opencode`), `backends.<tên>` (dsh có thêm `browser_dir`, mặc định `~/.dsh-hand/browser`; dsh/opencode có `go_price_per_mtok`), `timeout_min` (60), `max_tokens`, `sandbox` (`workspace-write`), `isolation` (`worktree` mặc định khi cwd là git repo, hoặc `none`), `worktree_root` (mặc định `~/.hybrid-hands/worktrees`; theo `HYBRID_HANDS_STATE_DIR` nếu đặt), sổ `ledger` `output/llm/hand_usage.json` (token), `quota_state` `output/llm/hand_quota.json`, `runs_dir` `output/llm/hand-ext`, `go_usage.ledger` (mặc định `~/.hybrid-hands/go_usage.jsonl`) và `go_usage.monthly_limit_usd` (mặc định 100; Go Plus 200).
- **Tự nén ngữ cảnh:** `backends.dsh.compact_at` và `backends.opencode.compact_at` (mặc định 272000 token) đặt ngưỡng tự nén cho riêng lượt chạy; `0` tắt. Với `dsh`, `context_window` (mặc định 1048576, khớp `templates/dsh-hand.yml`) quyết định `thresholdRatio` trong patch `compaction.patch.yml` của lượt; với `opencode`, hand đặt `OPENCODE_CONFIG_CONTENT` riêng lượt (`limit.input − reserved = compact_at`, `reserved` 20000). Không sửa `~/.dsh-hand/hand.patch.yml` hay `~/.config/opencode`; giá trị âm, không phải số nguyên, hoặc dsh `compact_at >= context_window` bị từ chối.

## 2. Một lượt giao việc

1. **Brief:** khuôn 7 mục (MỤC TIÊU, NGỮ CẢNH, PHẠM VI GHI, KHÔNG ĐƯỢC ĐỤNG, LUẬT BẮT BUỘC, KIỂM CHỨNG, TRẢ VỀ) vào file tạm trong scratchpad, ví dụ `<scratchpad>/brief-<nhãn>.md`. LUẬT BẮT BUỘC chép nguyên văn từ AGENTS.md/CLAUDE.md của repo, luôn có câu cấm đọc `.env`; PHẠM VI GHI liệt kê từng file.
2. **Run nền:** tool Bash với `run_in_background`:
   `hand-ext run --brief <file> --backend auto --label <nhãn> [--browser] [--cwd D] [--model M] [--effort E] [--timeout-min M] [--max-tokens N] [--sandbox S] [--isolation worktree|none] [--no-apply] [--keep-worktree]`
   Chờ thông báo khi lệnh thoát; không viết vòng chờ riêng. `auto` thử backend theo `order`, gặp hết hạn mức hoặc chưa đăng nhập thì sang backend kế tiếp. `--browser` chỉ dùng với `dsh`: `auto --browser` chỉ xét `dsh`; `--backend` khác `dsh` kèm `--browser` thoát 2. Khi bật, prompt có thêm luật trình duyệt và dsh nạp MCP Playwright cô lập cho riêng lượt chạy (không sửa patch chung). Mặc định `--isolation worktree`: hand chạy trong worktree tạm ngoài repo (HEAD + thay đổi chưa commit + untracked không ignore), sau đó `changes.patch` được áp về cwd gốc nếu không xung đột; `--no-apply` chỉ lưu patch, `--keep-worktree` giữ worktree để kiểm tra. Worktree được dọn cả khi timeout/lỗi; patch vẫn lưu. Cwd không phải git repo thì mặc định rơi về `none` kèm cảnh báo trong report; `--isolation worktree` tường minh mà không tạo được worktree thì thoát 2.
3. **Đọc kết quả:** khối tóm tắt cuối output (backend, token, `used_percent`/`resets_at` của backend, hoặc dòng `hạn mức: ~x% 5h, ~y% tuần (ước tính)` của Go) và `report.md` theo đường dẫn được in.
4. **Review:** brain tự `git diff` các file hand đã đổi; lỗi thì một lượt `run` mới với brief gọn chép sẵn phát hiện (hand ngoài không nhận SendMessage).
5. **Báo hạn mức:** backend, token, % hạn mức, thời điểm reset; với Go báo thêm % 5h/tuần và USD ước tính. Xem trạng thái các gói: `hand-ext status`; mức Go chi tiết: `hand-ext usage [--json]`; tổng lượt và token: `hand-ext report [--since D] [--backend B] [--label L]`; theo dõi lượt đang chạy và cây phiên/subagent: `hh-ps` (`--watch 5`, `--json`).

## 3. Xử lý lỗi và rủi ro

- **Mã thoát:** 0 ok, 1 failed, 2 sai cách dùng hoặc không tạo được worktree khi `isolation=worktree` được yêu cầu, 4 capped, 6 timeout, 7 mọi backend hết hạn mức hoặc chưa đăng nhập.
- **Cách ly worktree:** mặc định khi cwd là git repo; worktree chỉ có file tracked + thay đổi chưa commit của file tracked + file untracked không bị ignore, không bao giờ có file bị ignore (`.env`, `*.demo.env`...). Sau run, `changes.patch` nằm trong thư mục lượt chạy; áp bằng `git apply --check` rồi `git apply` nên xung đột thì không ghi đè thay đổi người dùng và report ghi `xung đột`. `--no-apply` chỉ lưu patch; `--keep-worktree` giữ worktree (mặc định dọn cả khi timeout/lỗi). Cwd không phải git repo: mặc định `none` kèm cảnh báo; `--isolation worktree` tường minh mà lỗi thì thoát 2, không âm thầm chạy trong repo gốc.
- **Exit 7 (`quota`, `not_logged_in` ở mọi backend):** giao lại việc cho `hybrid-hands:hand`; `not_logged_in` thì nhắc người dùng lệnh đăng nhập ở mục 1. Không dùng API key thay thế.
- **`capped` (exit 4, chạm `--max-tokens`):** đọc report xem phần đã xong; lượt tiếp là `run` mới với brief phần còn lại.
- **`timeout` (exit 6):** đọc report; việc dài thì chia nhỏ hoặc tăng `--timeout-min` có lý do.
- **Lỗi khác hoặc `doctor` không đạt:** `hybrid-hands:hand` làm dự phòng, báo người dùng kèm output thật.
- **OpenCode Go:** hết hạn mức mà Extra Usage còn bật hoặc Console còn credit thì bị tính tiền theo token, nên người dùng phải TẮT Extra Usage và để credit 0. Metadata models.dev vẫn ghi `release_date` 2026-09-10, nhưng OpenCode báo Go đã phục vụ bản 1017 dưới cùng id `deepseek-v4.1-flash` (khoảng 20/10/2026); `doctor` chỉ ghi chú, không coi là lỗi.
- **Sổ Go:** mỗi lượt `dsh`/`opencode` ghi `run_id`, `ended`, `backend`, `model`, `tokens`, `cost_usd`, `cost_source`, `cwd_basename` (không ghi đường dẫn tuyệt đối) vào `~/.hybrid-hands/go_usage.jsonl`; bản tóm tắt cạnh đó có cửa sổ trượt 5 giờ / 7 ngày / 30 ngày. Nếu CLI không lộ `opencode.allowance` thì chi phí là `estimated` từ token × `go_price_per_mtok` (mặc định giá peak: input $0,30, cached $0,006, output $1,20 mỗi 1M token); thiếu đơn giá thì `cost_usd = null`, `cost_source = unknown`. Cửa sổ Go có thể không trượt, nên số chỉ để ước lượng và **OpenCode Console là nguồn chuẩn**; đừng trình bày như số chính xác.
- **DeepSeek Harness (`dsh`):** dsh luôn đọc `<thư mục khởi chạy>/.env` (đã đọc mã nguồn bản 0.2.1-rc.5), nên `hand-ext` khởi chạy dsh từ `~/.dsh-hand/launch` (không có `.env`) và trỏ workspace sang repo bằng patch; không tạo `~/.dsh-hand/.env`. dsh không có luật chặn tool đọc `.env` theo mẫu file, nên brief vẫn phải chép luật cấm. Hết hạn mức (`QUOTA`, `RATE_LIMIT`) thì `auto` sang `opencode`. Bản dsh khác 0.2.1-rc.5 thì `doctor` không đạt tới khi đọc lại mã nguồn. `doctor` có dòng `browser`: thiếu `cli.js`/`ms-playwright` chỉ là ghi chú tuỳ chọn, không làm fail; nhưng `run --browser` sẽ báo lỗi rõ nếu thiếu.
- **Trình duyệt (`--browser`):** chỉ backend `dsh`, MCP server stdio `@deepseek-ai/dsh-mcp-client` tên `playwright` chạy `node <browser_dir>/node_modules/@playwright/mcp/cli.js --headless --isolated --browser chromium --blocked-origins "<5 origin TikTok>" --output-dir <run>/browser`, env chỉ `PLAYWRIGHT_BROWSERS_PATH=<browser_dir>/ms-playwright`. Chỉ duyệt trang công khai; không đăng nhập, không tạo tài khoản, không điền form, không mua, không vượt captcha; không mở TikTok; không tải hay chạy file tải về. `--blocked-origins` không phải ranh giới bảo mật và không chặn redirect, nên luật prompt là lớp chính. Không dùng API key hay key Go cho MCP; dsh lọc biến dạng key/token khỏi env con.
- **Gemini (dự kiến):** Gemini 4 Carbon chưa mở cho gói nào (chỉ Fairwind Program, 28/10/2026); gói AI Pro/Ultra đã chuyển sang Antigravity CLI. `backends.gemini` giữ khai báo nhưng không nằm trong `order`.
