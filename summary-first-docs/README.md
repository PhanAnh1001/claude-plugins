# summary-first-docs

## Tóm tắt

- **Mục đích:** marketplace Claude Code tự host (`summary-first-docs-local`) chứa plugin
  **summary-first-docs**: bốn skill viết tài liệu dùng chung cho mọi dự án, không phụ thuộc
  repo nào.
- **Bốn skill:** `structuring-documents` (tóm tắt trước, top-down), `citing-sources` (dẫn nguồn
  `http(s)` kèm ngày dữ liệu), `documenting-solutions` (tài liệu giải pháp đang hiệu lực trong
  `docs/solutions/`), `saving-research` (lưu nghiên cứu vào `docs/research/`).
- **Phiên bản:** 1.0.0. Không có hook, agent hay script; chỉ có skill.
- **Luật dự án ưu tiên:** đường dẫn, ngôn ngữ, giới hạn số dòng khai báo trong `AGENTS.md` /
  `CLAUDE.md` của dự án thắng giá trị mặc định của skill.
- **Việc cần làm:** cài một lần ở scope `user` (mục Cài đặt); sau mỗi lần sửa skill thì tăng
  `version` và chạy lệnh cập nhật.

## Bố cục

```
.claude-plugin/marketplace.json           marketplace summary-first-docs-local
plugins/summary-first-docs/
  .claude-plugin/plugin.json              tên, version
  skills/structuring-documents/SKILL.md   tóm tắt trước, nhóm -> nhánh
  skills/citing-sources/SKILL.md          dẫn nguồn, nhãn số liệu
  skills/documenting-solutions/SKILL.md   tài liệu giải pháp + template.md (tiêu đề tiếng Việt)
  skills/saving-research/SKILL.md         lưu nghiên cứu + template.md (khuôn báo cáo)
```

## Bốn skill

| Skill | Dùng khi | Kết quả |
|---|---|---|
| `structuring-documents` | viết/sửa mọi tài liệu (README, spec, plan, báo cáo, SKILL.md) | tài liệu mở bằng tóm tắt (mục đích, kết luận, con số, việc cần làm), phần chi tiết theo thứ tự nhóm -> nhánh |
| `citing-sources` | có số liệu, sự kiện, kết luận từ bên ngoài (báo cáo, giải pháp, câu trả lời chat) | mỗi claim có link `http(s)` nguồn mới nhất + ngày dữ liệu; nhãn chưa xác minh / vendor tự công bố / suy luận / đã bị thay / chưa có nguồn internet |
| `documenting-solutions` | xong một task, đổi/bỏ/thay một giải pháp | mỗi giải pháp một file `docs/solutions/<group>/<branch>/<solution>.md`, mục lục `docs/solutions/README.md` khớp cây thư mục |
| `saving-research` | nghiên cứu nhiều nguồn, kể cả skill `deep-research` | `docs/research/<YYYY-MM-DD>-<slug>/report.md` + `notes/<topic>.md` + mục lục `docs/research/README.md` |

Không có skill ghi quyết định: plugin không bắt buộc `docs/decisions.md` hay đánh số quyết
định. Dự án có nhật ký quyết định riêng thì `documenting-solutions` link tới mục liên quan.

## Cài đặt

Từ shell, thay `<thư-mục-repo>` bằng nơi clone repo `claude-plugins`:

```sh
claude plugin marketplace add <thư-mục-repo>/summary-first-docs
claude plugin install summary-first-docs@summary-first-docs-local --scope user
claude plugin list
```

`claude plugin list` phải có `summary-first-docs@summary-first-docs-local`, `Scope: user`,
`Status: enabled`. Skill có hiệu lực từ phiên Claude Code kế tiếp (hoặc `/reload-plugins`).

## Cập nhật

Sau khi sửa skill: tăng `version` trong `plugins/summary-first-docs/.claude-plugin/plugin.json`,
kiểm manifest rồi cập nhật:

```sh
claude plugin validate <thư-mục-repo>/summary-first-docs
claude plugin validate <thư-mục-repo>/summary-first-docs/plugins/summary-first-docs
claude plugin marketplace update summary-first-docs-local
claude plugin update summary-first-docs@summary-first-docs-local
```

Lúc cài, Claude Code chép một bản vào thư mục cache plugin của người dùng; không tăng `version`
thì bản cache có thể không được làm mới.
