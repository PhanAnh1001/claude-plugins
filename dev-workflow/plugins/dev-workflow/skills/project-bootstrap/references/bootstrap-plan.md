---
id: plan-project-bootstrap
status: draft
lane: L2
last-reviewed: YYYY-MM-DD
---

# Kế hoạch khởi tạo dự án <tên dự án>

## Tóm tắt

- **Mục đích:** đưa dự án từ repo trống tới vòng dev từng task theo 7 giai đoạn của skill
  `dev-workflow:project-bootstrap`; mỗi ô là một tiêu chí hoàn thành, chỉ tick khi sản phẩm đã có và
  đã kiểm.
- **Giai đoạn hiện tại:** <0–6>.
- **Chốt duyệt của người dùng:** luật repo và config (GĐ 0), SRS và câu hỏi mở (GĐ 1), từng ADR (GĐ 2),
  danh sách epic (GĐ 3), lộ trình MVP (GĐ 4).
- **Người cần làm gì:** <việc đang chờ người dùng quyết định>.

## 1. Giai đoạn 0 — luật repo

- [ ] `AGENTS.md` (+ `CLAUDE.md` chứa `@AGENTS.md`), `README.md`, `.gitignore`
- [ ] `docs/index.md` và `docs/document-governance.md`
- [ ] `.claude/dev-workflow.toml` có `paths.*` và `[jira]`
- [ ] Người dùng duyệt luật và config

## 2. Giai đoạn 1 — yêu cầu

- [ ] SRS bản nháp có mã `FR-<nhóm>-NNN`, NFR
- [ ] Sổ câu hỏi mở `Q-NN` (người quyết, mốc bị chặn, trạng thái)
- [ ] Đối chiếu màn prototype với mã FR (nếu có prototype)
- [ ] Nghiên cứu quy mô hoặc thị trường đã lưu và dẫn nguồn (nếu cần)
- [ ] Người dùng duyệt SRS, chốt câu hỏi chặn mốc đầu

## 3. Giai đoạn 2 — kiến trúc và quyết định

- [ ] Kiến trúc tổng thể và sơ đồ luồng (Mermaid)
- [ ] ADR cấu trúc repo
- [ ] ADR stack và phiên bản
- [ ] ADR mẫu tích hợp (hợp đồng plugin, provider) nếu có
- [ ] ADR chính sách CI
- [ ] Tóm tắt AGENTS.md ghi mỗi quyết định một dòng kèm đường dẫn ADR

## 4. Giai đoạn 3 — backlog Jira

- [ ] Tài liệu `jira.guide`: epic, label, loại issue, nguồn dùng lại, thứ tự, rủi ro port
- [ ] Epic đã tạo trên Jira (dry-run, người dùng xác nhận)
- [ ] Luật nhánh và merge request trong AGENTS.md
- [ ] Task khảo sát hoặc đo chạy song song (nếu cần)

## 5. Giai đoạn 4 — lộ trình MVP

- [ ] Plan lộ trình M0..Mn, mỗi dòng `T-mvp-NN` có `covers:` và ước lượng
- [ ] `dw trace`: không còn FR thiếu task
- [ ] Câu hỏi mở chặn M0–M1 đã chốt
- [ ] Người dùng duyệt lộ trình
- [ ] Task Jira của các mốc đầu đã tạo, gán theo quy tắc, mã Jira ghi vào lộ trình

## 6. Giai đoạn 5 — khung code và gate (M0)

- [ ] Khung thư mục, môi trường dev local, CI, test runner, linter, khung deploy
- [ ] `gate.commands` và `gate.lint` điền lệnh thật, chạy xanh
- [ ] AGENTS.md mục "current state" ghi cách chạy local và gate
- [ ] Khung đã merge vào nhánh tích hợp

## 7. Giai đoạn 6 — chuyển sang vòng dev

- [ ] Task đầu tiên của M1 chạy qua `dev-workflow:dev-triage`
- [ ] Ước lượng đã hiệu chỉnh theo thời gian log thực tế của các task đầu

## Ghi chú

- <quyết định, lý do bỏ qua một tiêu chí, ngày chốt>
