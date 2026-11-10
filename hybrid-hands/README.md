# hybrid-hands

Tóm tắt: phối hợp phiên chính, phiên phụ và hand theo tài khoản; cấu hình dùng chung toàn máy, có thể ghi đè ở repo và CLI.

## Phiên chính Sol trên Paseo

Mở brain Sol Codex (mặc định `gpt-6.1-sol`, effort high) tại repo chính bằng `side-session start --main --name sol-main [--prompt ...]`, rồi xem và trao đổi trên điện thoại qua Paseo. Cần daemon Paseo; không dùng `--worktree`. Bỏ prompt để Sol đọc luật repo và chờ việc; `--effort` ghi đè mặc định. Phiên chính không có handoff/watchdog và không chiếm slot phiên phụ; marker hay idle không tự archive phiên chính. Chỉ người dùng tự archive trên Paseo; dùng `side-session ls` để xem, `side-session stop sol-main` để interrupt, giữ phiên và lịch sử. `--dry-run` chỉ in kế hoạch, không gọi daemon.



Opus chia brief thành các gói L1 độc lập khác file, chủ động lấp tối đa `side_session.max_parallel` Sol (mặc định 4). MỖI SOL chia brief độc lập khác file và chạy nền tối đa `ext_hand.max_parallel` hand (mặc định 4), chờ đủ tất cả kết thúc rồi Sol review. Cùng file hoặc phụ thuộc phải tuần tự; không ép song song. Có thể 16 hand tổng khi 4 Sol độc lập; không phải cap toàn máy 4. `side_session.max_parallel` là số nguyên 1..6, mặc định 4; `ext_hand.max_parallel` vẫn là số nguyên 1..4, mặc định 4. Thứ tự scope: `HYBRID_HANDS_HAND_SCOPE` → `CODEX_THREAD_ID` → `CLAUDE_CODE_SESSION_ID` → repo root. Scope hand riêng mỗi Sol qua `HYBRID_HANDS_HAND_SCOPE` = uuid Sol, giữ nguyên `CODEX_HOME` và parent Claude session. Exit 8: đợi slot/tiến trình đang chạy kết thúc rồi thử lại; không đổi backend hay tự làm như lỗi hand.

Sol **BẮT BUỘC giao code/test/tài liệu L0/L1** bằng `hand-ext run --backend auto` theo `ext_hand.order` của repo. Sol chỉ tự viết khi hand-ext thoát lỗi (ghi lý do và mã thoát vào bàn giao) hoặc việc cần secret/dữ liệu khách hàng theo luật dữ liệu. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do để Opus quyết. Exit 8: chờ slot.

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

## Chọn hand theo tài khoản

### Hand Paseo opt-in: ưu tiên trước ngoại lệ native

`shell` vẫn là mode mặc định. Chỉ repo được operator bật `ext_hand.mode=auto` hoặc `paseo-required` mới dùng managed hand; không tự sửa config hay bật ở repo khác. Bảng native bên dưới chỉ áp dụng đường cũ. Khi mode opt-in và daemon/provider/capability sẵn sàng, **intent mới vốn giao native Sol low** phải chạy `hand-ext run --backend auto --mode paseo-required --brief /ABS/brief.md --cwd /ABS/REPO`, không spawn native trực tiếp. Native đang tồn tại giữ nguyên, không migrate. Vẫn chạy `hand-ext pick --json` trước; dispatcher giữ order, account/model/effort, quota/day guards và pool chung `ext_hand.max_parallel` (1..4), không ép backend codex vì intent ban đầu là Sol low.

Thiếu daemon/provider/capability **trước dispatch**: `auto` quay đường shell cũ, `paseo-required` báo lỗi, không silent fallback. Parent/project/target không xác minh được thì chặn. Sau create/send hoặc ACK không rõ, reconcile exact invocation/attempt/epoch, giữ reservation; không tạo shell/native writer thứ hai.

Mỗi managed hand có workspace/worktree riêng trong **cùng verified project** với parent, caller gắn parent canonical và tab/track của parent; không hứa sidebar native lồng child. Theo quyết định 09/11/2026 (thay Q4), khi execution đã settled đầy đủ report/hooks thì chuyển `awaiting_review`, tự archive **exact child** và workspace riêng của child; không cần review để archive, không archive parent. Membership chỉ theo public `agent.workspaceId`, không theo cwd vì nhiều workspace local có thể cùng checkout. Chỉ archive workspace do plugin tạo, kể cả private LOCAL, khi mọi member cùng workspaceId đã archived (known closed child của plugin phải archive trước), không có `main_session`/role `main` hay agent không do plugin tạo. Giữ workspace local shared/main/unknown; không suy ownership từ tên hoặc cwd, không gom theo cwd hay di chuyển/xoá thư mục. Plugin worktree giữ nguyên quy tắc hiện có; archive local không xoá checkout, Paseo chỉ có thể xoá worktree do Paseo sở hữu. Lỗi visibility giữ lifecycle/data để retry, không tạo writer trùng. `managed archive` idempotent. Sol vẫn phải đọc diff/report và `review-approve` trước followup. Followup restore workspace rồi mở lại cùng exact child (giữ agent/workspace IDs) với brief tự chứa, epoch/request key và baseline mới; không phải CLI context resume, không tạo child trùng. Thiếu cwd/worktree thì chặn. Giữ history, report, patch, worktree và mọi thư mục/artifact; không cleanup. Archive chỉ đổi khả năng hiển thị ở sidebar Paseo, không đổi các dòng done của hh-ps/panel. Một managed execution là một hand trong pool, không tạo side-session root; token từ parser/ledger chuẩn, ACP chỉ projection, thiếu usage/quota giữ `?`.

Containment managed worker trên macOS là best-effort có thời hạn: snapshot cây con khoảng 50 ms khi runner poll, trước cancel/reap, và scan cùng user theo exact entry `HYBRID_HANDS_INVOCATION_ID` bằng `KERN_PROCARGS2` (Linux dùng `/proc`). Worker giữ identity PID + OS start time + comm và quan hệ cha; trước mỗi signal phải xác minh lại identity. Cancel gửi TERM rồi KILL có thời hạn tới group còn được sở hữu và các identity cây con/marker, kể cả child đã `setsid` hoặc reparent. Gateway/controller và ancestors được bảo vệ. Chỉ root đã reap, group vắng và không còn process cây con/marker sống mới có evidence `root_group+tracked_tree+env_marker`; lỗi scan, mất authority hoặc process còn sống giữ unknown và reservation, kể cả hoàn tất bình thường. Sau restart không signal numeric PID được khôi phục khi thiếu quyền sở hữu `Popen`. Môi trường chỉ parse trong bộ nhớ, không lưu/log giá trị. Process vừa bỏ marker vừa double-fork giữa hai snapshot vẫn có thể thoát: macOS không có absolute containment như cgroup.

Phiên chính mặc định Opus 5.5 high v1; có thể mở Opus high v2/v… hoặc Sol 6.1 high. Phiên phụ mặc định Sol 6.1 high, có thể là Opus 5.5 high đúng tài khoản v1/v2/v… . Đổi model/account: mở phiên mới từ bàn giao, không dùng `/model` giữa phiên.

Mặc định `ext_hand.order`: dsh (`deepseek-v4.1-flash`, effort `off`, thinking disabled) → codex (`gpt-6.1-sol`, low) → claude-v1 (Opus 5.5 low) → claude-v2 (Opus 5.5 low). `claude_accounts` lấy từ mặc định plugin → global `~/.hybrid-hands/config.json` → repo; v1=`~/.claude`, v2=`~/.claude-hand`, thêm v… bằng cấu hình. `claude-main` và `claude` chỉ là alias tương thích lần lượt của `claude-v1` và `claude-v2`.

Nhãn tài khoản thống nhất dạng `{provider} {slot} {plan} {name}` (ví dụ `claude v1 Max anhtp`, `gpt v1 Plus anhtp`), đổi bằng `ext_hand.account_label_format` (chỉ 4 placeholder đó). Mỗi `ext_hand.claude_accounts.vN` và `ext_hand.gpt_accounts.vN` (mặc định `v1` home `~/.codex-hand`, chỉ phục vụ nhãn) nhận `plan`/`name` tuỳ chọn; thiếu `name` thì Claude lấy phần trước `@` của `oauthAccount.emailAddress` trong `<config_dir>/.claude.json`, GPT hiện `?`. Nhãn xuất hiện ở `parallel-subagents` status, `pick` và hh-ps (JSON thêm `account_label`, giữ field cũ). Plan GPT thiếu cấu hình lấy từ `rate_limits.plan_type` của rollout mới nhất. `hand-ext parallel-subagents accounts [--json]` liệt kê tài khoản đánh số; `on` không cờ trên terminal hỏi chọn, slash command hỏi bằng AskUserQuestion.

Luôn chạy `hand-ext pick --json` trước để biết backend/model/effort/account, `native`/`native_reason` và lý do bỏ qua, kể cả trước native v1 để giữ chặn ≥5%/ngày (thiếu nguồn cũng chặn). Ở đường cũ, cùng account và tools chọn đúng model/effort mới native; khác account hoặc thiếu capability dùng `hand-ext run --backend auto`. Không tự áp native cho account khác.

| Phiên phụ | dsh | codex low | claude-v1 low | claude-v2 low | UI v1 low |
|---|---|---|---|---|---|
| Sol | hand-ext | native Codex (đường cũ; opt-in xem trên) | hand-ext | hand-ext | hand-ext claude-v1 |
| Opus v1 | hand-ext | hand-ext | Agent hybrid-hands:hand | hand-ext | Native khi preflight v1 đủ; thiếu thì hand-ext claude-v1 |
| Opus v2 | hand-ext | hand-ext | hand-ext | Agent hybrid-hands:hand | hand-ext claude-v1 |

Sáng tạo UI mặc định claude-v1 low. Native v1 chỉ khi `hand-ext pick --json` thực trả `claude-v1`, model `claude-opus-5-5`, effort `low`, đúng account và đủ capability. Pick trả dsh/codex chưa chứng minh guard v1 đã qua: dùng `hand-ext run --backend claude-v1` để wrapper enforce guard, không sửa config/order hoặc suy guard pass. Guard chặn thì không spawn native v1; ghi yêu cầu để Opus quyết. Công việc theo order tiếp tục backend pick chọn.
Native Codex đường cũ dùng `fork_turns=none`, brief tự chứa, luật dữ liệu nguyên văn; executor làm trực tiếp, không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác. Tổng native + hand-ext ≤ `ext_hand.max_parallel` (1..4); cùng file/phụ thuộc tuần tự. Unknown sau spawn phải reconcile/wait, không tạo duplicate writer. Không bật parallel-subagents, không đổi slots/config. Completed giữ tab/history, không archive parent. Native không tạo run/meta/report/token ledger hand-ext; usage qua runtime/Paseo, thiếu token/USD~/quota ghi `?`, không suy quota.

Review thấy lỗi: giao lại cùng backend đúng một lần; lần thứ hai vẫn hỏng chuyển backend kế tiếp theo order dsh → codex → claude-v1 → claude-v2. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do vào bàn giao để Opus quyết; không tự đổi effort. Exit 8: đợi slot, không đổi backend/tự làm.


## Vận hành managed hand Paseo

Recipe này dành cho operator ở giai đoạn live đã được cấp quyền; lượt docs không chạy daemon/model thật. Official CLI package root phải là bản Paseo 0.15.0 đã xác minh; daemon home phải đúng target chứa parent. `ext_hand.paseo` nhận `package_root`, `target` (`kind: instance`, `home` tuyệt đối) và `state_root` tùy chọn; mode default vẫn `shell`, pilot chỉ bật repo được giao. Không sửa credential/settings hoặc đăng ký provider thủ công.

