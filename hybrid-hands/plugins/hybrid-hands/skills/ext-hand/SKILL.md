---
name: ext-hand
description: Giao một việc code hoặc tài liệu tự chứa cho hand ngoài chạy trên gói subscription thứ hai (mặc định dsh → codex → claude-v1 → claude-v2, native khi cùng account và đủ capability) bằng lệnh hand-ext - viết brief vào file, run nền với --backend auto, đọc report, Sol review diff, Opus đọc bàn giao, báo backend, token, % hạn mức và USD~ Go ước tính; xử lý exit 7, quota, capped, timeout, not_logged_in; cài đặt lần đầu từng backend; tuỳ chọn --browser cho dsh qua Playwright MCP cô lập, chỉ trang công khai, không TikTok. Không dùng API key; USD Go chỉ là ước tính từ token, Console là nguồn chuẩn. Từ khoá kích hoạt - "hand ngoài", "hand-ext", "gói thứ hai", "Codex", "OpenCode Go", "DeepSeek Harness", "dsh", "trình duyệt", "Playwright", "hand rẻ", "hạn mức hand", "mức đã dùng Go", "giao hand".
---

Tóm tắt cập nhật 0.35.0: cấu hình global và repo quyết định lựa chọn phiên/hand theo tài khoản.

Cấu hình ưu tiên: mặc định plugin → global `~/.hybrid-hands/config.json` (đổi đường dẫn bằng `HYBRID_HANDS_CONFIG`) → repo `.claude/hybrid-hands.json` → cờ CLI. Dict merge sâu; list/scalar thay nguyên. Global thiếu thì bỏ qua; global hỏng báo lỗi kèm đường dẫn và dừng. `hand-ext config --json` in cấu hình hiệu lực, nguồn từng key và đường dẫn file đã đọc. `ext_hand.claude_accounts` và `ext_hand.backends.*` đặt được ở global. Dưới Paseo, biến `HYBRID_HANDS_CONFIG` phải có trong môi trường daemon mới có tác dụng.

`ext_hand.native.{claude,codex}` nhận `auto` (mặc định) hoặc `off`. `hand-ext pick --json` trả `native` và `native_reason` theo cấu hình, account, model/effort; caller vẫn phải kiểm capability. `off` dùng hand-ext. Claude native phải khớp frontmatter agent (Opus 5.5 low); model/effort khác chạy qua wrapper.


## Chọn hand theo tài khoản

### Hand Paseo opt-in: ưu tiên trước ngoại lệ native

`shell` vẫn là mode mặc định. Chỉ repo được operator bật `ext_hand.mode=auto` hoặc `paseo-required` mới dùng managed hand; không tự sửa config hay bật ở repo khác. Bảng native bên dưới chỉ áp dụng đường cũ. Khi mode opt-in và daemon/provider/capability sẵn sàng, **intent mới vốn giao native Sol low** phải chạy `hand-ext run --backend auto --mode paseo-required --brief /ABS/brief.md --cwd /ABS/REPO`, không spawn native trực tiếp. Native đang tồn tại giữ nguyên, không migrate. Vẫn chạy `hand-ext pick --json` trước; dispatcher giữ order, account/model/effort, quota/day guards và pool chung `ext_hand.max_parallel` (1..4), không ép backend codex vì intent ban đầu là Sol low.

Thiếu daemon/provider/capability **trước dispatch**: `auto` quay đường shell cũ, `paseo-required` báo lỗi, không silent fallback. Parent/project/target không xác minh được thì chặn. Sau create/send hoặc ACK không rõ, reconcile exact invocation/attempt/epoch, giữ reservation; không tạo shell/native writer thứ hai.

Mỗi managed hand có workspace/worktree riêng trong **cùng verified project** với parent, caller gắn parent canonical và tab/track của parent; không hứa sidebar native lồng child. Theo quyết định 09/11/2026 (thay Q4), khi execution đã settled đầy đủ report/hooks thì chuyển `awaiting_review`, tự archive **exact child** và workspace riêng của child; không cần review để archive, không archive parent. Membership chỉ theo public `agent.workspaceId`, không theo cwd vì nhiều workspace local có thể cùng checkout. Chỉ archive workspace do plugin tạo, kể cả private LOCAL, khi mọi member cùng workspaceId đã archived (known closed child của plugin phải archive trước), không có `main_session`/role `main` hay agent không do plugin tạo. Giữ workspace local shared/main/unknown; không suy ownership từ tên hoặc cwd, không gom theo cwd hay di chuyển/xoá thư mục. Plugin worktree giữ nguyên quy tắc hiện có; archive local không xoá checkout, Paseo chỉ có thể xoá worktree do Paseo sở hữu. Lỗi visibility giữ lifecycle/data để retry, không tạo writer trùng. `managed archive` idempotent. Sol vẫn phải đọc diff/report và `review-approve` trước followup. Followup restore workspace rồi mở lại cùng exact child (giữ agent/workspace IDs) với brief tự chứa, epoch/request key và baseline mới; không phải CLI context resume, không tạo child trùng. Thiếu cwd/worktree thì chặn. Giữ history, report, patch, worktree và mọi thư mục/artifact; không cleanup. Archive chỉ đổi khả năng hiển thị ở sidebar Paseo, không đổi các dòng done của hh-ps/panel. Một managed execution là một hand trong pool, không tạo side-session root; token từ parser/ledger chuẩn, ACP chỉ projection, thiếu usage/quota giữ `?`.


