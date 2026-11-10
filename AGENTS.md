# Hướng dẫn sống cho repo claude-plugins

## Phạm vi và vai trò

**Phiên chính:** mặc định Opus 5.5 high v1; có thể mở Opus high v2/v… bằng `side-session start --main --provider claude --account v2` hoặc Sol high qua `side-session start --main`. Sol chính kiêm vai Opus + lead tech, L2/L3 người dùng duyệt. Phiên phụ mặc định Sol high, chọn Claude bằng `--provider claude --account v1|v2|v…`. Đổi model/account mở phiên mới từ bàn giao, không `/model` giữa phiên. Luật delegate và dữ liệu giữ nguyên.

Đọc brief, AGENTS.md/CLAUDE.md ở thư mục áp dụng trước khi sửa. Brief thiếu PHẠM VI GHI hoặc ghi CHỈ ĐỌC thì chỉ đọc; không mở rộng phạm vi. Giữ thay đổi chưa commit của người khác; cùng file/phụ thuộc phải tuần tự. Không nạp luật của `dev-workflow/` cho công việc hybrid-hands không liên quan.

Sol là lead tech/QA: giao code/test/tài liệu L0/L1 qua `hand-ext run --backend auto` theo `ext_hand.order`, review code hand mình giao; chỉ tự làm khi hand-ext lỗi (ghi lý do/mã thoát) hoặc việc cần secret/dữ liệu khách hàng. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do vào bàn giao để Opus quyết; exit 8 chờ slot. Review lỗi thì giao lại cùng backend đúng một lần; lần thứ hai vẫn hỏng chuyển backend kế tiếp trong order. Opus review spec/plan/giải pháp và đọc bàn giao. Hand nhận brief trực tiếp là executor, không phải Sol: làm trực tiếp phần được giao, không gọi hand-ext, không mở side-session, không recursion hay giao tiếp phiên khác. Chỉ Sol có quyền chia hand theo brief/policy; hand không tự review việc hand khác.

Ngoại lệ A mở rộng — chọn hand theo tài khoản:

Phiên chính mặc định Opus 5.5 high v1; có thể mở Opus high v2/v… hoặc Sol 6.1 high. Phiên phụ mặc định Sol 6.1 high, có thể là Opus 5.5 high đúng tài khoản v1/v2/v… . Đổi model/account: mở phiên mới từ bàn giao, không dùng `/model` giữa phiên.

Mặc định `ext_hand.order`: dsh (`deepseek-v4.1-flash`, effort `off`, thinking disabled) → codex (`gpt-6.1-sol`, low) → claude-v1 (Opus 5.5 low) → claude-v2 (Opus 5.5 low). `claude_accounts` lấy từ mặc định plugin → global `~/.hybrid-hands/config.json` → repo; v1=`~/.claude`, v2=`~/.claude-hand`, thêm v… bằng cấu hình. `claude-main` và `claude` chỉ là alias tương thích lần lượt của `claude-v1` và `claude-v2`.

Luôn chạy `hand-ext pick --json` trước để biết backend/model/effort/account, `native`/`native_reason` và lý do bỏ qua, kể cả trước native v1 để giữ chặn ≥5%/ngày (thiếu nguồn cũng chặn). Cùng account và tools chọn đúng model/effort mới native; khác account hoặc thiếu capability dùng `hand-ext run --backend auto`. Không tự áp native cho account khác.

| Phiên phụ | dsh | codex low | claude-v1 low | claude-v2 low | UI v1 low |
|---|---|---|---|---|---|
| Sol | hand-ext | native Codex | hand-ext | hand-ext | hand-ext claude-v1 |
| Opus v1 | hand-ext | hand-ext | Agent hybrid-hands:hand | hand-ext | Native khi preflight v1 đủ; thiếu thì hand-ext claude-v1 |
| Opus v2 | hand-ext | hand-ext | hand-ext | Agent hybrid-hands:hand | hand-ext claude-v1 |

