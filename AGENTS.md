# Hướng dẫn sống cho repo claude-plugins

Tóm tắt: làm đúng phạm vi brief, giữ luật dữ liệu và kiểm chứng thay đổi trước khi bàn giao.

## Phạm vi và vai trò

**Profile theo repo:** mỗi repo bắt buộc có khoá `profile` = `claude-mono` | `gpt-mono` | `hybrid`; thiếu thì `hand-ext pick/run`, `side-session start` và hook báo lỗi kèm `hand-ext profile set <tên>`. Chỉ đặt profile sau khi người dùng chốt cho repo đó; đổi profile thì mở phiên mới. `hand-ext profile` in bảng vai hiệu lực và nguồn từng ô; ghi đè ô ở `profiles.<tên>.<vai>` (vai có bậc: `collect.1`, `collect.2`, `chrome.1`, `chrome.2`).

| Vai | `claude-mono` | `gpt-mono` | `hybrid` |
|---|---|---|---|
| super brain | không có | không có | Claude v2 `claude-opus-5-5` high |
| brain | Claude v1 `claude-opus-5-5` high | GPT `gpt-6.1-sol` high | như `gpt-mono` |
| code | Claude v1 `claude-opus-5-5` low | GPT `gpt-6.1-sol` low | như `gpt-mono` |
| collect B1 / B2 | Claude v1 `claude-sonnet-5-5` low / medium | GPT `gpt-6.1-terra` low / low | như `gpt-mono` |
| chrome B1 / B2 | Claude v1 `claude-sonnet-5-5` low / medium | Claude v2 `claude-sonnet-5-5` low / medium | như `gpt-mono` |

Đọc brief, AGENTS.md/CLAUDE.md ở thư mục áp dụng trước khi sửa. Brief thiếu PHẠM VI GHI hoặc ghi CHỈ ĐỌC thì chỉ đọc; không mở rộng phạm vi. Giữ thay đổi chưa commit của người khác; cùng file/phụ thuộc phải tuần tự. Không nạp luật của `dev-workflow/` cho công việc hybrid-hands không liên quan.

**Brain** (phiên chính ở profile mono, phiên phụ ở mọi profile): brainstorm, viết spec/plan, chia việc, giao tối đa 4 subagent song song khác file (cùng file/phụ thuộc tuần tự), review code mình giao. Trước mỗi lượt giao chạy `hand-ext pick --role code|collect|chrome [--tier 1|2] --json`: `native` true → subagent native đúng `model`/`effort` pick trả (Claude: tool Agent `hybrid-hands:hand` với `model` = `agent_model`; Codex: subagent native `fork_turns=none`); `native` false → `hand-ext run --role … --tier …`. Vai `code` hỏng thì giao lại cùng bậc một lần rồi brain quyết. Native không tạo run/meta/report/token ledger hand-ext; usage qua runtime/Paseo, thiếu token/USD~/quota ghi `?`, không suy quota. Unknown sau spawn phải reconcile/wait, không tạo duplicate writer.

**Super brain** (chỉ `hybrid`, phiên chính Claude v2 mở bằng `side-session start --main --provider claude --account v2`, tuỳ chọn `--model claude-fable-5-2 --effort low`): viết/duyệt spec và plan, mở phiên brain bằng `side-session start`, review bàn giao `.done`; không code, không gọi `hand-ext pick/run`. L2/L3 người dùng duyệt spec/plan.

**Thang 2 bậc cho thu thập dữ liệu** (`collect`, `chrome`): gói ít code bắt đầu B1, gói phải viết script bắt đầu B2. B1 hỏng → chạy lại đúng một lần ở B2 bằng subagent mới, brief chép phần đã kiểm đạt (file:dòng) và chỉ giao phần thiếu (`hand-ext run --tier 2 --escalated-from RUN_ID` khi chạy qua hand-ext); B2 hỏng → dừng báo người dùng (ở `hybrid` báo super brain qua bàn giao). Hỏng = subagent báo chưa xong, `hand-ext run` thoát 1/4/6, hoặc brain kiểm mẫu không đạt. Không nâng khi thoát 7/8/9 hay vi phạm an toàn. Lượt native ghi `hand-ext ladder log --role … --tier … --result ok|fail`; `hand-ext ladder stats` in tỉ lệ B1 đạt và tỉ lệ nâng.

