## Tóm tắt

Đã triển khai panel agent/sidebar Paseo gọn trong scope được giao. Code dùng `compactTree` chọn dữ liệu và `rowText`/`summaryText` cho UI thật; fixture sau dùng chính các hàm này. Chưa build/reload/cài đặt, chưa full hybrid-hands; Sol giữ các bước cuối. Native token/quota: `?` khi nguồn không cấp.

## Quyết định

- Giữ ●/✓/✗/?, tên ngắn (32 ký tự), model·effort, elapsed, USD~. Quota tài khoản 5h/tuần mỗi account plan trong cây chỉ root; thiếu `?`. Chọn nguyên sample đủ window hơn, tie giữ sample đầu (root trước), không cộng/gộp window khác nguồn; không suy quota giữa Claude/GPT. Usage không có plan/sample không thêm TK giả vào cây có account rõ; hoàn toàn thiếu thì fallback TK5h?/tuần?. Bỏ khối LimitsBlock khỏi TreeView, header/footer, cwd/description/labels và text/mốc ended. Không render orphan hand-ext.
- `MAX_SIDE_SESSIONS=4`: flatten hậu duệ mỗi root, ưu tiên running rồi max ended/started, tie giữ thứ tự duyệt cây/agent đầu vào; hidden có summary done/error/running/unknown. Không mất agent của hidden side.
- Latest độc lập mỗi root theo max last_activity/ended/started và timestamp agent con; tie giữ thứ tự duyệt cây/agent đầu vào, không ép is_main. `MAX_SUBAGENTS=4` chung pool `subagents` + hand_runs có parent_session khớp. Các phiên khác/overflow chỉ summary. Hidden latest giữ agent mở dưới nhãn tên latest, không thêm full session row.
- Error (status/state lỗi hoặc exit/exit_code khác 0) trước running. Running live/status/state trước success cũ. Success từ status rõ hoặc exit 0; state=finished đơn thuần không xác nhận success. Unknown thật giữ ?.
- Running elapsed now−start; finished dùng ended−start hoặc duration có sẵn. Không có dữ liệu thời gian thì ?.

## Files đổi thực so baseline được giao

- `AGENTS.md` chỉ thêm ngoại lệ panel trong contract.
- `hybrid-hands/README.md` chỉ cross-ref mục6 và đoạn mục8.
- `hybrid-hands/paseo-hh-tree/OVERVIEW.md`.
- Panel: `client/compact.ts` (mới), `client/compact.test.ts` (mới, đúng3ca), `client/SessionBlock.tsx`, `client/ChildRows.tsx`, `client/TreeView.tsx`, `shared/tree.ts`.
- Manifest `plugin.json` 0.28.0 và changelog0.28.0. Đã gộp đúng bullet cc-switch Sol giao; không sửa code/test của phiên khác.
- `hand-*` evidence tại thư mục này. Danh sách máy kiểm trong `hand-doc-check.log`. Không sửa format.ts/format.test.ts/package/tsconfig/server so baseline; các thay đổi đó đã có trước hand.

## Kiểm chứng thật

- `node --experimental-strip-types --test client/*.test.ts`: exit0, 15 tests pass/0 fail, trong đó3ca mới. Log `hand-tests.log`.
- `npm run typecheck`: exit0. Log `hand-typecheck.log`.
- `node --experimental-strip-types docs/work-in-progress/panel-gon/hand-sample-fixture.ts`: exit0; `hand-samples.log`. Mẫu trước tái dựng từ baseline row template + baseline formatter; mẫu sau chạy formatter/selector được UI dùng. Đây là fixture với model/plan/name placeholders, không phải runtime RPC, ảnh UI hay bản cài.
- Python json.loads manifest + kiểm file đích của link mới/chỉnh: exit0; `hand-doc-check.log`.
- Có một lần đỏ lúc phát triển: câu lệnh sửa dùng workdir panel nhưng path repo-relative nên Python FileNotFoundError exit1; test chạy sau đó 14/15, ca b fixture recent side bị hidden ngoài dự tính (`hiddenAgents`3 thay vì1). Đã sửa đường dẫn tuyệt đối và fixture ended timestamp rõ; giữ thêm assert hidden-latest trong chính ca b, final15/15.
- Node có warning MODULE_TYPELESS_PACKAGE_JSON từ setup hiện hữu. Không đổi package để dọn warning.

## Giới hạn/việc Sol giữ

- `hh_ps/render.py` chỉ xuất `subagents` Claude và hand_runs; không có native Codex child source. Panel không tự dựng native hay sửa lib/hh_ps ngoài scope. Nếu tương lai native được đưa vào `subagents`, pool/summary chung dùng được; hiện chưa xác minh pipeline native runtime và không claim đã hiển thị native.
- `hh_ps` hiện không xuất exit_code/exit trong hand/subagent JSON; schema panel đã nhận optional để phân loại đúng khi có. Status hh_ps vẫn là bằng chứng hiện có; thiếu evidence giữ unknown.
- Full build/full suite/reload/update/install/runtime RPC do Sol thực hiện sau review. Hand không đọc dữ liệu runtime/log thật, không gọi API, không tạo tiến trình nền.
- Changelog đã ghi việc cc-switch theo thông tin Sol giao; hand không review việc hand khác.
