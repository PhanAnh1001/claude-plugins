# Bàn giao fix-limit-watch-valueerror — 2026-11-15

## Kết quả và nguyên nhân

Hoàn tất phần executor, phiên bản plugin 0.61.1. Không commit/push, cài runtime, sửa config/launchd hay state watcher thật.

`git log -5 --oneline -- hybrid-hands/plugins/hybrid-hands/lib/hand_ext/limit_watch/cli.py` và `git blame -L 107,116 -- hybrid-hands/plugins/hybrid-hands/lib/hand_ext/limit_watch/cli.py` xác định commit `ce27635b` ngày 2026-11-13 giới thiệu `raise ValueError('duplicate_agent_registration')`. Handler chỉ xuất message cho RegistrationError, nên lỗi duplicate/pending trở thành JSON chỉ có code ValueError. Dry-run cũng return trước check_registration.

## Thay đổi

- `hybrid-hands/plugins/hybrid-hands/lib/hand_ext/limit_watch/cli.py:102`: lỗi xung đột soạn sẵn, ID chỉ cho phép chữ/số/gạch; ID registry không an toàn không được echo. Từ chối ID khác cho cùng endpoint/agent kể cả done. Pending được ưu tiên và luôn yêu cầu đối soát ACK thủ công; cùng ID done vẫn rearm. ValueError thường chỉ được ánh xạ qua mã allowlist chính xác; lỗi khác có hướng xử lý chung, không echo exception. Dry-run đọc registry không tạo lock/thư mục, add thật kiểm tra lại dưới lock.
- `hybrid-hands/plugins/hybrid-hands/tests/test_limit_watch.py:86`: helper và 3 test mới, subTests cho self/side duplicate done, pending cùng/khác ID, dry-run, rearm và ValueError known/unknown với sentinel giả. Store trong TemporaryDirectory, build/launchd install được mock, không target thật.
- `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json:3`: 0.61.0 → 0.61.1. Marketplace tham chiếu source, không có trường version cần đổi.
- `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md:5`, `README.md:29` và `README.md:135`, `skills/limit-watch/SKILL.md:19`, `commands/limit-watch.md:22`: mô tả phục hồi bằng --id cũ và giới hạn ACK/dry-run.

## Kiểm chứng đỏ trước sửa

Sau khi thêm test, trước khi sửa implementation, chạy tại worktree được giao:

```sh
python3 -m unittest discover -s hybrid-hands/plugins/hybrid-hands/tests -p test_limit_watch.py -k test_add_ -v
```

Output chính xác (trích đoạn ngắn):

```text
AssertionError: None is not true

----------------------------------------------------------------------
Ran 6 tests in 0.040s

FAILED (failures=11)
```

Các subcase duplicate/pending thật thiếu message, dry-run trả 0 thay vì 1; known/unknown ValueError đều thiếu message. Đây là assertion failures, không phải import/runtime errors. Output đầy đủ được giữ tạm tại `/private/tmp/limit-watch-red.txt` trong phiên này.

## Kiểm chứng xanh

```sh
python3 -m unittest discover -s hybrid-hands/plugins/hybrid-hands/tests -p test_limit_watch.py -v
```

Lần cuối sau chỉnh sửa:

```text
----------------------------------------------------------------------
Ran 12 tests in 0.419s

OK
```

Thêm đúng 3 test methods, 46 dòng test/helper trên 93 dòng implementation thêm (git diff --numstat), đạt ngân sách ≤ 1/2. JSON plugin và marketplace parse thành công; các link Markdown local trong README/skill/command tồn tại. `git diff --check` sạch. Không chạy full suite; không thực thi on/off/done thật. Đây là sửa diagnostic/lifecycle validation nội bộ, không mở tính năng chi tiêu hay bảo mật chống tấn công bên ngoài.

## Social listening

Luật áp dụng nguyên văn: "Bạn quản lý source code repo này, khi đưa ra một giải pháp hoặc workflow cần tham khảo thêm nguồn social listening về lĩnh vực, quy trình đó."

- [flask-apscheduler issue #54](https://github.com/viniciuschiele/flask-apscheduler/issues/54), mở 2017-09-08; truy cập 2026-11-15. Thảo luận lỗi ID trùng trong persistent store nhắc rằng đổi ID hoặc xử lý database thủ công không phải cách phục hồi đáng tin cậy.
- [APScheduler 3.x user guide — Adding jobs](https://apscheduler.readthedocs.io/en/3.x/userguide.html#adding-jobs), ngày xuất bản không rõ; truy cập 2026-11-15. Tài liệu yêu cầu ID tường minh và replacement khi khởi tạo persistent jobs. Ở limit-watch chọn yêu cầu dùng đúng ID cũ, không thay thế ngầm, để giữ journal ACK. Đây là lựa chọn thiết kế theo contract nội bộ; các nguồn không bảo đảm an toàn ACK.

## Giới hạn / việc brain còn làm

Dry-run là snapshot không lock: registry có thể đổi trước add thật; add thật luôn kiểm tra lại. Không thay lifecycle, generation, persistent hoặc dispatch semantics. Test duplicate mới dùng registration.build giả; test build self/side hiện hữu vẫn xanh. Không kiểm thử daemon/launchd hay account thật theo brief. Giữ nguyên brief chưa tracked của brain. Brain review, chạy full suite đúng một lần theo kế hoạch riêng, rồi commit/release/cập nhật runtime và xác minh phiên bản nạp qua công cụ chính thức; executor không làm các bước đó.
