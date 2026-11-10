## Tóm tắt
- Kết quả: xong một phần gói A; đã review và commit, không merge/push.
- Task: A.2 (sổ repo), A.4–A.7 xong; A.3 xong order/Codex low; A.1 chưa đủ bằng chứng checkpoint 1017 nên giữ dsh model/effort/giá.
- Nhánh `side/luong-a`; commit `9c041c5`.
- Đổi 7 file hand_ext: registry/account/alias, selector/order, pick và quota chỉ đọc; 2 file hh_ps: ánh xạ tên; 4 test: contract và expectation mới.
- Test hẹp: hand_ext 174, hh_ps 94, calibration 22 đều xanh; panel 2 và defaults 2 xanh sau sửa tương thích cuối.
- Full suite đúng 1 lần: 451 ca, 1 lỗi legacy account label; đã sửa, kiểm lại nhóm liên quan xanh; KHÔNG claim full suite xanh sau sửa.
- Smoke `hand-ext pick --json`: exit 0, codex / gpt-6.1-sol / low / gpt, skipped=[]; `git diff --check` sạch.
- Khoá/lệnh chốt: `ext_hand.claude_accounts`, `config_dir`, `max_day_pct`; `claude-v<N>`; aliases `claude-main`→v1, `claude`→v2; `hand-ext pick [--json] [--cwd PATH]`.
- Mặc định: order dsh→codex→claude-v1→claude-v2; Claude Opus 5.5 low, Codex Sol 6.1 low; dsh vẫn deepseek-v4.1-flash high.
- Còn lại: xác minh Go checkpoint 1017, đổi dsh/thêm giá nếu đủ nguồn; nguồn config user-level chưa có đường dẫn được chốt; C/D release/runtime/config repo/kiểm thực tế.
- Hand: native Codex gpt-6.1-sol low trên Paseo, tối đa 1/4 hand đồng thời; token/USD~/quota `?`; không có ledger hand-ext.

## Git và phạm vi

Commit `9c041c5679a5bb22ca8c6008209c215b423a0a3e` trên nhánh `side/luong-a`; không push, không merge main. Cây làm việc sạch sau commit. Không sửa spec/plan ở cây chính; Opus tick từ bàn giao này. Không đổi side_session, manifest/version, CHANGELOG, README, AGENTS, scripts, templates, skills, settings hay cấu hình runtime. Không thay giá vì thiếu xác minh model mới.

## Kết quả theo task

- A.1: đã đọc code backend dsh, adapter cài cục bộ và tài liệu công khai ngày 2026-11-09. Cách tắt thinking xác minh được; checkpoint/ID Go 1017 chưa xác minh được. Theo override trong brief, tiếp tục các task còn lại và giữ dsh hiện tại.
- A.2: defaults `v1={config_dir:~/.claude,max_day_pct:5}`, `v2={config_dir:~/.claude-hand}`. `ext_hand.claude_accounts.v3` và các v<N> sinh backend tự động; model `claude-opus-5-5`, effort `low`. Alias cũ có cùng resolved options, bao gồm override backend legacy. Guard áp cho bất kỳ account có `max_day_pct`, dùng đúng config_dir và fail closed nếu không đo được.
- A.3: order mặc định bốn backend và Codex low đã đổi. Phần dsh bản 1017/off và entry giá chưa làm, do A.1. Cấu hình repo hiện vẫn order=[codex] đúng yêu cầu không sửa runtime.
- A.4: auto duyệt order lazily với cùng preflight như pick; bỏ qua quota state, doctor/login lỗi và guard ngày. Auth/quota khi chạy chuyển backend kế tiếp; hết order trả 7. Alias cũ/mới đối chiếu quota state hai chiều. Fallback khi dsh capacity có patch nhỏ dùng phần order còn lại, không ép Codex/model/effort. Giữ cơ chế an toàn có sẵn khi patch lớn/không đo được hoặc isolation none: giữ patch, dừng thay vì chạy writer khác.
- A.5: pick chỉ chọn bằng preflight, không chạy hand, không ghi ledger/quota state/lock; JSON `{backend,model,effort,account,skipped:[{backend,reason}]}`. Khi không chọn được: bốn field đầu null, exit 7. Codex account=`gpt`, Claude account=`claude-vN`. Check doctor chỉ xuất tên check lỗi, không xuất stdout tuỳ ý.
- A.6: hh_ps đọc tên legacy và canonical; account bị gỡ khỏi config vẫn giữ ledger/model pricing và quota unknown. Calibration chỉ thêm ánh xạ tương đương v1/v2; v3 không mượn calibration v2. Paseo panel dùng startsWith(claude), pane dùng tên backend dạng chuỗi nên không cần sửa UI/layout.
- A.7: đúng 2 ca acceptance trong test defaults (1 ca cũ thay, 1 ca thêm), cập nhật expectation test hiện có. Tổng dòng thêm test 86, implementation 210, dưới 1/2. Không thêm test tài liệu.

