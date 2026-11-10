## Tạm dừng
- Trạng thái: tạm dừng theo chỉ thị mới; chưa nghiệm thu S2. Không giao thêm hand, không chạy full suite.
- Commit WIP: `2c3f295` trên `side/cfg-goi-s2`, message `wip(S2): add read-only security doctor pending final review`; không push/merge.
- `lib/hand_ext/cli.py`: thêm cờ và dispatch `doctor --security [--json]` trước loader/doctor legacy.
- `lib/hand_ext/security_doctor.py`: auditor chỉ đọc Claude/Codex/Paseo/dsh, output allowlist và snippet cố định; chặn symlink/file bí mật.
- `tests/test_hand_ext_security.py`: 3 test tổng hợp bằng HOME giả, canary, parse lỗi, readonly, provider/listen/relay và CLI.
- Hand đầu: security suite Python 3.11 **3/3 pass**; Sol review phát hiện lỗi và giao đúng backend sửa một lượt trước khi có lệnh dừng.
- Hand sửa: security suite **3/3 pass mỗi Python 3.9 và 3.11**; CLI hẹp **3/3 pass mỗi phiên bản**; đây là kết quả hand báo, Sol chưa chạy lại.
- `git diff --check`: pass trước lệnh dừng; hand sửa cũng báo pass. Full suite: **0 lần**, hand cuối chưa được dispatch.
- Bandit/Semgrep/pip-audit không có; `npm audit --ignore-scripts --json` exit 1, **ENOLOCK**; chưa kết luận audit-clean.
- Paseo quan sát listener chỉ `127.0.0.1:49191`, `127.0.0.1:6767`; chưa chạy auditor mới với HOME thật, không có staging.
- Còn lại: Sol review lại corrective patch, kiểm chứng runtime phù hợp và full suite khi được cho tiếp tục. Không bump/cài runtime.
- `.s2-work/` không commit: đã xoá 3 brief do Sol tạo; giữ 2 JSON bằng chứng metadata thực, nên thư mục không chỉ chứa dữ liệu giả.

## Phạm vi và trạng thái code

Các đường dẫn file đổi ở trên tính từ `hybrid-hands/plugins/hybrid-hands/`, riêng test tính từ `hybrid-hands/`. Commit gồm đúng ba file, 472 dòng thêm. Không sửa `lib/side_session/`, `lib/cc_switch/`, shared loader, AGENTS.md, README, CHANGELOG, version hoặc cấu hình người dùng. Không push/merge hay cập nhật cài đặt plugin.

Đã đọc AGENTS.md trong worktree, spec mục 5.4, plan S2, ma trận S0 và skill ext-hand trước dispatch. Quyết định triển khai và ba ca nghiệm thu đã ghi trong brief hand trước code. Cả hai dispatch đều chạy `hand-ext pick --json` trước, chọn `codex`, `gpt-6.1-sol`, effort `low`; chạy bằng `hand-ext run --backend auto`, isolation worktree. Không native spawn, không side-session mới. Không có lỗi hand-ext/exit 7/8 và Sol không tự viết code/test.

## Review trước tạm dừng

Sol đã review bản đầu và phát hiện: CORS Paseo sai vị trí key, các dòng audit chưa phân biệt account/home, lỗi parse thiếu lớp lỗi/đường dẫn an toàn, Python 3.9 thiếu tomllib, discovery cấu hình worktree chưa theo chuẩn. Đã giao corrective pass đúng backend một lần trước lệnh tạm dừng.

Hand sửa báo đã sửa `daemon.cors.allowedOrigins`, snippet provider, TOML fallback, target an toàn và lớp lỗi; bổ sung deny credential, chỉ trích cấu hình cần dùng và discovery root/main-worktree. Hand đang chạy lúc nhận lệnh tạm dừng được chờ tới khi tự kết thúc, không kill. Patch đã áp về worktree. **Sol chưa review lại corrective patch**, vì dừng công việc bảo mật theo yêu cầu. WIP chưa đủ điều kiện release hoặc nghiệm thu.

