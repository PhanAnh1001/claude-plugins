LUẬT BẮT BUỘC: <chép NGUYÊN VĂN luật repo liên quan - hand không nhận hook, AGENTS.md không tự nạp vào ngữ cảnh hand>
KHÔNG ĐƯỢC ĐỤNG: <file/thư mục/lệnh cấm>
TRẢ VỀ: <định dạng báo cáo>
MỤC TIÊU: <một câu: kết quả cần đạt>
NGỮ CẢNH: <điều brain đã biết, kèm file:line; giả định đã chốt>
PHẠM VI GHI: <danh sách file/thư mục được sửa/tạo> | CHỈ ĐỌC
UỶ QUYỀN GIT: KHÔNG (mặc định; bỏ mục này cũng là KHÔNG). Chỉ trong gói Git riêng: repository=<đường dẫn>; hành động=<commit và/hoặc push>; branch=<tên>; remote=<bắt buộc nếu push>; file=<thuộc PHẠM VI GHI>. Không vượt chỉ dẫn ưu tiên cao hơn/runtime.
KIỂM CHỨNG: <lệnh test hẹp (-k/file) dùng trong lúc làm; lệnh test đầy đủ chạy ĐÚNG MỘT LẦN ở cuối; mức test: tối thiểu (chỉ case quan trọng) | kỹ (ảnh hưởng doanh thu); ca test: liệt kê ≤3 ca quan trọng nhất (tối thiểu); tiêu chí coi là xong>

Test hẹp (một file, `-k`, vài test) chạy bình thường ngay, không cần đo CPU; nếu có dấu hiệu nặng thì áp dụng hạ ưu tiên dưới đây.
Test nặng = có dấu hiệu nặng HOẶC CPU toàn máy ≥90%; dấu hiệu: full suite (pytest/jest/go test… không giới hạn file hay `-k`, `make test`, `npm test` cả bộ), song song (`-n auto`/`-n N`/xdist, `--workers`, `-j`), e2e, build kèm test cả bộ.
Không chặn vì nặng: chạy `nice -n 19 <lệnh>` (nhường CPU cho việc khác, máy rảnh vẫn dùng nhân hiệu năng). Không thêm `taskpolicy -b`: trên Apple Silicon nó chỉ cho chạy nhân tiết kiệm điện, test chậm khoảng 3 lần (đo ở ai-luxian AILUX-292: 241 s → 724 s); chỉ dùng khi brief ghi rõ việc không gấp. Không tự bật song song nếu brief không yêu cầu; tăng timeout tương ứng.
Chỉ trước test dự kiến >30s không có dấu hiệu nặng và không phải test hẹp, đo CPU bằng `ps -A -o %cpu= | awk -v n="$(sysctl -n hw.ncpu)" '{s+=$1} END {printf "%.0f\n", s/n}'`; kết quả ≥90 thì chạy hạ ưu tiên.
