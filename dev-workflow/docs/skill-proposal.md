---
id: skill-proposal
title: Đề xuất bộ skill cho quy trình phát triển có AI
status: draft
last-reviewed: 2026-10-09
---

# Đề xuất bộ skill cho quy trình phát triển có AI

## Tóm tắt

- **Mục đích:** đóng gói các nhóm việc lặp lại của hai dự án `tcp-assistant` và `slt-ocr-pro` thành skill
  Claude Code, để agent tự áp đúng quy trình mà người dùng không phải nhắc lại.
- **Kết luận chính:**
  - Trục chính là **quy trình SDLC**: một plugin dùng chung `dev-workflow`.
  - **Nghiệp vụ** là skill riêng trong `.claude/skills/` của từng repo.
  - **Độ khó** không tách thành skill riêng. Skill `dev-triage` xếp mỗi việc vào một trong 4 làn L0–L3.
- **Số liệu chính:**
  - Khoảng 2.070 prompt. `tcp-assistant` chiếm 77% (60 phiên, 1.604 prompt); `slt-ocr-pro` có 4 phiên, 85 prompt.
  - Skill chỉ được gọi khoảng 5 lần, trong khi subagent `hand` được gọi hơn 1.800 lần.
  - Hết context 42 lần. Việc Jira chiếm khoảng 10% số prompt.
- **Việc cần làm:**
  - Duyệt **đợt 1**: `session-closeout` + `jira-workflow`, `dev-triage` + `spec-plan`, `bug-investigation`.
  - Xem phương pháp và artifact đi kèm ở [ai-dev-workflow.md](ai-dev-workflow.md).

## 1. Hiện trạng

### 1.1 Nhóm việc trong lịch sử Claude Code

Tần suất ước lượng trên 550 prompt đã làm sạch của hai dự án. Các nhóm có chồng lấn.

| Nhóm việc | Tần suất | Độ khó điển hình |
|---|---|---|
| Quản lý Jira (tạo task, estimate, log work, Done, báo cáo tuần) | ~10% | Trung bình, chỉnh estimate nhiều lượt |
| Sửa bug nhỏ | ~15% | Thấp – trung bình |
| Figure/bản vẽ (trích hình, highlight thiết bị, toạ độ) | ~9% | Rất cao, nhiều lần hết context |
| UX/frontend: review hình và heading | ~8% | Cao, chỉnh nhỏ nhiều vòng |
| Ingest/chunking/heading | ~8% | Cao |
| Plugin/agent tooling (brain-hand, model, effort) | ~8% | Trung bình |
| Môi trường/deploy (docker, STG/demo, env, SSH) | ~6% | Cao |
| Spec/plan/docs/quy ước repo | ~5% | Trung bình |
| Điều tra hạ tầng/hiệu năng (embedding, GPU, timeout) | ~4% | Rất cao |
| Test: dọn, đánh giá tác dụng, đếm test | ~4% | Trung bình |
| Kiểm chất lượng câu hỏi RAG/chat | ~3% | Cao |

### 1.2 Điểm đau

1. Phải nhắc tay việc đồng bộ Jira cuối phiên. Quy tắc estimate ×1,1 bị sửa nhiều lần.
2. Chưa rõ khi nào cần spec/plan, khi nào sửa nhanh: lúc thì "không cần workflow", lúc lại "sao không tạo spec và plan".
3. Hết context 42 lần, phải nhắc "tiếp tục" hoặc "bật loop".
4. Vòng điều tra dài: figure không tất định, embedding/GPU, chunking.
5. UI review phải chỉnh hàng chục lượt.
6. Phải tự dán log server vì agent không truy cập được.
7. Agent nhận sai loại tài liệu (bản vẽ bị coi là O&M).
8. Môi trường demo/STG: quyền SSH, user dịch vụ, nhiều file env.
9. Quy ước repo phải nhắc lại: không `cd` trong lệnh ghép, không dùng đường dẫn tuyệt đối, tiếng Việt có dấu.
10. Phải đổi model/effort thủ công nhiều lần (`/model` 33 lần, `/effort` 18 lần).

