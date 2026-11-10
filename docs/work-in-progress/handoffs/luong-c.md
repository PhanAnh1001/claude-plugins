## Tóm tắt
- Kết quả: xong phạm vi tích hợp A+B, A.1/A.3 phần dsh theo quyết định người dùng, C.1–C.4 và phần release D.2 được giao; Sol đã review.
- Nhánh `side/luong-c`; commit `c1bcb496d39e200612a04904554e470b24814fb5`; đã merge `side/luong-b` (`fc5d786`), nền A `9c041c5`; không merge main/push.
- Loader/account: side-session dùng registry hand_ext duy nhất; defaults + repo, không user config; sửa env OAuth primary Claude.
- dsh: giữ `deepseek-v4.1-flash`, default/fallback effort `off`, template `off: null`; không đổi giá.
- Policy/templates/skills/README/AGENTS: bảng account-aware, leo thang một lần giao lại, exit 7 mới, brief phần tĩnh trước; thêm hai template Claude.
- Version manifest và USER_AGENT thực đọc đều `0.33.0`; CHANGELOG mới; spec/plan copy nguyên vẹn, không tick.
- Full suite đúng MỘT lần: `python3 -m unittest discover -s hybrid-hands/tests -q` → exit 1, 453 tests/60.224s, 2 failure assertion policy cũ; đã sửa assertions và chạy hẹp xanh, không chạy full lại.
- Test hẹp: defaults 2, dsh 41, side-session* 96, policy 3; sau full: isolation 12 và side-session-codex 13 đều OK.
- `claude plugin validate .../plugins/hybrid-hands` → exit 0, Validation passed; advisory directory: thiếu LICENSE/icon.
- Inject output **141 ký tự**, gồm newline; bash -n, JSON, 9 link file nội bộ, render template, git diff --check đều OK.
- Chưa làm: runtime install/reload, đổi config repo, restart Paseo, inference thật/checkpoint 1017, merge/push, tick plan; full suite chưa chạy lại sau sửa hai test theo yêu cầu một lần.
- Hand: 2 native Codex `gpt-6.1-sol` low theo Ngoại lệ A, completed; token/USD~/quota: ? / ? / ?; không có ledger hand-ext.

## Kết quả theo plan

- Tích hợp: merge B không xung đột vào worktree tách từ A; bản release chứa cả lịch sử hai gói. Đã đọc bàn giao `luong-a.md`, `luong-b.md`.
- A.1/A.3 phần dsh: làm theo chốt 09/11 của người dùng, giữ ID Go đang phục vụ, không thêm model/entry giá. Default trong constants và fallback backend đều off, khả năng off được khai báo rõ trong overlay model. USER_AGENT đã có cơ chế đọc manifest động, nên giữ cơ chế này và xác minh kết quả `hybrid-hands-hand-ext/0.33.0`.
- C.1/C.4: đồng bộ tài khoản v1/v2/v…, backend canonical/alias, chọn native theo account và capability, pool chung, unknown không tạo writer trùng, leo thang review lỗi, exit 7/8. AGENTS chỉ sửa các đoạn vai trò, Ngoại lệ A, order/exit 7 được giao.
- C.2: inject chỉ còn pointer và ba luật; SessionStart đối chiếu từng đoạn nguyên văn với AGENTS của cwd từ payload, rồi env/cwd dự phòng. Repo không có nội dung tương ứng giữ policy đầy đủ; chỉ marker/tên repo không đủ để rút. Brief dùng thứ tự LUẬT BẮT BUỘC → KHÔNG ĐƯỢC ĐỤNG → TRẢ VỀ → MỤC TIÊU → NGỮ CẢNH → PHẠM VI GHI → KIỂM CHỨNG.
- C.3: cập nhật assertions trong test_policy_brain_context, giữ ba test methods hiện có. Full suite phát hiện hai test prose contract cũ khác, đã sửa đúng assertions đó, không thêm test method.
- D.2 phần được giao: version/CHANGELOG/validate hoàn tất. Runtime và kiểm đường dẫn/version được nạp thuộc Opus, chưa làm.

## File trong commit release C

Đường dẫn rút gọn bên dưới lấy gốc `hybrid-hands/plugins/hybrid-hands/`, trừ khi ghi rõ:

