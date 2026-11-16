---
name: ext-hand
description: Giao một việc code, tài liệu hoặc thu thập dữ liệu tự chứa cho subagent theo vai của profile repo (claude-mono, gpt-mono, hybrid) - chạy `hand-ext pick --role code|collect|chrome [--tier 1|2] --json`, native true thì subagent native đúng model/effort, native false thì `hand-ext run --role … --tier …` chạy nền, đọc report, brain review diff, báo tài khoản, token, % hạn mức và USD~ ước tính; thang 2 bậc B1 → B2 cho thu thập dữ liệu và `hand-ext ladder log|stats`; xử lý exit 1/4/6/7/8/9, quota, timeout, not_logged_in; cài đặt lần đầu codex, claude-v1, claude-v2. Không dùng API key. Từ khoá kích hoạt - "hand ngoài", "hand-ext", "giao hand", "subagent", "profile", "vai", "pick --role", "thang bậc", "B1", "B2", "thu thập dữ liệu", "Codex", "hạn mức hand".
---

# Giao việc theo vai (hand-ext)

## Tóm tắt

- **Profile bắt buộc:** mỗi repo có khoá `profile` = `claude-mono` | `gpt-mono` | `hybrid`; thiếu thì `hand-ext pick/run` báo lỗi kèm `hand-ext profile set <tên>` (chỉ đặt sau khi người dùng chốt cho repo đó). `hand-ext profile` in bảng vai hiệu lực và nguồn từng ô. Bảng vai đầy đủ ở [AGENTS.md mục Phạm vi và vai trò](../../../../../AGENTS.md) và [README mục Profile và vai](../../../../README.md#profile-và-vai).
- **Vai giao được:** `code` (dev/tester), `collect` (thu thập dữ liệu, bậc 1/2), `chrome` (thu thập cần Claude in Chrome, bậc 1/2). Super brain không gọi pick/run.
- **Chuỗi bước:** `hand-ext pick --role <vai> [--tier N] --json` → `native` true: subagent native đúng `model`/`effort` (Claude: tool Agent `hybrid-hands:hand` với `model` = `agent_model`; Codex: subagent native `fork_turns=none`) → `native` false: brief vào file, `hand-ext run --role <vai> --tier <N>` chạy nền → đọc report → brain review diff → báo tài khoản, token, % hạn mức, USD~.
- **Song song:** tối đa 4 subagent (native và hand-ext chung pool), khác file; cùng file/phụ thuộc tuần tự.
- **Luật cứng:** không dùng hay tạo API key, không chuyển sang API khi hết hạn mức; Codex không chịu hook Claude Code nên brief chép nguyên văn luật cấm (nhất là cấm đọc `.env`) và PHẠM VI GHI hẹp.
- **Luật dữ liệu:** brain được đọc secret và dữ liệu khách hàng; luật dưới áp cho hand ngoài (codex dùng làm hand). Không giao hand ngoài việc phải đọc hoặc gửi secret (`.env`, token, mật khẩu, URL DB có mật khẩu) hay dữ liệu khách hàng (tài liệu, nội dung DB, log có dữ liệu khách hàng, tên/thông tin cá nhân); việc đó dùng hand Claude (`hybrid-hands:hand`). Được giao code, test, tài liệu kỹ thuật; tài liệu hay dữ liệu mẫu đã bỏ thông tin khách hàng và công khai được.
- **Cách ly:** `hand-ext run` mặc định tạo git worktree sạch (`.env` bị ignore không có trong workspace), lưu `changes.patch` rồi áp về repo; xem mục 3.

## 1. Pick, native và thang 2 bậc

`hand-ext pick --role code|collect|chrome [--tier 1|2] --json` trả `profile`, `role`, `tier`, `provider`, `account`, `model`, `effort`, `backend`, `agent_model`, `native`, `native_reason`, `guard_blocked`. `ext_hand.native.{claude,codex}=auto|off`; `off` buộc chạy qua `hand-ext run`. Native chỉ khi phiên gọi cùng tài khoản với vai. Unknown sau spawn phải reconcile/wait, không tạo writer trùng. Native không tạo run/meta/report/token ledger hand-ext; usage qua runtime/Paseo, thiếu token/USD~/quota ghi `?`.

Thang 2 bậc cho `collect`/`chrome`:

- **Bậc khởi đầu:** gói ít code (đọc trang, tải bằng công cụ sẵn có, social listening) bắt đầu B1; gói phải viết script bắt đầu B2.
- **Hỏng:** subagent báo chưa xong; `hand-ext run` thoát 1, 4 hoặc 6; brain kiểm mẫu không đạt (nguồn không mở được hoặc không nói điều được dẫn, chạy lại script ra kết quả khác, ghi ngoài phạm vi, bỏ sót luật trong brief).
- **Nâng:** B1 hỏng → chạy lại đúng một lần ở B2 bằng subagent mới, brief chép phần đã kiểm đạt (file:dòng) và chỉ giao phần thiếu; qua hand-ext dùng `hand-ext run --role <vai> --tier 2 --escalated-from RUN_ID`.
- **Dừng:** B2 hỏng → dừng báo người dùng (ở `hybrid` báo super brain qua bàn giao).
- **Không nâng:** thoát 7 (hết quota/guard), 8 (hết slot), 9 (đĩa đầy), vi phạm an toàn.
- **Ghi nhận:** lượt native ghi `hand-ext ladder log --role <vai> --tier <N> --result ok|fail [--escalated-from ID]`; `hand-ext ladder stats` in tỉ lệ B1 đạt và tỉ lệ nâng.
- Vai `code` không có thang; hỏng thì giao lại cùng bậc một lần rồi brain quyết.

Hết quota: không đổi tài khoản. Phiên Paseo đã đăng ký limit-watch thì chạy tiếp khi quota về; không thì ghi checkpoint vào bàn giao rồi dừng báo người dùng.

Guard ngày v1: `ext_hand.claude_accounts.v1.day_guard` (mặc định plugin `false`), `max_day_pct` (mặc định 8), `day_guard_days` (ví dụ `["sat","sun"]`), `day_guard_off_date: "YYYY-MM-DD"` tắt riêng một ngày. Khi bật, `hand-ext` tính % hạn mức tuần Claude máy này đã dùng từ 0h hôm nay (USD từ ledger statusline chia USD/1% ghim); chạm ngưỡng hoặc không tính được thì `pick` trả `native` false và thoát 7, `run` thoát 7. Chỉ đổi cấu hình guard khi người dùng yêu cầu.

## Hand Paseo opt-in

`shell` vẫn là mode mặc định. Chỉ repo được operator bật `ext_hand.mode=auto` hoặc `paseo-required` mới dùng managed hand; không tự sửa config hay bật ở repo khác. Khi mode opt-in và daemon/provider/capability sẵn sàng, **intent mới vốn giao subagent Codex native** phải chạy `hand-ext run --role <vai> --tier <N> --mode paseo-required --brief /ABS/brief.md --cwd /ABS/REPO`, không spawn native trực tiếp. Native đang tồn tại giữ nguyên, không migrate. Vẫn chạy `hand-ext pick --role … --json` trước; dispatcher giữ account/model/effort theo vai, guard ngày và pool chung tối đa 4.

Thiếu daemon/provider/capability **trước dispatch**: `auto` quay đường shell cũ, `paseo-required` báo lỗi, không silent fallback. Parent/project/target không xác minh được thì chặn. Sau create/send hoặc ACK không rõ, reconcile exact invocation/attempt/epoch, giữ reservation; không tạo shell/native writer thứ hai.

Mỗi managed hand có workspace/worktree riêng trong **cùng verified project** với parent, caller gắn parent canonical và tab/track của parent; không hứa sidebar native lồng child. Theo quyết định 09/11/2026 (thay Q4), khi execution đã settled đầy đủ report/hooks thì chuyển `awaiting_review`, tự archive **exact child** và workspace riêng của child; không cần review để archive, không archive parent. Membership chỉ theo public `agent.workspaceId`, không theo cwd vì nhiều workspace local có thể cùng checkout. Chỉ archive workspace do plugin tạo, kể cả private LOCAL, khi mọi member cùng workspaceId đã archived (known closed child của plugin phải archive trước), không có `main_session`/role `main` hay agent không do plugin tạo. Giữ workspace local shared/main/unknown; không suy ownership từ tên hoặc cwd, không gom theo cwd hay di chuyển/xoá thư mục. Plugin worktree giữ nguyên quy tắc hiện có; archive local không xoá checkout, Paseo chỉ có thể xoá worktree do Paseo sở hữu. Lỗi visibility giữ lifecycle/data để retry, không tạo writer trùng. `managed archive` idempotent. Brain vẫn phải đọc diff/report và `review-approve` trước followup. Followup restore workspace rồi mở lại cùng exact child (giữ agent/workspace IDs) với brief tự chứa, epoch/request key và baseline mới; không phải CLI context resume, không tạo child trùng. Thiếu cwd/worktree thì chặn. Giữ history, report, patch, worktree và mọi thư mục/artifact; không cleanup. Archive chỉ đổi khả năng hiển thị ở sidebar Paseo. Một managed execution là một hand trong pool, không tạo side-session root; token từ parser/ledger chuẩn, ACP chỉ projection, thiếu usage/quota giữ `?`.

### Review và follow-up managed

Brain lấy exact key bằng `hand-ext managed ls --cwd /ABS/REPO`, đọc diff/report trước `hand-ext managed review-approve --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH`. `hand-ext managed archive --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH` là thao tác idempotent sau settlement, không đợi review; `review-approve` vẫn bắt buộc trước followup. Giao tiếp bằng `hand-ext managed followup --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH --brief /ABS/fresh-brief.md`; key phải latest, epoch mới không resume CLI. Không archive parent hay cleanup worktree. Xem [recipe operator](../../../../README.md#vận-hành-managed-hand-paseo) khi cần setup/status; không tự chạy live setup từ một brief hand.

## Chờ usage limit bằng code — 0.58.0

Khi công việc còn dở và cần tự tiếp tục đúng phiên sau usage limit, dùng `hand-ext limit-watch on --persistent`, rồi `hand-ext limit-watch on --persistent --target /ABS/target.json` để đăng ký exact target và checkpoint. Không dùng vòng `/loop` gọi LLM để poll quota. Tắt bằng `hand-ext limit-watch off`, xem `hand-ext limit-watch status`; bỏ `--persistent` để one-shot. Job rỗng không tự tìm phiên. JSON/quan sát block, hướng dẫn brain, giới hạn ACK/tmux ở [README limit-watch](../../README.md). Brain/main dùng adapter Paseo riêng; `side-session send` vẫn cấm role main. Không sửa guard, account/model hoặc đăng ký target từ transcript/secret. Nếu đăng ký sau khi quota đã chặn phải có khối `blocked` từ quan sát thật của chính phiên, không suy từ quota account đầy.

### Social listening

Kế thừa nghiên cứu đã duyệt ngày 12/11/2026: [Claude #92004](https://github.com/anthropics/claude-code/issues/92004) (04/09/2026) → theo từng phiên; [Codex #8310](https://github.com/openai/codex/issues/8310) (19/12/2025) → checkpoint + bước tiếp; [Claude #35744](https://github.com/anthropics/claude-code/issues/35744) (18/03/2026, bình luận 28/05/2026) → kiểm runtime trước gửi. Đây là báo cáo cộng đồng chưa tái hiện; không dùng làm bằng chứng quota phục hồi.

## Giá và hạn mức

Theo dõi phiên và hand: app/daemon Paseo (agent và subagent), `side-session ls/watch`, `hand-ext status/report` và statusline; CLI `hh-ps`, pane cây và panel Paseo đã gỡ ở 0.66.0.

Giá chỉ từ [`config/model-prices.json`](../../config/model-prices.json), override bằng `HYBRID_HANDS_PRICING_FILE`; mỗi entry có source/price_date, file có verified_at. Mọi USD~ là ước tính offline trên gói subscription, không phải hoá đơn. Cache Claude dùng đúng giá cấu hình 5m/1h; không fallback theo họ/model khác. Nguồn giá công khai được xác minh ngày 2026-11-07 và lưu trong file canonical. Không thêm bảng giá backend thứ hai.

Quota tài khoản lấy từ cache/sample sẵn có của đúng gói; thiếu 5h/tuần hiện `?`, tuyệt đối không suy token hay USD thành quota GPT. Phần riêng hand tuần chỉ thêm khi có nguồn và gắn nhãn riêng.

Metadata mới giữ parent canonical, started, ended, status, exit_code, tokens, effort, duration cùng model/backend; meta và ledger của `hand-ext run` thêm `role`, `tier`, `attempt`, `escalated_from`. `CODEX_THREAD_ID`/`PASEO_AGENT_ID` được đối chiếu thành sid canonical để gắn đúng cha; `HYBRID_HANDS_HAND_SCOPE` chỉ giới hạn số hand đồng thời, không phải ID cha. Cây bao gồm phiên Codex/Claude và mọi loại agent/backend. Hand nhận brief trực tiếp là executor: làm trong phạm vi được giao, không gọi hand-ext, không mở side-session hay giao tiếp phiên khác.

Codex brain và hand dùng chung `~/.codex-hand`: mỗi lượt hand override `model` bằng `-m`, `model_reasoning_effort` bằng `-c`, `sandbox_mode` bằng `-s`. Doctor không chặn nếu ba khóa thiếu/lệch và không ghi config; kiểm tra cài đặt, đăng nhập gói và khóa legacy không override như `service_tier` vẫn bắt buộc.

## 2. Cài đặt lần đầu (mỗi máy, mỗi backend)

Lệnh chung: `hand-ext setup [--backend B|all] [--cwd D]` ghi cấu hình CLI và in lệnh đăng nhập; người dùng tự đăng nhập trong terminal riêng (agent không chạy, không thấy credential); rồi `hand-ext doctor [--backend B|all]` tới khi đạt. Nếu `hand-ext` không có trong PATH, gọi `${CLAUDE_PLUGIN_ROOT}/bin/hand-ext`.

| Backend | Gói | Người dùng tự đăng nhập |
|---|---|---|
| `codex` | ChatGPT, thư mục riêng `~/.codex-hand` | `CODEX_HOME=~/.codex-hand codex login --device-auth` |
| `claude-v2` | Claude tài khoản THỨ HAI, thư mục riêng `~/.claude-hand` | `CLAUDE_CONFIG_DIR=~/.claude-hand claude` rồi `/login` tài khoản thứ hai |
| `claude-v1` | Gói Claude CHÍNH `~/.claude` | đã đăng nhập sẵn (không đăng nhập thêm) |

`claude-main` và `claude` chỉ là alias tương thích của `claude-v1` và `claude-v2`. Cấu hình dự án ở `.claude/hybrid-hands.json`: khoá `profile`, ghi đè ô `profiles.<tên>.<vai>` (vai có bậc: `collect.1`, `collect.2`, `chrome.1`, `chrome.2`), và mục `ext_hand`: `backends.<tên>`, `claude_accounts`, `timeout_min`, `max_tokens`, `sandbox`, `isolation`, `worktree_root`, `ledger`, `quota_state`, `runs_dir`. Model của ô phải có trong danh sách model của plugin và file giá canonical; sai thì báo lỗi kèm khoá cấu hình.

- **Tự nén ngữ cảnh:** `backends.<tên>.compact_at` đặt ngưỡng tự nén cho riêng lượt chạy; `0` tắt; giá trị âm hoặc không phải số nguyên bị từ chối.

## 3. Một lượt giao việc qua hand-ext

1. **Brief:** khuôn 7 mục (LUẬT BẮT BUỘC, KHÔNG ĐƯỢC ĐỤNG, TRẢ VỀ, MỤC TIÊU, NGỮ CẢNH, PHẠM VI GHI, KIỂM CHỨNG) vào file tạm trong scratchpad, ví dụ `<scratchpad>/brief-<nhãn>.md`. LUẬT BẮT BUỘC chép nguyên văn từ AGENTS.md/CLAUDE.md của repo, luôn có câu cấm đọc `.env`; PHẠM VI GHI liệt kê từng file. KIỂM CHỨNG ghi mức test: tối thiểu (chỉ case quan trọng) hoặc kỹ (chỉ 2 nhóm: tính năng tạo hứng thú/giữ chân khiến người dùng trả tiền; bảo mật chống tấn công từ ngoài).
2. **Run nền:** tool Bash với `run_in_background`:
   `hand-ext run --brief <file> --role code|collect|chrome [--tier 1|2] [--escalated-from RUN_ID] --label <nhãn> [--mode shell|auto|paseo-required] [--cwd D] [--timeout-min M] [--max-tokens N] [--sandbox S] [--isolation worktree|none] [--no-apply] [--keep-worktree]`
   Chờ thông báo khi lệnh thoát; không viết vòng chờ riêng. `--role` lấy tài khoản/model/effort từ profile; `--escalated-from` chỉ dùng với `--tier 2`. Mặc định `--isolation worktree`: hand chạy trong worktree tạm ngoài repo (HEAD + thay đổi chưa commit + untracked không ignore), sau đó `changes.patch` được áp về cwd gốc nếu không xung đột; `--no-apply` chỉ lưu patch, `--keep-worktree` giữ worktree để kiểm tra. Worktree được dọn cả khi timeout/lỗi; patch vẫn lưu. Cwd không phải git repo thì mặc định rơi về `none` kèm cảnh báo trong report; `--isolation worktree` tường minh mà không tạo được worktree thì thoát 2.
3. **Đọc kết quả:** khối tóm tắt cuối output (backend, token, `used_percent`/`resets_at`) và `report.md` theo đường dẫn được in. Thư mục lượt có `brief.md`, `prompt.md`, `meta.json` (`base_commit`, `dirty`, `dirty_files`, `plugin_version`, `backend`, `model`, `effort`, `label`, `role`, `tier`, `attempt`, `escalated_from`) và `changes.base.patch` khi repo nguồn có thay đổi chưa commit; `events.jsonl` có `ts` ISO 8601. Lượt cũ thiếu meta hoặc `ts` vẫn đếm được dòng, cột thời gian để `?`.
4. **Review:** brain review code của mọi subagent mình giao (diff các file đã đổi). Lỗi thì một lượt `run` mới với brief gọn chép sẵn phát hiện (hand ngoài không nhận SendMessage).
5. **Báo hạn mức:** tài khoản, token, % hạn mức, thời điểm reset. Trạng thái các gói: `hand-ext status`; tổng lượt và token: `hand-ext report [--since D] [--backend B] [--label L]`; đo hiệu quả từng lượt: `hand-ext measure --runs <dir> [--runs <dir>...] [--since YYYY-MM-DD]`; thang bậc: `hand-ext ladder stats`; theo dõi phiên/subagent: app Paseo, `side-session ls/watch`.

## 4. Xử lý lỗi và rủi ro

- **Mã thoát:** 0 ok, 1 failed, 2 sai cách dùng hoặc không tạo được worktree khi `isolation=worktree` được yêu cầu, 4 capped, 6 timeout, 7 hết hạn mức/chưa đăng nhập/guard ngày chặn, 8 hết slot, 9 đĩa đầy.
- **Cách ly worktree:** mặc định khi cwd là git repo; worktree chỉ có file tracked + thay đổi chưa commit của file tracked + file untracked không bị ignore, không bao giờ có file bị ignore (`.env`, `*.demo.env`...). Sau run, `changes.patch` nằm trong thư mục lượt chạy; áp bằng `git apply --check` rồi `git apply` nên xung đột thì không ghi đè thay đổi người dùng và report ghi `xung đột`. `--no-apply` chỉ lưu patch; `--keep-worktree` giữ worktree (mặc định dọn cả khi timeout/lỗi). Cwd không phải git repo: mặc định `none` kèm cảnh báo; `--isolation worktree` tường minh mà lỗi thì thoát 2, không âm thầm chạy trong repo gốc.
- **Exit 7:** chạy `hand-ext doctor` trước, đọc lý do (cấu hình, đăng nhập, quota hoặc guard), không đổi tài khoản, không dùng API key thay thế; ghi lý do vào bàn giao rồi dừng báo. Exit 8: chờ slot.
- **`capped` (exit 4, chạm `--max-tokens`):** đọc report xem phần đã xong; lượt tiếp là `run` mới với brief phần còn lại.
- **`timeout` (exit 6):** đọc report; việc dài thì chia nhỏ hoặc tăng `--timeout-min` có lý do.
- **Lỗi khác hoặc `doctor` không đạt:** `hybrid-hands:hand` làm dự phòng, báo người dùng kèm output thật.
- **Sổ Codex:** mỗi lượt backend `codex` kết thúc ghi đúng một dòng JSON vào `~/.hybrid-hands/codex_usage.jsonl` (hoặc `$HYBRID_HANDS_STATE_DIR/codex_usage.jsonl` khi đặt; test đổi `HOME` được). Schema `schema=1`: `run_id`, `ended`, `model`, `effort`, `tokens {input,cached_input,output}`, `cost_usd`, `cost_source` (`estimated`/`unknown`), `codex_home` chỉ basename (ví dụ `.codex-hand`), `windows {"5h": {"used_percent","resets_at"} | null, "7d": {...} | null}` phân loại bằng `window_minutes` (300 = 5h, 10080 = tuần), không chỉ cửa sổ lớn nhất; có gói chỉ có primary tuần, cửa sổ không có mẫu là null. Rollout cũ thiếu độ dài mới dùng primary=5h/secondary=tuần. Giá lấy từ model-id trong bảng canonical `config/model-prices.json`; thiếu/bất hợp lệ thì `cost_usd=null`, `cost_source=unknown`; đủ thì `(input−cached_input)×input + cached_input×cached + output×output` chia 1e6, `estimated`. Không ghi hội thoại, absolute path hay dùng tài khoản `~/.codex`. Lỗi ghi sổ chỉ cảnh báo, không làm fail lượt.

## Tên agent và workspace Paseo — 0.36.1

Tên agent và workspace của phiên phụ có dạng `<tên> · <loại> phụ`: ví dụ `qa · Sol phụ` (Codex), `qa · Opus v1 phụ`, `qa · Opus v2 phụ` (Claude theo account). Main và workspace shared giữ title hiện có.

Managed agent và workspace có dạng `<tên cha> › hand <backend> · <label>`, ví dụ `qa › hand codex · docs`. Cha được xác minh là main dùng `chính`, cha chưa xác định dùng `?` (ví dụ `? › hand codex · docs`); không suy main từ cwd hay tên. Tên tối đa 60 ký tự; cắt label để giữ tiền tố cha và backend. Không đưa path, nội dung brief hay secret vào tên.

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

Mỗi run isolation tự gọi GC trước disk guard, chỉ lớp `finished` (`ext_hand.worktree_gc.auto=finished|off`, mặc định `finished`; lỗi chỉ cảnh báo). Lớp `preserved` (dirty nhưng `changes.patch` khớp diff hiện tại của run bắt đầu sạch) chỉ xoá bằng `--apply --include-preserved`. Run lỗi giữ worktree tự xoá worktree ngay khi run bắt đầu sạch và `changes.patch` khớp diff hiện tại (rỗng = sạch); không khớp/lỗi xác minh, run bắt đầu dirty hoặc `--keep-worktree` thì giữ. Dry-run liệt kê thêm `age_seconds` và bytes mọi mục; registry còn worktree sống không bị xoá theo hạn 7 ngày.

Trước tạo isolated worktree, disk guard cảnh báo dưới `disk_guard.warn_gb=20` GiB và chặn dưới `disk_guard.block_gb=5` GiB, exit 9. `--ignore-disk-guard` chỉ vượt chặn khi được phép chủ động. Sparse P4 bị chặn bởi S0 FAIL baseline `isolation.prepare`; không quảng bá `worktree_sparse_exclude` hay `--no-sparse` là đã có.

Sau `side-session start` cho phiên brain làm việc dài, dùng [skill limit-watch](../limit-watch/SKILL.md) để đăng ký `hand-ext limit-watch add --side NAME --checkpoint "Đã xong gì; bước kế; file .done"` trước khi hết hạn mức.

## Điều phối nhiệt và trình duyệt

Tóm tắt: brain chạy `hh-heat status` trước khi mở thêm phiên song song. Mỗi lúc tối đa một trình duyệt headless toàn máy qua `hh-heat browser --timeout-min 10 -- <lệnh>`; tối đa hai luồng brain có trình duyệt/build nặng, luồng thứ ba xếp hàng. Gom ảnh kiểm vào cuối đợt, đóng browser sau mỗi lượt; chụp khung cố định rồi dừng render khi làm được. Trước test nặng dùng `hh-heat gate --wait`; trình duyệt dùng ngưỡng CPU toàn máy 60%, luật hạ ưu tiên test thường 90% giữ nguyên. Không tự thêm cờ Metal/SwiftShader vì chưa có số đo xác nhận.