### 1.3 Cấu hình hiện có và lỗ hổng

- **Đang có:**
  - **Rules** `.claude/rules/*.md`: nạp theo `globs` khi chạm file khớp.
  - **`AGENTS.md`**: luôn nạp.
  - **Plugin `parallel-subagents`**: agent `hand` cùng hook SessionStart/UserPromptSubmit cho policy brain/hand.
  - **Plugin `jira-tools`**: skill `jira` và `jira-cli`.
  - **`tcp-assistant`** có thêm 4 skill: `measurement-evidence`, `local-docker-ingest`, `resume-loop`, `recover-lost-work`.
- **Lỗ hổng:**
  - Rule chỉ kích hoạt theo đường dẫn file. Các việc theo quy trình (điều tra lỗi, Jira, spec/plan, ADR) không có glob nào kích hoạt.
  - Hand không tự nạp `AGENTS.md`. Brain phải chép luật vào brief, dễ sót.
  - Mục Jira trong `AGENTS.md` gốc của `slt-ocr-pro` bị nạp ở mọi lượt dù hiếm khi cần.
  - CI của cả hai repo chỉ chạy lint. Gate test dựa vào agent tự chạy.

### 1.4 Phần trùng giữa hai repo

| Chủ đề | Ghi chú |
|---|---|
| Migrations | Gần như y hệt: ledger checksum, `IF NOT EXISTS`, `--drop` chỉ cho DB tên có `test` |
| Bố cục test | unit/integration/`private_data`/`live`, `--strict-markers`, thiếu Postgres là FAIL |
| Refactor | Tách theo trách nhiệm, thin facade. Ngưỡng 500 dòng (tcp) và 400 dòng (slt) |
| Quy trình bug | tcp có 8 bước (`tcp-assistant: AGENTS.md`), slt mới có một dòng |
| Nguyên văn là nguồn sự thật | tcp `ingest.md`, slt `extract.md` |
| Jira | Cùng `jira-tools`, estimate ×1,1. Khác project key (TPC/SLTOC) và cấu trúc epic |
| Docs governance | Cùng `document-governance.md`, frontmatter, template ADR/system-flow |

## 2. Nguyên tắc chia skill

### 2.1 Ba trục

| Trục | Đóng gói | Lý do |
|---|---|---|
| **Quy trình SDLC** (trục chính) | Plugin dùng chung `dev-workflow` | Giống nhau ở cả hai repo, và là chỗ đau nhất |
| **Nghiệp vụ** | Skill trong `<repo>/.claude/skills/` | Gắn với code và dữ liệu riêng |
| **Độ khó** | Làn L0–L3 do `dev-triage` chọn | Mỗi mức khó cũng là một quy trình, chỉ khác số bước |

Tham số riêng của từng repo nằm trong `.claude/dev-workflow.toml`: lệnh gate, ngưỡng số dòng, bảng code → docs, mã dự án Jira, epic. Nhờ vậy một skill dùng được cho mọi repo.

### 2.2 Bốn làn độ khó

| Làn | Tiêu chí | Bước bắt buộc |
|---|---|---|
| **L0 sửa nhanh** | ≤ 2 file, không đổi hành vi hay API | Sửa → gate → báo cáo |
| **L1 tiêu chuẩn** | Bug hoặc tính năng trong 1 module | Test đỏ → sửa → living docs → gate → tự review |
| **L2 lớn** | Nhiều module, đổi schema/API/contract | Spec + plan (+ ADR) → làm theo plan, tick ô → review |
| **L3 điều tra** | Không tất định, hiệu năng, hạ tầng | Giả thuyết → đo (một biến, n ≥ 3) → báo cáo, dừng chờ duyệt → L1/L2 |

## 3. Danh sách skill

### 3.1 Plugin dùng chung `dev-workflow`