Sáng tạo UI mặc định claude-v1 low. Native v1 chỉ khi `hand-ext pick --json` thực trả `claude-v1`, model `claude-opus-5-5`, effort `low`, đúng account và đủ capability. Pick trả dsh/codex chưa chứng minh guard v1 đã qua: dùng `hand-ext run --backend claude-v1` để wrapper enforce guard, không sửa config/order hoặc suy guard pass. Guard chặn thì không spawn native v1; ghi yêu cầu để Opus quyết. Công việc theo order tiếp tục backend pick chọn.
Native Codex dùng `fork_turns=none`, brief tự chứa, luật dữ liệu nguyên văn; executor làm trực tiếp, không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác. Tổng native + hand-ext ≤ `ext_hand.max_parallel` (1..4); cùng file/phụ thuộc tuần tự. Unknown sau spawn phải reconcile/wait, không tạo duplicate writer. Plugin parallel-subagents cũ luôn tắt ở mọi repo; mode `parallel_subagents.enabled` của hybrid-hands chỉ thay đổi qua `hand-ext parallel-subagents on|off` sau khi người dùng chốt cho repo đó, brain/hand không tự bật; không đổi slots/config. Completed giữ tab/history, không archive parent. Native không tạo run/meta/report/token ledger hand-ext; usage qua runtime/Paseo, thiếu token/USD~/quota ghi `?`, không suy quota.

Review thấy lỗi: giao lại cùng backend đúng một lần; lần thứ hai vẫn hỏng chuyển backend kế tiếp theo order dsh → codex → claude-v1 → claude-v2. Exit 7 khi mọi backend trong order không dùng được: chạy `hand-ext doctor`, ghi lý do vào bàn giao để Opus quyết; không tự đổi effort. Exit 8: đợi slot, không đổi backend/tự làm.


