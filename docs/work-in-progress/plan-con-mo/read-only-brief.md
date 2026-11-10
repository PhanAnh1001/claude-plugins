## MỤC TIÊU
L0 chỉ đọc: đọc hybrid-hands/README.md và tóm tắt chính xác 3 dòng bằng tiếng Việt.
## NGỮ CẢNH
Đây là probe thật của Sol plan-con-mo để kiểm worktree và usage; bạn là hand executor.
## PHẠM VI GHI
CHỈ ĐỌC, không tạo/sửa file nào, không chạy test. Chỉ đọc hybrid-hands/README.md và luật AGENTS.md áp dụng.
## KHÔNG ĐƯỢC ĐỤNG
Không đọc file khác ngoài hai file trên. Không sửa config, settings, credential, output/llm hay bản cài. Không commit/push. Không API trả phí.
## LUẬT BẮT BUỘC
Bạn là executor: làm trực tiếp, không gọi hand-ext/side-session, không tạo subagent, không recursion, không giao tiếp phiên khác, không review hand khác. Dùng cwd hoặc đường dẫn tuyệt đối; không cd ... &&. Không đọc transcript/log thật.
Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.
## KIỂM CHỨNG
Chỉ đọc README; không test và không ghi file.
## TRẢ VỀ
Chính xác 3 dòng tóm tắt README, không bổ sung dữ liệu usage tự đoán.
