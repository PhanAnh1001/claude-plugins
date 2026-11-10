# Giao việc phiên Sol `demo-subagent`: chạy một hand managed để người dùng xem trên Paseo

## Tóm tắt

- **Mục đích:** người dùng muốn nhìn trực tiếp trên app Paseo một subagent (hand managed) do phiên Sol phụ tạo: workspace riêng của hand, tab Subagents ở phiên cha (bạn), trạng thái chạy → xong → tự archive (0.36.0).
- **Việc:** giao **một** hand managed task disposable, chạy khoảng 2 phút để người dùng kịp xem; chờ xong; ghi bàn giao.
- **Kết thúc:** ghi `docs/work-in-progress/handoffs/demo-subagent.md` (tóm tắt: key, child agent id, workspace id, backend/model/effort, kết quả, có tự archive không) rồi tạo file rỗng `docs/work-in-progress/handoffs/demo-subagent.done`.

## 1. Các bước

1. `H=/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin`; `$H/hand-ext pick --json`.
2. Viết brief hand tự chứa ở `/Users/anhtp/app/claude-plugins-wt/demo-subagent-brief.md` (ngoài repo, không commit): executor tạo file `docs/work-in-progress/demo-subagent-scratch.md` một dòng `demo ok`, rồi chạy `sleep 120` đúng một lần, rồi kết thúc. Không đọc/sửa file nào khác. Chép nguyên văn luật dữ liệu ở mục 2; cấm hand gọi hand-ext/side-session/subagent, cấm `ps`/`pgrep`.
3. `$H/hand-ext run --backend auto --mode paseo-required --brief <brief> --cwd /Users/anhtp/app/claude-plugins --no-apply --label demo-subagent --timeout-min 6` (timeout lệnh hữu hạn ~8 phút).
4. Ngay khi child được tạo, ghi lại child agent id + workspace id (`$H/hand-ext managed ls --cwd /Users/anhtp/app/claude-plugins`, `paseo inspect`), và `$H/hh-ps --once` (đúng một dòng hand dưới bạn).
5. Sau khi xong: kiểm report/patch (chỉ một file scratch, không áp vào repo vì `--no-apply`), kiểm child + workspace đã tự archive; **không** stop, **không** followup.

## 2. Luật dữ liệu chung (chép nguyên văn vào brief hand)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## 3. Giới hạn

- PHẠM VI GHI: brief demo ngoài repo; execution/agent demo do bạn tạo; `docs/work-in-progress/handoffs/demo-subagent.md|.done`. Còn lại CHỈ ĐỌC. Không commit/push.
- Không sửa config/settings/credential; không restart/reload daemon; không stop/archive agent khác. Chỉ subscription. Mọi chờ có timeout hữu hạn.