- `AGENTS.md` gốc repo: vai trò mặc định và policy account/order/exit 7 mới.
- `hybrid-hands/README.md`: usage/config ví dụ, account/native, order và capacity fallback theo code A.
- `hybrid-hands/docs/2026-11-09-luong-mac-dinh-dsh-spec.md`: copy nguyên bản đã giao, không sửa nội dung.
- `hybrid-hands/docs/2026-11-09-luong-mac-dinh-dsh-plan.md`: copy nguyên bản đã giao, Opus tick sau.
- `.claude-plugin/plugin.json`: version 0.33.0 và description order/native mới.
- `CHANGELOG.md`: thêm mục 0.33.0 đầu file.
- `agents/hand.md`: đồng bộ thứ tự khuôn brief.
- `lib/hand_ext/constants.py`: dsh mặc định effort off.
- `lib/hand_ext/backends/dsh.py`: fallback effort off, giữ User-Agent động.
- `lib/side_session/config.py`: gọi loader canonical, bỏ defaults/merge registry trùng.
- `lib/side_session/commands.py`: primary ~/.claude unset CLAUDE_CONFIG_DIR kế thừa; custom/v2 vẫn set đúng thư mục.
- `scripts/inject-policy.sh`: output 141 ký tự.
- `scripts/session-start-policy.sh`: policy mới, dedup có đối chiếu AGENTS thật.
- `skills/ext-hand/SKILL.md`: chọn account/native, lỗi/leo thang, brief/cache/order/capacity mới.
- `skills/side-session/SKILL.md`: cờ account/main, Claude screen và policy mới.
- `skills/paseo/SKILL.md`: policy mới; giữ mục bridge read-only hiện có.
- `templates/dsh-hand.yml`: reasoningEfforts.off null cùng thinkingFormat deepseek sẵn có.
- `templates/ext-hand-preamble.md`: thứ tự brief mới.
- `templates/hand-brief.md`: phần tĩnh lên đầu.
- `templates/main-session-prompt-claude.md`: main Claude theo account, báo trực tiếp, không bắt marker hoàn thành main.
- `templates/main-session-prompt-codex.md`: policy mới cho main Sol.
- `templates/side-session-prompt-claude.md`: lead Claude theo account, handoff + sibling .done, chỉ dùng placeholders loader hỗ trợ.
- `templates/side-session-prompt-codex.md`: policy mới cho Sol, bỏ fallback codex medium.
- `templates/side-session-prompt.md`: Claude v1 theo account và policy mới.
- `hybrid-hands/tests/test_hand_ext_defaults.py`: assert dsh off/model/overlay trong ca có sẵn.
- `hybrid-hands/tests/test_side_session.py`: assert chung registry, override canonical/legacy/v3, OAuth primary/custom trong ca có sẵn.
- `hybrid-hands/tests/test_policy_brain_context.py`: giới hạn 300, markers mới, fallback/dedup đúng nội dung.
- `hybrid-hands/tests/test_hand_ext_isolation.py`: full data rule nằm ở policy đầy đủ; inject giữ pointer.
- `hybrid-hands/tests/test_side_session_codex.py`: assertions exit 7 mới, loại requirement codex medium cũ.

Code B trong merge được giữ; danh sách chi tiết và kiểm chứng baseline ở bàn giao `luong-b.md`. Không đổi `.claude/hybrid-hands.json`, statusline, pricing, credential/settings, runtime hay daemon.

## Kiểm chứng thật

Hand chạy test hẹp (mỗi lệnh exit 0; các lượt correction được review):

- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext_defaults.py' -q` → 2 tests OK.
- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext_dsh.py' -q` → 41 tests OK.
- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session*.py' -q` → 96 tests OK trước lượt full/correction assertions cuối.
- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_policy_brain_context.py' -q` → 3 tests OK, sau correction policy cũng OK.
- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext_isolation.py' -q` → 12 tests OK sau full.
- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_codex.py' -q` → 13 tests OK sau full.

Sol chạy:

