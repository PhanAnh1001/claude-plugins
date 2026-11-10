## Tóm tắt
- Kết quả: xong phần code B.1–B.4; Sol đã review, chờ tích hợp nguồn A và template C trước chạy thật.
- Nhánh: `side/luong-b`; commit: `fc5d7864fdf6c1752b39a60660580464c1768a43`; không merge main, không push.
- `cli.py`, `config.py`, `constants.py`: thêm cờ tài khoản, adapter registry, mặc định Claude Opus high và tên template.
- `actions.py`, `commands.py`: nối account qua start/main/resume, env đúng config_dir và giữ guard v1 hiện có.
- `handoff.py`, `state.py`, `tokens.py`: chọn template theo account, lưu account/config_dir, đếm đúng transcript.
- `test_side_session.py`, `test_side_session_paseo.py`: thêm 2 ca mới, cập nhật Claude main thành hợp lệ.
- Test hẹp: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session*.py' -q` → 96 tests OK.
- Full suite đúng một lần: `python3 -m unittest discover -s hybrid-hands/tests -q` → 452 tests OK (58.900s); `git diff --check` sạch.
- Chốt: `--account v1|v2|v…`, `--main --provider claude --account v2`, khoá `ext_hand.claude_accounts`.
- Cần C tạo `templates/side-session-prompt-claude.md`, `templates/main-session-prompt-claude.md`; thiếu file báo lỗi trước mutation.
- Chưa làm: nối loader user+repo của A, template/policy/version/validate/install, phiên thật; Opus làm lúc tích hợp.
- Hand: native Codex `gpt-6.1-sol` low theo Ngoại lệ A; token/USD~/quota: ? / ? / ?; không có ledger hand-ext.

## Kết quả theo plan

- B.1: thêm `--account` cho provider Claude; mặc định v1, lấy `config_dir` từ registry. Không giới hạn choices vào v1/v2 để tài khoản thêm qua config dùng được. Tài khoản không khai báo hoặc config_dir không hợp lệ trả exit 2 trước preflight/worktree/state. Provider khác có `--account` bị từ chối.
- B.2: `--main --provider claude --account v2` dùng Claude screen, mặc định `claude-opus-5-5`, effort `high`; không có handoff/watchdog/parent phiên phụ, không chiếm slot phụ. `--main` không chỉ định provider vẫn là Codex Sol high trên Paseo. Không mở rộng transport Claude sang Paseo. Main vẫn không dùng `--worktree`/`--resume`.
- B.3: v1 chọn template cũ; v2/v… chọn template Claude có `{account}`. Main Claude chọn template main riêng. Chỉ làm logic chọn/đọc/thay placeholder, không sửa hay tạo template.
- B.4: thêm đúng hai test methods mới theo spec 5.1; một ca v2 bao gồm launcher/env, state/resume/main và đường dẫn transcript bằng fixture; một ca account lạ bị từ chối trước mutation. Sửa một assertion cũ vốn coi main Claude không hợp lệ. Dòng test thêm 35, dòng code thêm 144 (<= 1/2).

## Các file đã đổi

Đường dẫn dưới đây tính từ `hybrid-hands/`:

