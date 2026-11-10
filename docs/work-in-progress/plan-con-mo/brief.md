# Brief Sol `plan-con-mo`: đóng các mục còn mở của plan ba tầng

## Tóm tắt

- Mục tiêu: đóng 3 việc còn mở: mục 4.6 và 5.6 của `hybrid-hands/docs/2026-11-07-ba-tang-opus-sol-dsh-plan.md`, cùng race test PID mà bàn giao `docs/work-in-progress/handoffs/sol-hand-paseo.md` ghi là chưa xử lý.
- Lane: L1. Mỗi mục kết thúc bằng một trong ba trạng thái: tick, sửa xong, hoặc ghi rõ còn mở kèm lý do.
- Phiên Sol khác (`panel-gon`) đang chạy song song trên `hybrid-hands/paseo-hh-tree/`, `AGENTS.md`, `hybrid-hands/README.md`, `plugin.json`, `CHANGELOG.md`. Phiên này không sửa các file đó. Nếu có thay đổi cần ghi changelog thì viết dòng đề xuất vào bàn giao.

## Việc

1. **4.6, worktree khi Sol gọi hand-ext.** Từ 0.25.2 Sol chạy full access và `writable_roots` đã bị bỏ. Chạy một lượt hand-ext thật, nhỏ, chỉ đọc (gộp với việc 2) để xác nhận `git worktree add` không còn lỗi. Đạt thì tick 4.6, ghi bằng chứng là run dir và exit code. Không dùng `--backend claude-main`, vì backend này tốn gói Claude chính.
2. **5.6, kiểm thực tế.** Một lượt `hand-ext run --backend auto` (repo hiện chọn codex gpt-6.1-sol low), nội dung L0 chỉ đọc, ví dụ tóm tắt 3 dòng một file README. Sau lượt chạy, kiểm `hh-ps --once` và statusline: dòng hand phải có đủ model, effort, USD~, % quota (thiếu thì `?`, không bịa). Kiểm Paseo không còn hiện tài khoản `~/.codex`. Ghi mẫu output đã làm sạch vào `docs/work-in-progress/plan-con-mo/`. Đạt thì tick 5.6. Lệch thì xác định nguyên nhân (file:dòng) rồi sửa nếu nằm trong phạm vi ghi. Lỗi nằm trong `lib/hh_ps/` thì sửa được. Lỗi nằm ở panel Paseo thì chỉ ghi lại để chuyển cho `panel-gon`.
3. **Race test PID.** Tìm test PID chập chờn. Bàn giao `sol-hand-paseo.md` có nhắc, có thể liên quan cc-switch. Chạy riêng test đó nhiều lần để xác định nguyên nhân. Sửa test hoặc code nếu race có thật; nếu không tái hiện được thì ghi số lần chạy và kết luận.

## PHẠM VI GHI

- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/`, `lib/cc_switch/`, `lib/hh_ps/` (chỉ khi việc 2 cần sửa), test tương ứng trong `hybrid-hands/tests/`.
- Tick và ghi kết quả vào `hybrid-hands/docs/2026-11-07-ba-tang-opus-sol-dsh-plan.md`, chỉ ở các mục 4.6 và 5.6.
- Bàn giao: `docs/work-in-progress/handoffs/plan-con-mo.md` + `.done`. Log và bằng chứng: `docs/work-in-progress/plan-con-mo/`.

## KHÔNG ĐƯỢC ĐỤNG

`hybrid-hands/paseo-hh-tree/`, `hybrid-hands/hh-tree-pane/`, `statusline/`, `AGENTS.md`, `hybrid-hands/README.md`, `plugin.json`, `CHANGELOG.md`, và các file cấm theo `AGENTS.md` (`.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `installed_plugins.json`, `~/.paseo/config.json`). Không cập nhật bản cài, vì việc này do `panel-gon` làm sau full test. Giữ mọi thay đổi chưa commit. Không commit hay push. Không xoá hoặc di chuyển `output/llm/`.

## LUẬT BẮT BUỘC (chép nguyên văn vào brief hand ngoài)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## KIỂM CHỨNG

- Mức test: tối thiểu. Sửa race thì thêm đúng 1 test tái hiện, hoặc làm test sẵn có ổn định hơn.
- Chỉ chạy test hẹp: file test PID/cc-switch, và test hh_ps nếu có sửa. Không chạy full suite, vì `panel-gon` chạy full một lần ở cuối.
- Xong khi: 4.6 và 5.6 đã tick hoặc có ghi chú rõ còn mở; race có kết luận.

## TRẢ VỀ

Bàn giao mở bằng khối `## Tóm tắt`. Khối này gồm: trạng thái từng việc 1–3; lệnh đã chạy và kết quả thật (backend, token, % quota, USD~ của lượt hand, thiếu ghi `?`); file đã đổi; dòng changelog đề xuất; phần chưa kiểm chứng.
