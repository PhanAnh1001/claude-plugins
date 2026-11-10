# Hướng dẫn sống cho repo claude-plugins

## Phạm vi và vai trò

Đọc brief, AGENTS.md/CLAUDE.md ở thư mục áp dụng trước khi sửa. Brief thiếu PHẠM VI GHI hoặc ghi CHỈ ĐỌC thì chỉ đọc; không mở rộng phạm vi. Giữ thay đổi chưa commit của người khác; cùng file/phụ thuộc phải tuần tự. Không nạp luật của `dev-workflow/` cho công việc hybrid-hands không liên quan.

Sol là lead tech/QA: giao code/test/tài liệu L0/L1 qua `hand-ext run --backend auto` theo `ext_hand.order`, review code hand mình giao; chỉ tự làm khi hand-ext lỗi (ghi lý do/mã thoát) hoặc việc cần secret/dữ liệu khách hàng. Exit 7 chạy doctor trước, chỉ chuyển codex medium khi xác nhận dsh hết quota; exit 8 chờ slot. Opus review spec/plan/giải pháp và đọc bàn giao. Hand nhận brief trực tiếp là executor, không phải Sol: làm trực tiếp phần được giao, không gọi hand-ext, không mở side-session, không recursion hay giao tiếp phiên khác. Chỉ Sol có quyền chia hand theo brief/policy; hand không tự review việc hand khác.

Ngoại lệ A (0.27.0) đã được người dùng cho phép: Sol trên Paseo dùng native subagent khi backend thực theo `ext_hand.order` là codex `gpt-6.1-sol` low và tools hỗ trợ model/effort riêng. Dùng `fork_turns=none`, full brief và luật dữ liệu chép nguyên văn; hand executor không recursion/giao tiếp phiên khác. Sol giữ tổng native + hand-ext đang chạy ≤ `ext_hand.max_parallel` (1..4), cùng file/phụ thuộc tuần tự; code/slots hand-ext không đổi. Ngoại lệ không áp cho Opus/Claude/dsh hay executor, không bật parallel-subagents/sửa config. Local Codex CLI 0.166.0 + Paseo CLI 0.15.0 đã được Sol probe: child completed đúng parent, timeline 3 dòng assistant. Native completed giữ tab/history, không archive top-level/parent; báo cáo/usage qua native/Paseo, không có run/meta/report/token ledger hand-ext, thiếu hiện `?`, không bịa quota. Thiếu native/capability trước spawn hoặc repo chọn backend khác thì fallback `hand-ext run --backend auto`; unknown sau spawn không tạo duplicate writer. Hand-ext shell không tự hiện hội thoại trên Paseo. A đạt nên B (agent ngang hàng/archive) chưa triển khai.

Không commit/push mặc định; không chạy lệnh phá hoại. Không sửa `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, credential/settings hay bật parallel-subagents trong công việc usage panel. Không xoá/di chuyển/dọn `output/llm/`. Shell dùng cwd/workdir hoặc đường dẫn tuyệt đối, không `cd <dir> && ...`. Không vòng chờ vô hạn; kết thúc tiến trình nền mình tạo trước báo cáo. Không tải/mua/gọi API trả phí hay tạo/dùng API key nếu brief không giao rõ và có trần chi phí.

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

## Contract dữ liệu và hiển thị 0.26.0

Bổ sung cuối dataclass với default để giữ tương thích:

- `Usage.account_plan: str = ""`, `account_5h_pct: Optional[float] = None`, `account_week_pct: Optional[float] = None`.
- `Subagent.started_at: Optional[float] = None`, `model: str = ""`, `effort: str = ""`.
- `HandRun.effort: str = ""`.
- `Session.model: str = ""`, `effort: str = ""`, `finished_at: Optional[float] = None`; property `ended_at` ưu tiên finished_at.

`lib/hh_ps/tree.py` tạo Snapshot rồi gọi `lib/hh_ps/usage_enrichment.py:enrich_snapshot(snapshot, cfg, now) -> None` trước return. API pricing hiện có giữ tương thích; cập nhật implementation giá ở nguồn canonical, không sinh bảng mặc định khác.

`CODEX_THREAD_ID`/`PASEO_AGENT_ID` được đối chiếu thành sid canonical để gắn cha; `HYBRID_HANDS_HAND_SCOPE` chỉ giới hạn số hand đồng thời, không phải ID cha. Cây bao gồm Sol Codex/Claude/dsh và mọi loại agent/backend. Metadata mới ghi parent canonical, started, ended, status, exit_code, tokens, effort, duration cùng model/backend. Legacy unknown giữ `?` ở UI, null/chuỗi rỗng theo JSON/dataclass; không bịa mốc hay quota.

Mỗi dòng session/subagent/hand/side provider mọi backend đủ model, effort, USD~, quota, ended hoặc `đang chạy`, elapsed. Riêng panel agent/sidebar Paseo dùng icon ●/✓/✗/?, tên ngắn, model·effort, elapsed, USD~; quota tài khoản 5h/tuần mỗi account plan một lần ở root, không hiện chữ trạng thái/mốc ended hay nhãn thừa. Mỗi cây chính flatten tối đa 4 phiên phụ (running trước, rồi ended/started mới nhất); phần dư gộp số done/error/running/unknown. Chỉ phiên hoạt động gần nhất trong từng cây mở tối đa 4 subagent/hand có cha; các agent khác gộp số, kể cả phiên bị ẩn. Tie giữ thứ tự duyệt cây/agent đầu vào; không ưu tiên is_main. Duration đang chạy tăng theo thời gian, xong cố định theo ended. KHÔNG hiện giờ bắt đầu trong text hh-ps, panel, statusline; meta/JSON vẫn giữ started. `hh-ps --once` chạy một lần; mặc định đủ việc chạy/vừa xong theo since, không fold 3/hide-ended. Cả hai giao diện cây (`hh-tree-pane`, panel agent/sidebar `paseo-hh-tree`) tuyệt đối không hiện nhóm orphan hand-ext; hh-ps text/JSON vẫn giữ orphan.

## Kiểm chứng

Chỉ chạy test hẹp phần đang sửa; full suite chỉ khi brief giao, một lần cuối. Tài liệu/manifest: kiểm JSON hợp lệ và link nội bộ, không thêm test cho text tài liệu, không claim cài đặt/test chưa chạy. Giữ mức test tối thiểu theo brief; chỉ hai nhóm cần mức kỹ là tính năng giữ chân/chi tiêu và bảo mật chống tấn công từ ngoài. Báo rõ lệnh/kết quả thật và phần còn chưa kiểm chứng.