- `hybrid-hands/plugins/hybrid-hands/bin/hand-ext pick --json` → exit 0, codex/gpt-6.1-sol/low/gpt, skipped=[] theo config repo hiện hành. Không chạy inference.
- `python3 -m unittest discover -s hybrid-hands/tests -q` → ĐÚNG MỘT lần, exit 1, 453 tests trong 60.224s, hai failure: test_data_rule_is_present_in_policy_surfaces đòi dữ liệu khách hàng/hand Claude trong inject ngắn; test_model_effort_approval_and_sandbox_argv đòi doctor-before/codex medium cũ. Không lỗi implementation nào khác được suite báo. Sau đó chỉ đổi hai test assertions và chạy hai nhóm hẹp kể trên; không claim full suite cuối xanh.
- `claude plugin validate /Users/anhtp/app/claude-plugins-wt/luong-c/hybrid-hands/plugins/hybrid-hands` → exit 0, Validation passed (đã chạy lại sau sửa description manifest). Directory advisory thiếu LICENSE và icon; chưa chạy profile directory, không thêm giấy phép hay icon ngoài task.
- `bash -n hybrid-hands/plugins/hybrid-hands/scripts/session-start-policy.sh hybrid-hands/plugins/hybrid-hands/scripts/inject-policy.sh` → exit 0.
- Offline Python: render build_prompt side/main cho v1/v2/v3 không còn placeholders account/name/handoff/brain/done/hand_ext; output inject 141 ký tự tính cả newline; manifest 0.33.0; USER_AGENT hybrid-hands-hand-ext/0.33.0; thứ tự brief đúng; hai bản docs bằng byte với bản nguồn khi kiểm; 9 Markdown file links nội bộ tồn tại; phạm vi ghi/JSON hợp lệ; không còn luật codex medium trong policy hiện hành.
- `git diff --check`, `git diff --cached --check` → exit 0; working tree sạch sau commit.

## Review và giới hạn cần Opus biết

Sol review diff mọi hand mình giao, yêu cầu sửa: OAuth layout primary Claude, template Claude còn placeholder Codex, khôi phục mục bridge và bullet dùng tool Claude bị thay nhầm, mô tả main Claude screen, capacity fallback theo order và guard native v1. Sau correction đã review lại; mọi native child đã completed, mọi lệnh nền của Sol đã thoát trước bàn giao.

`hand-ext pick` chỉ preflight tới backend đầu tiên dùng được. Pick ra dsh/codex chưa chứng minh guard v1 đã qua; policy chốt native v1 chỉ khi pick thực chọn đúng v1/model/effort. Task sáng tạo v1 chưa có proof guard thì đi wrapper `--backend claude-v1` để enforce guard, không thay order/config để lách kiểm tra.

Side-session giữ budget_check_cmd có sẵn của B; custom max_day_pct trong side-session vẫn quyết định bật guard command, không phải triển khai một phép đo/trần tuỳ chỉnh mới. Không claim đã kiểm các cap tuỳ chỉnh trong phiên runtime; xem giới hạn B trong bàn giao trước.

Nguồn reasoning đã kiểm trực tiếp ngày 09/11/2026: [DeepSeek Harness providers.md, Reasoning effort](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/guide/providers.md#reasoning-effort): off null cùng thinkingFormat deepseek dùng thinking disabled. Không gọi inference/API, chưa chứng minh checkpoint 1017 hoặc payload thực trên Go bằng một task thật.

Config repo vẫn order [codex] theo yêu cầu không sửa; defaults dsh mới chỉ có hiệu lực tại repo này khi Opus thực hiện D.3. Chưa install/update runtime ở repo nào, chưa kiểm version/path plugin thực được nạp, chưa restart Paseo. Bản spec/plan được copy nguyên văn, kể cả các mục A.1/A.3/C/D chưa tick và thông tin chờ quyết trước đó; quyết định mới trong brief và bàn giao này là căn cứ, Opus cập nhật plan nguồn.

Opus còn: tick plan, cập nhật runtime chính thức/kiểm version-path và reload nếu cần, sửa config theo D.3, D.4 kiểm thực tế, D.5 merge/push, D.6 memory, D.7 lịch đo 16/11. Không chạy lại full suite trong phiên này theo quy tắc đúng một lần.

## Hand và usage

Paseo có PASEO_AGENT_ID; pick thực codex gpt-6.1-sol low, cap ext_hand.max_parallel=4. Dùng 2 native children `integration` và `policy`, fork_turns=none, đúng model/effort, brief tự chứa đủ bảy mục và luật dữ liệu nguyên văn. Không recursion/hand-ext/side-session ở hand; sửa cùng file và các lượt correction chạy tuần tự, tối đa 2 children đồng thời. Native không tạo report/meta/token ledger hand-ext; dùng báo cáo runtime/Paseo. Token/USD~/quota không được tools cung cấp: ? / ? / ?. Không suy quota hay bịa chi phí.
