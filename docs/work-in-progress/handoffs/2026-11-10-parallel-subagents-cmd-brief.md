# Brief Sol: đổi tên lệnh thành parallel-subagents + slash command plugin (L0)

## Tóm tắt
- **Mục tiêu:** tên lệnh đầy đủ, rõ nghĩa ở cả hai lối vào: CLI `hand-ext parallel-subagents [on|off] [--json] [--cwd]` và slash command `/hybrid-hands:parallel-subagents [on|off]`.
- **Lane:** L0. Sol giao hand theo `ext_hand.order`, review, phát hành 0.37.2, điều phối commit/merge `main` theo AGENTS.md.
- **Người dùng chốt (10/11/2026):** dùng tên đầy đủ `parallel-subagents` cho cả CLI và slash command.

## LUẬT BẮT BUỘC
Theo AGENTS.md repo `/Users/anhtp/app/claude-plugins` (đọc trước). Luật dữ liệu chép nguyên văn vào brief hand ngoài:

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## KHÔNG ĐƯỢC ĐỤNG
- `.claude/hybrid-hands.json` thật của mọi repo; không chạy `on`/`off` trên repo thật (test chỉ dùng thư mục tạm).
- `parallel-subagents/`, `statusline/`, settings/credential/`installed_plugins.json`; không xoá/di chuyển `output/llm/`; giữ file untracked `docs/work-in-progress/*`.

## NGỮ CẢNH
- 0.37.1 (merge `c68f0e9`) đã có `hand-ext parallel [on|off] [--json] [--cwd]` ở `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/cli.py` và `lib/hand_ext/parallel_cmd.py`; test `hybrid-hands/tests/test_hand_parallel_cmd.py` (3 ca) và `test_policy_mode.py`.
- Lệnh slash hiện có cùng khuôn: `hybrid-hands/plugins/hybrid-hands/commands/to-paseo.md`, `to-term.md`.
- AGENTS.md (`:26`, `:31`, `:37`) và `hybrid-hands/README.md` đang nhắc `hand-ext parallel on|off`.

## Yêu cầu
1. CLI: subcommand chính `parallel-subagents`; giữ `parallel` làm alias tương thích (ẩn khỏi help nếu argparse cho phép, nếu không thì ghi "alias cũ"). Hành vi/flag không đổi.
2. Tạo `commands/parallel-subagents.md` → `/hybrid-hands:parallel-subagents [on|off]`: vỏ mỏng chạy `${CLAUDE_PLUGIN_ROOT}/bin/hand-ext parallel-subagents $ARGUMENTS` trong cwd repo hiện tại, in kết quả, nhắc mở phiên mới khi đã đổi. Không đối số → chỉ xem trạng thái; không tự bật; không chứa logic ghi config riêng.
3. AGENTS.md + README: đổi mọi chỗ sang tên đầy đủ, nêu hai cách (`/hybrid-hands:parallel-subagents on|off` trong Claude Code, `hand-ext parallel-subagents on|off` ngoài terminal/Codex); nhắc `parallel` là alias cũ một lần trong README. Sửa tối thiểu.
4. CHANGELOG + version 0.37.2.

## PHẠM VI GHI
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/cli.py`, `lib/hand_ext/parallel_cmd.py`
- `hybrid-hands/plugins/hybrid-hands/commands/parallel-subagents.md` (mới)
- `hybrid-hands/tests/test_hand_parallel_cmd.py`
- `hybrid-hands/README.md`, `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md`, `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json`
- `/Users/anhtp/app/claude-plugins/AGENTS.md`

## KIỂM CHỨNG
- Mức test: tối thiểu. Ca test: đổi test sẵn có sang `parallel-subagents` và thêm một assert alias `parallel` vẫn chạy; không thêm test cho text command.
- Test hẹp: `test_hand_parallel_cmd.py`, `test_policy_mode.py`; không full suite.
- JSON manifest hợp lệ, `claude plugin validate` nhận command mới.
- Review xanh → commit nhánh, push, merge `main`, push `main`; cập nhật cài đặt hybrid-hands qua công cụ chính thức cho mọi repo đang dùng (v1/v2), kiểm version + đường dẫn nạp + command file có trong cache; báo cần reload.

## TRẢ VỀ
Bàn giao `side-session` chuẩn, mở đầu Tóm tắt: ví dụ dùng cả hai lối vào, SHA commit/merge, version, lệnh test + kết quả thật, repo đã cập nhật, phần chưa kiểm chứng (slash command chỉ kiểm được sau reload). hand-ext lỗi ghi mã thoát (`--mode auto` từng trả `PARENT_REQUIRED` khi không có parent Paseo; `--mode shell` chạy được).
