MỤC TIÊU: `side-session ls` vẫn reconcile các phiên khác khi một phiên done có agent đã bị xoá khỏi Paseo hoặc workspace lệch; chỉ bỏ qua đúng phiên đó.

NGỮ CẢNH:
- `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo.py`, hàm `agent_archive_states(candidates)` (khoảng dòng 191-224). Vòng cuối hiện `raise PaseoError("AGENT_NOT_FOUND")` khi agent của một candidate không có trong snapshot, và `raise PaseoError("WORKSPACE_ID_MISMATCH")` khi workspace lệch. Lỗi này làm `ls` (`lib/side_session/actions.py`, hàm `ls`, khoảng dòng 456-490) bỏ cả vòng reconcile.
- Thực tế ở repo khác: 3 phiên done có agent đã hard-delete, nên mọi lần `ls` đều báo `workspace reconcile lỗi (AGENT_NOT_FOUND)` và không phiên nào được revive.
- `ls` chỉ reconcile phiên có `st.paseo_agent_id in archive_states`, nên chỉ cần hàm trả về map lọc.

VIỆC CẦN LÀM:
1. Trong `agent_archive_states`: giữ nguyên kiểm tra target và kiểm tra shape/ID trùng của toàn snapshot (các lỗi đó vẫn raise). Bỏ hai `raise` theo từng candidate; thay bằng: candidate có agent không có trong snapshot, thiếu `paseo_workspace_id`, hoặc `workspaceId` lệch thì không đưa vào kết quả. Trả về dict chỉ gồm agentId của các candidate hợp lệ → archived (bool). Cập nhật docstring một dòng cho đúng.
2. Test trong `hybrid-hands/tests/test_side_session_paseo.py` (dùng mock/fixture như các test `agent_archive_states`/`test_ls_batches_done_agent_archive_states` hiện có, quanh dòng 600-700): một ca có 3 candidate gồm agent hợp lệ đã unarchive, agent thiếu trong snapshot, agent có workspace lệch → kết quả chỉ có agent hợp lệ, không raise; ls revive đúng phiên hợp lệ và không in warning. Sửa test cũ nào đang kỳ vọng raise AGENT_NOT_FOUND/WORKSPACE_ID_MISMATCH từ hàm này cho đúng hành vi mới.
3. Thêm một dòng vào mục 0.33.1 trong `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md`: agent đã xoá hoặc workspace lệch chỉ bỏ qua phiên đó.

PHẠM VI GHI: `hybrid-hands/plugins/hybrid-hands/lib/side_session/paseo.py`, `hybrid-hands/tests/test_side_session_paseo.py`, `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md`.

KHÔNG ĐƯỢC ĐỤNG: mọi file khác; không đổi version; không chạy lệnh `paseo` thật hay `side-session` thật; không commit/push; không sửa `.claude/`, config, credential/settings; không xoá/di chuyển `output/llm/`. Không gọi hand-ext, không mở side-session, không recursion hay giao tiếp phiên khác.

LUẬT BẮT BUỘC:
Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

KIỂM CHỨNG: test hẹp `python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session_paseo.py'`; cuối chạy đúng một lần `python3 -m unittest discover -s hybrid-hands/tests -p 'test_side_session*.py'`. Mức test: tối thiểu, một ca mới như mục 2. Xong khi cả hai lệnh xanh.

TRẢ VỀ: danh sách file đổi, diff tóm tắt, kết quả thật của hai lệnh test.
