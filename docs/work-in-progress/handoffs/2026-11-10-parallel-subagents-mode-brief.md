# Brief Sol: chế độ parallel_subagents theo repo trong hybrid-hands (L1)

## Tóm tắt
- **Mục tiêu:** hybrid-hands có chế độ `parallel_subagents.enabled` bật riêng từng repo, mặc định tắt. Khi bật, hook bơm biến thể luật "giao hand Claude native song song" thay cho luật hybrid thường, không bơm hai bộ luật.
- **Lane:** L1, không có lựa chọn giải pháp lớn (phương án đã chốt bên dưới). Sol viết tiêu chí, giao hand theo `ext_hand.order`, review, rồi điều phối commit/merge `main` theo AGENTS.md.
- **Ngoài phạm vi (L2 sau):** cưỡng chế slot/admission thật cho native Agent. Bản này chỉ nhắc trong luật.
- **Người dùng đã chốt (10/11/2026):** làm L1 trước và đổi luật AGENTS.md của repo cho phép chế độ này.

## LUẬT BẮT BUỘC
Theo AGENTS.md repo `/Users/anhtp/app/claude-plugins` (đọc trước khi làm). Luật dữ liệu chép nguyên văn vào brief hand ngoài:

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## KHÔNG ĐƯỢC ĐỤNG
- `parallel-subagents/` (plugin cũ giữ nguyên, giữ tắt), `statusline/`.
- `.claude/hybrid-hands.json`, `~/.claude/settings.json`, `installed_plugins.json`, `~/.codex-hand/config.toml`, credential/settings; không bật parallel-subagents plugin ở repo nào.
- Không xoá/di chuyển `output/llm/`. Giữ thay đổi chưa commit của người khác (`docs/work-in-progress/*` đang untracked).

## NGỮ CẢNH (khảo sát hand codex, report `output/llm/hand-ext/20261110-083344-354735-merge-ps-khao-sat-codex/report.md`)
`P=parallel-subagents/plugins/parallel-subagents`, `H=hybrid-hands/plugins/hybrid-hands`.
- P 2.1.0 chỉ có `agents/hand.md`, `templates/hand-brief.md`, hook SessionStart (`P/scripts/session-start-policy.sh:8`) và UserPromptSubmit (`P/scripts/inject-policy.sh:5`): giao mọi việc thực thi cho hand Claude native, song song theo vùng độc lập; brain review code (`P/scripts/session-start-policy.sh:16`).
- H 0.36.1: loader default → global → repo có provenance (`H/lib/shared_config.py:64`, `:119`, thêm default ở quanh `:137`); repo config `.claude/hybrid-hands.json`, worktree fallback checkout chính (`H/lib/hand_ext/config.py:87`); `ext_hand.native` auto|off (`H/lib/hand_ext/config.py:207`).
- Hook H: SessionStart lấy cwd từ payload/`CLAUDE_PROJECT_DIR`/PWD (`H/scripts/session-start-policy.sh:66`), chưa gọi loader; UserPromptSubmit in chuỗi tĩnh (`H/scripts/inject-policy.sh:3`).
- Mâu thuẫn cần hợp nhất trong biến thể: delegate (H bắt `pick` + guard v1 `H/scripts/session-start-policy.sh:34`), review (`:58`), trần song song (`:45`, `H/lib/hand_ext/parallel.py:87`).

## Phương án đã chốt
1. Key `parallel_subagents.enabled` (bool, default `false`) trong default của shared loader; kiểm kiểu bool (sai kiểu → coi false + cảnh báo stderr, không crash hook).
2. Chỉ nhận `true` khi provenance là `repo` (hoặc CLI nếu có); `true` từ global bị bỏ qua kèm cảnh báo — bật riêng từng repo, không bật hàng loạt.
3. Helper render luật dùng chung cho cả hai hook: `enabled=false` → output y nguyên hiện tại (không đổi byte); `enabled=true` → biến thể:
   - Brain chia việc thành gói độc lập khác file, giao `hybrid-hands:hand` native chạy song song tối đa `ext_hand.max_parallel` (1..4), cùng file/phụ thuộc tuần tự; vẫn chạy `hand-ext pick --json` để giữ guard v1 ≥5%/ngày — guard chặn thì không spawn native v1.
   - Brain review code hand mình giao (thay phân vai Sol/Opus trong repo bật chế độ).
   - Giữ nguyên luật dữ liệu, KHUÔN BRIEF, LUẬT TEST TỐI THIỂU, LUẬT TIẾP VIỆC, LUẬT NGỮ CẢNH BRAIN, luật commit.
   - Một dòng đầu nêu rõ "chế độ parallel_subagents bật bởi <đường dẫn config repo>".
4. Hook lỗi đọc config → fallback luật thường, không chặn phiên.
5. AGENTS.md repo `/Users/anhtp/app/claude-plugins/AGENTS.md`: thay câu cấm "Không bật parallel-subagents" (đoạn native Codex và đoạn "Không sửa ... hay bật parallel-subagents trong công việc usage panel") bằng luật mới: plugin `parallel-subagents` cũ giữ tắt mọi repo; thay bằng chế độ `parallel_subagents.enabled` của hybrid-hands, chỉ bật qua config repo khi người dùng chốt cho repo đó; brain/hand không tự bật. Giữ cấm sửa `.claude/hybrid-hands.json` trong việc usage panel. Thêm dòng vào mục cấu hình ưu tiên nhắc key mới. Sửa tối thiểu, giữ cấu trúc.
6. README H (mục cấu hình ~`hybrid-hands/README.md:184`): mô tả key, ví dụ JSON repo, cách migrate từ plugin cũ (tắt plugin cũ, bật key, mở phiên mới vì luật cũ đã nạp còn hiệu lực).
7. Tăng version minor H (0.37.0) + CHANGELOG `H/CHANGELOG.md`.

## PHẠM VI GHI
- `H/lib/shared_config.py`, helper mới trong `H/lib/` (vd `H/lib/policy_mode.py`), `H/scripts/session-start-policy.sh`, `H/scripts/inject-policy.sh`
- `hybrid-hands/tests/` (test mới hẹp + fixture giả)
- `hybrid-hands/README.md`, `H/CHANGELOG.md`, `H/.claude-plugin/plugin.json`, marketplace manifest nếu có version
- `/Users/anhtp/app/claude-plugins/AGENTS.md`

## KIỂM CHỨNG
- Mức test: tối thiểu. Ca test (≤3): (a) không có key → output hai hook giống hệt hiện tại; (b) repo config `true` → hook in biến thể, có dòng nguồn config; (c) global `true` không có repo → luật thường + cảnh báo.
- Test hẹp: chỉ file test mới/liên quan (`python3 -m pytest hybrid-hands/tests/<file> -q`), không full suite.
- Validate JSON manifest; `claude plugin validate` nếu có.
- Sau review xanh: commit nhánh, push, merge `main`, push `main`; cập nhật cài đặt hybrid-hands qua công cụ chính thức cho repo này và mọi repo đang dùng; kiểm version + đường dẫn nạp thực tế; báo cần reload phiên đang mở.

## TRẢ VỀ
Bàn giao `side-session` chuẩn, mở đầu khối Tóm tắt: đã làm gì, commit/merge SHA, version, lệnh test + kết quả thật, repo đã cập nhật plugin, phần chưa kiểm chứng. Ghi mã thoát nếu hand-ext lỗi (ghi chú: `hand-ext run --mode auto` từng trả `PARENT_REQUIRED` ở `H/lib/hand_ext/paseo_controller.py:269` khi không có parent Paseo; `--mode shell` chạy được).
