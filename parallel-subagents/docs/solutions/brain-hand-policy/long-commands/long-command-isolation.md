# Tách lệnh dài ra hand riêng

Cập nhật: 2026-11-02 · Liên quan: [nghiên cứu 2026-11-02](../../../research/2026-11-02-subagent-prompt-cache/report.md)

## Tóm tắt

- **Giải pháp đang áp dụng (plugin 2.1.0):** lệnh dự kiến chạy quá 4 phút (full test suite, build image, e2e, deploy) giao cho một hand riêng chỉ chạy lệnh đó; hand làm việc chính chỉ chạy test hẹp và ghi lệnh dài chưa chạy vào mục báo cáo 5 "Lệnh dài cần hand riêng".
- **Nguyên nhân:** 313 lần Bash dài ở cuối một hand đã to làm cache 5 phút hết hạn, ghi lại 58,6 triệu token (số đo nội bộ).
- **Số chính:** ngữ cảnh median 196k, thời gian lệnh median 9,6 phút; tiết kiệm cùng giải pháp tiếp việc ~11–12% chi phí subagent (suy luận, chưa đo).
- **Việc cần làm:** brain giao lệnh dài cho hand riêng; hand báo lệnh dài thay vì tự chạy khi brief không giao.

## Nguyên nhân

- Cache subagent TTL 5 phút, ghi lại 1,25x input [docs](https://docs.claude.com/en/docs/build-with-claude/prompt-caching), [pricing](https://www.anthropic.com/pricing) (chưa kiểm chứng trên internet; tài liệu skill claude-api, Claude Code 2.1.316, 2026-10-06).
- Lệnh Bash chạy quá 5 phút thì request kế tiếp của hand phải ghi lại toàn bộ ngữ cảnh: 313 lần, 58,6 triệu token (số đo nội bộ, transcript 2026-09-30 → 2026-11-02 + `tools/cache-metrics/resume_miss.py`).

## Giải pháp đang áp dụng

- Brain (`session-start-policy.sh`, `inject-policy.sh`): lệnh >4 phút → hand riêng, ngữ cảnh nhỏ nên mất cache cũng rẻ; không gắn vào cuối hand đã đọc nhiều.
- Hand (`agents/hand.md`): nếu brief không giao riêng lệnh dài thì chỉ chạy test hẹp; ghi lệnh chính xác + thư mục chạy vào mục báo cáo 5. Brief giao đúng lệnh đó thì chạy bình thường.

## Vì sao chọn

- Hand chỉ chạy lệnh có ngữ cảnh vài chục nghìn token, nên một lần ghi lại sau lệnh dài rẻ hơn nhiều so với ghi lại ~196k (suy luận).
- Ngưỡng 4 phút chừa biên dưới TTL 5 phút.

## Phương án đã loại

- Chạy lệnh dài ở background trong cùng hand: hand vẫn phải resume sau khi lệnh xong, cache đã nguội.
- Bỏ chạy full test: mất kiểm chứng.

## Kiểm chứng

- Chưa đo sau thay đổi; đo lại tự động 2026-11-16 bằng `tools/cache-metrics/run_followup.sh`.

## File liên quan

- `plugins/parallel-subagents/scripts/session-start-policy.sh` - luật LỆNH DÀI.
- `plugins/parallel-subagents/scripts/inject-policy.sh` - bản ngắn.
- `plugins/parallel-subagents/agents/hand.md` - luật cho hand và mục báo cáo 5.

## Việc còn mở

- Hand khó ước lượng trước thời gian lệnh; xem số lần miss loại Bash dài sau lần đo 2026-11-16.