## Contract cho gói B/C

- Đọc bằng `hand_ext.config.load_config(...).claude_accounts["vN"]`: dict config_dir và optional max_day_pct đã resolve override.
- Lấy options đầy đủ bằng `cfg.options("claude-vN")`; unknown account ném ValueError. Trường dataclass claude_accounts thêm cuối với default factory để tương thích.
- Cấu hình repo nằm dưới `ext_hand.claude_accounts`; vẫn kế thừa config cây chính nếu linked worktree không có file riêng.
- Loader trước đây chỉ có config repo, không có nguồn config người dùng toàn cục. Chưa tự tạo đường dẫn/schema precedence mới. Opus cần chốt phần “repo hoặc người dùng” nếu muốn thêm global config.
- v1 config_dir custom được truyền CLAUDE_CONFIG_DIR đúng account; chỉ thư mục thực ~/.claude mới bỏ biến này để giữ OAuth layout Claude Code.
- Daily guard của v1 mặc định 5%; v2 không guard; account khác có max_day_pct thì guard như v1.
- `hand-ext pick --json` và `hand-ext pick --cwd PATH` hoạt động qua bin/hand-ext hiện có, không cần đổi wrapper.
- Tên backend ledger vẫn giữ tên người dùng gọi (alias cũ vẫn được đọc); `account` trong pick chuẩn hoá tên.
- Exit 0 selected, 7 hết backend; exit 8 slot giữ nguyên. Không đổi ext_hand.max_parallel hoặc kernel slots.

## A.1 — nguồn công khai và code, kiểm ngày 2026-11-09

1. https://opencode.ai/docs/console/go/ (URL cũ https://opencode.ai/docs/go/ chuyển hướng): liệt kê Go model ID `deepseek-v4.1-flash`, không công bố ánh xạ checkpoint 1017. https://models.opencode.ai/providers/opencode-go/ cũng liệt kê `deepseek-v4.1-flash` gắn canonical bản không suffix.
2. https://opencode.ai/data/deepseek/deepseek-v4-1-flash-1017 có trang 1017 và canonical model name, nhưng đây là trang thống kê, không xác nhận ID request/checkpoint được phục vụ trên Go. Không suy từ tên canonical sang Go model ID.
3. https://raw.githubusercontent.com/deepseek-ai/deepseek-harness/master/docs/user/guide/providers.md mục Reasoning effort: `reasoningEfforts.off` để trống/null, `compat.thinkingFormat: deepseek` làm off gửi `thinking:{type:disabled}`.
4. Code repo `lib/hand_ext/backends/dsh.py`: EFFORTS nhận off/low/high/max và truyền HAND_EXT_DSH_EFFORT; template hiện có thinkingFormat deepseek nhưng danh sách reasoningEfforts chỉ low/high/max.
5. Code adapter cài cục bộ (chỉ đọc code công khai, không auth): `/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@deepseek-ai/dsh/node_modules/@deepseek-ai/dsh-llm-pi-ai/lib/index.js` quanh 586–605 xác định off capability; `@earendil-works/pi-ai/dist/api/openai-completions.js` quanh 654–664 gửi disabled nếu off được hỗ trợ. Khi triển khai sau, cần khai báo off:null đúng model trong overlay/template; chỉ đổi chuỗi effort chưa đủ với template hiện tại.

Không gọi inference/API trả phí, không dùng API key để probe, không thêm model guessed hay fallback pricing. Chưa có kiểm thực tế report dsh 1017/thinking off/token/USD theo spec 5.2.1; để Opus quyết từ nguồn xác minh bổ sung.

