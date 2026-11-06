---
status: completed
lane: L3
date: 2026-11-06
---

# Vì sao một phiên brain dài ngày tốn token Claude gấp hơn 10 lần các phiên khác

## Tóm tắt

- **Câu hỏi:** một phiên brain (phiên chính điều phối hand) ở một repo dự án tốn token Claude nhiều hơn hẳn các phiên khác. Vì sao, và tối ưu được không?
- **Kết luận chính:**
  1. Phiên đó không đắt hơn ở từng lượt gọi: khoảng 19,7k token tương đương mỗi lượt, ngang các phiên khác (18–21k). Nó đắt vì **số lượt**: 1.570 lượt trong 3,3 ngày liền, so với 77–166 lượt ở các phiên khác, và mỗi lượt đọc lại ngữ cảnh trung vị 171k.
  2. **54% chi phí** đến từ các lượt brain tự tra cứu (`grep`, `cat`, `sed`, `git diff/log`, Read): 886 lượt.
  3. **17% chi phí** là ghi lại cache sau 17 lần tự nén và sau các lần nghỉ quá 1 giờ.
  4. **9% chi phí** là hỏi trạng thái trong lúc chờ (`side-session ls/watch`, `hh-ps`, `hand-ext status`), dù thông báo hoàn thành tự đến.
- **Đã áp dụng vào policy của plugin** (`scripts/session-start-policy.sh`, bản ngắn ở `scripts/inject-policy.sh`), mục "LUẬT NGỮ CẢNH BRAIN":
  - **A. Xoay phiên:** xong một đợt việc hoặc nghỉ quá 1 giờ thì ghi bàn giao và mở phiên brain mới.
  - **B. Không tự tra cứu:** cần quá 2 lệnh đọc thì giao hand; review đọc `git diff --stat` rồi chỉ các hunk cần thiết.
  - **D. Không hỏi trạng thái:** chờ thông báo hoàn thành, hoặc một `Monitor` chờ file kết thúc.
- **Ước tính tiết kiệm:** 40–55% chi phí của phiên brain loại này (suy luận từ số đo ở mục 3, chưa đo lại sau khi áp dụng).
- **Việc người đọc cần làm:** đo lại theo mục 5 sau vài ngày dùng policy mới. Nếu chi phí mỗi đợt việc không giảm thì xem lại luật.

## 1. Phương pháp đo

### 1.1 Nguồn số liệu

- Transcript `.jsonl` của Claude Code cho từng phiên và subagent. Mỗi lượt gọi API có `usage` gồm `input_tokens`, `cache_creation_input_tokens` (tách 5 phút và 1 giờ), `cache_read_input_tokens`, `output_tokens`.
- Các dòng cùng `message.id` là một lượt gọi. Khối nội dung được gộp trước khi đếm công cụ của lượt đó.
- Dòng `system` có `subtype: compact_boundary` cho biết lần tự nén, kèm `preTokens` và `postTokens`.
- Mọi phiên đo đều chạy Claude Opus 5.5.

### 1.2 Quy đổi về "token đầu vào tương đương"

Hệ số theo bảng giá Anthropic:

| Loại token | Hệ số | Nguồn |
|---|---|---|
| Đầu vào thường | 1× | |
| Ghi cache 5 phút | 1,25× | [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching) (11/2026) |
| Ghi cache 1 giờ | 2× | như trên |
| Đọc cache, Opus 5.5 | 0,05× (đa số model 0,1×) | như trên, chú thích bảng |
| Output, Opus | 5× (Opus 5.5: $4 vào, $20 ra mỗi MTok) | [pricing](https://platform.claude.com/docs/en/about-claude/pricing) (11/2026) |

Mọi ghi cache trong các phiên đo đều là loại 1 giờ.

### 1.3 Gán chi phí cho hành động

- Mỗi lượt gọi được gán theo công cụ đầu tiên mà lượt đó gọi. Lệnh Bash được phân loại theo nội dung lệnh: đọc, ghi, giao việc, hỏi trạng thái.
- Lượt không gọi công cụ được tính là "trả lời".

## 2. So sánh các phiên

| Phiên | Số lượt | Ngữ cảnh trung vị | Tự nén | Chi phí tương đương | Mỗi lượt |
|---|---|---|---|---|---|
| **Brain dài ngày** (3,3 ngày, một repo dự án) | 1.570 | 171k | 17 | **30,9M** | 19,7k |
| 49 hand Claude do phiên trên sinh | 843 | ~72k | – | thêm 10,9M | ~12,9k |
| Phiên phụ review 1 | 122 | ~150k | 1 | 2,3M | 18,6k |
| Phiên phụ review 2 | 77 | ~150k | 1 | 1,6M | 21,1k |
| Brain ở repo khác, 2 giờ | 166 | ~140k | 2 | 3,0M | 18,1k |
| Brain dài ngày ở repo khác (4 ngày) | 980 | ~167k | 14 | 20,6M | 21,0k |

- **Chi phí mỗi lượt gần như bằng nhau.** Khác biệt nằm ở số lượt. Phiên brain dài ngày thứ hai ở repo khác lặp lại đúng mẫu này, nên đây là mẫu sử dụng chứ không phải lỗi riêng của một phiên.
- **Cơ cấu chi phí của phiên brain dài ngày:** đọc cache 42%, ghi cache 35%, output 22%.
- **Ngữ cảnh nền:** lượt đầu của một phiên mới đã có 58–64k token (system prompt, công cụ, danh sách skill của các plugin, tài liệu luật của repo, hook). Sau mỗi lần tự nén, ngữ cảnh vẫn còn khoảng 95k (nền cộng bản tóm tắt khoảng 30k), rồi tăng tiếp tới ngưỡng nén 240–270k. Kết quả là 30% số lượt chạy ở mức trên 200k.

## 3. Nguyên nhân

### 3.1 Brain tự tra cứu (54%)

| Hành động mở đầu lượt | Số lượt | Chi phí | Tỷ lệ |
|---|---|---|---|
| Đọc: `grep`, `cat`, `sed`, `head`, `git diff/show/log/status`, Read | 886 | 16,8M | 54,2% |
| Trả lời (hết lượt) | 210 | 3,8M | 12,2% |
| Ghi: Write, Edit, `git add/commit/push` | 152 | 3,7M | 11,9% |
| Hỏi trạng thái: `side-session`, `hh-ps`, `hand-ext status`, Monitor | 158 | 2,8M | 9,1% |
| Giao việc: Agent, SendMessage, `hand-ext run` | 67 | 1,7M | 5,4% |
| Khác | 97 | 2,0M | 6,6% |

- **Lệnh nhỏ vẫn đắt:** mỗi lệnh đọc nhỏ khiến brain trả thêm một lượt gọi ở ngữ cảnh khoảng 170k, tức khoảng 19k token tương đương, dù lệnh chỉ trả vài dòng.
- **Ngữ cảnh phình nhanh:** kết quả các lệnh đọc cộng thêm khoảng 2,3 triệu ký tự vào ngữ cảnh, đẩy phiên tới ngưỡng tự nén nhanh hơn.
- **Một phần là review bắt buộc,** nhưng phần lớn là tra cứu từng bước: `grep` → `sed -n` → `grep` lại. Việc này một hand làm được, rồi trả kết luận gọn kèm file:dòng.

### 3.2 Một phiên chạy qua nhiều đợt việc (17% ghi lại cache, cộng ngữ cảnh cao)

- **Không bao giờ mở phiên mới:** phiên chạy 3,3 ngày, 17 lần tự nén.
  - Mỗi lần nén tốn một lượt tóm tắt, cộng một lần ghi lại khoảng 65k token ở hệ số 2×.
  - Lượt tóm tắt không có trong transcript, nên chưa nằm trong con số 30,9M (suy luận).
- **Nghỉ quá 1 giờ rồi làm tiếp:** có 8 lần như vậy (5 giờ, 12 giờ, 21 giờ…). Cache 1 giờ đã hết hạn, nên lượt đầu phải ghi lại 125–211k token ở hệ số 2×.
- **Tổng hai loại ghi lại** (các lần ghi trên 30k token): 5,2M, tức 16,9% chi phí.
- **Lẫn chủ đề:** khoảng 28% chi phí là việc của một repo khác (sửa plugin), làm ngay trong phiên brain của repo dự án. Ngữ cảnh vì vậy chứa hai chủ đề, và việc plugin bị tính phí ở mức ngữ cảnh cao.

### 3.3 Hỏi trạng thái trong lúc chờ (9%)

- 158 lượt hỏi trạng thái: `side-session ls/watch` 106 lần, `hh-ps` 27 lần, cùng `hand-ext status`.
- Trong khi đó có 122 thông báo hoàn thành tự đến. Hỏi trạng thái không làm việc chạy nhanh hơn, mỗi lần chỉ tốn thêm một lượt ở ngữ cảnh cao.

## 4. Giải pháp

### 4.1 Đã áp dụng vào policy

Mục "LUẬT NGỮ CẢNH BRAIN" trong `scripts/session-start-policy.sh`; bản ngắn nằm trong `scripts/inject-policy.sh`. LUẬT REVIEW được sửa để đọc gọn theo luật mới.

| Luật | Nội dung | Tác động ước tính (suy luận) |
|---|---|---|
| **A. Xoay phiên** | Xong một đợt việc (đã commit/push, đã ghi trạng thái còn mở) hoặc phiên nghỉ quá 1 giờ: brain ghi bàn giao rồi đề nghị người dùng mở phiên brain mới (`/clear` hoặc phiên mới) bắt đầu từ tài liệu đó. Việc thuộc repo khác làm ở phiên brain của repo đó. | Ngữ cảnh trung bình từ ~170k xuống ~100k và gần như hết ghi lại cache vì tự nén hay nghỉ lâu: ~25–30% |
| **B. Không tự tra cứu** | Cần quá 2 lệnh đọc thì giao hand. Brain chỉ tự đọc báo cáo hand, đoạn đã biết đích danh (≤ 80 dòng) và diff khi review (`git diff --stat` rồi hunk của file quyết định đúng sai). Ảnh đã duyệt không đọc lại. | Giảm khoảng một nửa của 54%: ~20–27% (hand ngoài không tốn token Claude; hand Claude rẻ hơn ~1,5 lần mỗi lượt) |
| **D. Không hỏi trạng thái** | Trong lúc chờ: kết thúc lượt và chờ thông báo hoàn thành. Việc không tự báo thì đặt một `Monitor` chờ file kết thúc. Chỉ hỏi khi người dùng hỏi hoặc việc đã quá hạn. | ~8% |

Ba luật chồng lên nhau một phần (B và D làm ngữ cảnh tăng chậm hơn, nên A ít khi phải xoay sớm). Gộp lại tôi ước tính 40–55% chi phí của phiên brain (suy luận).

### 4.2 Chưa áp dụng

- **Ngữ cảnh nền 58–64k:** tắt plugin không dùng trong repo sẽ bớt vài nghìn token mỗi lượt, tức khoảng 2–3% chi phí. Việc này thuộc cấu hình từng repo, không đưa vào policy.
- **Cache 5 phút thay cho 1 giờ:** không nên đổi. Hand thường chạy 10–20 phút, nên với cache 5 phút, mỗi thông báo hoàn thành sẽ phải ghi lại cả ngữ cảnh brain ở 1,25×, thay vì đọc ở 0,05×.
- **Hạ ngưỡng tự nén riêng cho brain:** có giảm ngữ cảnh trung bình, nhưng nén thường hơn thì mất chi tiết và tốn lượt tóm tắt. Luật A đạt cùng mục tiêu mà giữ được trạng thái trong tài liệu bàn giao.

## 5. Đo lại

- **Cách đo:** sau vài ngày dùng policy mới, đo lại bằng cùng phương pháp ở mục 1 cho các phiên brain của một đợt việc tương đương.
- **Chỉ số cần so** (in số thô từng phiên kèm trung vị, ít nhất 3 phiên):
  - chi phí tương đương mỗi đợt việc;
  - ngữ cảnh trung vị;
  - tỷ lệ lượt "đọc" và lượt "hỏi trạng thái";
  - số lần tự nén.
- **Tiêu chí đạt:**
  - chi phí mỗi đợt giảm ít nhất 30%;
  - tỷ lệ lượt đọc của brain dưới 25%;
  - không còn lượt hỏi trạng thái khi người dùng không hỏi.
