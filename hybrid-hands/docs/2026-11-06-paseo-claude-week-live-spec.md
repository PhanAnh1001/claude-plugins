# Spec: dòng Claude tuần trên cây Paseo cập nhật khi mọi phiên chạy qua Paseo

## Tóm tắt

- **Vấn đề:** cây/panel Paseo (`hh-ps`) lấy % hạn mức tuần Claude từ `~/.claude/.statusline-cache.json`. File này chỉ được ghi khi statusline render trong một phiên Claude Code tương tác. Phiên do Paseo chạy (`claude --output-format stream-json --input-format stream-json`, tiến trình cha `Paseo Daemon`) không render statusline. Kết quả là panel đứng ở số cũ.
  - Đo ngày 06/11/2026: cache dừng lúc 17:12 ở mức 10%, trong khi thực tế 22:12 đã là 15%.
  - Panel hiện "máy này 11,1%, máy khác 0%, tổng 10,9%, ước tính".
- **Quyết định:** sửa theo 2 bước.
  1. **Sửa ngay (giai đoạn 1):** khi cache cũ, panel ngoại suy % tuần = % trong cache + USD máy này phát sinh sau thời điểm cache / USD-per-1%. Số này đánh dấu ước tính (`~`). Đã có số ghim 13,74 USD/1% (statusline 0.19.0), nên ngoại suy dùng được ngay. Không cần nguồn mới.
  2. **Nguồn sống (giai đoạn 2):** tìm nguồn % thật không phụ thuộc statusline render. Ưu tiên sự kiện rate limit trong luồng stream-json mà Paseo daemon nhận được. Chỉ dùng endpoint usage OAuth khi người dùng duyệt (xem 2.3).
- **Số chính:**
  - USD/1% tuần đang ghim: 13,74 (`~/.claude/statusline-usd-per-pct.txt`, đo 04/11: Δ3%, 41,23 USD).
  - Ngưỡng cache cũ của panel: 30 phút (`hh_ps/week.py:344`).
- **Người đọc cần làm:** phiên brain mới làm theo plan `2026-11-06-paseo-claude-week-live-plan.md`, bắt đầu từ giai đoạn 1.

## 1. Giai đoạn 1: ngoại suy khi cache cũ

### 1.1 Hiện trạng

- `hh_ps/week.py` đọc % tuần và thời điểm từ `.statusline-cache.json`, và đọc `usd_per_pct`, `local`, `other` từ `.statusline-week-split.json` (`week.py:42`, `:356`). Cache cũ hơn 30 phút thì `estimated=True` (`week.py:344`), nhưng số % vẫn giữ nguyên số cũ.
- Statusline ghi cache ở `statusline.sh:228-239` (gọi tại `:317`) và ghi mẫu % ở `week-split.sh:60-72` (mỗi khi % đổi hoặc mỗi 300 giây). Cả hai chỉ chạy khi có render.
- `statusline/.../usage_ledger.py` đã có `window_messages(homes, since, until)` tính USD theo khung giờ từ transcript (thêm ở 0.19.0).

### 1.2 Hành vi mới

- Cache cũ hơn ngưỡng và có `usd_per_pct` thì tính:
  - `pct_now ≈ pct_cache + USD_máy_này(cache_ts → now) / usd_per_pct`.
  - Kẹp kết quả trong [pct_cache, 100].
- Phần "máy này" của dòng tuần tăng cùng lượng đó. Phần "máy khác" giữ nguyên, vì không biết máy khác dùng bao nhiêu sau cache_ts.
- Dòng tuần vẫn `estimated=True` và hiện `~`. Nguồn ghi rõ, ví dụ `source="statusline_cache+extrapolated"`.
- Không có `usd_per_pct`, hoặc reset tuần đã qua so với cache: giữ hành vi cũ.

### 1.3 Giới hạn đã biết

- Số ngoại suy thấp hơn thực tế nếu máy khác dùng Claude sau cache_ts. Đây là lý do vẫn đánh dấu ước tính.
- Sai số còn phụ thuộc độ đúng của USD/1% ghim (một lần đo, Δ3%, sai số làm tròn khoảng ±33%).

## 2. Giai đoạn 2: nguồn % sống

### 2.1 Ứng viên A: sự kiện rate limit trong stream-json (ưu tiên)

- Claude Code ở chế độ `--output-format stream-json` có thể phát sự kiện rate limit kèm loại hạn mức, mức dùng và thời điểm reset. Cần kiểm chứng trên log hoặc luồng của Paseo daemon xem có trường % (utilization) cho `seven_day` và `five_hour` không.
- Nếu có: Paseo daemon (hoặc một mod) ghi mẫu mới nhất vào một file trạng thái riêng. `hh_ps/week.py` lấy mẫu mới nhất giữa file đó và cache statusline.

### 2.2 Ứng viên B: dữ liệu trong transcript

- Kiểm xem transcript `~/.claude/projects/**/*.jsonl` có ghi thông tin rate limit không. Khả năng thấp, nhưng kiểm rẻ.

### 2.3 Ứng viên C: endpoint usage OAuth (cần người dùng duyệt)

- Lệnh `/usage` của Claude Code lấy số từ một endpoint dùng token OAuth của gói. Đọc token đó là đụng secret. Theo luật dữ liệu, việc này không được giao hand ngoài, và chỉ làm khi người dùng đồng ý rõ ràng. Không dùng hay tạo API key.

### 2.4 Tiêu chí chọn

- Chọn ứng viên đầu tiên có % thật cho `seven_day`, cập nhật ít nhất mỗi lượt gọi model, và không cần secret.
- Không ứng viên nào đạt thì dừng ở giai đoạn 1 và ghi kết luận vào spec này.
