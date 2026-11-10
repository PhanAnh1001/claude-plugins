# Hand executor: parallel-subagents command 0.37.2 (L0)

Bạn là hand executor, làm trực tiếp; không hand-ext, side-session, subagent, recursion, giao tiếp phiên khác hay review hand khác. Đọc AGENTS.md và CLAUDE.md áp dụng. Không commit/push/merge, không cập nhật runtime; Sol làm sau review. Không đọc transcript/log thật. Chỉ dùng code/fixtures giả công khai.

## Luật dữ liệu nguyên văn

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## Yêu cầu và tiêu chí chấp nhận

1. CLI chính `hand-ext parallel-subagents [on|off] [--json] [--cwd]`; `parallel` alias tương thích, ẩn khỏi help nếu argparse cho phép sạch, nếu không ghi rõ alias cũ. Giữ nguyên hành vi/flags. Ưu tiên argparse aliases và help ghi alias cũ thay vì thủ thuật private.
2. Tạo `commands/parallel-subagents.md`, frontmatter description, argument-hint `[on|off]`, allowed-tools Bash theo khuôn commands/to-paseo.md. Vỏ mỏng thực thi `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" parallel-subagents $ARGUMENTS` bằng Bash ở cwd repo hiện tại, in kết quả, nhắc mở phiên mới khi đã đổi. Không đối số chỉ xem, không tự bật, không ghi config bằng logic riêng, lỗi báo lỗi. Không chạy on/off repo thật.
3. Thay mọi `hand-ext parallel` trong AGENTS.md và README sang tên đầy đủ. Nêu hai lối `/hybrid-hands:parallel-subagents on|off` trong Claude Code và `hand-ext parallel-subagents on|off` terminal/Codex; README nhắc `parallel` alias cũ đúng một lần. Sửa tối thiểu, giữ luật chỉ đổi mode khi user chốt.
4. Bump manifest 0.37.2, changelog 2026-11-10 về rename/alias/slash command. Không sửa lịch sử release cũ.

## Phạm vi ghi (chỉ các file này)

- hybrid-hands/plugins/hybrid-hands/lib/hand_ext/cli.py
- hybrid-hands/plugins/hybrid-hands/lib/hand_ext/parallel_cmd.py (chỉ nếu cần)
- hybrid-hands/plugins/hybrid-hands/commands/parallel-subagents.md (mới)
- hybrid-hands/tests/test_hand_parallel_cmd.py
- hybrid-hands/README.md
- hybrid-hands/plugins/hybrid-hands/CHANGELOG.md
- hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json
- AGENTS.md

Không đụng `.claude/hybrid-hands.json` thật mọi repo, parallel-subagents/, statusline/, settings/credential/installed_plugins.json, output/llm/, file untracked docs/work-in-progress/*. Không bật/tắt mode thật.

## Kiểm chứng (tối đa 3 ca test sẵn có)

- Chuyển helper test sang gọi parallel-subagents, giữ ba test hiện có: on bảo toàn key/fallback, off idempotent, config lỗi không đổi. Thêm một assert alias parallel vẫn chạy vào một test hiện có, không thêm ca test hoặc test text command.
- Chỉ chạy `python3 -m unittest discover -s hybrid-hands/tests -p test_hand_parallel_cmd.py` và tương tự `test_policy_mode.py`; không full suite.
- JSON manifest hợp lệ; `claude plugin validate hybrid-hands/plugins/hybrid-hands` và `claude plugin validate hybrid-hands` nếu khả dụng. Sol sẽ kiểm lại.
- Báo danh sách file đổi, lệnh/kết quả thật, điểm chưa kiểm chứng. Slash runtime chỉ kiểm sau reload.
