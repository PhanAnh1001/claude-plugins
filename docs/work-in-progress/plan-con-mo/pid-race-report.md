# PID race: cc-switch self worker

Race được xác nhận: test integration trước sửa pass 26/30, fail 4/30 (lượt 3, 7, 11, 25). Các fail đều worker exit 4 sau khi đã log TUI thoát, rồi run_paseo báo cùng PID vẫn mở. Đây là log fixture giả do test tạo, không phải dữ liệu phiên thật.

## Nguyên nhân và sửa

- `hybrid-hands/plugins/hybrid-hands/lib/cc_switch/proc.py:38`: `pid_alive` ban đầu có thể thấy zombie còn tồn tại. Test cha reap sleeper tại `hybrid-hands/tests/test_cc_switch_self.py:234`, trước lúc `ps` chạy tại proc.py:40. `_ps_value` trả None khi PID đã biến mất, nhưng code cũ trả True vô điều kiện. `sessions.py:40` vì vậy đưa PID đã chết vào live sessions; `paseo_cmd.py:138` từ chối reload.
- `self_cmd.py:176` chấp nhận zombie là đã thoát; kiểm tra lại sau đó trong run_paseo tạo cửa sổ quan sát khác. Không sửa luồng này: lỗi cụ thể là fallback True khi PID đã biến mất.
- Sửa tối thiểu `proc.py:41–44`: khi ps không có trạng thái, gọi lại `pid_alive`. Giữ fallback True nếu ps không dùng được nhưng PID thực sự vẫn sống.
- Thêm đúng một test deterministic `test_cc_switch_self.py:208`, hai subtest cho PID biến mất / PID vẫn sống. Mock kill probe True rồi False chứng minh lỗi; trường hợp True rồi True giữ fallback. Test fail trước sửa, pass sau sửa. Không đổi timing của integration test cũ.

## Phạm vi đổi

Chỉ `hybrid-hands/plugins/hybrid-hands/lib/cc_switch/proc.py`, `hybrid-hands/tests/test_cc_switch_self.py` và hai artifact báo cáo `pid-race-report.md`, `pid-race-tests.txt`. Không sửa baseline, không commit/push/cập nhật bản cài.

## Kiểm chứng

Chi tiết output và từng lượt ở `pid-race-tests.txt`. Các lệnh unittest dùng cwd `hybrid-hands/tests`:

1. `python3 -m unittest test_cc_switch_self.CcSwitchSelfTest.test_worker_sigterms_tui_then_reloads_paseo`: trước sửa 30 lượt, 26 pass / 4 fail.
2. `python3 -m unittest test_cc_switch_self.CcSwitchSelfTest.test_process_alive_rechecks_pid_when_ps_has_no_state`: trước sửa exit 1 với hai subtest fail; sau sửa exit 0, 1 test pass.
3. Sau sửa integration 30 lượt: 30 pass / 0 fail. Sau đó `python3 -m unittest test_cc_switch_self test_cc_switch test_cc_switch_term_self`: exit 0, 58 tests pass trong 24.872s.

`git diff --check -- hybrid-hands/plugins/hybrid-hands/lib/cc_switch/proc.py hybrid-hands/tests/test_cc_switch_self.py`: exit 0.

Không chạy full suite. Chỉ dùng ba loại kiểm tra: regression deterministic, integration PID lặp, ba file liên quan.

## Giới hạn

Kiểm chứng tại macOS của workspace, không kiểm Linux hoặc PID reuse. Một lần recheck không tạo snapshot process-table nguyên tử; thay đổi chỉ giải quyết trường hợp PID biến mất trước ps. Khi ps không khả dụng, zombie vẫn giữ fallback của kill(pid, 0) như trước. Không đọc auth, credential, transcript/log thật, runtime usage. Không tạo tiến trình nền ngoài subprocess test; test runner đã kết thúc exit 0 trước bàn giao; test tự terminate/reap sleeper và worker.

Đề xuất changelog: “Fix cc-switch --self falsely reporting a reaped TUI PID as live when it exits between the liveness probe and ps.”

Token/quota runtime: ? / ?.