## Kiểm chứng đã chạy thực tế

Hand code đầu:

- `PYTHONDONTWRITEBYTECODE=1 python3.11 -B -m unittest discover -s hybrid-hands/tests -p test_hand_ext_security.py`: 3 tests OK.
- `git diff --check`: pass.

Hand corrective:

- `python3 -B -m unittest discover -s hybrid-hands/tests -p test_hand_ext_security.py`: 3 tests OK.
- `python3.11 -B -m unittest discover -s hybrid-hands/tests -p test_hand_ext_security.py`: 3 tests OK.
- `PYTHONPATH=hybrid-hands/tests python3 -B -m unittest test_hand_ext_core.BrowserCliTest test_hand_ext_dsh.DoctorTest.test_doctor_command_does_not_fail_without_browser`: 3 tests OK.
- Cùng lệnh CLI hẹp với `python3.11`: 3 tests OK.
- `git diff --check` và kiểm whitespace file mới: hand báo pass.

Test dùng HOME/fixture giả, subprocess CLI text/JSON; hand báo canary không lộ và kiểm lỗi parse/type/UTF-8/oversize, forbidden reads, symlink, readonly, mapping/provider/listen/relay. Sol chưa chạy lại các test này. Python hệ thống là 3.9.6; Python 3.11 có sẵn.

Sol đã chạy discovery công cụ: không có `bandit`, `semgrep`, `pip-audit` trong PATH, không cài thêm. `npm audit --ignore-scripts --json` tại `hybrid-hands/paseo-hh-tree` exit 1 với ENOLOCK, không có kết quả quét dependency hợp lệ và không tạo lockfile.

Sol chạy `paseo daemon status --json` exit 0, chỉ trích whitelist PID; daemon pid 59306, worker pid 68800. `lsof -nP -a -p <pid> -iTCP -sTCP:LISTEN` quan sát worker nghe `127.0.0.1:49191` và `127.0.0.1:6767`. Đây là kiểm listener tại thời điểm quan sát, không chứng minh relay tắt hay sandbox enforcement. Không có staging; chưa chạy doctor --security với cấu hình người dùng thật.

## Chưa thực hiện / để tiếp tục khi được phép

- Review lại corrective patch trước khi coi S2 hoàn tất; kiểm schema/snippet và contract không lộ dữ liệu.
- Full suite Python và TypeScript chưa chạy lần nào cho S2. Có soạn brief nhưng chưa dispatch; brief đã xoá sau lệnh dừng.
- Chưa SAST vì thiếu công cụ; dependency audit chưa có kết quả. Chưa runtime audit HOME thật.
- Không quyết mục 7.2; không thay policy, không sửa settings/credential, không cài plugin/runtime.

## Artifact và usage hand

Report hand đầu: [cfg-s2-code report](/Users/anhtp/app/claude-plugins-wt/cfg-goi-s2/output/llm/hand-ext/20261109-170215-132340-cfg-s2-code-codex/report.md).

Report hand sửa: [cfg-s2-fix report](/Users/anhtp/app/claude-plugins-wt/cfg-goi-s2/output/llm/hand-ext/20261109-170805-187566-cfg-s2-fix-codex/report.md).

Không xoá/di chuyển `output/llm/`. Hai tiến trình hand Sol tạo đã kết thúc exit 0, không còn hand do Sol tạo đang chạy. Hand cuối/full suite không được tạo.

Token hand đầu: input 780528, cached_input 694912, output 8394; hand sửa: input 461170, cached_input 424320, output 5962. Runtime report observed used_percent 12.0, reset 2026-11-16T06:19:22+00:00; đây không phải phần quota quy riêng cho hai hand. USD~ không thu thập: `?`.

Scratch giữ hai file không commit: `.s2-work/dependency-audit.json` và `.s2-work/daemon-observation.json`. Chúng chứa mã lỗi audit/PID/listener thực đã whitelist, không có giá trị secret; giữ vì điều kiện xoá thư mục chỉ chứa dữ liệu giả không áp dụng. Ba brief do Sol tạo đã xoá.