Phiên chính mặc định Opus 5.5 high v1; có thể mở Opus high v2/v… hoặc Sol 6.1 high. Phiên phụ mặc định Sol 6.1 high, có thể là Opus 5.5 high đúng tài khoản v1/v2/v… . Đổi model/account: mở phiên mới từ bàn giao, không dùng `/model` giữa phiên.

Mặc định `ext_hand.order`: dsh (`deepseek-v4.1-flash`, effort `off`, thinking disabled) → codex (`gpt-6.1-sol`, low) → claude-v1 (Opus 5.5 low) → claude-v2 (Opus 5.5 low). `claude_accounts` lấy từ mặc định plugin → global `~/.hybrid-hands/config.json` → repo; v1=`~/.claude`, v2=`~/.claude-hand`, thêm v… bằng cấu hình. `claude-main` và `claude` chỉ là alias tương thích lần lượt của `claude-v1` và `claude-v2`.

Luôn chạy `hand-ext pick --json` trước để biết backend/model/effort/account, `native`/`native_reason` và lý do bỏ qua, kể cả trước native v1 để giữ chặn ≥5%/ngày (thiếu nguồn cũng chặn). Ở đường cũ, cùng account và tools chọn đúng model/effort mới native; khác account hoặc thiếu capability dùng `hand-ext run --backend auto`. Không tự áp native cho account khác.

| Phiên phụ | dsh | codex low | claude-v1 low | claude-v2 low | UI v1 low |
|---|---|---|---|---|---|
| Sol | hand-ext | native Codex (đường cũ; opt-in xem trên) | hand-ext | hand-ext | hand-ext claude-v1 |
| Opus v1 | hand-ext | hand-ext | Agent hybrid-hands:hand | hand-ext | Native khi preflight v1 đủ; thiếu thì hand-ext claude-v1 |
| Opus v2 | hand-ext | hand-ext | hand-ext | Agent hybrid-hands:hand | hand-ext claude-v1 |

Sáng tạo UI mặc định claude-v1 low. Native v1 chỉ khi `hand-ext pick --json` thực trả `claude-v1`, model `claude-opus-5-5`, effort `low`, đúng account và đủ capability. Pick trả dsh/codex chưa chứng minh guard v1 đã qua: dùng `hand-ext run --backend claude-v1` để wrapper enforce guard, không sửa config/order hoặc suy guard pass. Guard chặn thì không spawn native v1; ghi yêu cầu để Opus quyết. Công việc theo order tiếp tục backend pick chọn.
Native Codex đường cũ dùng `fork_turns=none`, brief tự chứa, luật dữ liệu nguyên văn; executor làm trực tiếp, không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác. Tổng native + hand-ext ≤ `ext_hand.max_parallel` (1..4); cùng file/phụ thuộc tuần tự. Unknown sau spawn phải reconcile/wait, không tạo duplicate writer. Không bật parallel-subagents, không đổi slots/config. Completed giữ tab/history, không archive parent. Native không tạo run/meta/report/token ledger hand-ext; usage qua runtime/Paseo, thiếu token/USD~/quota ghi `?`, không suy quota.

Review thấy lỗi: giao lại cùng backend đúng một lần; lần thứ hai vẫn hỏng chuyển backend kế tiếp theo order dsh → codex → claude-v1 → claude-v2. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do vào bàn giao để Opus quyết; không tự đổi effort. Exit 8: đợi slot, không đổi backend/tự làm.


### Review và follow-up managed

