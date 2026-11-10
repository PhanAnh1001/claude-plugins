# Brief Sol `panel-gon`: panel Paseo gọn, giới hạn 4 phiên phụ / 4 subagent

## Tóm tắt

- Mục tiêu: panel agent và sidebar Paseo (`hybrid-hands/paseo-hh-tree/`) chỉ còn chữ cần thiết; mỗi phiên chính hiện tối đa 4 phiên phụ; chỉ phiên gần nhất hiện tối đa 4 subagent; phần cũ hơn gộp thành dòng đếm xong/lỗi.
- Lane: L1 có lựa chọn giải pháp → mở bàn giao bằng tóm tắt quyết định ≤1 trang (danh sách chữ giữ/bỏ, luật chọn "gần nhất").
- Phạm vi: chỉ panel Paseo. `hh-ps` text/JSON, `hh-tree-pane`, statusline giữ nguyên.
- Phiên Sol khác (`plan-con-mo`) đang chạy song song trên `lib/hand_ext/`, test PID, cc-switch. Không đụng các file đó; phiên này giữ quyền bump version.

## Yêu cầu của người dùng (nguyên văn)

"tối ưu hiển thị panel paseo giảm text chỉ giữ lại text cần thiết, hiển thị 4 phiên phụ trong phiên chính và 4 subagent trong phiên gần nhất, các phiên và subagent cũ thì tóm tắt số lượng done và false"

## Quyết định mặc định của Opus (Sol được chỉnh nếu có lý do, ghi vào tóm tắt quyết định)

1. Chữ trên mỗi dòng: icon trạng thái (đang chạy / xong / lỗi) thay cho chữ `đang chạy`/mốc kết thúc; tên ngắn; `model·effort` gọn; elapsed; `USD~`. Quota tài khoản (5h/tuần) hiện một lần ở dòng đầu phiên chính hoặc header, không lặp trên mỗi dòng con. Bỏ nhãn lặp, tiêu đề cột, chữ giải thích. Thiếu dữ liệu vẫn `?` (không bịa).
2. Phiên phụ: dưới mỗi phiên chính hiện tối đa 4 phiên phụ; đang chạy ưu tiên, sau đó gần nhất theo mốc kết thúc/bắt đầu. Phần còn lại gộp một dòng dạng `+N cũ: X✓ Y✗`.
3. Subagent (subagent Claude, native Codex child, hand-ext có phiên cha): chỉ phiên gần nhất (phiên có hoạt động mới nhất trong cây: phiên chính hoặc phiên phụ) hiện tối đa 4 subagent, cùng thứ tự ưu tiên; subagent cũ hơn và subagent của mọi phiên khác chỉ hiện dòng đếm `N subagent: X✓ Y✗`.
4. "done" = hoàn tất thành công; "false" = lỗi: failed/error, exit ≠ 0, timeout, killed. Trạng thái không rõ chỉ hiện `?N` khi N > 0; đang chạy không bao giờ bị ẩn khỏi số đếm.
5. Số 4 là hằng số đặt tên rõ trong code panel, không thêm config/settings.
6. Vẫn tuyệt đối không hiện nhóm orphan hand-ext ở panel.

## PHẠM VI GHI

- `hybrid-hands/paseo-hh-tree/` (client/, server/, shared/, test, OVERVIEW.md, package.json nếu cần).
- Mục "Contract dữ liệu và hiển thị 0.26.0" trong `AGENTS.md` gốc repo và đoạn panel trong `hybrid-hands/README.md`: cập nhật đúng phần panel Paseo cho khớp hành vi mới (ngắn, giữ cấu trúc).
- Bump `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json` + `plugins/hybrid-hands/CHANGELOG.md` lên 0.28.0 (phiên `plan-con-mo` sẽ không bump; nếu nó bàn giao trước có ghi chú changelog thì gộp vào cùng mục 0.28.0).
- Bàn giao: `docs/work-in-progress/handoffs/panel-gon.md` + `.done`; log/bằng chứng: `docs/work-in-progress/panel-gon/`.

## KHÔNG ĐƯỢC ĐỤNG

`lib/hand_ext/`, `lib/cc_switch/`, test PID/cc-switch, `hybrid-hands/hh-tree-pane/`, `statusline/`, `lib/hh_ps/` (trừ khi panel thiếu trường dữ liệu bắt buộc thì ghi vào bàn giao, không tự sửa). Giữ mọi thay đổi chưa commit hiện có. Các file cấm sửa theo `AGENTS.md`. Không commit/push. Không xoá/di chuyển `output/llm/`.

## LUẬT BẮT BUỘC (chép nguyên văn vào brief hand ngoài)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## KIỂM CHỨNG

- Mức test: tối thiểu. Ca test (tối đa 3): (a) 6 phiên phụ → hiện 4 + dòng `+2 cũ` đếm đúng xong/lỗi; (b) chỉ phiên gần nhất hiện ≤4 subagent, phiên khác chỉ dòng đếm; (c) dòng con không còn quota/chữ `đang chạy`, thiếu dữ liệu vẫn `?`.
- Trong lúc làm: test hẹp của `paseo-hh-tree` (format/tree test) và typecheck/build panel.
- Cuối cùng, đúng một lần: build panel + full suite hybrid-hands. Xanh thì cập nhật bản cài mọi scope bằng CLI như các đợt trước (`hybrid-hands/README.md`), reload plugin Paseo, chụp mẫu text panel đã làm sạch (không dữ liệu nhạy cảm) vào `docs/work-in-progress/panel-gon/`.
- Xong khi: 3 ca đạt, full xanh, bản cài 0.28.0, mẫu panel trước/sau trong bàn giao.

## TRẢ VỀ

Bàn giao mở bằng khối `## Tóm tắt` (kết quả, quyết định, file đổi, lệnh test và kết quả thật, bản cài, phần chưa kiểm chứng), sau đó tóm tắt quyết định ≤1 trang và mẫu panel trước/sau.