## File đã đổi và lý do

Đường dẫn dưới đây tính từ `hybrid-hands/`:

- `plugins/hybrid-hands/lib/hand_ext/constants.py`: defaults registry, order bốn backend và Codex/Claude low.
- `plugins/hybrid-hands/lib/hand_ext/config.py`: merge account registry/legacy override, sinh options canonical và alias, public dataclass contract.
- `plugins/hybrid-hands/lib/hand_ext/backends/__init__.py`: nhận backend Claude đánh số và alias cũ.
- `plugins/hybrid-hands/lib/hand_ext/backends/claude.py`: account runtime, guard theo max_day_pct và đúng config_dir.
- `plugins/hybrid-hands/lib/hand_ext/run_cmd.py`: preflight dùng chung, auto lazy fallback theo order, capacity fallback theo tail.
- `plugins/hybrid-hands/lib/hand_ext/cli.py`: parser/output pick, doctor/setup liệt kê cả backend cấu hình.
- `plugins/hybrid-hands/lib/hand_ext/quota_state.py`: reader không tạo lock; writer vẫn khoá và atomic os.replace.
- `plugins/hybrid-hands/lib/hh_ps/usage_enrichment.py`: ánh xạ backend cũ/mới, quota đúng account và unknown khi tài khoản không còn; giữ legacy no-config.
- `plugins/hybrid-hands/lib/hh_ps/claude_calibration.py`: ánh xạ canonical v1/v2 tương đương tên cũ.
- `tests/test_hand_ext_defaults.py`: hai ca acceptance về order/account/alias/removed account và pick bỏ qua/exhausted/không ghi file.
- `tests/test_hand_ext_capacity.py`: fixture order có Codex tường minh, expectation fallback theo order.
- `tests/test_hand_ext_claude.py`: expectation custom config_dir đúng tài khoản.
- `tests/test_hand_ext_codex.py`: expectation Codex effort low.

## Kiểm chứng và review

Hand chạy:

- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext*.py' -q`: 174 passed, sau sửa fixture/expectation.
- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hh_ps*.py' -q`: 94 passed; chạy lại sau correction cuối cũng 94 passed.
- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_claude_calibration.py' -q`: 22 passed.
- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_ext_defaults.py' -q`: 2 passed sau correction.
- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_usage_panel.py' -q`: 2 passed sau correction.

Sol chạy:

- `python3 -m unittest discover -s hybrid-hands/tests -q`: đúng MỘT lần, exit 1, 451 tests trong 60.676s, failure duy nhất test_missing_quota_is_unknown (legacy claude-main no-config mất account_plan). Giao hand sửa mapping, review lại diff; KHÔNG chạy lại full suite theo yêu cầu.
- `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hand_usage_panel.py' -q`: exit 0, 2 tests/0.087s sau correction cuối.
- `hybrid-hands/plugins/hybrid-hands/bin/hand-ext pick --json`: exit 0; codex/gpt-6.1-sol/low/gpt, skipped=[] theo config hiện hành. Không chạy hand inference thực.
- `git diff --check`: sạch trước commit.

Sol review toàn bộ diff, yêu cầu sửa crash removed-account và tránh áp calibration v2 cho v3, rồi sửa tương thích legacy phát hiện từ full suite. Không sửa file test ngoài phạm vi. Không claim validation plugin, release, cài đặt hay version runtime đã chạy; các việc này thuộc gói C/D theo brief. Không có tiến trình nền Sol tạo còn chạy.

## Hand và usage

Đã xác minh Paseo có PASEO_AGENT_ID, tools native spawn/wait hỗ trợ chọn model/effort; config thực tế chọn codex gpt-6.1-sol low, cap 4. Dùng một native child `implement_a`, fork_turns=none, model gpt-6.1-sol, reasoning_effort=low, brief tự chứa luật dữ liệu. Hand executor không recursion/delegate/side-session. Mọi lượt sửa đã kết thúc trước review/commit/bàn giao. Không gọi hand-ext nên không có mã lỗi hand-ext hay fallback quota; native không tạo report/meta/ledger hand-ext. Runtime không cung cấp token/USD~/quota: `?`.