| Skill | Việc làm | Nguồn |
|---|---|---|
| `dev-triage` | Xếp làn L0–L3, liệt kê các skill sẽ dùng, hỏi lại khi việc nằm giữa hai làn | Mới |
| `spec-plan` | Spec/plan/ADR từ template, tick ô, chuyển `completed`, xoá thiết kế cũ | Tách từ rule docs |
| `bug-investigation` | 8 bước: git log/blame, test đỏ đúng lý do, báo cáo nguyên nhân, chờ duyệt | `tcp-assistant: AGENTS.md` |
| `measurement-evidence` | Đo trước/sau cho làn L3 | Chuyển từ tcp |
| `db-migration` | File NNN mới, `store.py`, test, table-catalog | Gộp hai rule migrations |
| `self-review` | Checklist review diff: luật repo, trần số dòng, docs đi kèm, contract | Mới, bổ sung `/code-review` |
| `session-closeout` | Gate, tick plan, đồng bộ Jira (tạo task, estimate, log work, Done), tóm tắt | Mới, giải quyết điểm đau 1 |
| `resume-work` | Khôi phục khi hết context hoặc gặp lỗi 529 | Gộp `resume-loop` + `recover-lost-work` |
| `port-between-repos` | Chuyển code/docs giữa các repo, giữ trích dẫn nguồn | Mới |

### 3.2 Skill nghiệp vụ theo repo

- **`slt-ocr-pro`:**
  - `ocr-debug`: từ file hoặc document_id, so text layer với OCR và bbox theo trang.
  - `extract-template`: thêm/sửa template trích xuất kèm test verify/repair và docs.
  - `vlm-change`: dùng `MockTransport`, test `@live`, `redact_url`.
  - `review-export`: module structure/review/export, kiểm tất định và diff figure.
- **`tcp-assistant`:**
  - `ingest-debug`: lần theo document_id qua DB, storage và lệnh rerun.
  - `drawing-figure-qa`: KKS, toạ độ, highlight trên bộ câu hỏi chấp nhận.
  - `answer-path-perf`: đo TTFT ≤ 15 s.
  - `rag-question-eval`: chạy bộ câu hỏi chat.
  - `infra-triage`: embedding/GPU/vLLM, STG/demo, SSH/env.
- **Dùng chung khi có frontend:** `ui-review-iterate`: chạy FE, chụp màn hình, so với quy ước UX trước khi báo xong.

### 3.3 Vận hành

- `jira-workflow`: đặt trong plugin `jira-tools`, tham số hoá theo `dev-workflow.toml`. Sau đó gỡ mục Jira khỏi `AGENTS.md` gốc.

## 4. Cơ chế để skill thực sự được dùng

1. **Gọi từ policy:** thêm một dòng vào hook UserPromptSubmit: "bắt đầu bằng `dev-triage`, kết thúc bằng `session-closeout`". Brief cho hand thêm mục `SKILL CẦN NẠP`; hand có tool Skill nên không cần chép luật thủ công.
2. **Mô tả skill:** viết theo từ ngữ người dùng hay gõ ("update jira", "sao lại lỗi", "tạo spec"), rồi đo khả năng kích hoạt bằng eval của `skill-creator`.
3. **Phân vai:** rules giữ bất biến ngắn theo file; skill giữ quy trình nhiều bước; `AGENTS.md` chỉ giữ luật mọi lượt đều cần.

## 5. Lộ trình

| Đợt | Skill | Lý do ưu tiên |
|---|---|---|
| 1 | `session-closeout` + `jira-workflow`, `dev-triage` + `spec-plan`, `bug-investigation` | Giải quyết điểm đau 1–2 và chuẩn hoá quy trình bug |
| 2 | `ocr-debug`, `ingest-debug`, `drawing-figure-qa`, `measurement-evidence`, `resume-work` | Rút ngắn các vòng điều tra dài |
| 3 | `self-review`, `ui-review-iterate`, `infra-triage`, `port-between-repos` | Chất lượng và vận hành. Dọn `AGENTS.md` (bản của tcp dài 639 dòng, vượt trần 500) |

## 6. Vấn đề phát hiện thêm

- Phần chạy test trong CI của cả hai repo đang bị comment.
- Cần kiểm tra `jira-tools: plugins/jira-tools/config/jira.json` không chứa PAT.
- Gốc repo `claude-plugins` còn file rác (`jira-tools.zip`, `find.py`).
