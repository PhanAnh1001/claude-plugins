---
name: weekly-report
description: Tạo 4 báo cáo tuần từ Jira của tài khoản hiện tại — chi tiết và tóm tắt việc đã làm (thứ Sáu tuần trước → thứ Sáu tuần này), chi tiết và tóm tắt việc sẽ làm (thứ Sáu tuần này → thứ Năm tuần sau) — bằng lệnh jira-cli report của plugin jira-tools. Từ khoá - "báo cáo tuần", "báo cáo đã làm", "báo cáo sẽ làm", "kế hoạch tuần", "weekly report", "tóm tắt task tuần".
---

# Báo cáo tuần từ Jira

## Tóm tắt

- **Mục đích:** từ Jira và git của tài khoản hiện tại, tạo 4 báo cáo dán thẳng vào chat/email:
  chi tiết đã làm, tóm tắt đã làm, chi tiết sẽ làm, tóm tắt sẽ làm.
- **Kỳ báo cáo:** neo vào thứ Sáu gần nhất không sau ngày neo (mặc định hôm nay). Đã làm = thứ Sáu
  tuần trước → thứ Sáu tuần này (cả hai đầu); sẽ làm = thứ Sáu tuần này → thứ Năm tuần sau.
- **Cách làm:** 4 bước — lấy dữ liệu (`report --json`), soạn nội dung, render bằng
  `report --input` để đúng format, rồi ghi chú ngắn. Không tự viết format bằng tay.
- **Độ dài:** báo cáo phải gọn: gộp task theo kết quả, ít dòng, dòng ngắn (cách làm ở Bước 2).
  Không có giới hạn cứng, tự cân theo lượng việc trong tuần.
- **Giới hạn:** chỉ đọc Jira; không sửa Jira trừ khi người dùng yêu cầu.

## Bước 1. Lấy dữ liệu

Chạy từ thư mục repo của dự án (cwd), để CLI tự chọn dự án và đọc commit của repo đó:

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/jira-cli" report --json [--kind done|plan|all] [--anchor YYYY-MM-DD]
```

- Gọi bằng `/jira-tools:weekly-report [done|plan|all] [YYYY-MM-DD]`: từ `done`/`plan`/`all` là
  `--kind`, ngày là `--anchor`; bỏ trống thì `all` và hôm nay.
- "chỉ báo cáo đã làm" → `--kind done`; "chỉ kế hoạch" → `--kind plan`; ngày cụ thể → `--anchor`.
- "Sẽ làm" là các task chưa Done đang giao cho mình: muốn đổi danh sách thì giao lại hoặc bỏ giao
  task trên Jira trước (theo yêu cầu người dùng), rồi chạy lại.
- Cờ khác: `--from`/`--to` (ghi đè kỳ, chỉ với done hoặc plan), `--user`, `--repo PATH` (lặp lại),
  `--git-author`, `--exclude-epic KEY` (lặp lại, chỉ cho plan), `--project`.
- Nguồn "đã làm" là hợp của: issue có worklog của mình trong kỳ, issue mình được giao và resolved
  trong kỳ, key Jira nhắc trong commit của mình trong kỳ. Mỗi issue có `sources`, `commits`,
  `status`, `epic_name`, `remaining_estimate_seconds`.

## Bước 2. Soạn nội dung

Người nhận đọc lướt trong chat/email nên báo cáo phải gọn: ít dòng, mỗi dòng ngắn. Không có giới
hạn cứng; tự cân theo lượng việc trong tuần, tuần ít việc thì viết ít hơn.

- Gộp theo kết quả, không theo task: nhiều task cùng một kết quả thành một dòng và liệt kê mọi
  key của chúng trong `keys` (một dòng mang vài key là bình thường). Không bỏ key nào của dữ liệu
  khỏi báo cáo chi tiết.
- Mỗi dòng chỉ nêu vài ý ngắn. Không liệt kê từng màn hình, endpoint, tên hàm, tên bảng, tên job;
  giữ số ADR và tên tính năng người đọc đã biết.
- Tránh nhóm chỉ có một dòng: gộp việc lẻ (sửa lỗi, hạ tầng) vào nhóm gần nhất hoặc một nhóm
  ghép, ví dụ "Bản vẽ, mô tả hình và hạ tầng".
- Nhóm theo chủ đề (epic/label), đặt tên nhóm theo chức năng người dùng hiểu, ví dụ "Nạp tài liệu
  và kho tri thức", "Trợ lý AI", "Hạ tầng và triển khai", "Kiến trúc". Báo cáo tóm tắt dùng cùng
  nhóm với báo cáo chi tiết.
- Dùng `commits` để mô tả đúng việc đã làm, không chỉ chép summary.
- Báo cáo chi tiết: ngôn ngữ kỹ thuật vừa phải; việc chưa xong ghi "(đang làm)" ở cuối dòng.
- Báo cáo tóm tắt: ngắn hơn hẳn báo cáo chi tiết, mỗi nhóm một hai dòng; ngôn ngữ người quản lý
  đọc được, nêu kết quả, không key, không thuật ngữ nội bộ.
- Báo cáo "sẽ làm": task đang In Progress viết là "Hoàn tất ...".
- Soạn xong đọc lại một lượt: dòng nào gộp được với dòng khác, hay bỏ bớt chi tiết mà không mất
  ý, thì gộp và bỏ trước khi render.

Ví dụ gộp — thay vì ba dòng:

```
 - Lõi license thay cờ bật nhóm tính năng (AILUX-212)
 - Danh mục tính năng và API /v1/features mới (AILUX-213)
 - Triển khai license bằng Secret và bộ cài (AILUX-215)
