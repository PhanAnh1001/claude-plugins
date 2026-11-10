# Brief Sol `native-child`: hiện subagent native Codex và exit code trên hh-ps và panel Paseo

## Tóm tắt

- Mục tiêu: cây `hh-ps` (text/JSON) có thêm subagent native Codex do Sol tạo theo ngoại lệ A. Panel Paseo hiện các subagent này dưới đúng phiên Sol cha, tính vào giới hạn 4 subagent và vào dòng đếm `X✓ Y✗`. Exit code/status của hand-ext và subagent được xuất ra để panel đếm lỗi đúng.
- Lane: L1 có lựa chọn giải pháp: chọn nguồn dữ liệu native. Bàn giao mở bằng tóm tắt quyết định ≤1 trang.
- Người dùng đã đồng ý làm phần này (07/11). Bản 0.28.0 đã phát hành ở phiên `release-028`, nên phiên này bump lên 0.29.0.

## Ngữ cảnh

- Bàn giao `docs/work-in-progress/handoffs/panel-gon.md`, mục "Nguồn native và metadata chưa có": hh-ps JSON chưa có native Codex child, cũng chưa xuất exit_code cho hand/subagent.
- Bàn giao `docs/work-in-progress/handoffs/sol-hand-paseo.md`: Paseo 0.15.0 có `listProviderSubagents`/`fetchProviderSubagentTimeline`. Native child còn có rollout riêng dưới `CODEX_HOME` `~/.codex-hand`, metadata rollout ghi model/effort/parent thread. Sol chọn nguồn đáng tin nhất, ưu tiên metadata có sẵn và không cần daemon nếu được.
- Contract 0.26.0 trong `AGENTS.md`: thêm field vào cuối dataclass, có default. Legacy unknown hiện `?`. Không bịa mốc hay quota. Native không có run/meta/report hand-ext: token/USD~ chỉ hiện khi nguồn native cấp, thiếu thì `?`. Với native, thiếu exit code thì suy status từ nguồn: completed → ✓, failed/errored/cancelled → ✗, còn lại → `?`.

## PHẠM VI GHI

- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/` (thêm source native, models, tree, JSON, render) cùng test tương ứng trong `hybrid-hands/tests/`, chỉ dùng fixture giả.
- `hybrid-hands/paseo-hh-tree/` (shared/server/client, test): hiện loại native và dùng exit/status mới.
- `hybrid-hands/hh-tree-pane/`: chỉ sửa khi cần để không vỡ do dữ liệu mới. Không thiết kế lại hh-tree-pane.
- Mục contract trong `AGENTS.md` và đoạn liên quan trong `hybrid-hands/README.md`; `plugin.json` + `CHANGELOG.md` mục 0.29.0.
- Bàn giao `docs/work-in-progress/handoffs/native-child.md` + `.done`, log ở `docs/work-in-progress/native-child/`.

## KHÔNG ĐƯỢC ĐỤNG

`statusline/`, `lib/hand_ext/` (trừ khi exit_code phải ghi thêm vào meta: chỉ thêm field, không đổi luồng run), `lib/cc_switch/`. Các file cấm theo `AGENTS.md`: `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `~/.paseo/config.json`, `installed_plugins.json` sửa tay, credential. Không `paseo daemon restart`. Không commit/push. Không xoá/di chuyển `output/llm/`. Giữ mọi thay đổi chưa commit.

## LUẬT BẮT BUỘC (chép nguyên văn vào brief hand ngoài)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

Sol tự đọc metadata rollout thật (model, effort, parent, status, mốc thời gian, token) để kiểm chứng. Không đọc nội dung hội thoại vào bàn giao. Không giao hand đọc rollout thật.

## KIỂM CHỨNG

- Mức test: tối thiểu. Tối đa 3 ca test:
  - (a) Fixture rollout native giả có parent là Sol → hh-ps JSON có node native dưới đúng Sol, model/effort/status đúng.
  - (b) Hand-ext exit ≠ 0 và native failed → panel đếm vào ✗.
  - (c) Native thiếu token → USD~ `?`, không lỗi.
- Trong lúc làm: test hẹp hh_ps và test panel, typecheck/build panel.
- Cuối, đúng một lần: full suite hybrid-hands. Full xanh thì làm tiếp:
  - Cập nhật bản cài mọi scope bằng CLI, rebuild và reload plugin Paseo (không restart daemon).
  - Kiểm thật: Sol tạo một native child low chỉ đọc. `hh-ps --once --json` và panel phải hiện child đó dưới Sol. Lưu mẫu đã làm sạch.
- Xong khi: 3 ca đạt, full xanh, bản cài 0.29.0, mẫu thật có native child.

## TRẢ VỀ

Bàn giao mở bằng `## Tóm tắt`: quyết định nguồn, file đổi, lệnh và kết quả thật, bản cài, mẫu hh-ps/panel, phần chưa kiểm chứng.