Sol lấy exact key bằng `hand-ext managed ls --cwd /ABS/REPO`, đọc diff/report trước `hand-ext managed review-approve --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH`. `hand-ext managed archive --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH` là thao tác idempotent sau settlement, không đợi review; `review-approve` vẫn bắt buộc trước followup. Giao tiếp bằng `hand-ext managed followup --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH --brief /ABS/fresh-brief.md`; key phải latest, epoch mới không resume CLI. Không archive parent hay cleanup worktree. Xem [recipe operator](../../../../README.md#vận-hành-managed-hand-paseo) khi cần setup/status; không tự chạy live setup từ một brief hand.

## Usage panel 0.26.0

`hh-ps --once` chạy một lần; `--json` giữ dữ liệu máy đọc, `--watch 5` theo dõi. Mặc định hiện đủ việc chạy/vừa xong theo `--since`, không gấp còn 3 việc và không ẩn cây đã xong (`--full`/`--ended` giữ tương thích). Mỗi dòng session/subagent/hand và phiên phụ mọi provider/backend có model, effort, USD~, quota tài khoản 5h/tuần, ended hoặc `đang chạy`, elapsed. Elapsed đang chạy tăng theo thời gian; ended cố định duration khi xong. Không hiện giờ bắt đầu trong text/panel/statusline; metadata/JSON vẫn giữ started. Thiếu nguồn hoặc legacy unknown hiện `?`, không bịa.

Giá chỉ từ [`config/model-prices.json`](../../config/model-prices.json), override bằng `HYBRID_HANDS_PRICING_FILE`; mỗi entry có source/price_date, file có verified_at. Mọi USD~ là ước tính offline trên gói subscription, không phải hoá đơn. Cache Claude dùng đúng giá cấu hình 5m/1h; không fallback theo họ/model khác. Nguồn giá công khai được xác minh ngày 2026-11-07 và lưu trong file canonical. Giá DeepSeek peak là ước tính bảo thủ. Không thêm bảng giá backend thứ hai.

Quota tài khoản lấy từ cache/sample sẵn có của đúng gói; thiếu 5h/tuần hiện `?`, tuyệt đối không suy token hay USD thành quota GPT. Phần riêng hand tuần chỉ thêm khi có nguồn và gắn nhãn riêng. Cả hai giao diện cây `hh-tree-pane` và `paseo-hh-tree` không hiện nhóm orphan hand-ext; `hh-ps` text/JSON vẫn giữ orphan.

Metadata mới giữ parent canonical, started, ended, status, exit_code, tokens, effort, duration cùng model/backend. `CODEX_THREAD_ID`/`PASEO_AGENT_ID` được đối chiếu thành sid canonical để gắn đúng cha; `HYBRID_HANDS_HAND_SCOPE` chỉ giới hạn số hand đồng thời, không phải ID cha. Cây bao gồm phiên Sol Codex/Claude/dsh và mọi loại agent/backend. Hand nhận brief trực tiếp là executor: làm trong phạm vi được giao, không gọi hand-ext, không mở side-session hay giao tiếp phiên khác. Luật Sol bắt buộc delegate chỉ áp dụng vai trò Sol; dùng `hand-ext run --backend auto` trừ ngoại lệ native trên Paseo nêu trên.



Opus chia brief thành các gói L1 độc lập khác file, chủ động lấp tối đa `side_session.max_parallel` Sol (mặc định 4). MỖI SOL chia brief độc lập khác file và chạy nền tổng native + hand-ext tối đa `ext_hand.max_parallel` hand (mặc định 4), chờ đủ tất cả kết thúc rồi Sol review. Cùng file hoặc phụ thuộc phải tuần tự; không ép song song. Có thể 16 hand tổng khi 4 Sol độc lập; không phải cap toàn máy 4. Hai giới hạn là số nguyên 1..4, có thể giảm, không >4. Scope hand riêng mỗi Sol qua `HYBRID_HANDS_HAND_SCOPE` = uuid Sol, giữ nguyên `CODEX_HOME` và parent Claude session. Exit 8: đợi slot/tiến trình đang chạy kết thúc rồi thử lại; không đổi backend hay tự làm như lỗi hand.


# Hand ngoài (hand-ext)

Trừ native đường cũ cùng tài khoản nêu trên, Sol **BẮT BUỘC giao code/test/tài liệu L0/L1** bằng `hand-ext run --backend auto` theo `ext_hand.order` của repo. Sol chỉ tự viết khi hand-ext thoát lỗi (ghi lý do và mã thoát vào bàn giao) hoặc việc cần secret/dữ liệu khách hàng theo luật dữ liệu. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do để Opus quyết. Exit 8: chờ slot.

Codex Sol và hand dùng chung `~/.codex-hand`: mỗi lượt hand override `model` bằng `-m`, `model_reasoning_effort` bằng `-c`, `sandbox_mode` bằng `-s`. Doctor không chặn nếu ba khóa thiếu/lệch và không ghi config; kiểm tra cài đặt, đăng nhập gói và khóa legacy không override như `service_tier` vẫn bắt buộc.

## Tóm tắt

- **Dùng khi (mặc định):** việc code/tài liệu tự chứa, phạm vi file rõ: sửa hay viết script, viết test, refactor trong vài file, soát hay sửa tài liệu, đọc code trả lời câu hỏi. Chạy trên gói subscription thứ hai để giữ hạn mức gói Claude chính cho brain. Phiên Sol mặc định là Codex (`side-session start --provider codex`, model `gpt-6.1-sol`, effort `high`).
- **Không dùng khi:** cần tool riêng Claude Code (Chrome, MCP, Skill, đọc ảnh, SendMessage), hoặc chạy lệnh trả phí của dự án: dùng hand Claude `hybrid-hands:hand` theo luật dữ liệu và phạm vi đã duyệt. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do để Opus quyết. Exit 8: chờ slot.
- **Chuỗi bước:** brief vào file → `hand-ext run --backend auto` chạy nền → đọc report → Sol review diff, Opus đọc bàn giao → báo backend, token, % hạn mức (Claude/Codex) hoặc % Go 5h/tuần kèm USD~ ước tính, thời điểm reset.
- **Luật cứng:** không bao giờ dùng hay tạo API key, không chuyển sang API khi hết hạn mức; Codex, DeepSeek Harness và Gemini không chịu hook của Claude Code nên brief chép nguyên văn luật cấm (nhất là cấm đọc `.env`) và PHẠM VI GHI hẹp.
- **Luật dữ liệu:** phiên phụ Sol được đọc secret và dữ liệu khách hàng như Opus; luật dưới áp cho hand ngoài (dsh, gemini, codex dùng làm hand). Không giao hand ngoài việc phải đọc hoặc gửi secret (`.env`, token, mật khẩu, URL DB có mật khẩu) hay dữ liệu khách hàng (tài liệu, nội dung DB, log có dữ liệu khách hàng, tên/thông tin cá nhân); việc đó dùng hand Claude (`hybrid-hands:hand`). Được giao code, test, tài liệu kỹ thuật; tài liệu hay dữ liệu mẫu đã bỏ thông tin khách hàng và công khai được.
- **Cách ly:** `hand-ext run` mặc định tạo git worktree sạch (chỉ file tracked + thay đổi chưa commit/untracked không bị ignore, nên `.env` bị ignore không có trong workspace), chạy hand ở đó rồi lưu `changes.patch` và áp về repo; xem mục 2.
- **Mức Go:** hạn mức OpenCode Go tính bằng USD theo tháng cho từng model (DeepSeek V4.1 Flash: $100; 5 giờ = 20%, tuần = 50%, tháng = 100%). `dsh` ghi sổ toàn máy (bản ghi cũ của backend `opencode` đã gỡ vẫn được tính) `~/.hybrid-hands/go_usage.jsonl`; `hand-ext usage [--json]` và `hand-ext status` đọc bản tóm tắt. Số từ sổ là **ước tính** dự phòng (OpenCode chưa công bố mốc reset, CLI không giữ `opencode.allowance`), Console là nguồn chuẩn; không bịa số khi thiếu đơn giá.
- **Số Go thật:** ngay sau mỗi lượt `dsh`, `hand-ext` chạy script fetch của plugin statusline rồi đọc cache chung `$CLAUDE_HOME/.statusline-go-usage.json` (cùng cache với status line) để in % Go thật 5h/tuần/tháng kèm giờ reset; `hand-ext status` chỉ đọc cache, `hand-ext usage` làm mới rồi in trước bảng ước tính. Tắt bằng `go_usage.live: false` trong `.claude/hybrid-hands.json` hoặc `HYBRID_HANDS_GO_LIVE=0`; đặt `HYBRID_HANDS_GO_FETCH` khi script không nằm trong plugin đã cài. Số ước tính từ sổ chỉ là dự phòng; khi báo người dùng thì báo số thật.
- **Backend:** Mặc định dsh (`deepseek-v4.1-flash`, effort `off`, thinking disabled) → codex (`gpt-6.1-sol`, low) → claude-v1 (Opus low) → claude-v2 (Opus low). Auto bỏ qua backend hết quota/chưa đăng nhập/bị chặn ngày. `--browser` chỉ dùng dsh. Cơ chế 429 quá tải và sổ Codex xem mục 3.

## Ba tầng và lane

| Tầng | Vai trò |
|---|---|
| Opus (brain, gói Claude chính) | Thư ký, solution architect, BA, product manager; phân lane, viết spec/plan L2/L3, duyệt tóm tắt, đọc bàn giao, không đọc diff task đã giao Sol |
| Sol (phiên phụ Codex `gpt-6.1-sol` effort high, tài khoản ChatGPT riêng, `CODEX_HOME` `~/.codex-hand`) | Lead tech, lead QA, quyền ngang Opus; viết spec L1, review code mọi hand mình giao, gọi `hand-ext run --backend auto` theo `ext_hand.order` |
| dsh (gói OpenCode Go) | Dev, tester |
| Hand Opus `low` (`hybrid-hands:hand`) | Việc sáng tạo: UI design, mockup, design token, câu chữ; phần code hoá giao hand mặc định theo `ext_hand.order` |

| Lane | Ai viết spec/plan | Ai duyệt | Ai làm | Ai review code |
|---|---|---|---|---|
| L0 (sửa nhanh) | Không viết spec | Không duyệt | hand theo `ext_hand.order` | Sol |
| L1, không có lựa chọn giải pháp | Sol | Không duyệt, Opus đọc bàn giao | hand theo `ext_hand.order` | Sol |
| L1 có lựa chọn giải pháp, hoặc thuộc mức kỹ | Sol, mở đầu bằng tóm tắt quyết định 1 trang | Opus đọc tóm tắt | hand theo `ext_hand.order` | Sol |
| L2/L3 | Opus | Người dùng | Opus cắt thành các gói cỡ L1, giao các phiên Sol | Sol |

Dự phòng: dsh 429 quá tải (`prefill_cap_refused`, không phải hết hạn mức) khi `--backend auto` → patch dsh ≥ `backends.dsh.capacity_wait_min_lines` (mặc định 30 dòng thêm+xoá, tính từ baseline) thì giữ worktree, chờ `backends.dsh.capacity_wait_seconds` (mặc định 180 s) rồi chạy tiếp dsh tối đa 2 lần (tổng 3); vẫn quá tải thì `failed`, giữ `changes.patch` + worktree, không áp về gốc, không chuyển codex. Patch nhỏ hơn ngưỡng → bỏ patch dsh, chạy lại brief gốc qua phần `cfg.order` còn lại sau dsh, preflight lần lượt, giữ CLI model/effort overrides; hết backend dùng được thì exit 7; `--browser` thì `failed` giữ patch vì không hỗ trợ fallback browser sang backend khác. `hand-ext` thoát 7 thì chạy `hand-ext doctor`, đọc lý do rồi mới chọn hand dự phòng. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do để Opus quyết. Exit 8: chờ slot.

## 1. Cài đặt lần đầu (mỗi máy, mỗi backend)

Lệnh chung: `hand-ext setup [--backend B|all] [--cwd D]` ghi cấu hình CLI và in lệnh đăng nhập; người dùng tự đăng nhập trong terminal riêng (agent không chạy, không thấy credential); rồi `hand-ext doctor [--backend B|all]` tới khi đạt. Nếu `hand-ext` không có trong PATH, gọi `${CLAUDE_PLUGIN_ROOT}/bin/hand-ext`.

| Backend | Gói | Người dùng tự đăng nhập |
|---|---|---|
| `codex` | ChatGPT, thư mục riêng `~/.codex-hand` | `CODEX_HOME=~/.codex-hand codex login --device-auth` |
| `claude-v2` | Claude tài khoản THỨ HAI, thư mục riêng `~/.claude-hand` | `CLAUDE_CONFIG_DIR=~/.claude-hand claude` rồi `/login` tài khoản thứ hai |
| `claude-v1` | Gói Claude CHÍNH `~/.claude`, model `claude-opus-5-5` effort `low`, mặc định cho sáng tạo | đã đăng nhập sẵn (không đăng nhập thêm) |
| `dsh` | OpenCode Go qua DeepSeek Harness, thư mục riêng `~/.dsh-hand`; tuỳ chọn `--browser` | cài `npm install -g @deepseek-ai/dsh@latest`; chép API key Go từ OpenCode Console vào `~/.dsh-hand/go.key`, `chmod 600`; TẮT Extra Usage, credit Console 0; cài trình duyệt theo mục 1.1 nếu dùng `--browser` |
| `gemini` | dự kiến | chưa dùng được (xem mục 3) |

### 1.1 Cài trình duyệt cho `dsh` (tuỳ chọn `--browser`)

Thư mục mặc định `~/.dsh-hand/browser` (đổi bằng `backends.dsh.browser_dir` trong `.claude/hybrid-hands.json`):

```sh
npm install --prefix ~/.dsh-hand/browser @playwright/mcp@0.0.83
PLAYWRIGHT_BROWSERS_PATH=~/.dsh-hand/browser/ms-playwright \
  ~/.dsh-hand/browser/node_modules/.bin/playwright install chromium
```

`hand-ext doctor --backend dsh` kiểm `node_modules/@playwright/mcp/cli.js` và `ms-playwright`; thiếu thì báo "thiếu (tuỳ chọn)" và không làm doctor fail. Chỉ cần cài khi dùng `--browser`.

Cấu hình dự án ở `.claude/hybrid-hands.json`, mục `ext_hand`: `order`, `backends.<tên>`, `timeout_min`, `max_tokens`, `sandbox`, `isolation`, `worktree_root`, `ledger`, `quota_state`, `runs_dir`, `go_usage.ledger`, `go_usage.monthly_limit_usd`. Đơn giá dùng bảng canonical nêu ở mục Usage panel; không duy trì `price_per_mtok`/`go_price_per_mtok` như bảng mặc định thứ hai. `claude-v1` giữ model/effort và `max_day_pct`; dsh giữ cấu hình browser và capacity wait.

- **Tự nén ngữ cảnh:** `backends.dsh.compact_at` (mặc định 472000 token) đặt ngưỡng tự nén cho riêng lượt chạy; `0` tắt. Với `dsh`, `context_window` (mặc định 1048576, khớp `templates/dsh-hand.yml`) quyết định `thresholdRatio` trong patch `compaction.patch.yml` của lượt. Không sửa `~/.dsh-hand/hand.patch.yml`; giá trị âm, không phải số nguyên, hoặc dsh `compact_at >= context_window` bị từ chối.

## 2. Một lượt giao việc

1. **Brief:** khuôn 7 mục (LUẬT BẮT BUỘC, KHÔNG ĐƯỢC ĐỤNG, TRẢ VỀ, MỤC TIÊU, NGỮ CẢNH, PHẠM VI GHI, KIỂM CHỨNG) vào file tạm trong scratchpad, ví dụ `<scratchpad>/brief-<nhãn>.md`. LUẬT BẮT BUỘC chép nguyên văn từ AGENTS.md/CLAUDE.md của repo, luôn có câu cấm đọc `.env`; PHẠM VI GHI liệt kê từng file. KIỂM CHỨNG ghi mức test: tối thiểu (chỉ case quan trọng) hoặc kỹ (chỉ 2 nhóm: tính năng tạo hứng thú/giữ chân khiến người dùng trả tiền; bảo mật chống tấn công từ ngoài).
2. **Run nền:** tool Bash với `run_in_background`:
   `hand-ext run --brief <file> --backend auto --label <nhãn> [--mode shell|auto|paseo-required] [--browser] [--cwd D] [--model M] [--effort E] [--timeout-min M] [--max-tokens N] [--sandbox S] [--isolation worktree|none] [--no-apply] [--keep-worktree]`
   Chờ thông báo khi lệnh thoát; không viết vòng chờ riêng. `auto` thử backend theo `order`, gặp hết hạn mức hoặc chưa đăng nhập thì sang backend kế tiếp. `--browser` chỉ dùng với `dsh`: `auto --browser` chỉ xét `dsh`; `--backend` khác `dsh` kèm `--browser` thoát 2. Khi bật, prompt có thêm luật trình duyệt và dsh nạp MCP Playwright cô lập cho riêng lượt chạy (không sửa patch chung). Mặc định `--isolation worktree`: hand chạy trong worktree tạm ngoài repo (HEAD + thay đổi chưa commit + untracked không ignore), sau đó `changes.patch` được áp về cwd gốc nếu không xung đột; `--no-apply` chỉ lưu patch, `--keep-worktree` giữ worktree để kiểm tra. Worktree được dọn cả khi timeout/lỗi; patch vẫn lưu. Cwd không phải git repo thì mặc định rơi về `none` kèm cảnh báo trong report; `--isolation worktree` tường minh mà không tạo được worktree thì thoát 2.
3. **Đọc kết quả:** khối tóm tắt cuối output (backend, token, `used_percent`/`resets_at` của backend, hoặc dòng `hạn mức: ~x% 5h, ~y% tuần (ước tính)` của Go) và `report.md` theo đường dẫn được in. Từ 0.22.0, thư mục lượt có thêm `brief.md`, `prompt.md`, `meta.json` (`base_commit`, `dirty`, `dirty_files`, `plugin_version`, `backend`, `model`, `label`) và `changes.base.patch` khi repo nguồn có thay đổi chưa commit; `events.jsonl` có thêm `ts` ISO 8601. Lượt cũ thiếu meta hoặc `ts` vẫn đếm được dòng, cột thời gian để `?`.
4. **Review:** Sol review code của mọi hand mình giao (diff các file hand đã đổi); Opus review spec/plan/giải pháp và đọc bàn giao, không đọc diff của task đã giao Sol. Lỗi thì một lượt `run` mới với brief gọn chép sẵn phát hiện (hand ngoài không nhận SendMessage).
5. **Báo hạn mức:** backend, token, % hạn mức, thời điểm reset; với Go báo thêm % 5h/tuần và USD~ ước tính. Xem trạng thái các gói: `hand-ext status`; mức Go chi tiết: `hand-ext usage [--json]`; tổng lượt và token: `hand-ext report [--since D] [--backend B] [--label L]`; đo hiệu quả từng lượt: `hand-ext measure --runs <dir> [--runs <dir>...] [--backend dsh] [--since YYYY-MM-DD]` (bảng dòng test/code/docs, % test, số lệnh test, giây test, giây lượt; gộp theo `plugin_version`); theo dõi lượt đang chạy và cây phiên/subagent: `hh-ps` (`--once`, `--watch 5`, `--json`).

## 3. Xử lý lỗi và rủi ro

- **Mã thoát:** 0 ok, 1 failed, 2 sai cách dùng hoặc không tạo được worktree khi `isolation=worktree` được yêu cầu, 4 capped, 6 timeout, 7 mọi backend hết hạn mức hoặc chưa đăng nhập.
- **Cách ly worktree:** mặc định khi cwd là git repo; worktree chỉ có file tracked + thay đổi chưa commit của file tracked + file untracked không bị ignore, không bao giờ có file bị ignore (`.env`, `*.demo.env`...). Sau run, `changes.patch` nằm trong thư mục lượt chạy; áp bằng `git apply --check` rồi `git apply` nên xung đột thì không ghi đè thay đổi người dùng và report ghi `xung đột`. `--no-apply` chỉ lưu patch; `--keep-worktree` giữ worktree (mặc định dọn cả khi timeout/lỗi). Cwd không phải git repo: mặc định `none` kèm cảnh báo; `--isolation worktree` tường minh mà lỗi thì thoát 2, không âm thầm chạy trong repo gốc.
- **Exit 7:** chạy `hand-ext doctor` trước, đọc lý do (cấu hình, đăng nhập hoặc quota), không giả định dsh hết quota. Không dùng API key thay thế. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do để Opus quyết. Exit 8: chờ slot.
- **`capped` (exit 4, chạm `--max-tokens`):** đọc report xem phần đã xong; lượt tiếp là `run` mới với brief phần còn lại.
- **`timeout` (exit 6):** đọc report; việc dài thì chia nhỏ hoặc tăng `--timeout-min` có lý do.
- **Lỗi khác hoặc `doctor` không đạt:** `hybrid-hands:hand` làm dự phòng, báo người dùng kèm output thật.
- **OpenCode Go:** hết hạn mức mà Extra Usage còn bật hoặc Console còn credit thì bị tính tiền theo token, nên người dùng phải TẮT Extra Usage và để credit 0. Metadata models.dev vẫn ghi `release_date` 2026-09-10, nhưng OpenCode báo Go đã phục vụ bản 1017 dưới cùng id `deepseek-v4.1-flash` (khoảng 20/10/2026); `doctor` chỉ ghi chú, không coi là lỗi.
- **Sổ Go:** mỗi lượt `dsh` ghi `run_id`, `ended`, `backend`, `model`, `tokens`, `cost_usd`, `cost_source`, `cwd_basename` (không ghi đường dẫn tuyệt đối) vào `~/.hybrid-hands/go_usage.jsonl`; bản tóm tắt cạnh đó có cửa sổ trượt 5 giờ / 7 ngày / 30 ngày. Nếu CLI không lộ `opencode.allowance` thì chi phí là `estimated` từ token × giá model canonical (giá DeepSeek peak là ước tính bảo thủ); thiếu đơn giá thì `cost_usd = null`, `cost_source = unknown`. Cửa sổ Go có thể không trượt, nên số chỉ để ước lượng và **OpenCode Console là nguồn chuẩn**; đừng trình bày như số chính xác.
- **Sổ Codex:** mỗi lượt backend `codex` kết thúc ghi đúng một dòng JSON vào `~/.hybrid-hands/codex_usage.jsonl` (hoặc `$HYBRID_HANDS_STATE_DIR/codex_usage.jsonl` khi đặt; test đổi `HOME` được). Schema `schema=1`: `run_id`, `ended`, `model`, `effort`, `tokens {input,cached_input,output}`, `cost_usd`, `cost_source` (`estimated`/`unknown`), `codex_home` chỉ basename (ví dụ `.codex-hand`), `windows {"5h": {"used_percent","resets_at"} | null, "7d": {...} | null}` phân loại bằng `window_minutes` (300 = 5h, 10080 = tuần), không chỉ cửa sổ lớn nhất; có gói chỉ có primary tuần, cửa sổ không có mẫu là null. Rollout cũ thiếu độ dài mới dùng primary=5h/secondary=tuần. Giá lấy từ model-id trong bảng canonical `config/model-prices.json`; thiếu/bất hợp lệ thì `cost_usd=null`, `cost_source=unknown`; đủ thì `(input−cached_input)×input + cached_input×cached + output×output` chia 1e6, `estimated`. Không ghi hội thoại, absolute path hay dùng tài khoản `~/.codex`. Lỗi ghi sổ chỉ cảnh báo, không làm fail lượt.
- **DeepSeek Harness (`dsh`):** dsh luôn đọc `<thư mục khởi chạy>/.env` (đã đọc mã nguồn bản 0.2.1-rc.5), nên `hand-ext` khởi chạy dsh từ `~/.dsh-hand/launch` (không có `.env`) và trỏ workspace sang repo bằng patch; không tạo `~/.dsh-hand/.env`. dsh không có luật chặn tool đọc `.env` theo mẫu file, nên brief vẫn phải chép luật cấm. Bản dsh khác 0.2.1-rc.5 thì `doctor` không đạt tới khi đọc lại mã nguồn. `doctor` có dòng `browser`: thiếu `cli.js`/`ms-playwright` chỉ là ghi chú tuỳ chọn, không làm fail; nhưng `run --browser` sẽ báo lỗi rõ nếu thiếu. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do để Opus quyết. Exit 8: chờ slot.
- **dsh trong sandbox Codex (`CODEX_SANDBOX=seatbelt`):** macOS cấm lồng `sandbox-exec`, nên `workspace-write` được đổi thành `danger-full-access` cho dsh (seatbelt ngoài vẫn giới hạn quyền ghi; mode thật ghi vào `meta.json` của lượt); `read-only` thì dsh từ chối chạy (fail-closed, `auto` coi dsh là backend không dùng được) — dùng `workspace-write` hoặc hand Claude.
- **429 `prefill_cap_refused`:** Go quá tải tạm thời (`at capacity`, `retry shortly`), không phải hết hạn mức; `hand-ext` không ghi `quota_state`. Với `--backend auto`, hand-ext đếm patch dsh do hand tạo từ baseline (thêm+xoá, gồm file mới/staged): nếu ≥ `backends.dsh.capacity_wait_min_lines` (mặc định 30) thì giữ nguyên worktree, chờ `backends.dsh.capacity_wait_seconds` (mặc định 180 s, 0 để test) rồi chạy tiếp dsh với prompt có ghi chú "đã có patch, làm tiếp", tối đa 2 lần chạy tiếp (tổng 3 lần). Vẫn quá tải: `failed`, giữ `changes.patch` và worktree, không áp patch dở về source, không chuyển codex dù số dòng giảm. Patch dưới ngưỡng (kể cả rỗng): bỏ patch dsh trong worktree, không áp source, chạy lại brief gốc qua các backend còn lại sau dsh trong `cfg.order`, preflight lần lượt; giữ CLI overrides `--model`/`--effort` theo run. Không gọi backend ngoài order; hết backend dùng được thì exit 7. `--browser` không fallback backend khác: `failed`, giữ worktree và patch, ghi lý do. Lỗi đếm patch hoặc `isolation=none`: fail-closed, giữ patch/dữ liệu, không reset source. Khi đã chọn nhánh giữ patch lớn, lượt chạy tiếp lỗi khác (quota/auth/timeout/lỗi chung) cũng giữ worktree và patch, không áp source và không chuyển codex; vẫn ghi quota thật nếu có. `--backend dsh` tường minh giữ hành vi cũ; quota thật giữ quy tắc cũ.
- **Trình duyệt (`--browser`):** chỉ backend `dsh`, MCP server stdio `@deepseek-ai/dsh-mcp-client` tên `playwright` chạy `node <browser_dir>/node_modules/@playwright/mcp/cli.js --headless --isolated --browser chromium --blocked-origins "<5 origin TikTok>" --output-dir <run>/browser`, env chỉ `PLAYWRIGHT_BROWSERS_PATH=<browser_dir>/ms-playwright`. Chỉ duyệt trang công khai; không đăng nhập, không tạo tài khoản, không điền form, không mua, không vượt captcha; không mở TikTok; không tải hay chạy file tải về. `--blocked-origins` không phải ranh giới bảo mật và không chặn redirect, nên luật prompt là lớp chính. Không dùng API key hay key Go cho MCP; dsh lọc biến dạng key/token khỏi env con.
- **`claude-v1` (sáng tạo):** dùng code backend `claude` nhưng trỏ gói chính `~/.claude`, mặc định `claude-opus-5-5` effort `low`, hạn mức ghi theo khoá riêng và nằm trong `order`. Trước khi chạy, `hand-ext` tính % hạn mức tuần Claude máy này đã dùng từ 0h hôm nay (USD từ ledger statusline chia USD/1% ghim); từ `claude_accounts.v1.max_day_pct` (mặc định 5%) trở lên hoặc không tính được thì thoát 7, ghi yêu cầu vào bàn giao để Opus quyết. Mặc định dùng cho việc sáng tạo (UI design, mockup, design token, câu chữ); code hoá giao hand theo `ext_hand.order`.
- **Gemini (dự kiến):** Gemini 4 Carbon chưa mở cho gói nào (chỉ Fairwind Program, 28/10/2026); gói AI Pro/Ultra đã chuyển sang Antigravity CLI. `backends.gemini` giữ khai báo nhưng không nằm trong `order`.

## Tên agent và workspace Paseo — 0.36.1

Tên agent và workspace của phiên phụ có dạng `<tên> · <loại> phụ`: ví dụ `qa · Sol phụ` (Codex), `qa · Opus v1 phụ`, `qa · Opus v2 phụ` (Claude theo account) hoặc `qa · dsh phụ`. Main và workspace shared giữ title hiện có.

Managed agent và workspace có dạng `<tên cha> › hand <backend> · <label>`, ví dụ `qa › hand codex · docs`. Cha được xác minh là main dùng `chính`, cha chưa xác định dùng `?` (ví dụ `? › hand dsh · docs`); không suy main từ cwd hay tên. Tên tối đa 60 ký tự; cắt label để giữ tiền tố cha và backend. Không đưa path, nội dung brief hay secret vào tên.

Naming áp dụng khi create, `side-session send` và managed followup; lặp lại cùng tên là idempotent, không tạo agent/workspace mới. Dùng API public Paseo 0.15.0: `createAgent` nhận `title`, đổi tên agent bằng `client.updateAgent(agentId, {name: title})` (đọc lại ở `.title`), đổi tên workspace bằng `client.setWorkspaceTitle(workspaceId, title)` (trả `{title}`). Workspace create chưa có title option nên đặt tên sau create. Hai method đổi tên không nằm trong required capabilities preflight: naming là best effort, lỗi chỉ cảnh báo, không chặn lifecycle; `ls`/`watch` retry hữu hạn, không chờ vô hạn hay tạo writer trùng.

Sửa tên cũ bằng các lệnh sau; mặc định dry-run, thêm `--apply` mới ghi:

```bash
side-session tidy --names --name qa
side-session tidy --names --name qa --apply
hand-ext managed names --cwd /ABS/REPO
hand-ext managed names --cwd /ABS/REPO --apply
```

`side-session tidy --names [--name NAME] [--apply]` chỉ sửa tên side-session do plugin sở hữu; bỏ `--name` để xét các phiên trong phạm vi state. `hand-ext managed names --cwd /ABS [--apply]` là thao tác tương đương cho managed hand. Dry-run không ghi; apply chỉ đổi tên agent/workspace plugin-owned được xác minh, chặn main, shared, foreign và workspace có member chưa rõ ownership. Không suy ownership từ title/cwd. Cả hai lặp an toàn và không archive. `side-session tidy` không có `--names` vẫn giữ contract archive hiện có; naming không đổi review gate, restore/send, IDs, history, worktree hay artifacts.

## GC worktree hand và disk guard

`hand-ext gc [--cwd /ABS/REPO] [--json] [--apply]` mặc định dry-run, chỉ đọc metadata ownership/registry/git và kích thước. Apply có khoá + recheck, chỉ xoá worktree sạch đã kết thúc có completion evidence hợp lệ; running/dirty/unknown, managed chưa settled hoặc detached HEAD đã đổi khỏi base đều giữ. Không force, không xoá patch/report hay `output/llm/`; ignored files trong worktree bị xoá cùng worktree. Nhánh giữ nguyên; journal `<machine_state_dir>/worktree-gc.jsonl` giữ HEAD/branch cho khôi phục tracked commits, không phục hồi ignored files. Tôn trọng brief/session cấm apply hoặc yêu cầu duyệt.

Mỗi run isolation tự gọi GC trước disk guard, chỉ lớp `finished` (`ext_hand.worktree_gc.auto=finished|off`, mặc định `finished`; lỗi chỉ cảnh báo). Lớp `preserved` (dirty nhưng `changes.patch` khớp diff hiện tại của run bắt đầu sạch) chỉ xoá bằng `--apply --include-preserved`. Run lỗi giữ worktree (nhánh giữ patch dsh, kể cả lượt cuối quá tải) tự xoá worktree ngay khi run bắt đầu sạch và `changes.patch` khớp diff hiện tại (rỗng = sạch); không khớp/lỗi xác minh, run bắt đầu dirty, lượt quá tải còn chạy tiếp hoặc `--keep-worktree` thì giữ. Dry-run liệt kê thêm `age_seconds` và bytes mọi mục; registry còn worktree sống không bị xoá theo hạn 7 ngày.

Trước tạo isolated worktree, disk guard cảnh báo dưới `disk_guard.warn_gb=20` GiB và chặn dưới `disk_guard.block_gb=5` GiB, exit 9. `--ignore-disk-guard` chỉ vượt chặn khi được phép chủ động. Sparse P4 bị chặn bởi S0 FAIL baseline `isolation.prepare`; không quảng bá `worktree_sparse_exclude` hay `--no-sparse` là đã có.
