# Brief Sol: lệnh bật/tắt parallel_subagents + làm rõ AGENTS.md (L0)

## Tóm tắt
- **Mục tiêu:** thêm lệnh ngắn `hand-ext parallel on|off` (không đối số = in trạng thái hiệu lực + nguồn) ghi đúng key `parallel_subagents.enabled` vào `.claude/hybrid-hands.json` của repo hiện tại; sửa câu AGENTS.md:31 cho rõ phạm vi cấm.
- **Lane:** L0, gom một phiên. Sol giao hand theo `ext_hand.order`, review, phát hành 0.37.1, điều phối commit/merge `main` theo AGENTS.md.
- **Người dùng chốt (10/11/2026):** làm L0 này, tên lệnh rút gọn cho dễ dùng.

## LUẬT BẮT BUỘC
Theo AGENTS.md repo `/Users/anhtp/app/claude-plugins` (đọc trước). Luật dữ liệu chép nguyên văn vào brief hand ngoài:

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## KHÔNG ĐƯỢC ĐỤNG
- `.claude/hybrid-hands.json` thật của bất kỳ repo nào (test chỉ dùng thư mục tạm/fixture); không chạy `hand-ext parallel on` trên repo thật.
- `parallel-subagents/`, `statusline/`, settings/credential/`installed_plugins.json`; không xoá/di chuyển `output/llm/`; giữ file untracked `docs/work-in-progress/*`.

## NGỮ CẢNH
- 0.37.0 (merge `39a9e4a`) đã có key `parallel_subagents.enabled`, mặc định false, true chỉ hiệu lực từ repo config, global true bị bỏ qua kèm warning (AGENTS.md:37; loader `hybrid-hands/plugins/hybrid-hands/lib/shared_config.py`, repo config path/fallback worktree ở `lib/hand_ext/config.py:87`).
- Tên lệnh: `hand-ext parallel`. Nếu `parallel` đã là subcommand có sẵn thì dùng `hand-ext psa` và ghi lý do trong bàn giao.
- AGENTS.md:31 hiện viết "Không sửa `.claude/hybrid-hands.json`, ... credential/settings trong công việc usage panel; plugin parallel-subagents cũ luôn tắt, mode `parallel_subagents.enabled` chỉ người dùng chốt ..." — người đọc dễ hiểu là cấm sửa file này mọi lúc.

## Yêu cầu
1. `hand-ext parallel` (không đối số): in `parallel_subagents: on|off (nguồn: <default|global|repo>, file: <path>)`, kèm warning nếu global đặt true.
2. `hand-ext parallel on|off`: đọc JSON repo config hiện có (tạo `.claude/` + file nếu thiếu), set đúng `parallel_subagents.enabled` true/false, giữ nguyên mọi key khác và thứ tự key, ghi atomic (file tạm + rename), indent 2 + newline cuối. JSON hỏng → báo lỗi kèm đường dẫn, exit ≠ 0, không ghi. Chạy trong worktree: ghi vào config checkout chính nếu đó là file loader thực sự đọc (theo fallback hiện có) và in rõ đường dẫn đã ghi. Idempotent. Sau khi ghi in nhắc "mở phiên mới để hook nạp luật".
3. `--json` cho trạng thái nếu các subcommand khác có quy ước `--json`.
4. AGENTS.md:31: tách câu, ghi rõ cấm sửa các file đó chỉ áp cho công việc usage panel; key `parallel_subagents` chỉ đổi bằng `hand-ext parallel on|off` khi người dùng chốt cho repo đó, brain/hand không tự bật. Sửa tối thiểu, giữ `:26`, `:37` nhất quán (thêm tên lệnh vào `:37`).
5. README (mục parallel_subagents): thay hướng dẫn sửa JSON tay bằng lệnh mới. CHANGELOG + version 0.37.1.

## PHẠM VI GHI
- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/` (CLI/subcommand mới), `hybrid-hands/plugins/hybrid-hands/lib/shared_config.py` nếu cần helper ghi
- `hybrid-hands/tests/` (test hẹp mới)
- `hybrid-hands/README.md`, `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md`, `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json`, marketplace manifest nếu có version
- `/Users/anhtp/app/claude-plugins/AGENTS.md`

## KIỂM CHỨNG
- Mức test: tối thiểu. Ca test (≤3): (a) `on` trên config có key khác → chỉ thêm key, key khác giữ nguyên, trạng thái báo on/repo; (b) `off` idempotent + file chưa tồn tại được tạo; (c) JSON hỏng → exit ≠ 0, file không đổi.
- Test hẹp: file test mới + `hybrid-hands/tests/test_policy_mode.py`; không full suite.
- Validate JSON manifest, `claude plugin validate`.
- Review xanh → commit nhánh, push, merge `main`, push `main`; cập nhật cài đặt hybrid-hands qua công cụ chính thức cho mọi repo đang dùng (v1/v2), kiểm version + đường dẫn nạp; báo cần reload.

## TRẢ VỀ
Bàn giao `side-session` chuẩn, mở đầu Tóm tắt: tên lệnh cuối cùng, ví dụ dùng, SHA commit/merge, version, lệnh test + kết quả thật, repo đã cập nhật, phần chưa kiểm chứng. hand-ext lỗi thì ghi mã thoát (lưu ý `--mode auto` từng trả `PARENT_REQUIRED` khi không có parent Paseo; `--mode shell` chạy được).
