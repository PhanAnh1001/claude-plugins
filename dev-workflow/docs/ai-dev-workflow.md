---
id: ai-dev-workflow
title: Workflow phát triển phần mềm có AI (theo phương pháp ai4ba)
status: draft
last-reviewed: 2026-10-09
---

# Workflow phát triển phần mềm có AI

## Tóm tắt

- **Mục đích:** lấy phương pháp của [ai4ba.com](https://ai4ba.com/) (BA-Kit) làm nền, rồi nối tiếp phần
  dành cho developer. Đầu ra là các file `.md` có cấu trúc để AI và người dùng tiếp qua từng bước.
- **Nguyên tắc** (theo ai4ba): các bước của workflow không đổi. AI làm việc bên trong từng bước, còn người
  đứng ở các cổng giữa các bước.
- **Kết quả chính:**
  - **Bỏ hoặc gộp:** biên bản họp, BRD/URD/PRD riêng (với việc nhỏ), mockup chi tiết làm trước,
    tài liệu thiết kế cho việc nhỏ, planning poker, viết test case từ đầu, ma trận truy vết Excel, nhập Jira tay.
  - **Đổi sang `.md` có cấu trúc:** brainstorm, SRS, story, `design.md`, `plan.md`, `traceability.md`, CR, bug.
    Mọi yêu cầu có ID `<TYPE>-<feature>-NNN`.
  - **Ba mức tự động:** tự động hoàn toàn / AI soạn, người duyệt / chỉ người làm.
  - **Năm cổng duyệt phía dev:** SRS, `design.md` (từ L2), `plan.md`, review diff, release.
- **Ranh giới BA → dev:** SRS không chứa quyết định kỹ thuật. Từ `design.md` trở đi là phần của dev.
- **Việc cần làm:** duyệt quy ước thư mục và ID ở mục 4, sau đó dựng template và skill
  (xem [skill-proposal.md](skill-proposal.md)).

## 1. Nguồn tham khảo

- **Site và tác giả:** ai4ba.com là khoá học tiếng Việt cho BA/PO của Phan Minh Hoàng. Bộ BA-Kit gồm 55 skill,
  19 rule, 48 template, chạy trên Claude Code.
- **Chuỗi lệnh:** `/brainstorm` → `/srs` → `/wireframe-html` → `/userstory` + `/jira` → `/test-cases`.
  Thay đổi yêu cầu đi qua `/cr` (báo cáo ảnh hưởng trước, sửa sau khi duyệt). Truy vết chéo dùng `/gap`.
- **Người giữ bốn điểm:** kiểm đầu vào, duyệt bản nháp, phê duyệt quyết định, và biết lúc nào dừng AI để hỏi stakeholder.
- **Giới hạn của nguồn:**
  - Thân các bài blog và nội dung thật của skill/template phải trả phí. Tài liệu này chỉ dùng phần công khai
    và hai tài liệu mẫu (brainstorm, SRS).
  - Site không liệt kê quy trình làm tay. Mục 2 là SDLC chuẩn do nhóm tự tóm tắt.
  - Site tự mâu thuẫn: trang chủ đi thẳng brainstorm → SRS, còn tài liệu mẫu bắt qua URD → BRD → PRD.
    Mục 3.1 giải quyết bằng cách để PRD tuỳ theo làn.

## 2. Quy trình chưa có AI

| # | Bước | Đầu ra truyền thống | Người làm |
|---|---|---|---|
| 1 | Khảo sát, lấy yêu cầu | Biên bản họp, ghi chú | BA + stakeholder |
| 2 | Phân tích, đặc tả | BRD/URD/PRD → SRS (Word) | BA |
| 3 | Thiết kế màn hình | Mockup (Figma/Draw.io), mô tả control | BA/UX |
| 4 | Backlog | User story + AC trên Jira | PO/BA |
| 5 | Thiết kế kỹ thuật | Kiến trúc, API, DB, quyết định | Dev lead/architect |
| 6 | Lập kế hoạch, ước lượng | Chia task, planning poker | Team |
| 7 | Lập trình | Code + unit test | Dev |
| 8 | Kiểm thử | Test case (Excel), integration test, UAT | QC + dev |
| 9 | Review | Code review, review tài liệu | Peer |
| 10 | Tài liệu | Docs kỹ thuật, ma trận truy vết | Dev/BA |
| 11 | Phát hành | Build, deploy, release note | DevOps |
| 12 | Bảo trì, thay đổi | Bug report, CR, phân tích ảnh hưởng | Cả team |

## 3. Thay đổi khi thêm AI

### 3.1 Bỏ qua hoặc gộp

| Bước | Bỏ hoặc gộp gì | Điều kiện |
|---|---|---|
| 1 | Biên bản họp: AI phỏng vấn và ghi thẳng vào `brainstorm.md` | Luôn |
| 2 | BRD/URD/PRD riêng: gộp vào brainstorm + SRS | Việc L0–L1. Từ L2 mới cần PRD |
| 3 | Mockup chi tiết làm trước: thay bằng wireframe HTML bấm được | Chỉ làm giao diện kỹ sau khi chốt flow |
| 5 | Tài liệu thiết kế riêng | Bỏ ở L0–L1. Từ L2 mới cần `design.md` + ADR |
| 6 | Planning poker: AI chia task và ước lượng (AI làm + người duyệt, ×1,1) | Người chỉnh lại |
| 8 | Viết test case từ đầu: sinh từ AC/FR | Người duyệt |
| 10 | Ma trận truy vết Excel: sinh tự động từ ID | Luôn |
| 11 | Nhập Jira tay | Luôn |

**Không bao giờ bỏ:** chốt scope với stakeholder, các cổng duyệt, quyết định kiến trúc, UAT, quyết định phát hành.

### 3.2 Chuyển sang `.md` có cấu trúc

| Bước | File `.md` | Cấu trúc chính | Ai viết |
|---|---|---|---|
| 1 | `brainstorms/<slug>.md` | Năng lực P0/P1/P2, Decision Points `D1…`, `OQ-n` dạng checkbox | BA + AI |
| 2 | `srs/spec.md`, `flows.md`, `states.md`, `erd.md` | Bảng `FR/NFR/BR/E/SC-<feature>-NNN` có cột `Source` và `Verify by`; `[NEEDS CLARIFICATION]` | BA + AI |
| 3 | `html-wireframe/` + screen description | Bảng control có tham chiếu FR | BA + AI |
| 4 | `userstories/` | Story + AC, liên kết FR | BA + AI |
| 5 | `dev/design.md` | Frontmatter `status`, `implements: [FR-…]`; API, DB, migration; quyết định → ADR | Dev + AI |
| 6 | `dev/plan.md` | Task `T-<feature>-NN` có checkbox, `covers: FR-…`, làn L0–L3, estimate | Dev + AI |
| 7–8 | Code và test | Tên/marker test có ID, ví dụ `test_FR_auth_001_…` | AI làm, dev duyệt |
| 10 | `_shared/traceability.md` | FR ↔ UC ↔ Screen ↔ Task ↔ Test ↔ file code | Tự động |
| 12 | `cr/CR-YYYYMMDD-NNN.md`, `bugs/<date>-<slug>.md` | CR: báo cáo ảnh hưởng trước. Bug: test đỏ + nguyên nhân gốc | AI soạn, người duyệt |

Bàn giao BA → dev dựa vào ba thứ:
- **Cột `Verify by`** của bảng FR thành checklist test.
- **Ma trận lỗi `E-…`** thành các ca lỗi bắt buộc phải xử lý.
- **Tiêu chí `SC-…`** thành điều kiện coi task là xong.

### 3.3 Mức tự động

| Mức | Phần việc |
|---|---|
| **Tự động hoàn toàn** (hook, script, CI) | Kiểm ID và truy vết, phát hiện docs lệch code, lint, gate test, dựng preview, đồng bộ Jira, tick plan |
| **AI soạn, người duyệt** | brainstorm, SRS, story/AC, `design.md`, `plan.md`, code, test, báo cáo CR, báo cáo bug |
| **Chỉ người làm** | Chốt scope với stakeholder, quyết định kiến trúc (ký ADR), duyệt CR, merge, phát hành, UAT |

### 3.4 Cổng duyệt phía dev

Mỗi cổng là một trường `status` trong frontmatter của file tương ứng.

1. **SRS approved:** điều kiện để vào dev.
2. **`design.md` approved:** chỉ áp dụng từ L2.
3. **`plan.md` approved.**
4. **Review diff:** có đủ ánh xạ FR → test.
5. **Release.**

## 4. Quy ước thư mục và ID

### 4.1 Thư mục

```text
docs/<feature>/
  brainstorms/<slug>.md      # BA
  srs/spec.md, flows.md, states.md, erd.md
  html-wireframe/
  userstories/
  dev/design.md, plan.md     # dev
  cr/CR-YYYYMMDD-NNN.md
  bugs/<date>-<slug>.md
docs/_shared/traceability.md # sinh tự động
```

### 4.2 ID

| Tiền tố | Ý nghĩa | Nơi định nghĩa |
|---|---|---|
| `FR-<feature>-NNN` | Yêu cầu chức năng | SRS |
| `NFR-<feature>-NNN` | Yêu cầu phi chức năng | SRS |
| `BR-<feature>-NNN` | Luật nghiệp vụ | SRS |
| `E-<feature>-NNN` | Ca lỗi | SRS |
| `SC-<feature>-NN` | Tiêu chí thành công | SRS |
| `OQ-n` | Câu hỏi mở | brainstorm/SRS |
| `T-<feature>-NN` | Task dev | `plan.md` |
| `CR-YYYYMMDD-NNN` | Yêu cầu thay đổi | `cr/` |

## 5. Ánh xạ sang plugin `dev-workflow`

| Skill | Vai trò trong workflow |
|---|---|
| `dev-triage` | Đọc FR liên quan, chọn làn L0–L3. Làn quyết định có cần cổng 2 hay không |
| `spec-plan` | Từ `srs/spec.md` sinh `dev/design.md` và `dev/plan.md` có `covers: FR-…` |
| `bug-investigation` + CR | Sinh `bugs/…md` và `cr/…md`, báo cáo trước, sửa sau khi duyệt |
| `session-closeout` | Cập nhật `traceability.md`, tick plan, đồng bộ Jira |
| `trace-check` (mới) | Script kiểm mọi FR đều có task và test |
