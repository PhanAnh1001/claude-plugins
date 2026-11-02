# Tiếp việc cho hand theo trạng thái cache

Cập nhật: 2026-11-02 · Liên quan: [nghiên cứu 2026-11-02](../../../research/2026-11-02-subagent-prompt-cache/report.md)

## Tóm tắt

- **Giải pháp đang áp dụng (plugin 2.1.0):** brain chọn SendMessage hay sinh hand mới theo trạng thái cache của hand: nóng → SendMessage ngay; nguội và ngữ cảnh >80k → hand mới với brief gọn; ngữ cảnh >200k → luôn hand mới.
- **Nguyên nhân:** cache của subagent chỉ sống 5 phút; 341 lần resume khi cache nguội đã ghi lại 54,8 triệu token (số đo nội bộ).
- **Số chính:** chỉ 59,8% resume diễn ra trong 5 phút; 118 lần resume có ngữ cảnh >200k; cùng giải pháp tách lệnh dài ước tính tiết kiệm ~11–12% chi phí subagent (suy luận, chưa đo).
- **Việc cần làm:** brain theo luật này khi giao tiếp việc; xem kết quả đo lại 2026-11-16.

## Nguyên nhân

- Subagent ghi cache TTL 5 phút, giá 1,25x input; read chỉ 0,05x với Opus 5.5 [docs](https://docs.claude.com/en/docs/build-with-claude/prompt-caching), [pricing](https://www.anthropic.com/pricing) (chưa kiểm chứng trên internet; tài liệu skill claude-api, Claude Code 2.1.316, 2026-10-06).
- Policy 2.0.2 chỉ nhắc TTL một cách định tính ("cache có TTL nên tiếp việc sớm thì rẻ, để lâu lợi thế giảm"), không có ngưỡng thời gian hay kích thước ngữ cảnh, nên brain vẫn SendMessage cho hand đã nguội. Thực tế 341 lần resume sau nghỉ 5–60 phút (median 15,1 phút, ngữ cảnh median 164k) ghi lại 54,8 triệu token (số đo nội bộ, transcript 2026-09-30 → 2026-11-02 + `tools/cache-metrics/resume_miss.py`).

## Giải pháp đang áp dụng

- **Cache NÓNG** (giao trong lượt nhận báo cáo, không chờ người dùng/hand khác/lệnh dài xen giữa) và việc chạm cùng file/module: SendMessage, brief chỉ ghi phần thay đổi; giao ngay trước khi hỏi người dùng.
- **Cache NGUỘI** (đã qua một lượt chờ người dùng, hoặc hand xong hơn 5 phút trước): xem `subagent_tokens` trong usage của thông báo hoàn thành. ≤80k: vẫn SendMessage. >80k: hand mới, brief chép sẵn phát hiện kèm file:dòng từ báo cáo hand cũ.
- **Luôn hand mới** khi việc độc lập/khác vùng code, hand cũ đã làm nhiều việc khác nhau hoặc ngữ cảnh >200k, hoặc hand cũ đang chạy.
- Áp dụng cả khi review phát hiện lỗi và brain giao sửa.

## Vì sao chọn

- Ghi lại ngữ cảnh lớn khi nguội đắt ngang tạo hand mới, còn hand mới với brief gọn chỉ ghi phần nhỏ (suy luận từ hệ số giá trên).
- Ngưỡng 80k: dưới mức này chi phí ghi lại nhỏ, lợi ích giữ hiểu biết của hand cũ còn đáng; 200k: gần median ngữ cảnh của các miss lớn (164k–196k). Hai ngưỡng chọn theo phân bố, chưa tối ưu.

## Phương án đã loại

- Ưu tiên SendMessage cho hand cũ, chỉ nhắc TTL định tính (policy 2.0.2): gây 341 lần miss lớn.
- Luôn sinh hand mới: mất cache nóng rẻ (read 0,05x) trong 59,8% lần resume nhanh.
- Giữ cache sống bằng request "ping": tốn request; plugin không điều khiển được TTL hay request của subagent; chưa kiểm chứng Claude Code có tùy chọn này.

## Kiểm chứng

- Chưa đo sau thay đổi. Lần đo lại tự động 2026-11-16 09:07 (giờ local) bằng `tools/cache-metrics/run_followup.sh`; so với số trong [report](../../../research/2026-11-02-subagent-prompt-cache/report.md).

## File liên quan

- `plugins/parallel-subagents/scripts/session-start-policy.sh` - LUẬT TIẾP VIỆC đầy đủ.
- `plugins/parallel-subagents/scripts/inject-policy.sh` - bản ngắn bơm mỗi prompt.
- `tools/cache-metrics/` - script đo.

## Việc còn mở

- Xác nhận mức tiết kiệm sau lần đo 2026-11-16; chỉnh ngưỡng 80k/200k nếu cần.