```

viết một dòng:

```
 - Lõi license thay cờ bật nhóm, danh mục tính năng, triển khai bằng Secret và bộ cài (AILUX-212, AILUX-213, AILUX-215)
```

## Bước 3. Render đúng format

Ghi JSON soạn sẵn vào file tạm **ngoài repo** (thư mục scratchpad của phiên hoặc `mktemp`), rồi:

```bash
"${CLAUDE_PLUGIN_ROOT}/bin/jira-cli" report --input <file>
```

Dán **nguyên văn** output: dòng `== <tiêu đề> ==` viết thành tiêu đề in đậm bên ngoài, phần báo
cáo bên dưới đặt trong một khối code ``` riêng, vì Markdown bỏ dấu cách đầu dòng trước `-` nếu để
ngoài khối code. Không gõ lại hay sửa tay nội dung trong khối. Lệnh `--input` chỉ render, không
gọi Jira.

Ví dụ input:

```json
{
  "title": "LUXIAN",
  "reports": [
    {"heading": "Báo cáo chi tiết đã làm (30/10 – 06/11/2026)", "style": "detail",
     "groups": [{"name": "Trợ lý AI",
                 "items": [{"text": "Trả lời có trích dẫn trang", "keys": ["AILUX-5", "AILUX-6"]},
                           {"text": "Rà soát prompt", "keys": []}]}]},
    {"heading": "Báo cáo tóm tắt đã làm (30/10 – 06/11/2026)", "style": "summary",
     "groups": [{"name": "Trợ lý AI",
                 "items": [{"text": "Trợ lý trả lời kèm trích dẫn trang tài liệu"}]}]}
  ]
}
```

Output:

```
== Báo cáo chi tiết đã làm (30/10 – 06/11/2026) ==

* Dự án LUXIAN
1. Trợ lý AI
 - Trả lời có trích dẫn trang (AILUX-5, AILUX-6)
 - Rà soát prompt

== Báo cáo tóm tắt đã làm (30/10 – 06/11/2026) ==

LUXIAN
1. Trợ lý AI
 - Trợ lý trả lời kèm trích dẫn trang tài liệu
```

Format: báo cáo chi tiết mở bằng `* Dự án <title>`, tóm tắt mở bằng `<title>`; nhóm đánh số
`1.`, `2.`…; mục con bắt đầu bằng một dấu cách rồi `- `; mục không có key thì không in ngoặc.

## Bước 4. Ghi chú sau 4 khối

Ghi ngắn, vài gạch đầu dòng, không lặp lại nội dung báo cáo: task chưa log work
(không có `worklog` trong `sources`), task có commit nhưng vẫn To Do hoặc In Progress, tổng ước
lượng còn lại (`plan.remaining_hours`) so với 40 giờ/tuần. Không sửa Jira trừ khi người dùng yêu
cầu.