- `plugins/hybrid-hands/lib/side_session/cli.py`: cờ `--account` và help main/model/effort phản ánh Claude.
- `plugins/hybrid-hands/lib/side_session/config.py`: thêm `SideConfig.claude_accounts`; helper default/load/resolve registry để nối gói A.
- `plugins/hybrid-hands/lib/side_session/constants.py`: mặc định Claude model/effort, placeholder account và hai tên template.
- `plugins/hybrid-hands/lib/side_session/actions.py`: validate tài khoản, main Claude qua screen không watchdog, resume giữ account/config_dir, giữ guard v1 và đếm transcript đúng account.
- `plugins/hybrid-hands/lib/side_session/commands.py`: thêm model/effort Claude và truyền `CLAUDE_CONFIG_DIR` đã expand qua env launcher.
- `plugins/hybrid-hands/lib/side_session/handoff.py`: chọn template theo account/role và thay `{account}`; lỗi dependency rõ khi thiếu file.
- `plugins/hybrid-hands/lib/side_session/state.py`: bổ sung cuối dataclass `account='v1'`, `claude_config_dir=''`, `model=''`, `effort=''` để state cũ còn đọc được.
- `plugins/hybrid-hands/lib/side_session/tokens.py`: tham số config_dir cho transcript, vẫn giữ override fixture `SIDE_SESSION_CLAUDE_PROJECTS`.
- `tests/test_side_session.py`: hai ca mới theo phạm vi kiểm chứng.
- `tests/test_side_session_paseo.py`: bỏ Claude khỏi các provider main bị từ chối.

Không sửa `lib/hand_ext/**`, templates, cấu hình, version/changelog/README/AGENTS, scripts/skills hoặc spec/plan. `bin/side-session` không cần đổi.

## Contract nối gói A

Registry public đã dùng: `ext_hand.claude_accounts` trong `.claude/hybrid-hands.json`.

- `default_claude_accounts()` ở `lib/side_session/config.py` ưu tiên `hand_ext.constants.DEFAULTS['claude_accounts']` khi A đã thêm nguồn này; hiện fallback đúng spec: v1 `~/.claude`, `max_day_pct=5`; v2 `~/.claude-hand`, không max_day_pct.
- `load_claude_accounts(repo)` là điểm adapter nhỏ cần Opus nối nguồn cấu hình canonical sau merge A. Hiện gọi `hand_ext.config._read_section(repo)` và merge từng account lên defaults; `_read_section` của baseline chỉ đọc repo/config của main-worktree nếu worktree không có config. Chưa có loader user+repo mới của A trong worktree này; cấu hình user mới cần nối tại adapter này, không nhân bản thêm sổ khác.
- `claude_account(cfg, account)` validate config_dir và expand `~`; đường tương đối tính từ repo.
- Runtime đặt `CLAUDE_CONFIG_DIR` theo tài khoản; state ghim config_dir để resume không trôi sang account khác khi cấu hình đổi. `--resume` không truyền account giữ account trong state; truyền account khác bị từ chối. Resume luôn validate account còn trong registry rồi mới dùng config_dir đã ghim.
- State cũ không có account nhận default v1; model/effort rỗng vẫn dùng default launcher.

Ví dụ thêm tài khoản ở repo (chỉ minh hoạ, không sửa cấu hình thật):

```json
{"ext_hand":{"claude_accounts":{"v3":{"config_dir":"~/.claude-v3"}}}}
```

Guard ngày: B giữ nguyên cơ chế `side_session.budget_check_cmd` sẵn có của v1, cùng `--budget-exempt`, `--force-budget`, exit 4 khi start bị từ chối và watch daystop mã 20. Claude account không có `max_day_pct` (v2 mặc định) bỏ qua guard này để không nhận trần v1. B không thêm phép tính 5% tự động mới; `max_day_pct` hiện chỉ quyết định có dùng command guard sẵn có hay không, không truyền số/config_dir cho command. Các tài khoản tuỳ chỉnh có trần riêng cần Opus đánh giá khi nối guard canonical của A; không được coi các giá trị cap khác 5 đã được B thực thi độc lập.

## Tên lệnh/cờ/template cho gói C

```sh
side-session start --name opus-v1 --provider claude --prompt '...'
side-session start --name opus-v2 --provider claude --account v2 --prompt '...'
side-session start --name opus-v3 --provider claude --account v3 --prompt '...'
side-session start --name main-v2 --main --provider claude --account v2
side-session start --name sol-main --main
side-session start --name opus-v2 --resume
```