Xong một tính năng (test hẹp xanh, đã review) thì Opus/Sol điều phối commit, push nhánh rồi merge ngay vào `main` và push `main` (người dùng chốt 08/11/2026); hand executor không commit/merge. Ngoài trường hợp đó không commit/push mặc định; không chạy lệnh phá hoại. Riêng công việc usage panel: không sửa `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings. Plugin parallel-subagents cũ luôn tắt, mode `parallel_subagents.enabled` chỉ thay đổi qua `hand-ext parallel-subagents on|off` sau khi người dùng chốt cho repo đó, brain/hand không tự bật. Không xoá/di chuyển/dọn `output/llm/`. Shell dùng cwd/workdir hoặc đường dẫn tuyệt đối, không `cd <dir> && ...`. Không vòng chờ vô hạn; kết thúc tiến trình nền mình tạo trước báo cáo. Không tải/mua/gọi API trả phí hay tạo/dùng API key nếu brief không giao rõ và có trần chi phí.

Sau mỗi lần sửa plugin, Opus/Sol phải validate, chạy test hẹp phù hợp và hoàn tất review, tăng version thích hợp cùng changelog, rồi cập nhật cài đặt plugin vừa sửa cho repo hiện tại và mọi repo khác đang dùng plugin đó qua công cụ chính thức. Không tự bật plugin ở repo chưa dùng; không sửa thủ công credential/settings hay sổ cài đặt. Kiểm chứng version và đường dẫn plugin được nạp thực tế ở các repo đã cập nhật; nếu phiên đang mở không hot load được thì báo rõ cần reload. Giữ nguyên luật commit/push/merge ở trên; hand executor chỉ làm phần được giao, không tự cập nhật runtime khi brief dành việc đó cho brain.

Cấu hình ưu tiên: mặc định plugin → global `~/.hybrid-hands/config.json` (đổi bằng `HYBRID_HANDS_CONFIG`) → repo → cờ CLI. Dict merge sâu; list/scalar thay nguyên.
`hand-ext config --json` in cấu hình hiệu lực và nguồn từng key; global hỏng báo lỗi kèm đường dẫn.
`hand-ext models` xem/set/unset model ba tầng brain/side/hand theo repo, ghi cùng file với `parallel-subagents`; chỉ set/unset khi người dùng chốt thay đổi cụ thể, mở phiên mới để áp dụng.
`parallel_subagents.enabled=false` mặc định; chỉ bool thật hợp lệ, sai kiểu về false kèm warning. True chỉ hiệu lực từ repo (giữ provenance và fallback worktree); global true bị bỏ qua kèm warning. Trong Claude Code dùng `/hybrid-hands:parallel-subagents on|off`, trong terminal/Codex dùng `hand-ext parallel-subagents on|off`. Dùng `hand-ext parallel-subagents` để xem trạng thái; chỉ dùng `hand-ext parallel-subagents on|off` sau khi người dùng chốt cho repo đó, brain/hand không tự bật; mở phiên mới để hook nạp luật.
`ext_hand.native.{claude,codex}=auto|off`; `pick --json` trả `native`/`native_reason`, caller vẫn kiểm capability. Claude chính/phụ mặc định transport Paseo; có thể chọn `screen` qua cấu hình.

## Luật dữ liệu chung (chép nguyên văn vào brief hand ngoài)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

Sol có quyền dữ liệu như Opus; luật không giao secret/dữ liệu khách hàng áp dụng cho hand ngoài. Việc đó dùng hand Claude. Sol được dùng công cụ plugin để chỉ đọc metadata/usage tổng hợp phục vụ kiểm chứng thực tế. Quy tắc chỉ dùng code/fixtures giả và không đọc transcript/log thật áp dụng cho hand ngoài, không cấm runtime đọc token usage. Công cụ runtime được đọc auth nội bộ theo luật trên không có nghĩa hand được mở auth file; cấm hiện giá trị `.env`, token, credential vẫn áp dụng mọi tầng.

## Layout và nguồn chuẩn

- `hybrid-hands/README.md`: sử dụng plugin và contract usage panel; `plugins/hybrid-hands/CHANGELOG.md` giữ lịch sử release.
- `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json`: phiên bản plugin.
- `hybrid-hands/plugins/hybrid-hands/bin/`: CLI hand-ext, side-session, hh-ps, cc-switch; `lib/hand_ext/`, `lib/side_session/`, `lib/hh_ps/`, `lib/cc_switch/`: implementation tương ứng.
- `hybrid-hands/plugins/hybrid-hands/skills/`: ext-hand, paseo, side-session; `agents/`, `templates/`, `scripts/`, `hooks/`: policy và launcher.
- `hybrid-hands/hh-tree-pane/`: cây cạnh terminal; `hybrid-hands/paseo-hh-tree/`: panel agent và sidebar Paseo; `hybrid-hands/tests/`: test Python/fixtures giả.
- `statusline/`: plugin riêng, chỉ sửa khi brief giao rõ; dùng cùng nguyên tắc UI bỏ giờ bắt đầu.

Nguồn giá DUY NHẤT: `hybrid-hands/plugins/hybrid-hands/config/model-prices.json`; env override `HYBRID_HANDS_PRICING_FILE`. Schema `{version:1, verified_at:"2026-11-07", models:{<model-id>:{input,cached,output,cache_write_5m?,cache_write_1h?,source,price_date}}}` (USD/MTok). Mỗi entry giữ date/source; không hardcode bảng thứ hai hay fallback theo model/họ khi model lạ. Cache Claude tính đúng giá cấu hình, tách cache ghi 5m/1h. Nguồn công khai được xác minh ngày 2026-11-07; DeepSeek peak là ước tính bảo thủ. Các URL và giá đầy đủ ở [file canonical](hybrid-hands/plugins/hybrid-hands/config/model-prices.json), không nhân bản giá vào tài liệu hay code.

Mọi USD~ là ước tính offline subscription, không phải hoá đơn. Quota tài khoản 5h/tuần lấy cache/sample sẵn có, thiếu `?`; không suy token/USD thành quota GPT. Phần riêng hand tuần chỉ hiện khi có nguồn và nhãn riêng.

## Contract dữ liệu và hiển thị 0.30.0

Bổ sung cuối dataclass với default để giữ tương thích:

- `Usage.account_plan: str = ""`, `account_5h_pct: Optional[float] = None`, `account_week_pct: Optional[float] = None`.
- `Subagent.started_at: Optional[float] = None`, `model: str = ""`, `effort: str = ""`; native bổ sung `provider: str = ""`, `status: str = ""`, `exit_code: Optional[int] = None`, `finished_at: Optional[float] = None`.
- `HandRun.effort: str = ""`, `exit_code: Optional[int] = None`.
- `Session.model: str = ""`, `effort: str = ""`, `finished_at: Optional[float] = None`; property `ended_at` ưu tiên finished_at.

- `Snapshot.machine_usage: List[dict] = field(default_factory=list)` được bổ sung cuối dataclass.

`lib/hh_ps/tree.py` tạo Snapshot rồi gọi `lib/hh_ps/usage_enrichment.py:enrich_snapshot(snapshot, cfg, now) -> None` trước return. API pricing hiện có giữ tương thích; cập nhật implementation giá ở nguồn canonical, không sinh bảng mặc định khác.

`CODEX_THREAD_ID`/`PASEO_AGENT_ID` được đối chiếu thành sid canonical để gắn cha; `HYBRID_HANDS_HAND_SCOPE` chỉ giới hạn số hand đồng thời, không phải ID cha. Cây bao gồm Sol Codex/Claude/dsh và mọi loại agent/backend. Metadata mới ghi parent canonical, started, ended, status, exit_code, tokens, effort, duration cùng model/backend. Legacy unknown giữ `?` ở UI, null/chuỗi rỗng theo JSON/dataclass; không bịa mốc hay quota.

Native Codex lấy metadata rollout cục bộ trong đường dẫn cố định `~/.codex-hand/sessions` (không dùng override `CODEX_HOME`, giữ cô lập tài khoản), không gọi daemon RPC/API. Gắn cha bằng `session_meta.parent_thread_id` hoặc `session_meta.source.subagent.thread_spawn.parent_thread_id`; đối chiếu `session_meta.id` của pinned Sol rollout để đưa thread cha về sid canonical. Native nằm trong `Session.subagents`, `agent_type=native-codex`, `provider=codex`; JSON xuất status/provider/parent canonical và exit_code nullable cho subagent/hand. Không tạo run/meta/report/token ledger hand-ext. Chỉ lấy token từ nguồn native và tính USD~ theo giá canonical; thiếu token/giá hiện `?`. Không suy completed từ mtime hoặc im lặng. Completed → ✓; failed/errored/cancelled hoặc exit_code khác 0 → ✗ (lỗi ưu tiên); unknown → ?. Native cùng pool tối đa 4 với subagent/hand, cùng số đếm `X✓ Y✗`.

Mỗi dòng session/subagent/hand/side provider mọi backend đủ model, effort, USD~, quota, ended hoặc `đang chạy`, elapsed. Panel agent/sidebar Paseo: running/busy dùng theme accent nếu accent là xanh dương, nếu không dùng màu xanh dương dự phòng bảo đảm tương phản ở giao diện sáng/tối; done dùng statusSuccess (xanh lá); failed/exit khác 0/timeout/killed dùng statusDanger (đỏ); idle/silent dùng statusWarning (vàng); lost/unknown dùng foregroundMuted (xám). Số đếm ✓ xanh lá, ✗ đỏ. Dòng đã kết thúc hiện giờ local HH:MM, thêm dd/mm nếu khác ngày; running không hiện giờ kết thúc. Không hiện giờ bắt đầu. Mỗi dòng hiện USD~ riêng, provider Claude/GPT và usage.week_pct riêng trong tuần; thiếu hiện ?. Không thay phần riêng bằng phần trăm tài khoản hoặc suy quota GPT.

Khối riêng ở đầu panel/sidebar hiện tổng USD~ toàn máy trong tuần của Claude/GPT và phần trăm tài khoản 5h/tuần, thay quota ở dòng root. JSON tree.machine_usage:[{plan,window:"tuần",usd,source}] cung cấp tổng toàn máy, không cộng các dòng cây đang hiển thị. Claude dùng phép tổng hợp tuần cục bộ hiện có. GPT đọc rollout trong đường dẫn cố định ~/.codex-hand/sessions và ~/.codex-hand/archived_sessions, khử trùng theo thread, chỉ cộng token delta được chứa trong cửa sổ tuần hiện tại; thiếu cửa sổ/giá/nguồn giữ unknown. Không cộng trùng ledger và rollout. Riêng gắn native child vào cây vẫn chỉ đọc sessions.

Giữ tối đa 6 phiên phụ, pool chung 4 agent, lựa chọn phiên gần nhất, số đếm phần ẩn và loại nhóm orphan. Addon này chỉ áp dụng panel/sidebar Paseo; hh-tree-pane giữ bố cục, chỉ nhận sửa tương thích native status/exit/unknown ban đầu.

Mỗi cây chính flatten tối đa 6 phiên phụ (running trước, rồi ended/started mới nhất); phần dư gộp số done/error/running/unknown. Chỉ phiên hoạt động gần nhất trong từng cây mở tối đa 4 subagent/hand có cha; các agent khác gộp số, kể cả phiên bị ẩn. Tie giữ thứ tự duyệt cây/agent đầu vào; không ưu tiên is_main. Duration đang chạy tăng theo thời gian, xong cố định theo ended. KHÔNG hiện giờ bắt đầu trong text hh-ps, panel, statusline; meta/JSON vẫn giữ started. `hh-ps --once` chạy một lần; mặc định đủ việc chạy/vừa xong theo since, không fold 3/hide-ended. Cả hai giao diện cây (`hh-tree-pane`, panel agent/sidebar `paseo-hh-tree`) tuyệt đối không hiện nhóm orphan hand-ext; hh-ps text/JSON vẫn giữ orphan.

### Nguồn usage 0.30.0

GPT machine `USD~` cộng các token delta có timestamp quan sát được trong cửa sổ reset quota tuần hiện tại từ hai đường dẫn cố định `~/.codex-hand/sessions` và `~/.codex-hand/archived_sessions`, khử trùng thread/event, không cộng trùng ledger. Thread chỉ có metadata, chưa có token event không làm tổng observed thành unknown. Không có token event trong cửa sổ thì hiện `?`; token event thiếu baseline/timestamp/model-price hợp lệ, file không đọc được hoặc thiếu cửa sổ hiện tại cũng giữ `?`. Model lạ không fallback; giá duy nhất từ file canonical. Tổng chỉ phản ánh token events cục bộ đo được, không bảo đảm đủ mọi hoạt động tài khoản; đây là ước tính offline subscription, không phải hoá đơn. Riêng gắn native child vào cây vẫn chỉ đọc `sessions`.

GPT phần riêng của session pinned rollout/native child dùng `rate_limits` weekly `used_percent` cuối trừ đầu: cần ít nhất hai sample có timestamp hợp lệ, không giảm, cùng reset và reset đó còn hiện tại. Thiếu điều kiện hoặc qua reset thì `?`. Bổ sung cuối `Usage` với default `week_pct_source: str = ""`; khi đo được, source là `codex_rate_limits_delta`, `week_pct_estimated` là false và nhãn `GPT riêng (đo) N% tuần`. Đây là biến động quota tài khoản trong khoảng phiên, có thể gồm phiên chạy đồng thời, không phải phần sử dụng quy riêng độc quyền cho phiên. Không suy quota từ token/USD.

GPT account có duration tường minh phân loại 5h bằng `window_minutes=300`; sample primary tuần (`10080`) không được đổi nhãn thành 5h. Source account rollout legacy thiếu duration giữ tương thích primary=5h/secondary=tuần theo contract cũ. Riêng phép đo GPT phần riêng mới bắt buộc duration tuần tường minh `window_minutes=10080`. Claude 5h dùng cache/live sẵn có, kiểm freshness và reset hiện tại, chấp nhận reset numeric hoặc ISO; thiếu/hết hạn hiện `?`. Statusline dùng chung helper nguồn usage; phiên bản statusline được quản lý riêng. Giữ contract colors/layout/counts/pool và unknown legacy hiện có.

## Contract archive workspace (09/11/2026)

Membership chỉ theo public `agent.workspaceId`, không theo cwd vì nhiều workspace local có thể cùng checkout. Chỉ archive workspace do plugin tạo, kể cả private LOCAL, khi mọi member cùng workspaceId đã archived (known closed child của plugin phải archive trước), không có `main_session`/role `main` hay agent không do plugin tạo. Giữ workspace local shared/main/unknown; không suy ownership từ tên hoặc cwd, không gom theo cwd hay di chuyển/xoá thư mục. Plugin worktree giữ nguyên quy tắc hiện có; archive local không xoá checkout, Paseo chỉ có thể xoá worktree do Paseo sở hữu. Managed settled đủ report/hooks → `awaiting_review`, tự archive exact child và workspace riêng theo quy tắc này; `managed archive` idempotent, `review-approve` vẫn chặn followup tới khi được duyệt. Followup restore workspace rồi reopen cùng child, cùng IDs và epoch mới. Side-session Paseo mọi provider done archive child trước workspace; warning workspace không chặn done, `ls`/`watch` retry có giới hạn. Lỗi visibility giữ lifecycle/data, không tạo writer trùng.

`side-session tidy [--name NAME] [--apply]`: mặc định dry-run, chỉ liệt kê eligible/blocked và exact IDs dự kiến. Ví dụ `side-session tidy --name NAME` để xem, `side-session tidy --name NAME --apply` để áp dụng. `--apply` idempotent, chỉ archive workspace có ownership từ plugin side state, rỗng/đã archive hết member hoặc có known closed plugin child được archive trước; chặn main, agent không do plugin tạo và member active. `--name` giới hạn cleanup; giữ thư mục local và artifacts. `side-session send` giữ restore workspace rồi cùng exact agent trước gửi, history marker và không create; lỗi xác định trước gửi có thể retry, ACK mơ hồ giữ pending chặn gửi trùng. `start --resume` giữ tương thích.

## Kiểm chứng

Chỉ chạy test hẹp phần đang sửa; full suite chỉ khi brief giao, một lần cuối. Tài liệu/manifest: kiểm JSON hợp lệ và link nội bộ, không thêm test cho text tài liệu, không claim cài đặt/test chưa chạy. Giữ mức test tối thiểu theo brief; chỉ hai nhóm cần mức kỹ là tính năng giữ chân/chi tiêu và bảo mật chống tấn công từ ngoài. Báo rõ lệnh/kết quả thật và phần còn chưa kiểm chứng.