```sh
hand-ext provider setup --home /ABS/DAEMON_HOME --package-root /ABS/PASEO_CLI_ROOT --dry-run
hand-ext provider setup --home /ABS/DAEMON_HOME --package-root /ABS/PASEO_CLI_ROOT --apply
paseo daemon reload --home /ABS/DAEMON_HOME
hand-ext provider status --cwd /ABS/REPO
```

Setup mặc định dry-run, chỉ đề xuất `hh-hand-codex`, `hh-hand-dsh`, `hh-hand-claude-v1`, `hh-hand-claude-v2` (`extends: acp`, entry `bin/hand-paseo-acp`); apply giữ providers/khóa khác và backup private trước atomic write theo official schema. Config đã ghi không chứng minh runtime đã nạp. Paseo 0.15.0 hỗ trợ public `daemon reload`: operator kiểm `appliedPaths`, `restartRequiredPaths`, `overrideControlledPaths`, rồi status phải xác nhận catalog provider khả dụng. Không cần mặc định restart chỉ để thêm providers; không hứa auto-watch. Reload có thể áp mọi thay đổi reloadable đang chờ, nên operator kiểm delta trước. Đây là kết luận source, chưa kiểm live.

Sau dispatch, lấy exact key từ output hoặc `managed ls`; `EPOCH` là số nguyên >=1. Khi settled đủ report/hooks, hand chuyển `awaiting_review` và tự archive child/workspace riêng theo contract managed ở trên. Sol vẫn đọc report/diff và kiểm completion/quiescence trước `review-approve`, rồi mới followup. `managed archive` chỉ cần khi retry visibility, có tính idempotent và không đợi review. Các lệnh lifecycle chỉ chấp nhận latest exact epoch và terminal evidence:

```sh
hand-ext managed ls --cwd /ABS/REPO
# Retry archive nếu cần; không phải bước sau review
hand-ext managed archive --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH
hand-ext managed review-approve --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH
hand-ext managed followup --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH --brief /ABS/fresh-brief.md
```

`hand-ext managed recover --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH` mặc định chỉ kiểm chứng, không ghi state/sink/reservation; thêm `--apply` mới cho phép settlement. Với cancelled-unresolved, phương thức `post_hoc_reverify` bắt buộc latest exact epoch, binding bất biến khớp, inventory OS identity đầy đủ (PID + OS start + uid), root đã được retained Popen reap, và owner có self-ack đúng worker/key sau khi runner trả về hoặc OS identity owner đã chết/reused. Mọi identity đã theo dõi phải vắng/reused và scan marker cùng user mới phải sạch; owner/ancestor chỉ được loại khỏi scan bằng identity chính xác. PID vắng, UI idle hay timeout không đủ bằng chứng. Record thiếu proof đầy đủ bị từ chối ở đường chuẩn; không bổ sung OS birth từ PID hiện tại.

Apply giữ status `cancelled` và exit code đã lưu, dùng supervisor, năm completion hooks và admission release chuẩn; không launch lại backend, không tạo usage giả hay xoá reservation thủ công. Apply lặp lại sau settlement không đổi record; hook `in_progress` chưa có proof vẫn giữ reservation. Diagnostics chỉ chứa method/stage/mã lỗi cho phép/PID/OS start và identity inventory, không chứa env/argv/stderr hay exception text. Unknown cũ không tự xoá qua scan bình thường; recover cần đầy đủ proof mới. Lỗi scan thật làm inventory incomplete và không thể được hợp thức hoá bằng PID absence.

Ngoại lệ do người vận hành xác nhận chỉ dành cho record cancelled/unresolved legacy trước 0.35.5 thiếu inventory/reap proof: `hand-ext managed recover --cwd /ABS/REPO --key INVOCATION_UUID:ATTEMPT_UUID:EPOCH --legacy-attest --reason "lý do kiểm chứng"` (dry-run; thêm `--apply` để ghi). Flag và lý do xác nhận nguồn gốc trước 0.35.5 theo người vận hành; record cũ không lưu phiên bản plugin nên không tự xác minh được tuổi record. Evidence inventory/reap hiện đại, kể cả incomplete/failed, đều bị từ chối. Record có complete proof phải dùng `post_hoc_reverify`. Ngoại lệ kiểm binding durable, latest epoch, revision và reservation dưới lock, owner đã vắng hoặc chứng minh PID reused, root/group đã vắng hoặc root khác OS birth, cùng scan marker mới sạch, không có bất định/EPERM. Owner còn sống thì đóng đúng child qua public Paseo rồi thử lại. Khi birth cũ thiếu, `--owner-os-start` (và `--root-os-start` nếu cần) chỉ nhận birth người vận hành đã quan sát trước đó, gắn đúng PID đã lưu; không suy từ opaque `start_identity`. Recover không gửi tín hiệu dừng tiến trình.

Attestation giữ `quiescence.confirmed=false`, ghi `details.attested=true`, method `operator_legacy_attest`, lý do và bằng chứng an toàn; không tạo `root_reaped` hay `inventory_complete`. Đây là ngoại lệ của con người để chạy năm completion hooks và release đúng một lần, không phải xác nhận containment đầy đủ. Rủi ro còn lại: tiến trình đã gỡ marker **và** thoát khỏi cây theo dõi có thể không được phát hiện. Mọi false quiescence khác vẫn giữ reservation.

AdmissionConflict/AdmissionFull trước reservation/dispatch ghi terminal `not_admitted`, exit 8 với kind và holding execution key (không có key nếu slot shell giữ pool); hh-ps hiển thị lỗi kết thúc. Intent legacy chưa từng admission cũng có thể dùng cùng lệnh attestation để ghi `not_admitted`, chỉ khi record và pool đều không có reservation cho exact key, không process/owner/writer/placement/dispatch/start/artifact hay receipt lạ. Durable reservation được ghi trước CAS không phải bằng chứng chưa admission. Dry-run không ghi; apply lặp lại giữ nguyên bytes.


Sau settlement đầy đủ report/hooks, trạng thái `awaiting_review` tự archive exact child và workspace riêng; archive idempotent, không cần review. Followup vẫn bắt buộc `review-approve`, restore workspace rồi dùng key epoch hiện tại để cấp epoch/request key và baseline mới trên cùng child; thiếu cwd/worktree thì chặn. Không dùng `paseo send` trực tiếp cho managed task, không hứa backend resume. Khi ACK/outcome/settlement chưa rõ, giữ key/reservation để reconcile; không chạy lại run tạo invocation mới. Không cleanup worktree hay `output/llm/`.

[Spec/interface](docs/2026-11-09-hand-paseo-agent-spec.md) và [plan/gate](docs/2026-11-09-hand-paseo-agent-plan.md) giữ trạng thái offline/live/release. Source/fixtures không chứng minh stop/reopen/placement từng backend đã chạy thật; release/install do brain điều phối riêng.

Codex Sol và hand dùng chung `~/.codex-hand`: mỗi lượt hand override `model` bằng `-m`, `model_reasoning_effort` bằng `-c`, `sandbox_mode` bằng `-s`. Doctor không chặn nếu ba khóa thiếu/lệch và không ghi config; kiểm tra cài đặt, đăng nhập gói và khóa legacy không override như `service_tier` vẫn bắt buộc.

## Tóm tắt

- **Mục đích:** plugin Claude Code điều phối brain/hand lai theo 3 tầng Opus / Sol / dsh, bật theo từng dự án thay cho `parallel-subagents`: Opus (brain) chạy trên gói Claude chính; Sol là phiên phụ Codex trên tài khoản ChatGPT riêng; việc code/test/tài liệu L0/L1 bắt buộc giao hand theo `ext_hand.order` trên gói subscription thứ hai để giữ hạn mức gói chính.
- **Thành phần:**
  - hand ngoài: lệnh `hand-ext` (order mặc định dsh → codex → claude-v1 → claude-v2; gemini chỉ gọi tường minh; sổ token `output/llm/hand_usage.json`, sổ USD~ Go toàn máy `~/.hybrid-hands/go_usage.jsonl` và sổ Codex `~/.hybrid-hands/codex_usage.jsonl`, lệnh `hand-ext usage`), skill `ext-hand`;
  - hand Claude: agent `hybrid-hands:hand` (gói chính) cho việc cần tool riêng của Claude Code, lệnh trả phí của dự án, hoặc sau khi `hand-ext` thoát 7 và đã đọc lý do từ `hand-ext doctor`;
  - phiên phụ: lệnh `side-session` (mặc định mở phiên Sol Codex `gpt-6.1-sol` effort high, có ngữ cảnh brain riêng cho gói việc dài; hợp đồng bàn giao `.done`), skill `side-session`; lệnh `hh-ps` xem cây phiên Claude → subagent → lượt hand ngoài; lệnh `cc-switch` chuyển một phiên Claude qua lại giữa terminal và Paseo mà không để transcript rẽ nhánh; skill `paseo` theo dõi từ điện thoại;
  - hook SessionStart (khuôn brief, luật chọn hand, luật hạn mức) và UserPromptSubmit (bản ngắn).
- **Luật hạn mức:** không dùng/tạo API key, không chuyển API khi hết quota; báo backend, token, quota/reset và USD~ sau lượt (thiếu ghi `?`). Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do để Opus quyết. Exit 8: chờ slot.
- **Luật dữ liệu:** phiên phụ Sol được đọc secret và dữ liệu khách hàng như Opus; luật dưới áp cho hand ngoài (dsh, gemini, codex dùng làm hand): không giao hand ngoài việc phải đọc hoặc gửi secret (`.env`, token, mật khẩu, URL DB có mật khẩu) hay dữ liệu khách hàng (tài liệu, nội dung DB, log có dữ liệu khách hàng, tên/thông tin cá nhân); việc đó dùng hand Claude. Được giao code, test, tài liệu kỹ thuật; tài liệu hay dữ liệu mẫu đã bỏ thông tin khách hàng và công khai được. Không hiện giá trị `.env` áp cho mọi tầng.
- **Luật test tối thiểu:** brain ghi mức test trong KIỂM CHỨNG của brief; mặc định hand chỉ viết test tối thiểu đủ chứng minh thay đổi đúng (1 test đường chính + tối đa 1-2 case biên/lỗi quan trọng, ưu tiên thêm assert vào test sẵn có). Mức "kỹ" chỉ gồm ĐÚNG 2 nhóm: (1) tính năng tạo hứng thú, giữ chân khiến người dùng trả tiền; (2) bảo mật chống tấn công từ ngoài. Hai nhóm này test đủ nhánh/biên/lỗi và kiểm chứng thực tế bằng luồng thật; nhóm (1) đo bằng event analytics + feature flag/A-B, chỉ đọc số tổng hợp không có thông tin cá nhân, nhóm (2) chạy SAST, quét dependency, DAST staging.
- **Cách ly worktree:** `hand-ext run` mặc định chạy hand trong git worktree sạch (chỉ file tracked + thay đổi chưa commit/untracked không bị ignore; `.env` bị ignore không có trong workspace), lưu `changes.patch` rồi áp về cwd gốc; xem mục 5.3.
- **Bật theo dự án:** cài ở scope project trong thư mục dự án, tắt `parallel-subagents` ở scope project (xem mục 3).
- **Việc cần làm lần đầu:** `hand-ext setup`, người dùng tự đăng nhập từng backend (mục 5), rồi `hand-ext doctor`.

## Ba tầng Opus / Sol / dsh

