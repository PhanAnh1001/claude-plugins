## Tóm tắt
- Kết quả: xong bản sửa và review; chưa gộp/cập nhật runtime.
- `lib/hand_ext/limit_watch/cli.py`: diagnostic an toàn, chỉ rõ ID trùng, bảo vệ ACK; dry-run kiểm registry chỉ đọc.
- `tests/test_limit_watch.py`: 3 test hồi quy, đỏ trước sửa rồi xanh.
- Manifest + CHANGELOG + README + skill + command: version 0.61.1 và hướng dẫn dùng ID cũ.
- Test hẹp Sol: 12/12; thư mục tests lồng: 17/17.
- Full `hybrid-hands/tests`: 612 tests/316.882s, 1 ERROR nền disk_guard; tái hiện riêng trên main.
- `claude plugin validate`: Validation passed; catalog báo thiếu LICENSE và icon có sẵn, chưa xử lý ngoài scope.
- Không push, không commit main, không đổi watcher/target/launchd thật, không sửa repo 3d-scenic-wonders.
- Brain còn gộp nhánh, cập nhật plugin qua công cụ chính thức, reload rồi chạy lệnh bên dưới.

## Xác minh target thật (chỉ đọc)
`targets/brain-3d-main.json` có agent_id `43959106-d239-45f5-abe3-ecbce2437e29`, native_id `66282e0e-e4ca-4e16-87e0-b1bfdb416ffd`; journal state.json xác nhận target này `done`, reason `work_finished`. Khớp brain C. Không sửa các file này. Trường hợp side cũ ngày 13/11 chưa đối chiếu metadata thật; test mô phỏng cùng cơ chế registry, không kết luận nguyên nhân side lịch sử đã được chứng minh.

## Quyết định và lệnh brain C
Chọn từ chối ID khác, hướng dẫn dùng lại ID cũ; không phục hồi ngầm vì pending ACK phải được đối soát. Cùng ID đã done vẫn rearm như trước. Sau khi brain gộp, cập nhật plugin và reload, chạy từ CHÍNH brain C, cwd `/Users/anhtp/app/3d-scenic-wonders`:

```sh
hand-ext limit-watch add --self --id brain-3d-main --checkpoint docs/work-in-progress/handoffs/luong-c.md --dry-run
hand-ext limit-watch add --self --id brain-3d-main --checkpoint docs/work-in-progress/handoffs/luong-c.md
```
Nếu metadata/ACK đã đổi và lệnh bị chặn, giữ nguyên journal, đối soát trước; không đổi ID hay off/on. Phiên sửa này KHÔNG chạy hai lệnh đó.

## Kiểm chứng Sol và review
Đã đọc diff toàn bộ implementation/test và thay đổi tài liệu; safe ID được giới hạn regex, ValueError chỉ ánh xạ mã soạn sẵn hoặc fallback, không echo exception lạ. Kiểm tra trùng và pending diễn ra trước ghi target, dưới lock đối với add thật. Dry-run là snapshot không lock. Test mới mock build; không chứng minh daemon/account thật.

- `python3 -m unittest discover -s hybrid-hands/plugins/hybrid-hands/tests -p test_limit_watch.py -v`: 12 tests OK, 0.680s.
- `nice -n 19 taskpolicy -b python3 -m unittest discover -s hybrid-hands/plugins/hybrid-hands/tests -v`: 17 tests OK, 2.491s. Đây là thư mục lồng, không phải toàn bộ suite chính.
- `nice -n 19 taskpolicy -b python3 -m unittest discover -s hybrid-hands/tests -v`: chạy đúng một lần, 612 tests, 316.882s, ERROR duy nhất `test_cli_and_prepare_preflight`: `Config` thiếu `machine_state_dir`, tại gc.py:414.
- Đối chiếu main bằng riêng `python3 -m unittest discover -s hybrid-hands/tests -p test_disk_guard.py -k test_cli_and_prepare_preflight -v`: cùng ERROR và stack; không chạy lại full suite.
- `claude plugin validate hybrid-hands/plugins/hybrid-hands`: Validation passed; directory/catalog báo LICENSE_MISSING, ICON_MISSING và khuyến nghị install line. Không tự thêm license.
- `git diff --check`: sạch.
Log full suite: `/tmp/fix-limit-watch-plugin-suite.txt`; log suite lồng: `/tmp/fix-limit-watch-full-suite.txt` (tạm, có thể mất sau reboot).

## Điều phối và effort
Hand-ext lần đầu với `--effort medium` thoát 2: managed model/effort/sandbox phải khớp policy ghim. Không đổi config; lần sau dùng policy ghim codex gpt-6.1-sol low. Lượt đầu hand từ chối vì brief giới hạn đường dẫn khác cwd cách ly, chưa sửa file; đã sửa brief cho phép cwd do dispatcher tạo và giao lại cùng backend. Lượt kế tiếp hoàn tất, Sol review và managed review-approve exact key `8c618587-75f7-4e2e-9555-a6c0fb1cd189:61429990-6d51-4972-a0b5-9f7ae8f277bd:1`. Đây là giới hạn effort thực tế so với yêu cầu medium; không tuyên bố hand chạy medium. Không tự cập nhật runtime trước brain gộp vì scope brief giới hạn worktree và cấm thay đổi repo khác.

## Chi tiết executor: nguyên nhân, đỏ → xanh, Social listening
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

## Commit bàn giao
`988877d` trên nhánh `side/fix-limit-watch-valueerror`, worktree `/Users/anhtp/app/claude-plugins-wt/fix-limit-watch-valueerror`. Không push.
