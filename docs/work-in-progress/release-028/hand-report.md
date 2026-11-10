# Hand report: release 0.28 fixes

Đã sửa đúng ba file nguồn so với `baseline/`, giữ các thay đổi có sẵn trong baseline:

- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/dsh.py`: giữ API `USER_AGENT`, đọc version từ manifest canonical; chỉ nhận chuỗi version an toàn cho header và dùng `unknown` nếu file thiếu/hỏng hoặc giá trị không hợp lệ. Không còn literal `0.27.0` trong file.
- `hybrid-hands/tests/test_hh_ps_codex.py`: chỉ đổi regex assertion hiện hữu thành `reset (?:\d\d/\d\d )?\d\d:\d\d`, nhận cả `HH:MM` và `dd/mm HH:MM`. Không đổi renderer, fixture hay thêm test.
- `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md`: thêm một bullet trong 0.28.0 về nguồn version User-Agent.

Lệnh duy nhất chạy test, từ `/Users/anhtp/app/claude-plugins`:

```sh
PYTHONPATH=hybrid-hands/tests python3 -m unittest test_hand_ext_dsh.VersionTest.test_user_agent_matches_plugin_version test_hh_ps_codex.CodexPanelTest.test_codex_usd_pct_samples_and_gpt_account_limits -q
```

Kết quả thật: 2 test đạt, exit code 0; unittest báo 0.042 giây, thời gian tiến trình 0.190077 giây. Output, thời điểm UTC và exit code ở `hand-two-tests.log` và `hand-two-tests.json`.

Đối chiếu ba file baseline xác nhận chỉ ba file nguồn được giao khác baseline; các file báo cáo/log nằm trong phạm vi ghi riêng. Không chạy full suite, cài đặt/reload CLI hoặc restart daemon; không commit/push. Không kiểm chứng runtime thật hoặc đường lỗi manifest bằng test mới. Không thay đổi manifest, renderer hay panel.

Token/quota: ?. Native không có meta/report/token ledger hand-ext. Không có tiến trình nền được tạo. Chờ Sol review; không tạo release-028.done hoặc bàn giao tổng.