Các lệnh mở phiên phụ vẫn cần `--prompt` hoặc `--prompt-file`; main có thể bỏ prompt. Claude mặc định Opus 5.5 high, override qua `--model`/`--effort`. `--account` chỉ dùng với provider Claude. Chuyển model/tài khoản theo policy là mở phiên mới.

Gói C cần tạo trong `hybrid-hands/plugins/hybrid-hands/`:

1. `templates/side-session-prompt-claude.md`: v2/v…; dùng `{account}` để xác định đúng tài khoản cho bảng chọn native/hand-ext; có thể dùng `{name}`, `{handoff}`, `{brain}`, marker `[[brain]]` như template cũ.
2. `templates/main-session-prompt-claude.md`: main Claude mọi account; dùng `{account}`, nội dung main riêng, không yêu cầu handoff/.done. Cùng bộ thay placeholder như trên nhưng không nên dùng handoff.
3. `templates/side-session-prompt.md` hiện dùng cho v1: C có thể ghi rõ v1 hoặc dùng `{account}` (B đã thay placeholder này).

Thiếu hai file mới sẽ báo `side-session: thiếu template ... (dependency gói C)`, exit 2 trước tạo worktree/state. Không fallback sang nội dung v1. Do đó nhánh B độc lập chưa thể mở v2/main Claude thật trước khi có template C.

## Kiểm chứng và review thực tế

- Hand lần đầu chạy hẹp có hai lỗi fixture legacy, sửa fixture rồi chạy xanh; không chạy full suite ở hand.
- Sol review diff toàn bộ, yêu cầu sửa một lượt: help CLI còn mô tả Codex-only; resume tài khoản đã xoá khỏi registry phải trả lỗi usage thay vì ném ValueError qua preflight. Hand đã sửa, Sol review lại đạt.
- Sol tự chạy nhóm `test_side_session*.py`: 96 tests OK (16.099s) trước lượt chỉnh cuối. Hand chạy lại sau chỉnh cuối: 96 tests OK (12.757s).
- Sol chạy đúng một lần lệnh full suite đã giao sau review cuối: `python3 -m unittest discover -s hybrid-hands/tests -q` → exit 0, 452 tests OK (58.900s).
- `git diff --check` → exit 0, không lỗi whitespace. Help CLI đã được chạy để review cờ. Tests dùng fake screen/Claude/Codex/Paseo và fixture template; không mở phiên thực tế, không đọc auth/transcript/log thật.
- Không chạy plugin validate/cập nhật runtime/version vì brief dành phần đó cho Opus/gói C/D. Không claim template mới hay tích hợp A đã được kiểm thực tế.

## Hand và usage

- Xác nhận Paseo qua `PASEO_AGENT_ID` có mặt; cấu hình repo hiện hành có order `[codex]`, model `gpt-6.1-sol`, effort `low`.
- Theo Ngoại lệ A trong `hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md`, dùng một native child `implement_b`, `fork_turns=none`, đúng model/effort, full brief tự chứa và luật dữ liệu nguyên văn. Một child trong pool; không có hand-ext writer song song, không bật parallel-subagents, không archive parent/history.
- Backend native: `gpt-6.1-sol` low. Token: ?; USD~: ?; quota: ?. Runtime native không cung cấp số liệu trong kết quả tools phiên này; không tạo meta/report/token ledger hand-ext, không suy quota.
- Hand đã completed, test subprocess đã kết thúc; không còn tiến trình nền do lượt này tạo đang chạy.

## Bước tiếp theo cho Opus

1. Đọc/cherry-pick commit gói B; không cần tick plan từ nhánh này (B không sửa plan).
2. Khi merge A, nối adapter `load_claude_accounts()` sang loader canonical có cấu hình user+repo và rà guard tài khoản có max_day_pct tuỳ chỉnh.
3. Giao C tạo template theo tên/placeholder chốt trên, đồng bộ policy/README.
4. Opus làm version/CHANGELOG/validate/install và kiểm launch thực tế theo D; sau đó điều phối merge/push.
