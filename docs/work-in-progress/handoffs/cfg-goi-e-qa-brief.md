# Gói E — hand QA riêng, kiểm chứng cuối chỉ đọc
Bạn là hand executor tester, không phải Sol. Không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác/review hand khác. Không commit/push/merge.
PHẠM VI GHI: không sửa tracked file. Chỉ artifacts test tạm trong HOME tạm do test tạo và report của hand-ext. Không sửa code/test/config/settings/credential/AGENTS/README/CHANGELOG/version. Đọc AGENTS.md áp dụng.

Bối cảnh: Gói E cc-switch giữ CLAUDE_CONFIG_DIR khi chuyển Claude sang Paseo. Hand code trước chưa sửa file vì API import/resume Paseo không nhận env; Sol đã đối chiếu source. Đây là hand tester độc lập, không review code hand khác.

Thực hiện đúng hai phần, KHÔNG chạy phiên/daemon/model thật:
1. Đúng MỘT ca diagnostic bằng fixture giả hiện có CcFixture (tests/fixtures/cc_switch/cc_fixture.py): di chuyển cây account fixture vào HOME tạm/.claude-hand, cập nhật tham chiếu fx.claude/fx.sessions/fx.projects tương ứng hoặc tạo fixture riêng nhỏ. Set CLAUDE_CONFIG_DIR chính xác thư mục đó, HYBRID_HANDS_CONFIG tới file absent dưới HOME tạm, HOME tạm. Chạy CLI cc-switch paseo --session SID_IMPORT --dry-run; sau đó cùng ca dùng fake paseo import (PATH fixture) để ghi argv. Xác nhận dry-run không gọi fake paseo; kiểm tra lời gọi thực tế có session/cwd nhưng KHÔNG có env account trong payload/lệnh. Báo acceptance giữ account hiện đang FAIL; không coi env kế thừa của subprocess là request agent. Không in giá trị giả SECRET_* trong fixture output. Dùng python heredoc để không tạo test tracked mới; báo lệnh thực tế và kết quả. Không kill/chuyển TUI thật. CcFixture.close phải được gọi finally.
2. Chạy FULL PYTHON SUITE đúng MỘT LẦN cuối: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_*.py'`. Bọc subprocess với HOME và HYBRID_HANDS_CONFIG tạm (không tạo config global thật), timeout hữu hạn đủ 10 phút. Ghi tổng test/pass/fail/error/skip và exit code thật. Không chạy lại dù lỗi, không sửa lỗi, không cài dependency, không full suite khác. Phân biệt lỗi baseline và acceptance còn thiếu, không claim đã fix. Nếu suite lỗi ghi tên test/trace nguyên nhân an toàn rút gọn, không in credential. Cleanup tiến trình fixture do mình tạo. Báo tracked git diff/status cuối. Không đọc log/transcript thật.

TRẢ VỀ: Lệnh/kết quả thật của một ca diagnostic và full suite đúng một lần; file đổi phải 0; phần chưa kiểm chứng. Không viết code.

Luật dữ liệu nguyên văn:
Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.