| Tầng | Vai trò |
|---|---|
| Opus (brain, gói Claude chính) | Thư ký, solution architect, BA, product manager; phân lane, viết spec/plan L2/L3, duyệt tóm tắt, đọc bàn giao, không đọc diff task đã giao Sol |
| Sol (phiên phụ Codex `gpt-6.1-sol` effort high, tài khoản ChatGPT riêng, `CODEX_HOME` `~/.codex-hand`) | Lead tech, lead QA, quyền ngang Opus; viết spec L1, review code mọi hand mình giao, gọi `hand-ext run --backend auto` theo `ext_hand.order` |
| dsh (gói OpenCode Go) | Dev, tester |
| Hand Opus `low` (`hybrid-hands:hand`) | Việc sáng tạo: UI design, mockup, design token, câu chữ; phần code hoá giao hand theo `ext_hand.order` |

| Lane | Ai viết spec/plan | Ai duyệt | Ai làm | Ai review code |
|---|---|---|---|---|
| L0 (sửa nhanh) | Không viết spec | Không duyệt | hand theo `ext_hand.order` | Sol |
| L1, không có lựa chọn giải pháp | Sol | Không duyệt, Opus đọc bàn giao | hand theo `ext_hand.order` | Sol |
| L1 có lựa chọn giải pháp, hoặc thuộc mức kỹ | Sol, mở đầu bằng tóm tắt quyết định 1 trang | Opus đọc tóm tắt | hand theo `ext_hand.order` | Sol |
| L2/L3 | Opus | Người dùng | Opus cắt thành các gói cỡ L1, giao các phiên Sol | Sol |

Opus gom nhiều việc L0 vào một phiên Sol (mỗi task một phiên), mở bằng `side-session start --provider codex`, chờ `<handoff_dir>/<tên>.done` bằng Monitor rồi đọc `side-session handoff`. L2/L3 do Opus viết spec/plan, người dùng duyệt, Opus cắt thành gói cỡ L1 giao các phiên Sol (tối đa `max_parallel`). Việc sáng tạo giao `hybrid-hands:hand`; trong phiên Sol gọi `hand-ext run --backend claude-v1` (thoát 7 khi máy đã dùng ≥5% hạn mức tuần Claude trong ngày hoặc không tính được, khi đó ghi yêu cầu vào bàn giao để Opus quyết).

## 1. Cây thư mục

```text
hybrid-hands/
├── .claude-plugin/marketplace.json     # marketplace hybrid-hands-local
├── README.md
├── paseo-hh-tree/                      # plugin Paseo hiện cây phiên trong app
├── tests/                              # test của hand-ext, side-session, hh-ps, cc-switch
└── plugins/hybrid-hands/
    ├── .claude-plugin/plugin.json
    ├── agents/hand.md                  # hand Claude
    ├── bin/hand-ext, bin/side-session, bin/hh-ps, bin/cc-switch  # vào PATH của tool Bash khi plugin bật
    ├── lib/hand_ext/ (backends/: codex | claude | dsh; day_budget.py, isolation.py), lib/side_session/, lib/hh_ps/, lib/cc_switch/
    ├── commands/to-paseo.md, commands/to-term.md  # slash command chuyển phiên hai chiều
    ├── hooks/hooks.json
    ├── scripts/session-start-policy.sh, scripts/inject-policy.sh
    ├── skills/ext-hand/, skills/side-session/, skills/paseo/
    └── templates/hand-brief.md, ext-hand-preamble.md, dsh-hand.yml, side-session-prompt.md, side-session-prompt-codex.md
```

## 2. Cài đặt

Chạy trong thư mục dự án (`<thư-mục-repo>` là nơi clone repo claude-plugins):

```sh
claude plugin marketplace add <thư-mục-repo>/hybrid-hands
claude plugin install hybrid-hands@hybrid-hands-local --scope project
claude plugin validate <thư-mục-repo>/hybrid-hands
```

`bin/` của plugin nằm trong PATH của tool Bash khi plugin bật; hook SessionStart vẫn in đường dẫn tuyệt đối tới `bin/` để brain gọi được nếu PATH thiếu.

## 3. Chuyển qua lại với parallel-subagents

Trong thư mục dự án:

```sh
# dùng hybrid-hands cho dự án này
claude plugin disable parallel-subagents@parallel-subagents-local --scope project
claude plugin enable hybrid-hands@hybrid-hands-local --scope project
# quay lại parallel-subagents
claude plugin disable hybrid-hands@hybrid-hands-local --scope project
claude plugin enable parallel-subagents@parallel-subagents-local --scope project
```