**Hết quota:** không đổi tài khoản. Phiên trong Paseo đã đăng ký limit-watch thì chạy tiếp khi quota về; không thì ghi checkpoint vào bàn giao rồi dừng báo người dùng. Exit 8: đợi slot, không đổi backend/tự làm.

**Guard ngày v1:** cấu hình theo tài khoản `ext_hand.claude_accounts.v1` với `day_guard`, `max_day_pct`, `day_guard_days` (ví dụ 3%, `["sat","sun"]`), bật ở repo ở nhà. Guard chặn hoặc thiếu nguồn đo thì `pick` trả `native` false kèm lý do; không giao subagent v1, dừng báo người dùng.

**Hand executor:** nhận brief trực tiếp, làm đúng phần được giao, không gọi hand-ext, không mở side-session, không recursion hay giao tiếp phiên khác, không review việc hand khác. Chỉ brain có quyền chia hand theo brief/policy. `claude_accounts` lấy từ mặc định plugin → global → repo; v1=`~/.claude`, v2=`~/.claude-hand`, thêm v… bằng cấu hình; `claude-main` và `claude` chỉ là alias tương thích của `claude-v1` và `claude-v2`. Đổi model/account mở phiên mới từ bàn giao, không `/model` giữa phiên.

Xong một tính năng (test hẹp xanh, đã review) thì brain/super brain điều phối commit, push nhánh rồi merge ngay vào `main` và push `main` (người dùng chốt 08/11/2026); hand executor mặc định không commit/push, chỉ được commit/push trong gói Git riêng do brain chỉ thị rõ repository, hành động, branch và remote nếu push; chỉ file trong phạm vi, không vượt chỉ dẫn ưu tiên cao hơn/runtime, báo lệnh/SHA/branch/remote/kết quả; nhiệm vụ triển khai/test không cấp quyền Git, vẫn cấm hand merge/force push/viết lại lịch sử. Ngoài trường hợp đó không commit/push mặc định; không chạy lệnh phá hoại. Riêng công việc usage panel: không sửa `.claude/hybrid-hands.json`, `~/.codex/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings. Không xoá/di chuyển/dọn `output/llm/`. Shell dùng cwd/workdir hoặc đường dẫn tuyệt đối, không `cd <dir> && ...`. Không vòng chờ vô hạn; kết thúc tiến trình nền mình tạo trước báo cáo. Không tải/mua/gọi API trả phí hay tạo/dùng API key nếu brief không giao rõ và có trần chi phí.

Ngoại lệ sửa `claude-plugins` từ repo khác (người dùng chốt 16/11/2026, nguyên văn: "sửa lại luật để cho phép các repo khác sửa claude-plugins"): việc thuộc repo khác vẫn làm ở phiên brain riêng của repo đó, nhưng phiên brain của repo bất kỳ được sửa repo `claude-plugins` ngay trong phiên, với điều kiện đọc và làm theo AGENTS.md này (làm trong worktree/nhánh riêng, validate, test hẹp, brain review, tăng version kèm changelog, cập nhật cài đặt plugin).

Sau mỗi lần sửa plugin, brain phải validate, chạy test hẹp phù hợp và hoàn tất review, tăng version thích hợp cùng changelog, rồi cập nhật cài đặt plugin vừa sửa cho repo hiện tại và mọi repo khác đang dùng plugin đó qua công cụ chính thức. Không tự bật plugin ở repo chưa dùng; không sửa thủ công credential/settings hay sổ cài đặt. Kiểm chứng version và đường dẫn plugin được nạp thực tế ở các repo đã cập nhật; nếu phiên đang mở không hot load được thì báo rõ cần reload. Giữ nguyên luật commit/push/merge ở trên; hand executor chỉ làm phần được giao, không tự cập nhật runtime khi brief dành việc đó cho brain.

> Sau khi người dùng duyệt manifest và ownership floor cụ thể, cho phép `hand-ext accounts sync --apply` tạo overlay và reconcile đúng khoá settings đã duyệt bằng backup + atomic write; tuyệt đối không sửa credential, state hay sổ cài đặt thủ công. Plugin/MCP chỉ qua CLI chính thức với phạm vi đã duyệt. Luật cập nhật plugin áp dụng cho mọi thư mục tài khoản đang dùng plugin ở repo hiện tại và các repo khác; không tự bật nơi chưa dùng. Phải kiểm version và đường dẫn nạp thực tế theo từng repo/account, báo cần reload nếu phiên đang mở chưa nhận bản mới.

Cấu hình ưu tiên: mặc định plugin → global `~/.hybrid-hands/config.json` (đổi bằng `HYBRID_HANDS_CONFIG`) → repo → cờ CLI. Dict merge sâu; list/scalar thay nguyên.
`hand-ext config --json` in cấu hình hiệu lực và nguồn từng key; global hỏng báo lỗi kèm đường dẫn.
`hand-ext models` xem/set/unset model tầng brain/side/hand theo repo (`hand-ext models options` liệt kê lựa chọn); chỉ set/unset khi người dùng chốt thay đổi cụ thể, mở phiên mới để áp dụng.
`ext_hand.native.{claude,codex}=auto|off`; `pick --role … --json` trả `native`/`native_reason`. Claude chính/phụ mặc định transport Paseo; có thể chọn `screen` qua cấu hình.

## Luật dữ liệu chung (chép nguyên văn vào brief hand ngoài)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

Sol có quyền dữ liệu như Opus; luật không giao secret/dữ liệu khách hàng áp dụng cho hand ngoài. Việc đó dùng hand Claude. Sol được dùng công cụ plugin để chỉ đọc metadata/usage tổng hợp phục vụ kiểm chứng thực tế. Quy tắc chỉ dùng code/fixtures giả và không đọc transcript/log thật áp dụng cho hand ngoài, không cấm runtime đọc token usage. Công cụ runtime được đọc auth nội bộ theo luật trên không có nghĩa hand được mở auth file; cấm hiện giá trị `.env`, token, credential vẫn áp dụng mọi tầng.

## Layout và nguồn chuẩn

- `hybrid-hands/README.md`: sử dụng plugin; `plugins/hybrid-hands/CHANGELOG.md` giữ lịch sử release.
- `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json`: phiên bản plugin.
- `hybrid-hands/plugins/hybrid-hands/bin/`: CLI hand-ext, side-session, cc-switch; `lib/hand_ext/`, `lib/side_session/`, `lib/cc_switch/`: implementation tương ứng; `lib/hh_ps/`: thư viện usage dùng chung (giá, nguồn usage Claude/GPT, quota) cho statusline, limit-watch, guard ngày, cc-switch.
- `hybrid-hands/plugins/hybrid-hands/skills/`: ext-hand, paseo, side-session, limit-watch, open-gpt-brain; `agents/`, `templates/`, `scripts/`, `hooks/`: policy và launcher.
- `hybrid-hands/tests/`: test Python/fixtures giả.
- `statusline/`: plugin riêng, chỉ sửa khi brief giao rõ; UI bỏ giờ bắt đầu.

Theo dõi phiên/hand (người dùng chốt 16/11/2026 bỏ hh-ps, pane cây và panel Paseo, bản 0.66.0): app/daemon Paseo (agent và subagent), `side-session ls/watch`, `hand-ext status/report`, statusline.

Nguồn giá DUY NHẤT: `hybrid-hands/plugins/hybrid-hands/config/model-prices.json`; env override `HYBRID_HANDS_PRICING_FILE`. Schema `{version:1, verified_at:"2026-11-07", models:{<model-id>:{input,cached,output,cache_write_5m?,cache_write_1h?,source,price_date}}}` (USD/MTok). Mỗi entry giữ date/source; không hardcode bảng thứ hai hay fallback theo model/họ khi model lạ. Cache Claude tính đúng giá cấu hình, tách cache ghi 5m/1h. Nguồn công khai được xác minh ngày 2026-11-07. Các URL và giá đầy đủ ở [file canonical](hybrid-hands/plugins/hybrid-hands/config/model-prices.json), không nhân bản giá vào tài liệu hay code.

Mọi USD~ là ước tính offline subscription, không phải hoá đơn. Quota tài khoản 5h/tuần lấy cache/sample sẵn có, thiếu `?`; không suy token/USD thành quota GPT. Phần riêng hand tuần chỉ hiện khi có nguồn và nhãn riêng.

## Contract dữ liệu usage 0.30.0

Bổ sung cuối dataclass với default để giữ tương thích:

- `Usage.account_plan: str = ""`, `account_5h_pct: Optional[float] = None`, `account_week_pct: Optional[float] = None`.
- `HandRun.effort: str = ""`, `exit_code: Optional[int] = None`.

API pricing hiện có giữ tương thích; cập nhật implementation giá ở nguồn canonical, không sinh bảng mặc định khác. Metadata hand ghi parent canonical, started, ended, status, exit_code, tokens, effort, duration cùng model/backend. Legacy unknown giữ `?` ở UI, null/chuỗi rỗng theo JSON/dataclass; không bịa mốc hay quota. Native subagent không tạo run/meta/report/token ledger hand-ext.

### Nguồn usage 0.30.0

GPT phần riêng của session pinned rollout/native child dùng `rate_limits` weekly `used_percent` cuối trừ đầu: cần ít nhất hai sample có timestamp hợp lệ, không giảm, cùng reset và reset đó còn hiện tại. Thiếu điều kiện hoặc qua reset thì `?`. Bổ sung cuối `Usage` với default `week_pct_source: str = ""`; khi đo được, source là `codex_rate_limits_delta`, `week_pct_estimated` là false và nhãn `GPT riêng (đo) N% tuần`. Đây là biến động quota tài khoản trong khoảng phiên, có thể gồm phiên chạy đồng thời, không phải phần sử dụng quy riêng độc quyền cho phiên. Không suy quota từ token/USD.

GPT account có duration tường minh phân loại 5h bằng `window_minutes=300`; sample primary tuần (`10080`) không được đổi nhãn thành 5h. Source account rollout legacy thiếu duration giữ tương thích primary=5h/secondary=tuần theo contract cũ. Riêng phép đo GPT phần riêng mới bắt buộc duration tuần tường minh `window_minutes=10080`. Claude 5h dùng cache/live sẵn có, kiểm freshness và reset hiện tại, chấp nhận reset numeric hoặc ISO; thiếu/hết hạn hiện `?`. Statusline dùng chung helper nguồn usage; phiên bản statusline được quản lý riêng. Model lạ không fallback; giá duy nhất từ file canonical.

## Contract archive workspace (09/11/2026)

Membership chỉ theo public `agent.workspaceId`, không theo cwd vì nhiều workspace local có thể cùng checkout. Chỉ archive workspace do plugin tạo, kể cả private LOCAL, khi mọi member cùng workspaceId đã archived (known closed child của plugin phải archive trước), không có `main_session`/role `main` hay agent không do plugin tạo. Giữ workspace local shared/main/unknown; không suy ownership từ tên hoặc cwd, không gom theo cwd hay di chuyển/xoá thư mục. Plugin worktree giữ nguyên quy tắc hiện có; archive local không xoá checkout, Paseo chỉ có thể xoá worktree do Paseo sở hữu. Managed settled đủ report/hooks → `awaiting_review`, tự archive exact child và workspace riêng theo quy tắc này; `managed archive` idempotent, `review-approve` vẫn chặn followup tới khi được duyệt. Followup restore workspace rồi reopen cùng child, cùng IDs và epoch mới. Side-session Paseo mọi provider done archive child trước workspace; warning workspace không chặn done, `ls`/`watch` retry có giới hạn. Lỗi visibility giữ lifecycle/data, không tạo writer trùng.

`side-session tidy [--name NAME] [--apply]`: mặc định dry-run, chỉ liệt kê eligible/blocked và exact IDs dự kiến. Ví dụ `side-session tidy --name NAME` để xem, `side-session tidy --name NAME --apply` để áp dụng. `--apply` idempotent, chỉ archive workspace có ownership từ plugin side state, rỗng/đã archive hết member hoặc có known closed plugin child được archive trước; chặn main, agent không do plugin tạo và member active. `--name` giới hạn cleanup; giữ thư mục local và artifacts. `side-session send` giữ restore workspace rồi cùng exact agent trước gửi, history marker và không create; lỗi xác định trước gửi có thể retry, ACK mơ hồ giữ pending chặn gửi trùng. `start --resume` giữ tương thích.

## Kiểm chứng

Test hẹp (một file, `-k`, vài test) chạy bình thường ngay, không cần đo CPU; nếu có dấu hiệu nặng thì áp dụng hạ ưu tiên dưới đây.
Test nặng = có dấu hiệu nặng HOẶC CPU toàn máy ≥90%; dấu hiệu: full suite (pytest/jest/go test… không giới hạn file hay `-k`, `make test`, `npm test` cả bộ), song song (`-n auto`/`-n N`/xdist, `--workers`, `-j`), e2e, build kèm test cả bộ.
Không chặn vì nặng: chạy `nice -n 19 <lệnh>` (nhường CPU cho việc khác, máy rảnh vẫn dùng nhân hiệu năng). Không thêm `taskpolicy -b`: trên Apple Silicon nó chỉ cho chạy nhân tiết kiệm điện, test chậm khoảng 3 lần (đo ở ai-luxian AILUX-292: 241 s → 724 s); chỉ dùng khi brief ghi rõ việc không gấp. Không tự bật song song nếu brief không yêu cầu; tăng timeout tương ứng.
Chỉ trước test dự kiến >30s không có dấu hiệu nặng và không phải test hẹp, đo CPU bằng `ps -A -o %cpu= | awk -v n="$(sysctl -n hw.ncpu)" '{s+=$1} END {printf "%.0f\n", s/n}'`; kết quả ≥90 thì chạy hạ ưu tiên.

Chỉ chạy test hẹp phần đang sửa; full suite chỉ khi brief giao, một lần cuối. Tài liệu/manifest: kiểm JSON hợp lệ và link nội bộ, không thêm test cho text tài liệu, không claim cài đặt/test chưa chạy. Giữ mức test tối thiểu theo brief; chỉ hai nhóm cần mức kỹ là tính năng giữ chân/chi tiêu và bảo mật chống tấn công từ ngoài. Báo rõ lệnh/kết quả thật và phần còn chưa kiểm chứng.

<!-- plan-status-rule -->
## Trang tình hình plan

- Số liệu trong `docs/status/` do GitHub Action plan-status tự cập nhật; không sửa tay phần số liệu.
- Sau khi tick plan hoặc xong việc lớn: `git pull`, có thể chạy `/dev-workflow:plan-status`, viết lại khối
  ghi chú tay (rủi ro, quyết định chờ người dùng, ≤5 dòng) rồi commit `docs/status/`.
- Cấu hình ở `.claude/plan-status.toml`; dự án con thêm một `[[page]]`.