Hai plugin không nên bật cùng lúc (hai policy brain/hand chồng nhau). Cơ sở: `enabledPlugins` đặt được ở mọi file settings ([settings reference](https://code.claude.com/docs/en/settings-reference.md#enabledplugins), 11/2026) và khoá cùng tên ở scope cao hơn ghi đè scope thấp hơn, thứ tự managed > dòng lệnh > project local > project > user ([settings precedence](https://code.claude.com/docs/en/settings.md#settings-precedence), 11/2026). Scope project ghi vào `.claude/settings.json` (commit, áp cho cả nhóm); muốn chỉ áp cho máy mình thì dùng `--scope local`.

## 4. Cấu hình global và dự án

Cấu hình ưu tiên: mặc định plugin → global `~/.hybrid-hands/config.json` (đổi đường dẫn bằng `HYBRID_HANDS_CONFIG`) → repo `.claude/hybrid-hands.json` → cờ CLI. Dict merge sâu; list/scalar thay nguyên. Global thiếu thì bỏ qua; global hỏng báo lỗi kèm đường dẫn và dừng. `hand-ext config --json` in cấu hình hiệu lực, nguồn từng key và đường dẫn file đã đọc. `ext_hand.claude_accounts` và `ext_hand.backends.*` đặt được ở global. Dưới Paseo, biến `HYBRID_HANDS_CONFIG` phải có trong môi trường daemon mới có tác dụng.

### Model ba tầng theo repo — 0.45.0

`hand-ext models` xem model/effort/account và nguồn cấu hình của brain, phiên phụ và hand. Chỉ dùng `set`/`unset` khi người dùng chốt thay đổi cụ thể; ghi atomic vào cùng file repo đã resolve như `parallel-subagents`, kể cả fallback main worktree, không tạo config riêng cho worktree.

```sh
hand-ext models --json
hand-ext models options --json
hand-ext models set --tier brain --model claude-opus-5-5 --effort high --account v2
hand-ext models set --brain claude:claude-opus-5-5:high@v1 --side codex:gpt-6.1-sol:high --dry-run
hand-ext models set --hand codex=gpt-6.1-sol:low --hand-order dsh,codex,claude-v1,claude-v2
hand-ext models unset hand --dry-run
```

Cờ phẳng `--tier brain|side|hand --model MODEL --effort EFFORT [--account vN]` suy provider từ capability của model và không dùng chung với `--brain`, `--side`, `--hand`, `--hand-order`. Codex chuẩn hoá effort `max` thành `xhigh`. Account chỉ áp cho Claude; GPT/DeepSeek bỏ qua và cảnh báo. Brain/side Claude không truyền account thì giữ account hiện tại; Hand Claude bắt buộc chọn account hợp lệ để xác định backend `claude-vN` (GPT dùng `codex`, DeepSeek dùng `dsh`). Trong màn hình chọn, model DeepSeek chỉ cho tầng Hand và effort `off` nhập qua “Other”; các danh sách quá bốn mục cũng dùng “Other”.

Brain/side chỉ nhận `claude|codex`, `@vN` chỉ Claude; model cần có giá canonical và capability provider. `unset brain|side|hand` gỡ override cả tầng, giữ cấu hình khác và trở về nguồn kế thừa. Các lệnh hỗ trợ `--cwd PATH`, `--json`; set/unset có `--dry-run`. Trong Claude Code dùng [`/hybrid-hands:models`](plugins/hybrid-hands/commands/models.md) để chỉ xem, không hỏi hay ghi; `/hybrid-hands:models set` mở một màn hình gồm bốn câu Tầng, Model, Effort, Account trong một lần AskUserQuestion, rồi chạy một lệnh với `--tier`, `--model`, `--effort`, `--account`. Lựa chọn là xác nhận để ghi, không thêm dry-run hay hỏi xác nhận. `hand-ext models options --json` cung cấp danh sách chỉ đọc cho luồng chọn; slash command với đối số khác chuyển nguyên cho CLI. Ghi thành công: mở phiên mới để áp dụng; phiên đang chạy giữ model/account hiện tại. Mặc định brain trong code vẫn là Codex Sol high.

### Mode parallel-subagents

`parallel_subagents.enabled` mặc định `false`, chỉ chấp nhận bool JSON thật (`true`/`false`); sai kiểu về `false` và warning stderr. `true` chỉ hiệu lực khi provenance là repo `.claude/hybrid-hands.json` (kể cả fallback config main worktree); global `true` bị bỏ qua kèm warning, consumer chỉ thấy `false`. `hand-ext config --json` giữ nguồn và đường dẫn config. Hook gặp config lỗi sẽ warning không hiện giá trị, dùng policy thường và exit 0; CLI giữ cách báo lỗi cấu hình hiện có.

Chỉ thay đổi mode sau khi người dùng chốt cho repo đó; brain/hand không tự bật. Plugin `parallel-subagents` cũ luôn tắt. Trong Claude Code dùng `/hybrid-hands:parallel-subagents on|off`; trong terminal/Codex dùng `hand-ext parallel-subagents on|off`. `parallel` là alias cũ tương thích. Dùng lệnh thay vì sửa JSON thủ công:

```bash
hand-ext parallel-subagents                         # trạng thái, nguồn và file
hand-ext parallel-subagents --json                  # chỉ trạng thái dạng JSON
hand-ext parallel-subagents on --cwd /duong/dan/repo
hand-ext parallel-subagents off --cwd /duong/dan/repo
```

Lệnh on/off giữ các key khác, ghi bool vào config repo và in đường dẫn đã ghi. Trong linked worktree chưa có config riêng, nếu loader dùng config main checkout thì lệnh ghi đúng file fallback đó (ảnh hưởng các worktree dùng chung file). Chưa có file thì tạo `.claude/hybrid-hands.json` tại repo hiện tại. JSON lỗi hoặc section không phải object bị từ chối, giữ nguyên file. Luôn **mở phiên mới để hook nạp luật**; luật đã nạp trong phiên cũ vẫn còn hiệu lực.

`parallel_subagents.backend` mặc định `"claude-v1"`, nhận string từ global hoặc repo; alias `claude-main`/`claude` thành `claude-v1`/`claude-v2`. Sai kiểu hoặc backend không tồn tại trong cấu hình hiệu lực thì warning không hiện giá trị và dùng `claude-v1`; `hand-ext config --json` giữ nguồn key. Dùng `hand-ext parallel-subagents on --backend claude-v2` (slash command cũng nhận `--backend`); backend sai exit 2, không ghi. Status text/JSON hiện backend, model, effort và nguồn backend; model/effort lấy từ `ext_hand` hiện có. `hand-ext parallel-subagents on --account v2` ghi cùng lúc backend `claude-v2` và `main_session.claude_account = "v2"` để brain (`side-session start --main --provider claude`) và subagent native cùng tài khoản; status hiện `brain_account` và cảnh báo `account_mismatch` khi lệch.

Mode bật giao subagent theo backend đã chọn, tối đa `ext_hand.max_parallel` thực (1..4); cùng file/phụ thuộc tuần tự, brain review code hand mình giao. Trước mỗi lượt giao chạy `hand-ext pick --json --backend NAME`: chỉ preflight backend đó, giữ guard v1 ≥5%/ngày và không fallback theo order. `native: true` dùng Agent `hybrid-hands:hand` cho Claude hoặc native Codex theo ngoại lệ A, đúng account/capability; còn lại dùng `hand-ext run --backend NAME` cho gói việc. Guard chặn hoặc exit 7 thì không spawn, ghi yêu cầu để brain quyết, không tự đổi backend/config.

`main_session` áp cho `side-session start --main`: `provider` mặc định `codex`, `codex_model`/`codex_effort` mặc định `gpt-6.1-sol`/`high`, `claude_model`/`claude_effort`/`claude_account` mặc định `claude-opus-5-5`/`high`/`v1`. `side_session` có các key tương ứng, gồm `provider`, `codex_model`, `codex_effort` và các key `claude_*`. Cờ `--provider`, `--model`, `--effort`, `--account` ghi đè cấu hình; `--resume` mặc định provider Claude và giữ account của state. `main_session` không áp cho phiên người dùng tự mở bằng `claude`.

`main_session.claude_auto_compact_window` mặc định `272000` cho mọi account Claude (`v1`, `v2`, …). Giá trị hợp lệ là số nguyên `100000..1000000` (kể cả hai biên); `null` hoặc chuỗi chính xác `"auto"` bỏ override. Boolean, chuỗi số và các kiểu/giá trị khác báo lỗi cấu hình kèm đường dẫn nguồn. Key và provenance có trong `hand-ext config --json`, theo thứ tự plugin → global → repo; không sửa settings Claude.

`side-session start --main --provider claude` với mọi account, qua Paseo hoặc screen, truyền `CLAUDE_CODE_AUTO_COMPACT_WINDOW` khi có window; `null`/`"auto"` không truyền override. `side-session ls` hiển thị cap theo window đã áp dụng và được lưu lúc khởi chạy main, kèm `(tự nén)`, không theo cấu hình thay đổi sau đó. Main cũ chưa lưu window đã áp dụng giữ cách hiển thị trước đây; cần mở main MỚI để nhận env/window mới, không sửa settings hay restart/dừng main đang chạy. Phiên phụ và hand giữ hành vi hiện có; backend hand Claude lọc biến compact kế thừa từ môi trường phiên chính.


Cả hai mục có `transport` cho Claude: mặc định `paseo`, chọn `screen` tường minh trong cấu hình (không có cờ `--transport`). Paseo lỗi thì báo lỗi, không tự lùi về screen. Phiên Claude qua Paseo nhận `CLAUDE_CONFIG_DIR` theo account. Template Sol chính nhận model/effort thực tế, đường dẫn tuyệt đối tới bin/skill và khuôn brief.

`ext_hand.native.{claude,codex}` nhận `auto` (mặc định) hoặc `off`. `hand-ext pick --json` trả `native` và `native_reason` theo cấu hình, account, model/effort; caller vẫn phải kiểm capability. `off` dùng hand-ext. Claude native phải khớp frontmatter agent (Opus 5.5 low); model/effort khác chạy qua wrapper.

Ví dụ global ngắn (các key còn lại giữ mặc định):

```json
{
  "main_session": {"provider": "claude", "claude_account": "v2"},
  "side_session": {"provider": "codex", "transport": "paseo"},
  "ext_hand": {"native": {"claude": "off", "codex": "auto"}},
  "paseo": {"claude_providers": {"v2": "claude-v2"}}
}
```

Cấu hình repo `.claude/hybrid-hands.json`:


```json
{
  "ext_hand": {
    "max_parallel": 4,
    "order": ["dsh", "codex", "claude-v1", "claude-v2"],
    "claude_accounts": {
      "v1": { "config_dir": "~/.claude", "max_day_pct": 5 },
      "v2": { "config_dir": "~/.claude-hand" }
    },
    "timeout_min": 60,
    "max_tokens": null,
    "sandbox": "workspace-write",
    "ledger": "output/llm/hand_usage.json",
    "quota_state": "output/llm/hand_quota.json",
    "runs_dir": "output/llm/hand-ext",
    "isolation": "worktree",
    "worktree_root": "~/.hybrid-hands/worktrees",
    "go_usage": {
      "ledger": "~/.hybrid-hands/go_usage.jsonl",
      "monthly_limit_usd": 100
    },
    "backends": {
      "codex": { "home": "~/.codex-hand", "model": "gpt-6.1-sol", "effort": "low" },
      "claude-v2": { "model": "claude-opus-5-5", "effort": "low", "max_turns": 80 },
      "claude-v1": { "model": "claude-opus-5-5", "effort": "low" },
      "dsh": { "home": "~/.dsh-hand", "key_file": "~/.dsh-hand/go.key", "browser_dir": "~/.dsh-hand/browser", "model": "deepseek-v4.1-flash", "effort": "off", "base_url": "https://opencode.ai/inference/go/openai/v1", "capacity_wait_min_lines": 30, "capacity_wait_seconds": 180 },
      "gemini": { "home": "~/.gemini-hand", "model": "gemini-4-carbon" }
    }
  },
  "side_session": {
    "max_parallel": 4,
    "handoff_dir": "docs/work-in-progress/handoffs",
    "codex_model": "gpt-6.1-sol",
    "codex_effort": "high"
  },
  "ps": {
    "session_meta_globs": ["docs/work-in-progress/*.meta"]
  }
}
```

Tên khoá chuẩn theo `lib/hand_ext/constants.py` (mặc định), `lib/side_session/` và `lib/hh_ps/`; thiếu file thì dùng các giá trị mặc định trên. `ps.session_meta_globs` (mặc định rỗng) là danh sách glob tương đối repo trỏ tới file `<TÊN>.meta` của launcher riêng (dạng `key=value`: `uuid=`, `cap_usd=` là trần token, `started=`, `screen_pid=`, `exempt=` chỉ là miễn trần ngày, trần token vẫn hiện); `hh-ps` dùng để hiện trần token và tỉ lệ. `<PL>` được thay bằng thư mục plugin. Order mặc định dsh → codex → claude-v1 → claude-v2; gemini chỉ gọi tường minh. `claude-v1` trỏ gói chính `~/.claude`, mặc định `claude-opus-5-5`/`low`, mặc định cho sáng tạo và chặn khi máy đã dùng từ `max_day_pct` (mặc định 5%) hạn mức tuần Claude trong ngày. Sổ Go nằm ngoài repo (mặc định `~/.hybrid-hands/go_usage.jsonl`, bản tóm tắt cạnh đó); đổi bằng `go_usage.ledger`, còn biến `HYBRID_HANDS_STATE_DIR` đổi thư mục mặc định (dùng cho test). Sổ Codex nằm cạnh sổ Go (mặc định `~/.hybrid-hands/codex_usage.jsonl`, cũng theo `HYBRID_HANDS_STATE_DIR`; xem mục 5.2). `backends.dsh.capacity_wait_min_lines` (mặc định 30) và `capacity_wait_seconds` (mặc định 180; 0 để test) điều khiển dự phòng 429. Đơn giá dùng bảng canonical `config/model-prices.json` (mục 6); không cấu hình bảng giá backend thứ hai.

`ext_hand.isolation` nhận `worktree` (mặc định khi cwd là git repo) hoặc `none`; cờ `--isolation` ghi đè cho một lượt. `ext_hand.worktree_root` là thư mục chứa worktree tạm, mặc định `~/.hybrid-hands/worktrees` (nếu không khai báo thì đi theo `HYBRID_HANDS_STATE_DIR`); đường dẫn tương đối tính từ git toplevel. Không nên đặt `worktree_root` trong repo trừ khi thư mục đó bị ignore. Cwd không phải git repo mà isolation là mặc định thì lượt chạy rơi về `none` kèm cảnh báo trong report; nếu `worktree` được yêu cầu tường minh (config hoặc cờ) mà không tạo được worktree sạch thì `run` thoát 2, không âm thầm chạy trong repo gốc.

### 4.1 Phiên phụ: Sol Codex, Chrome, phiên cha, trần ngày, hand ngoài

Theo quyết định 09/11/2026 (thay Q4), side-session qua Paseo ở mọi provider ghi report/handoff rồi `.done`: archive exact child, sau đó archive workspace theo ownership/membership sau; không archive parent. Membership chỉ theo public `agent.workspaceId`, không theo cwd vì nhiều workspace local có thể cùng checkout. Chỉ archive workspace do plugin tạo, kể cả private LOCAL, khi mọi member cùng workspaceId đã archived (known closed child của plugin phải archive trước), không có `main_session`/role `main` hay agent không do plugin tạo. Giữ workspace local shared/main/unknown; không suy ownership từ tên hoặc cwd, không gom theo cwd hay di chuyển/xoá thư mục. Plugin worktree giữ nguyên quy tắc hiện có; archive local không xoá checkout, Paseo chỉ có thể xoá worktree do Paseo sở hữu. Cảnh báo archive workspace không chặn trạng thái `done`; `ls`/`watch` retry có giới hạn. Giữ handoff, state, history, worktree, patch và report, không cleanup. Archive chỉ ẩn ở sidebar Paseo; các dòng done của hh-ps/panel giữ nguyên.

Giao lại bằng `side-session send --name NAME --prompt-file /ABS/FILE` cho mọi provider Paseo. Trình tự: restore workspace → unarchive cùng exact agent qua public send → gửi prompt, đặt state `running`, đổi tên `.done` cũ sang tên duy nhất để giữ lịch sử và khởi động lại watchdog. Không create agent trùng; thiếu cwd/worktree thì chặn. Khi ACK chưa rõ, trạng thái pending chặn gửi lại để tránh prompt trùng; lỗi xác định xảy ra trước khi gửi có thể retry. `start --resume` giữ tương thích hiện có. Lỗi visibility giữ lifecycle/data, không tạo writer trùng.

`side-session tidy [--name NAME] [--apply]`: mặc định dry-run, chỉ liệt kê eligible/blocked và exact IDs dự kiến. Ví dụ `side-session tidy --name NAME` để xem, `side-session tidy --name NAME --apply` để áp dụng. `--apply` idempotent, chỉ archive workspace có ownership từ plugin side state, rỗng/đã archive hết member hoặc có known closed plugin child được archive trước; chặn main, agent không do plugin tạo và member active. `--name` giới hạn cleanup; giữ thư mục local và artifacts.

`side-session start` mặc định `--provider codex`: mở phiên Sol trên Codex với `--dangerously-bypass-approvals-and-sandbox` (không sandbox, không hỏi phê duyệt, toàn quyền ghi và mạng); `--model`/`--effort` mặc định `side_session.codex_model`/`codex_effort` (`gpt-6.1-sol`/`high`). `--resume` vẫn mặc định `claude`. Phiên Sol ghi `<handoff_dir>/<tên>.md` rồi tạo `<handoff_dir>/<tên>.done`; `ls`/`watch` báo `done`, Opus chờ file `.done` bằng Monitor. Các cờ khác:
- `--chrome` / `--no-chrome`: mặc định theo `claude_args` (mặc định `--no-chrome`). `--chrome` thay mọi `--no-chrome` trong argv claude bằng `--chrome` và ghi `chrome` vào state; chỉ dùng với provider `claude`, provider khác in lỗi và thoát 2.
- `--account v1|v2|v…`: account Claude từ defaults plugin + repo (mặc định v1); `--main --provider claude --account v2` mở main Opus v2. Đổi model/account mở phiên mới từ bàn giao.
- `--provider claude|dsh`: `claude` mở phiên Claude Code (ListAgents/SendMessage); `dsh` chạy hand ngoài trong screen bằng `hand-ext run --backend dsh --brief <state_dir>/<tên>.prompt.md --label side:<tên> --cwd <worktree> [--timeout-min <giờ×60>] [--model M] [--effort E]`; không truyền `--max-tokens` vì hand-ext tính cả token đọc cache, trần do `watch` canh (không tính cached). Bắt buộc `--worktree` (thiếu thoát 2); prompt sau khi ghép template phải có mục `LUẬT BẮT BUỘC` (thiếu thoát 2). `watch`/`ls` đọc token của lượt `hand-ext` nhãn `side:<tên>` bắt đầu từ `state.started` (vào + ra, không tính cached); khi lượt kết thúc, chép `report.md` thành `<handoff_dir>/<tên>.md` nếu chưa có và đặt `stopped` (ok) hoặc `dead` (lỗi).
- `--budget-exempt` / `--force-budget`: bỏ qua trần ngày ở lần `start` này; `--budget-exempt` ghi `budget_exempt=True` và cũng miễn mã 20 khi `watch`, còn `--force-budget` chỉ bỏ qua một lần.
- Mọi phiên ghi `parent_session` = `CLAUDE_CODE_SESSION_ID` của phiên gọi; môi trường phiên con bỏ `CLAUDE_CODE_CHILD_SESSION`.

`side_session.budget_check_cmd` (mặc định `[]` = tắt) là argv của lệnh kiểm trần ngày, chạy không qua shell, timeout 30 s; phần tử đầu là đường dẫn tương đối thì tính từ repo (ví dụ `["scripts/day-budget.sh", "status"]`). `start`: mã khác 0 (kể cả lỗi không chạy được lệnh) in stdout của lệnh rồi từ chối, thoát 4, trừ khi có `--budget-exempt` hoặc `--force-budget`. `watch`: chạy lại mỗi vòng; mã 20 và state không `budget_exempt` thì dừng phiên với trạng thái `daystop`. `side-session ls` thêm cột `CHROME`.

Với phiên phụ `codex`, argv có `-c model_auto_compact_token_limit=272000`: Codex tự nén context, `watch` không dừng `capped` theo tổng token tiêu. `TOKENS/CAP` hiển thị `last_token_usage` cuối (input gồm cached + output) trên 272000, không có dấu ` !`; tổng token cộng dồn chỉ để báo cáo.

`side_session.codex_model`/`codex_effort` (mặc định `gpt-6.1-sol`/`high`) là model/effort cho provider `codex` (Sol) và được chuyển tiếp cho hand-ext khi có `--model`/`--effort`; `--model`/`--effort` của `start` đè cho một lượt.

`side_session.status_line_cmd` (mặc định `""` = status line mặc định) là lệnh status line cho phiên phụ provider `claude`, đường dẫn tương đối tính từ repo; `start` truyền `--settings {"statusLine":{"type":"command","command":<đường dẫn tuyệt đối>}}`, ví dụ để phiên phụ ghi số liệu cho lệnh trần ngày.

## 5. Backend của hand ngoài

Lệnh: `hand-ext pick [--json]`, `hand-ext setup|doctor [--backend B|all] [--cwd D]`, `hand-ext run --brief F|- [--backend B|auto] [--browser] [--label L] [--cwd D] [--model M] [--effort E] [--timeout-min M] [--max-tokens N] [--sandbox S] [--isolation worktree|none] [--no-apply] [--keep-worktree]`, `hand-ext status`, `hand-ext usage [--json]`, `hand-ext report`, `hand-ext measure --runs <dir> [--runs <dir>...] [--backend B] [--since D]`. Mã thoát: 0 ok, 1 failed, 2 sai cách dùng hoặc không tạo được worktree khi `isolation=worktree` được yêu cầu, 4 capped, 6 timeout, 7 mọi backend hết hạn mức hoặc chưa đăng nhập. `--browser` chỉ dùng với backend `dsh`: `--backend auto --browser` chỉ xét `dsh`, còn `--backend` khác `dsh` kèm `--browser` thoát 2. Backend `opencode` đã gỡ ở 0.19.0: `order` cũ còn tên này thì `run --backend auto` bỏ qua kèm dòng `bỏ qua opencode: backend 'opencode' không hỗ trợ (đã gỡ, dùng dsh)`, còn `--backend opencode` thoát 2. `claude-v1` nằm trong `order`, mặc định cho sáng tạo. Với `--backend auto`, dsh 429 quá tải được xử lý theo ngưỡng patch/`capacity_wait_*` (mục 5.2), không ghi quota; patch lớn giữ backend, patch nhỏ chạy lại theo phần order còn lại. Mỗi lượt codex ghi sổ `codex_usage.jsonl` (mục 5.2).

| Backend | Gói | Người dùng tự đăng nhập | Theo dõi hạn mức | Rủi ro tính tiền |
|---|---|---|---|---|
| `codex` | ChatGPT | `CODEX_HOME=~/.codex-hand codex login --device-auth` | `used_percent`, `resets_at` từ sự kiện của `codex exec --json`; sổ `~/.hybrid-hands/codex_usage.jsonl` giữ riêng cửa sổ 5h/7d và USD~ ước tính | đăng nhập API key thì tính tiền; `doctor` chặn, hand gỡ biến `OPENAI_API_KEY`; model thiếu giá canonical thì USD null, không bịa giá |
| `claude-v2` | Claude tài khoản thứ hai | `CLAUDE_CONFIG_DIR=~/.claude-hand claude` rồi `/login` | lỗi hết hạn mức trong stream, `hand-ext status` | dùng nhầm tài khoản chính thì ăn hạn mức brain; hook repo vẫn chạy |
| `claude-v1` | Gói Claude CHÍNH `~/.claude`; `claude-opus-5-5`, effort `low`; mặc định cho sáng tạo | đã đăng nhập sẵn, không đăng nhập thêm | % tuần Claude máy này đã dùng trong ngày so với `max_day_pct`; `hand-ext status` | dùng cho việc không sáng tạo sẽ ăn hạn mức brain; từ 5%/ngày hoặc không tính được thì thoát 7, ghi yêu cầu vào bàn giao để Opus quyết |
| `dsh` | OpenCode Go qua DeepSeek Harness (`dsh --profile headless`, DeepSeek V4.1 Flash, effort `off`, thinking disabled); tuỳ chọn `--browser` qua Playwright MCP cô lập | cài `npm install -g @deepseek-ai/dsh@latest`; người dùng tự chép API key Go từ OpenCode Console vào `~/.dsh-hand/go.key` (một dòng) rồi `chmod 600 ~/.dsh-hand/go.key`; cài trình duyệt theo mục 5.1 nếu dùng `--browser` | lỗi `QUOTA`/`RATE_LIMIT` trong sự kiện `turn_end`, `hand-ext status`; USD~ ước tính trong sổ Go toàn máy (mục 5.2); 429 quá tải có nhánh riêng, không ghi quota | Extra Usage bật hoặc Console còn credit thì tính tiền khi hết hạn mức: phải TẮT Extra Usage, để credit 0; metadata models.dev ghi 0910 nhưng OpenCode báo Go đã phục vụ 1017 dưới cùng id; dsh luôn đọc `<cwd>/.env` nên hand khởi chạy dsh từ `~/.dsh-hand/launch` và trỏ workspace sang repo bằng patch `templates/dsh-hand.yml`; không được tạo `~/.dsh-hand/.env`; dsh bản developer preview, `doctor` chỉ đạt với bản đã đọc mã nguồn (0.2.1-rc.5) |
| `gemini` | dự kiến | chưa có | chưa có | Gemini 4 Carbon chưa mở cho gói nào (chỉ Fairwind Program, 28/10/2026); gói AI Pro/Ultra đã chuyển sang Antigravity CLI |

### 5.1 Trình duyệt cho `dsh` (`--browser`)

`--browser` mặc định tắt. Khi bật, `hand-ext` ghi thêm một patch riêng cho lượt chạy tại `<runs_dir>/<run_id>/browser.patch.json` và truyền nó bằng `--patch` sau patch chung; file `~/.dsh-hand/hand.patch.yml` không bị sửa. Patch này thêm MCP server stdio `@deepseek-ai/dsh-mcp-client` tên `playwright`, chạy `node <browser_dir>/node_modules/@playwright/mcp/cli.js --headless --isolated --browser chromium --blocked-origins "<5 origin TikTok>" --output-dir <runs_dir>/<run_id>/browser`; env của server chỉ có `PLAYWRIGHT_BROWSERS_PATH=<browser_dir>/ms-playwright` (dsh tự lọc biến dạng key/token và `DSH_*`, nên key Go không sang tiến trình MCP).

Cài một lần (thư mục mặc định `~/.dsh-hand/browser`, đổi bằng `backends.dsh.browser_dir`):

```sh
npm install --prefix ~/.dsh-hand/browser @playwright/mcp@0.0.83
PLAYWRIGHT_BROWSERS_PATH=~/.dsh-hand/browser/ms-playwright \
  ~/.dsh-hand/browser/node_modules/.bin/playwright install chromium
```

`hand-ext doctor --backend dsh` có dòng `browser` báo thiếu `cli.js`/`ms-playwright` nhưng không làm doctor fail vì trình duyệt là tuỳ chọn.

Giới hạn: chỉ duyệt trang công khai; không đăng nhập, không tạo tài khoản, không điền form, không mua, không vượt captcha; không mở TikTok; không tải hay chạy file tải về. `--blocked-origins` chặn request tới 5 origin TikTok nhưng tài liệu Playwright ghi rõ nó không phải ranh giới bảo mật và không chặn redirect, nên luật trong prompt mới là lớp chính. `--isolated` giữ profile trình duyệt trong bộ nhớ; thư mục `<run>/browser` chỉ chứa output (ảnh, snapshot) của lượt chạy.

### 5.2 Mức đã dùng gói OpenCode Go

OpenCode Go tính hạn mức bằng USD theo tháng cho từng model: cửa sổ 5 giờ dùng 20% hạn mức tháng, tuần 50%, tháng 100%. DeepSeek V4.1 Flash có hạn mức tháng **$100**; giá peak dùng cho ước tính bảo thủ lấy từ bảng canonical (mục 6). Nguồn: <https://opencode.ai/docs/go/> (đọc 04/11/2026; nguyên văn "Usage limits are defined as monthly dollar amounts." và "5-hour — 20% of the monthly limit; weekly — 50%; and monthly — 100%."). Go Plus dùng cùng bảng giá với hạn mức tháng $200, đổi bằng `go_usage.monthly_limit_usd`.

Mỗi lượt `dsh` ghi một dòng (bản ghi cũ của backend `opencode` đã gỡ ở 0.19.0 vẫn được tính) vào sổ toàn máy `~/.hybrid-hands/go_usage.jsonl` (không theo repo, vì hạn mức theo tài khoản): `run_id`, `ended`, `backend`, `model`, `tokens`, `cost_usd`, `cost_source` (`exact`/`estimated`/`unknown`), `cwd_basename` (chỉ tên thư mục, không đường dẫn tuyệt đối). Bản tóm tắt `go_usage_summary.json` cạnh sổ được ghi lại sau mỗi lượt và bởi `hand-ext usage [--json]`; mỗi model có ba cửa sổ trượt 5 giờ / 7 ngày / 30 ngày với `used_usd`, `limit_usd`, `percent`, `estimated`, cộng `updated_at`.

USD~ hiển thị là ước tính offline `(input − cached_input) × giá input + cached_input × giá cached + output × giá output`, chia 1 triệu, theo model trong bảng canonical. DeepSeek dùng giá peak như ước tính bảo thủ, không phải hoá đơn hay quota thật. Model thiếu giá thì `cost_usd = null`, `cost_source = unknown`; giá trị `exact` trong sổ legacy không biến USD~ panel thành hoá đơn.

**Sổ Codex:** mỗi lượt backend `codex` kết thúc ghi đúng một dòng JSON vào `~/.hybrid-hands/codex_usage.jsonl` (mặc định theo `HOME`, hoặc `$HYBRID_HANDS_STATE_DIR/codex_usage.jsonl` khi đặt; test đổi `HOME` được). Schema `schema=1`: `run_id`, `ended`, `model`, `effort`, `tokens {input,cached_input,output}`, `cost_usd`, `cost_source` (`estimated`/`unknown`), `codex_home` chỉ basename (ví dụ `.codex-hand`), `windows {"5h": {"used_percent","resets_at"} | null, "7d": {...} | null}` phân loại bằng `window_minutes` (300 = 5h, 10080 = tuần), không chỉ cửa sổ lớn nhất; có gói chỉ có primary tuần, cửa sổ không có mẫu là null. Rollout cũ thiếu độ dài mới dùng primary=5h/secondary=tuần. Giá lấy theo model-id từ bảng canonical `config/model-prices.json`; thiếu hoặc bất hợp lệ thì `cost_usd = null`, `cost_source = unknown` (không bịa giá); đủ thì `(input−cached_input)×input + cached_input×cached + output×output` chia 1e6 và `cost_source = estimated`. Không ghi hội thoại, prompt hay absolute path; không dùng tài khoản `~/.codex`. Lỗi ghi sổ chỉ cảnh báo, không làm fail lượt.

**Dự phòng 429 quá tải (chỉ `--backend auto` với dsh):** nhận diện bằng `is_capacity_error`/`CAPACITY_PATTERN` (không phải quota thật). Hand-ext đếm patch do hand tạo tính từ baseline isolation (không tính thay đổi có sẵn của người dùng), tổng dòng thêm+xoá, gồm file mới và staged. Nếu ≥ `backends.dsh.capacity_wait_min_lines` (mặc định 30): giữ đúng worktree, chờ `backends.dsh.capacity_wait_seconds` (mặc định 180; 0 trong test), chạy tiếp dsh với prompt thêm "đã có patch, làm tiếp", tối đa 2 lần chạy tiếp (tổng 3). Vẫn 429: `failed`, giữ `changes.patch` và worktree, không áp patch dở về source, không chuyển codex dù số dòng giảm. Patch dưới ngưỡng (kể cả rỗng): bỏ patch dsh trong worktree, không áp source, chạy lại brief gốc qua các backend còn lại sau dsh trong `cfg.order`, preflight lần lượt; giữ CLI overrides `--model`/`--effort` theo run. Không gọi backend ngoài order; hết backend dùng được thì exit 7. `--browser` không fallback backend khác: `failed`, giữ worktree và patch, ghi lý do. Lỗi đếm patch hoặc `isolation=none`: fail-closed, giữ dữ liệu, không reset source. Khi đã giữ patch lớn, mọi lượt chạy tiếp không thành công cũng giữ worktree/patch, không áp source hoặc chuyển codex; quota thật vẫn được ghi. `--backend dsh` tường minh và quota thật giữ hành vi cũ; mỗi lần chạy lại vẫn ghi registry, ledger và sổ Go/Codex riêng.

Cửa sổ của Go **có thể không trượt**: OpenCode chưa công bố mốc reset, nên số của `hand-ext usage`, `hand-ext status` và statusline chỉ là ước tính để biết đang ở đâu; **OpenCode Console là nguồn chuẩn**. `hand-ext status` in thêm bảng Go khi đã có tóm tắt; khối cuối mỗi `run` in `hạn mức: ~x% 5h, ~y% tuần (ước tính)`.

### 5.3 Cách ly worktree (mặc định)

Vì hook của Claude Code không chạy trong dsh/codex/gemini, hàng rào chắc nhất là secret không tồn tại trong thư mục hand làm việc. Khi `isolation=worktree` (mặc định nếu cwd là git repo), `hand-ext run`:

1. Tạo worktree detached tại `HEAD` dưới `worktree_root` (mặc định `~/.hybrid-hands/worktrees/<repo>-<run-id>`), ngoài repo.
2. Chép trạng thái làm việc: áp `git diff HEAD --binary` của file tracked rồi chép các file untracked **không bị ignore** (`git ls-files --others --exclude-standard`). File bị ignore như `.env`, `*.demo.env` không bao giờ được chép, nên không có trong workspace. Lớp chặn thứ hai: untracked có basename giống secret (`.env`, `*.env`, `*.pem`, `*.key`, `id_rsa*`, `.netrc`, `.npmrc`, `.pypirc`; trừ `.env.example`/`.env.sample`/`.env.template`/`*.env.example`) bị bỏ qua dù repo quên ignore, và symlink untracked chỉ được chép khi là đường dẫn tương đối, đích resolve nằm trong repo và không giống secret; tên bị bỏ được ghi vào report.
3. Chạy backend với cwd/worktree (dsh nhận worktree qua `HAND_EXT_DSH_WORKSPACE`).
4. Sau run, chụp trạng thái worktree bằng một git index riêng, ghi diff nhị phân vào `<runs_dir>/<run-id>/changes.patch`, rồi áp về cwd gốc bằng `git apply --check` + `git apply`. Xung đột thì không ghi đè thay đổi người dùng: report ghi `xung đột` kèm danh sách file, patch vẫn nằm trong thư mục lượt chạy. Patch rỗng thì bỏ qua áp.
5. Dọn worktree (`git worktree remove --force` + `git worktree prune`) kể cả khi timeout/lỗi; patch vẫn được lưu. `--keep-worktree` giữ worktree để kiểm tra; `--no-apply` chỉ lưu patch, không áp.

Cờ `--isolation none` tắt cách ly cho một lượt (chỉ dùng khi biết repo không có secret/dữ liệu khách hàng). Cwd không phải git repo và isolation là mặc định: chạy trực tiếp `none` kèm cảnh báo trong report. `--isolation worktree` tường minh mà không tạo được worktree sạch (không phải git repo, HEAD chưa có commit, đường dẫn đã tồn tại, lỗi git) thì thoát 2. Worktree được tạo từ `HEAD` nhưng có thay đổi chưa commit, nên hand thấy đúng trạng thái làm việc; hand không thấy file bị ignore hay file untracked nghi bí mật.

### 5.4 Dữ liệu mỗi lượt và lệnh đo

Từ 0.22.0, mỗi thư mục `<runs_dir>/<run_id>/` có thêm `brief.md` (brief nhận vào, kể cả khi đọc từ stdin), `prompt.md` (prompt đầy đủ gửi backend), `meta.json` (`base_commit`, `dirty`, `dirty_files`, `plugin_version`, `backend`, `model`, `label`) và `changes.base.patch` khi repo nguồn có thay đổi chưa commit; `events.jsonl` có thêm `ts` ISO 8601 để tính thời gian từng lệnh. Lượt cũ thiếu meta hoặc `ts` vẫn đếm được dòng; cột thời gian lệnh test để `-`, `plugin_version` là `unknown`.

`hand-ext measure --runs <dir> [--runs <dir>...] [--backend dsh] [--since YYYY-MM-DD]` đọc các thư mục lượt (nhận cả `runs_dir` lẫn một thư mục lượt), đếm dòng thêm test/code/docs từ `changes.patch`: Test nếu nằm trong `tests/`, `test/`, `__tests__/`, `spec/` hoặc tên dạng `test_*`, `*_test.*`, `*.spec.*`, `*.test.*`, `*.bats`; Docs nếu là `.md`, `.rst`, `.txt` hoặc nằm trong `docs/`; còn lại là Code (ưu tiên Test trước Docs). Lệnh test nhận `pytest`, `unittest`, `bats`, `npm test`, `npx vitest`, `go test`, `cargo test`; thời gian một lệnh là `ts` của `tool_result` trừ `ts` của `tool_call` cùng id. Kết quả in bảng theo lượt (tên, version, backend, dòng test/code/docs, % test/(test+code), số lệnh test, tổng giây lệnh test, giây lượt) rồi gộp theo `plugin_version` (tổng dòng, % test, trung bình/trung vị dòng test). `--backend` lọc theo `meta.json`, thiếu meta thì suy ra từ hậu tố tên lượt; `--since` lọc theo ngày bắt đầu của lượt.

## 6. Theo dõi phiên và hand: `hh-ps`

`hh-ps [--since 6h] [--all] [--once] [--json] [--watch N] [--count K] [--cwd D] [--main-session UUID]` dựng cây chỉ đọc: phiên chính → subagent, lượt hand và phiên phụ (mọi provider/backend). `--once` chạy một lần, cũng là mặc định; `--watch N` làm mới mỗi N giây (tối thiểu 2), `--count K` giới hạn số lần vẽ. `--main-session` nhận UUID, ghi đè `CLAUDE_CODE_SESSION_ID`; `--all` lấy mọi project.

Mặc định hiện đủ việc đang chạy và vừa xong theo `--since` (m/h/d), không gấp còn 3 việc, không ẩn cây đã kết thúc. `--full` và `--ended` giữ để tương thích. Phiên phụ có `parent_session` khớp phiên đang hiện được lồng dưới cha; state của repo khác cũng được nạp khi dựng cây. `hh-ps` text và JSON vẫn giữ lượt hand ngoài không rõ cha (`orphan_runs`); cả hai giao diện cây (`hh-tree-pane` và `paseo-hh-tree`) không hiện nhóm orphan hand-ext.

Mỗi dòng session/subagent/hand/side provider có model, effort, `USD~`, hạn mức tài khoản 5h/tuần, giờ kết thúc hoặc `đang chạy`, và elapsed. Elapsed của việc đang chạy tăng theo thời gian; việc đã xong dùng mốc ended để cố định duration. Không hiện giờ bắt đầu trong text, panel hay statusline; metadata/JSON giữ started để tính duration. Giờ kết thúc dùng giờ máy; dữ liệu legacy không biết model/effort/thời gian/quota/giá hiện `?`, không dựng giá trị thay thế. Token vẫn có trong JSON, không cần hiện trong panel. Riêng panel Paseo dùng hiển thị gọn và giới hạn ở [mục 8](#8-xem-cây-trên-paseo).

### Giá và hạn mức

Nguồn giá duy nhất là [`plugins/hybrid-hands/config/model-prices.json`](plugins/hybrid-hands/config/model-prices.json), có thể thay bằng `HYBRID_HANDS_PRICING_FILE`. Schema: `{version:1, verified_at:"2026-11-07", models:{<model-id>:{input,cached,output,cache_write_5m?,cache_write_1h?,source,price_date}}}`; đơn vị USD/MTok. Mỗi entry giữ URL nguồn và ngày giá. Model chưa biết không fallback sang model khác hay họ Opus/Sonnet/Haiku; file override thiếu/hỏng không dùng một bảng giá dự phòng.

Mọi `USD~` là ước tính offline từ token trên gói subscription, không phải hoá đơn. Claude tính cache đọc/ghi theo đúng giá cấu hình, tách cache ghi 5m/1h, không giả định cache đọc bằng một tỉ lệ input cố định. Nguồn công khai được xác minh ngày 2026-11-07; URL nguồn và giá chỉ lưu trong file canonical ở trên. Giá DeepSeek V4.1 Flash peak dùng như ước tính bảo thủ. Không duy trì bảng giá thứ hai trong cấu hình backend hay code.

Phần trăm **tài khoản** 5h/tuần lấy từ cache/sample sẵn có của đúng gói Claude/GPT/Go; thiếu nguồn hiện `?`. Không suy token hoặc USD thành quota GPT. Phần **riêng hand tuần** chỉ thêm khi có nguồn tính được và có nhãn riêng, không trộn với phần trăm tài khoản. Cache/sample hết kỳ reset không được trình bày như số hiện tại. Khối hạn mức giữ nguồn và giờ reset khi có; số ước tính được đánh dấu `~`.

Sổ usage của statusline dùng version 4 và fingerprint để nhận biết dữ liệu cần tính lại. USD~ Claude vẫn là ước tính offline, không phải chi phí chính xác hay hoá đơn.

### Hiệu chỉnh Claude ngoài — 0.32.0

Nguồn hiệu chỉnh là tài khoản Claude ngoài ở `~/.claude-hand`. Runtime ưu tiên live `rate_limit_event`/cache trực tiếp còn mới và đúng reset của Claude hand; dự phòng usage report Paseo bằng cách đối chiếu email từ metadata auth Claude chính thức trong nội bộ, kể cả khi Paseo đăng nhập bằng Pi. Chỉ lưu định danh tài khoản đã hash, không lưu email thô hay credential. Nguồn trực tiếp không cần đổi settings. Mẫu được lấy khoảng mỗi 120 giây; cache Paseo tối đa 5 phút. Không lấy quota của tài khoản khác làm mẫu hiệu chỉnh.

USD~ chỉ cộng token từ transcript Claude hand: input, output, cache đọc, cache ghi 5m và 1h, theo [giá canonical](plugins/hybrid-hands/config/model-prices.json). Rate USD~/1% tuần = chênh lệch USD quan sát ÷ chênh lệch quota tuần, cần hai quan sát hợp lệ cùng tài khoản và reset còn hiện tại. Nguồn quota số nguyên cần delta ít nhất 2 điểm phần trăm để giảm sai số làm tròn; nguồn có phần lẻ thực dùng được delta dương nhỏ hơn. Rate chung giữ unknown đến khi đủ ngưỡng và cache chỉ sẵn sàng sau hai quan sát đó; không dựng baseline lịch sử. Mẫu stale/thiếu, model không có giá hoặc không có delta hợp lệ đều hiện `?`.

Panel/sidebar thêm khối Claude ngoài gồm quota 5h/tuần, USD~/1% và các nhóm token tổng hợp từ transcript nguồn. USD~ từng lượt ngoài vẫn unknown nếu registry cũ thiếu tách cache hoặc tương quan session. Theo lựa chọn người dùng, rate được dùng chung để ước tính phần Claude riêng giữa các tài khoản, chỉ thay ước tính hiện có khi rate mới sẵn sàng; đây là ước tính subscription, không phải hoá đơn hay đồng hồ sử dụng chính xác riêng từng tài khoản. Giữ độ chính xác gốc khi tính, chỉ định dạng % một chữ số lẻ: API trả số nguyên hiển thị `x.0%` không có nghĩa đo chính xác tới 0,1%. Statusline đọc cùng cache, ưu tiên rate pin và giữ fallback cũ nếu chưa có rate hiệu chỉnh hợp lệ; không gọi mạng để lấy calibration khi vẽ.

### Nguồn usage 0.30.0

GPT machine `USD~` cộng các token delta có timestamp quan sát được trong cửa sổ reset quota tuần hiện tại từ hai đường dẫn cố định `~/.codex-hand/sessions` và `~/.codex-hand/archived_sessions`, khử trùng thread/event, không cộng trùng ledger. Thread chỉ có metadata, chưa có token event không làm tổng observed thành unknown. Không có token event trong cửa sổ thì hiện `?`; token event thiếu baseline/timestamp/model-price hợp lệ, file không đọc được hoặc thiếu cửa sổ hiện tại cũng giữ `?`. Model lạ không fallback; giá duy nhất từ file canonical. Tổng chỉ phản ánh token events cục bộ đo được, không bảo đảm đủ mọi hoạt động tài khoản; đây là ước tính offline subscription, không phải hoá đơn. Riêng gắn native child vào cây vẫn chỉ đọc `sessions`.

GPT phần riêng của session pinned rollout/native child dùng `rate_limits` weekly `used_percent` cuối trừ đầu: cần ít nhất hai sample có timestamp hợp lệ, không giảm, cùng reset và reset đó còn hiện tại. Thiếu điều kiện hoặc qua reset thì `?`. Bổ sung cuối `Usage` với default `week_pct_source: str = ""`; khi đo được, source là `codex_rate_limits_delta`, `week_pct_estimated` là false và nhãn `GPT riêng (đo) N% tuần`. Đây là biến động quota tài khoản trong khoảng phiên, có thể gồm phiên chạy đồng thời, không phải phần sử dụng quy riêng độc quyền cho phiên. Không suy quota từ token/USD.

GPT account có duration tường minh phân loại 5h bằng `window_minutes=300`; sample primary tuần (`10080`) không được đổi nhãn thành 5h. Source account rollout legacy thiếu duration giữ tương thích primary=5h/secondary=tuần theo contract cũ. Riêng phép đo GPT phần riêng mới bắt buộc duration tuần tường minh `window_minutes=10080`. Claude 5h dùng cache/live sẵn có, kiểm freshness và reset hiện tại, chấp nhận reset numeric hoặc ISO; thiếu/hết hạn hiện `?`. Statusline dùng chung helper nguồn usage; phiên bản statusline được quản lý riêng. Giữ contract colors/layout/counts/pool và unknown legacy hiện có.

### Kho chỉ mục hh-store — 0.41.0

`hh-ps` ghi một chỉ mục SQLite (WAL, quyền 0600) tại `~/.hybrid-hands/state/hh-store.sqlite3` (theo `HYBRID_HANDS_STATE_DIR`). Mỗi lần chạy chỉ đọc phần mới thêm của rollout Codex và transcript Claude. File không đổi stat thì không đọc lại, và tổng GPT tuần được cache theo thread. File nguồn vẫn là nguồn sự thật: xoá kho thì lần sau tự dựng lại, kết quả giữ nguyên. Kho lỗi, khoá bận hoặc `HYBRID_HANDS_STORE=off` thì quay về đường đọc file cũ. Đo thật `hh-ps --since 3h --json --ended --full`: ~9 s → ~0,7 s (p50, n=5), output giống hệt khi tắt kho.

### Làm mới trực tiếp hh-store — 0.42.0

Daemon `hh-indexer` giữ kho luôn mới giữa các lần chạy hh-ps. Nó theo dõi file nguồn bằng kqueue, ingest sau 300 ms debounce và chỉ tăng `revision` khi có thay đổi thật. Hook Claude và hh-ps chạy từ terminal tự khởi nó; nó tự thoát sau 10 phút không có reader. Pane `hh-tree-pane` và Paseo `paseo-hh-tree` theo dõi `revision` và chỉ chạy hh-ps khi số đổi; chu kỳ cũ giữ làm lưới an toàn. Pane cần phiên Claude mới để nạp `watchPaths`. Tắt bằng `HYBRID_HANDS_INDEXER=off`.

Đo thật (10/11/2026): dữ liệu đổi → revision đổi p50 0,39 s, max 2,33 s (n=9). CPU nền indexer 0,37–0,50%. Hook trả về ~7 ms. Xem trạng thái bằng `hh-store status`.

### Dữ liệu và contract

`hh-ps` đọc metadata phiên, usage transcript và registry trên máy; không in nội dung hội thoại/prompt hay credential, không gọi mạng để tính USD. Snapshot JSON giữ `sessions[]` (có `subagents[]`, `hand_runs[]`), `orphan_runs[]`, `limits[]`, `totals`, `generated_at`, `since_seconds`, thông tin lọc project và phiên chính. `usage` giữ token/USD, phần tuần riêng và `account_plan`, `account_5h_pct`, `account_week_pct`; trường thiếu dùng null hoặc chuỗi rỗng theo model dữ liệu.

Từ 0.29.0, native Codex child được đọc từ metadata rollout cục bộ trong đường dẫn cố định `~/.codex-hand/sessions` (không dùng override `CODEX_HOME`, giữ cô lập tài khoản), không gọi daemon RPC/API. `session_meta.parent_thread_id` hoặc `session_meta.source.subagent.thread_spawn.parent_thread_id` xác định thread cha; `session_meta.id` của pinned Sol rollout đối chiếu thread đó về sid canonical. Child nằm trong `sessions[].subagents[]` với `agent_type=native-codex`, `provider=codex`, status, parent canonical, `ended_at` và `exit_code` nullable; dataclass giữ `finished_at` optional. JSON của hand cũng giữ `exit_code` nullable. Các field mới được thêm cuối dataclass với default để giữ tương thích. Không suy completed từ mtime hay im lặng.

Token chỉ lấy từ nguồn native, USD~ dùng giá canonical; thiếu token hoặc giá hiện `?`, không suy quota. Native không có run/meta/report/token ledger hand-ext. Nguồn đọc không lấy nội dung chat, prompt hay credential.

`CODEX_THREAD_ID`/`PASEO_AGENT_ID` được đối chiếu thành sid canonical để gắn hand vào đúng cha. `HYBRID_HANDS_HAND_SCOPE` chỉ giới hạn số hand đồng thời, không phải ID cha. Cây bao gồm phiên Sol Codex/Claude/dsh và mọi loại agent/backend. Metadata mới lưu parent canonical, `started`, `ended`, `status`, `exit_code`, `tokens`, `effort`, `duration` cùng backend/model. Legacy thiếu dữ liệu giữ unknown. Contract dataclass và bước enrichment được ghi tại [AGENTS.md](../AGENTS.md); `tree.py` tạo Snapshot rồi gọi `enrich_snapshot(snapshot, cfg, now)` trước khi return.

## 7. Chuyển phiên giữa terminal và Paseo: `cc-switch`

`cc-switch paseo` tra `paseo.claude_providers` theo account phiên hiện tại khi `paseo import`; mặc định `{"v1":"claude"}`. Thiếu ánh xạ thì dừng trước khi đóng TUI. Muốn chuyển phiên v2, người dùng tự khai báo provider Claude v2 trong `~/.paseo/config.json` với env `CLAUDE_CONFIG_DIR=~/.claude-hand`, rồi đặt `paseo.claude_providers.v2` bằng tên provider đó trong global hoặc repo. Ánh xạ không tự tạo provider Paseo.


`cc-switch term [--agent ID|--session SID] [--dry-run] [-- <đối số thêm cho claude>]` lấy agent Paseo provider `claude` của project hiện tại (hoặc chọn theo id/tiền tố/session), chờ `paseo wait` nếu agent đang chạy, từ chối nếu đã có TUI `claude` sống cùng session, rồi `chdir` vào cwd agent và `exec claude --resume <sid> [--model <model>]`. Sau đó đừng gửi tin cho agent từ Paseo cho tới khi chuyển lại.

`cc-switch paseo [--session SID] [--dry-run]` lấy transcript sửa gần nhất có dòng `user` trong project (hoặc session chỉ định), từ chối nếu TUI còn sống (phải `/exit` trước), rồi `paseo agent reload <id>` nếu đã có agent, không thì `paseo import <sid> --provider claude --cwd <cwd> --json`. Xong thì mở Paseo trên điện thoại để tiếp tục. `cc-switch term` ghi sổ bàn giao ở `~/.hybrid-hands/cc-switch/handoff.json` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`); `cc-switch paseo` không có `--session` dùng phiên trong sổ nếu transcript còn và xoá mục sau khi nạp lại/import thành công. `cc-switch status [--all]` in bảng id/title/status Paseo/session/TUI và nơi đang giữ (`terminal`, `paseo`, `không`).

**Chuyển chính phiên TUI đang mở:** `cc-switch paseo --self [--idle-sec 20] [--exit-timeout 30] [--dry-run]` dùng ngay bên trong phiên Claude Code TUI, không cần `/exit` bằng tay. Lệnh lấy session từ `CLAUDE_CODE_SESSION_ID`, tìm pid TUI đang mở qua sổ `~/.claude/sessions/<pid>.json` (nhiều pid thì chọn pid là tổ tiên của tiến trình gọi bằng `ps -o ppid=`), rồi tách một tiến trình nền độc lập; log ở `~/.hybrid-hands/cc-switch/self-<sid8>.log` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`). Tiến trình nền chờ transcript đứng yên `--idle-sec` giây (tối đa 30 phút), kiểm lại pid vẫn là TUI của session, gửi SIGTERM và chờ TUI thoát tối đa `--exit-timeout` giây (không SIGKILL), rồi chạy đúng luồng `cc-switch paseo --session <sid>`. Lệnh cha trả về ngay và in pid TUI, thời gian chờ, đường log cùng cách quay lại (`cc-switch term`); đừng gõ hay nhấn Enter cho tới khi TUI tự đóng. `--dry-run` chỉ in kế hoạch, không tách tiến trình; `--self` không đi cùng `--session` (sai cách dùng, thoát 2).

**Chuyển chính phiên Paseo về terminal:** `cc-switch term --self [--idle-sec 20] [--app Terminal|iTerm] [--dry-run]` dùng bên trong phiên Claude Code do Paseo giữ (agent Paseo provider `claude`). Lệnh lấy session từ `CLAUDE_CODE_SESSION_ID`, từ chối nếu phiên đã mở trong terminal, tìm agent Paseo theo session (không có thì báo "phiên không do Paseo giữ" và gợi ý `cc-switch term --session`), và chỉ chạy trên macOS. `--dry-run` in kế hoạch gồm session/agent rút gọn, cwd, app, lệnh sẽ chạy trong cửa sổ và đường log. Không dry-run: lệnh tách một tiến trình nền rồi in hướng dẫn đừng gửi tin cho agent từ Paseo cho tới khi chạy `/to-paseo` hoặc `cc-switch paseo`; cửa sổ sẽ mở sau khi lượt hiện tại xong. Tiến trình nền chờ transcript đứng yên `--idle-sec` giây (tối đa 30 phút), kiểm lại không còn TUI sống cho session, rồi ghi `cd <cwd> && exec <bin/cc-switch> term --session <sid>` vào `~/.hybrid-hands/cc-switch/term-<sid8>.command` (quyền 700) và chạy `open -a Terminal` (hoặc `iTerm`) với file đó — đúng luồng `cc-switch term` hiện có: ghi sổ bàn giao và `exec claude --resume`. Log ở `~/.hybrid-hands/cc-switch/self-<sid8>.log` (đổi gốc bằng `HYBRID_HANDS_STATE_DIR`). Cách mở bằng `open` không cần quyền Automation của macOS. `--self` không đi cùng `--agent`/`--session` và không nhận đối số sau `--` (sai cách dùng, thoát 2).

**Slash command `/to-paseo` và `/to-term`:** plugin có hai lệnh trong `commands/`; mỗi lệnh chỉ chạy đúng một lệnh `cc-switch paseo --self` hoặc `cc-switch term --self` bằng tool Bash làm hành động cuối, rồi trả lời một câu ngắn. Nếu `cc-switch` không có trong `PATH`, dùng đường dẫn tuyệt đối mà hook SessionStart in ra. Chưa kiểm hai slash command chạy được bên trong agent Paseo (cần máy có Terminal.app).

**Vì sao phải reload:** tiến trình `claude` do Paseo giữ hội thoại trong bộ nhớ. Lượt làm ở terminal ghi tiếp vào cùng transcript; nếu Paseo trả lời mà không reload, nó dựa vào lịch sử cũ và ghi một nhánh rẽ. Lần `--resume` sau đi theo lá mới nhất nên lượt terminal bị mất khỏi ngữ cảnh. `paseo agent reload` khởi lại tiến trình lười, resume từ transcript nên thấy đủ lượt terminal. `cc-switch` chỉ đọc các trường agent đã khai báo và không đọc `.key`; việc ghi trạng thái là do `paseo`.

Mã thoát: 2 sai cách dùng (kể cả `--self` đi cùng `--agent`/`--session` hoặc có đối số sau `--`) và `term --self` trên hệ điều hành không phải macOS, 3 không tìm thấy agent/transcript hoặc pid TUI (kể cả session không do Paseo giữ), 4 TUI còn sống, không xác định được pid, hoặc không mở được cửa sổ terminal (`open` lỗi), 5 lệnh `paseo` lỗi.

## 8. Xem cây trên Paseo

Plugin `hh-tree` trong [`paseo-hh-tree/`](paseo-hh-tree/OVERVIEW.md) hiện panel cạnh agent và sidebar Paseo (desktop/điện thoại), làm mới mỗi 5 giây. Panel agent/sidebar Paseo: running/busy dùng theme accent nếu accent là xanh dương, nếu không dùng màu xanh dương dự phòng bảo đảm tương phản ở giao diện sáng/tối; done dùng statusSuccess (xanh lá); failed/exit khác 0/timeout/killed dùng statusDanger (đỏ); idle/silent dùng statusWarning (vàng); lost/unknown dùng foregroundMuted (xám). Số đếm ✓ xanh lá, ✗ đỏ. Dòng đã kết thúc hiện giờ local HH:MM, thêm dd/mm nếu khác ngày; running không hiện giờ kết thúc. Không hiện giờ bắt đầu. Mỗi dòng hiện USD~ riêng, provider Claude/GPT và usage.week_pct riêng trong tuần; thiếu hiện ?. Không thay phần riêng bằng phần trăm tài khoản hoặc suy quota GPT.

Khối riêng ở đầu panel/sidebar hiện tổng USD~ toàn máy trong tuần của Claude/GPT và phần trăm tài khoản 5h/tuần, thay quota ở dòng root. JSON tree.machine_usage:[{plan,window:"tuần",usd,source}] cung cấp tổng toàn máy, không cộng các dòng cây đang hiển thị. Claude dùng phép tổng hợp tuần cục bộ hiện có. GPT đọc rollout trong đường dẫn cố định ~/.codex-hand/sessions và ~/.codex-hand/archived_sessions, khử trùng theo thread, chỉ cộng token delta được chứa trong cửa sổ tuần hiện tại; thiếu cửa sổ/giá/nguồn giữ unknown. Không cộng trùng ledger và rollout. Riêng gắn native child vào cây vẫn chỉ đọc sessions.

Panel/Cây phiên chỉ hiện cây có phiên chính đang chạy theo live/status; phiên chính đã kết thúc hoặc unknown ẩn cả cây, phiên phụ thiếu parent không hiện riêng. Tên ưu tiên description rút gọn (32 ký tự), rồi ai_title và tên/label có nghĩa; thiếu hiện `?`, không dùng ID. Snapshot hiện có description cho subagent; session dùng ai_title/name/title và hand dùng label khi backend chưa cung cấp description. Tổng usage toàn máy vẫn giữ nguyên.

Giữ tối đa 6 phiên phụ, pool chung 4 agent, lựa chọn phiên gần nhất, số đếm phần ẩn và loại nhóm orphan. Addon này chỉ áp dụng panel/sidebar Paseo; hh-tree-pane giữ bố cục, chỉ nhận sửa tương thích native status/exit/unknown ban đầu.

Mỗi cây chính hiện tối đa 6 phiên phụ từ toàn bộ hậu duệ, ưu tiên đang chạy rồi ended/started mới nhất. Phần dư gộp `+N cũ: X✓ Y✗`, thêm `●N`/`?N` khi có running/unknown. Chỉ phiên hoạt động gần nhất trong từng cây (max last_activity/ended/started và mốc agent con, tie giữ thứ tự duyệt cây/agent đầu vào) mở tối đa 4 subagent và hand có cha chung một pool; mọi agent khác gộp `N subagent: X✓ Y✗`, kể cả trong phiên bị ẩn. Nếu phiên gần nhất bị gộp, agent mở của nó có nhãn tên phiên dưới dòng gộp. Không ép phiên is_main là gần nhất. Lỗi có precedence trên trạng thái running cũ; không tính running vào done/error. Native Codex child từ JSON `hh-ps` nằm chung pool và số đếm này. `completed` → ✓; `failed`/`errored`/`cancelled` hoặc `exit_code` khác 0 → ✗ (lỗi ưu tiên), unknown → ?. [`hh-tree-pane`](hh-tree-pane/README.md) và `hh-ps` giữ contract mục 6.

### 8.1 Bật % sống cho phiên Paseo

Wrapper `bin/claude-tee` đứng giữa Paseo và `claude` để dòng tuần Claude lấy **mẫu % sống** thay vì chờ statusline ghi cache: nó chuyển tiếp nguyên luồng stream-json, bắt sự kiện `rate_limit_event`, rồi ghi mẫu mới nhất của `seven_day`/`five_hour` (`utilization`, `resets_at`, `ts`) vào `$CLAUDE_CONFIG_DIR/.hh-claude-rate-limit.json` (mặc định `~/.claude/.hh-claude-rate-limit.json`). File trạng thái chỉ có `version`, `updated_at` và `windows`; **không** lưu nội dung hội thoại, `session_id`, prompt hay token.

Khi mẫu `seven_day` mới hơn mtime `.statusline-cache.json` (hoặc không có cache), `hh-ps`/`hh-tree` dùng thẳng mẫu làm `total_pct` tuần, **không ngoại suy**, và `source` trong `--json` bắt đầu bằng `rate_limit_event` (thêm `+week_split` khi có summary); máy này = `local` của summary + USD phát sinh sau mốc cache ÷ `usd_per_pct`, máy khác = `max(tổng − máy này, 0)`. Mẫu cũ hơn cache thì giữ đường cache/ngoại suy cũ. Wrapper chỉ ghi được khi `claude` chạy với `--output-format stream-json` (Paseo chạy như vậy); phiên TUI ngoài Paseo vẫn dùng cache statusline.

Cấu hình trong `~/.paseo/config.json` — thử provider riêng `claude-tee` trước, chạy một agent thử rồi mới ghi đè provider `claude`:

```json
{
  "agents": {
    "providers": {
      "claude-tee": {
        "extends": "claude",
        "command": ["<đường dẫn tuyệt đối tới plugin>/bin/claude-tee"]
      }
    }
  }
}
```

Sau khi sửa: `paseo reload`, rồi `paseo run --provider claude-tee ...` để kiểm. Muốn mọi agent `claude` đi qua wrapper thì đổi khối trên thành `"claude": {"command": ["<đường dẫn tuyệt đối tới plugin>/bin/claude-tee"]}` (bỏ `extends`) và `paseo reload`. Nếu `claude` trên `PATH` trỏ nhầm vào wrapper, đặt `env.HH_CLAUDE_REAL` của provider thành đường dẫn `claude` thật. Cách gỡ: bỏ provider `claude-tee`/khôi phục `command` cũ của `claude`, `paseo reload`; có thể xoá `.hh-claude-rate-limit.json`, `hh-ps` tự quay lại đọc cache statusline.

## 9. Cập nhật

Tăng `version` trong `plugins/hybrid-hands/.claude-plugin/plugin.json`, chạy `claude plugin validate`, rồi `claude plugin marketplace update hybrid-hands-local` và `claude plugin update hybrid-hands@hybrid-hands-local`.
