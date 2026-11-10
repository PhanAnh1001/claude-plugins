## Tóm tắt

- Kết quả: **xong phần panel, xong một phần toàn brief**; bản phát hành bị chặn bởi full suite ngoài phạm vi sửa.
- Quyết định: dòng gọn bằng icon/tên/model·effort/elapsed/USD~, quota mỗi account một lần ở root; tối đa 4 phiên phụ và 4 subagent của latest, phần dư giữ đủ số đếm.
- File: 7 file panel + AGENTS.md, README, plugin.json và CHANGELOG; giữ thay đổi chưa commit trước task, không sửa lib/hand_ext, hh_ps, cc-switch hay các panel khác.
- Kiểm chứng panel: 15/15 test (đúng 3 ca mới), typecheck exit 0; final Paseo build client/server exit 0; JSON/link/diff và validate exit 0.
- Full duy nhất: `python3 -m unittest discover -s hybrid-hands/tests -q` → 415 test/47.486s, **413 đạt, 2 fail, exit 1**; không chạy lại.
- Hai lỗi: dsh User-Agent 0.27.0 lệch manifest 0.28.0; assertion hh-ps reset không nhận ngày kế tiếp. Đều ngoài PHẠM VI GHI.
- Bản cài: chưa update/reload vì full chưa xanh; CLI đọc lại 9 record user/project/local đều 0.27.0, source folder 0.28.0. Không sửa registry/settings thủ công.
- Runtime: RPC thành công; mẫu đã làm sạch qua JSX thật giảm 42 → 26 dòng. Đây là render text bằng host stub, chưa kiểm màn hình/điện thoại hoặc plugin sau reload.
- Còn mở: native Codex child chưa có trong JSON hh-ps; exit_code/exit hand/subagent cũng chưa được xuất. Không claim đã hiển thị native hoặc phân biệt exit mà nguồn không cấp.
- Changelog 0.28.0 đã gộp ghi chú race PID từ bàn giao plan-con-mo. Một native hand đã kết thúc, Sol review xong; token/quota native `?`; không commit/push.

## Tóm tắt quyết định (≤1 trang)

- Giữ icon ●/✓/✗/?, tên ngắn tối đa 32 ký tự, model·effort, elapsed và USD~. Bỏ nhãn model/effort, root/side session, cwd, mô tả dư, trạng thái bằng chữ, mốc bắt đầu/kết thúc và header/footer giải thích. Thiếu dữ liệu giữ `?`.
- Quota 5h/tuần của từng account plan trong cây hiện một lần ở root. Chọn nguyên sample có nhiều window hơn, tie giữ sample đầu/root trước; không cộng hay ghép window từ hai sample, không suy quota Claude sang GPT. Hoàn toàn thiếu nguồn thì `TK 5h ? · tuần ?`.
- Mỗi root flatten hậu duệ thành tối đa 4 dòng phiên phụ: running trước, sau đó max ended/started mới nhất; tie giữ thứ tự duyệt cây. Phần dư `+N cũ: X✓ Y✗`, thêm `●N` hoặc `?N` khi có.
- Trong từng cây root, latest là phiên có max last_activity/ended/started và mốc hoạt động agent con; tie giữ thứ tự duyệt, không ép is_main. Chỉ latest mở tổng tối đa 4 subagent/hand có parent khớp, cùng luật ưu tiên. Các agent khác gộp số, kể cả phiên ẩn; latest bị ẩn giữ agent dưới nhãn tên phiên trong phần gộp, không thêm full session row thứ năm.
- Error/exit khác 0/timeout/killed ưu tiên trước running; running trước success cũ. Chỉ status thành công rõ hoặc exit 0 xác nhận done; state=finished đơn thuần vẫn unknown. Duration running tăng theo now−start, đã xong cố định ended−start hoặc duration có sẵn.
- `MAX_SIDE_SESSIONS=4`, `MAX_SUBAGENTS=4` chỉ ở panel, không thêm setting. Không render orphan hand-ext. Native/exit metadata chưa có nguồn được ghi là hạn chế, không sửa hh-ps hay dựng dữ liệu giả.

## File thay đổi và review Sol

Danh sách dưới so với [baseline trước task](../panel-gon/baseline/), không so toàn bộ dirty repo với HEAD. [Danh sách máy đọc](../panel-gon/changed-files.json).

| File | Lý do |
|---|---|
| [compact.ts](../../../hybrid-hands/paseo-hh-tree/client/compact.ts) | Chọn/gộp phiên và agent, trạng thái, elapsed, quota từng account; hai constant 4. |
| [compact.test.ts](../../../hybrid-hands/paseo-hh-tree/client/compact.test.ts) | Đúng 3 ca acceptance, gồm biên running/unknown/hidden/mixed quota. |
| [SessionBlock.tsx](../../../hybrid-hands/paseo-hh-tree/client/SessionBlock.tsx) | Render view gọn dùng selector/formatter chung, giữ count phần ẩn. |
| [ChildRows.tsx](../../../hybrid-hands/paseo-hh-tree/client/ChildRows.tsx) | Dòng agent/hand dùng format gọn, bỏ quota và chữ trạng thái lặp. |
| [TreeView.tsx](../../../hybrid-hands/paseo-hh-tree/client/TreeView.tsx) | Bỏ header/footer và khối quota lặp; agent panel/sidebar dùng cùng cây. |
| [shared/tree.ts](../../../hybrid-hands/paseo-hh-tree/shared/tree.ts) | Nhận status/state mở rộng và exit_code/exit optional; không sửa JSON upstream. |
| [OVERVIEW.md](../../../hybrid-hands/paseo-hh-tree/OVERVIEW.md) | Cập nhật contract panel và giới hạn nguồn. |
| [AGENTS.md](../../../AGENTS.md) | Chỉ bổ sung ngoại lệ panel trong mục Contract dữ liệu và hiển thị 0.26.0. |
| [README.md](../../../hybrid-hands/README.md) | Sửa mục panel Paseo và cross-ref ngắn ở contract chung. |
| [plugin.json](../../../hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json) | Bump source 0.27.0 → 0.28.0. |
| [CHANGELOG.md](../../../hybrid-hands/plugins/hybrid-hands/CHANGELOG.md) | Thêm 0.28.0 và gộp bullet cc-switch từ plan-con-mo. |

Sol đọc diff hand so baseline, kiểm UI dùng selector/formatter, scope, orphan, quota, hidden count và schema. Review yêu cầu sửa state=finished không tự đồng nghĩa success; running không bị success cũ nuốt; quota mixed Claude/GPT không mất và không trộn sample; tài liệu tie theo thứ tự đầu vào thống nhất. Bản cuối không đổi format.ts/format.test.ts/package/tsconfig/server so baseline; các dirty change ở đó đã có trước task. Không review code của hand/phiên plan-con-mo; chỉ đọc bàn giao để gộp changelog.

## Kiểm chứng thật

| Lệnh / kiểm tra | Kết quả |
|---|---|
| `node --experimental-strip-types --test client/*.test.ts` (cwd panel, hand chạy) | 15/15, exit 0; [log](../panel-gon/hand-tests.log). |
| `npm run typecheck` (cwd panel, hand chạy) | Exit 0; [log](../panel-gon/hand-typecheck.log). |
| `node docs/work-in-progress/panel-gon/qa-build.mjs` (Sol, final đúng một lần) | Paseo 0.15.0 compileDirectoryPlugin exit 0, client 20,963 bytes / server 15,657 bytes; [hash/kết quả](../panel-gon/final-build.json). |
| `python3 -m unittest discover -s hybrid-hands/tests -q` (Sol, full đúng một lần) | 415 test, 47.486s, 2 fail, exit 1; [log](../panel-gon/full-hybrid-hands.log), [JSON](../panel-gon/full-hybrid-hands.json). |
| `claude plugin validate hybrid-hands` và `claude plugin validate hybrid-hands/plugins/hybrid-hands` | Exit 0 / validation passed. Plugin check báo metadata LICENSE/icon thiếu ở profile directory, không chặn local validation; không sửa metadata ngoài brief. |
| JSON manifest, link đích tài liệu, `git diff --check --` các file trong scope | Đạt; [hand doc check](../panel-gon/hand-doc-check.log). |
| `node docs/work-in-progress/panel-gon/qa-runtime.mjs` | RPC thật exit 0; chỉ giữ metadata đã làm sạch; [metadata](../panel-gon/runtime-metadata.json). |
| `node docs/work-in-progress/panel-gon/qa-render.mjs` | Dựng SessionBlock baseline/bản cuối từ cùng snapshot đã làm sạch, exit 0; 42 → 26 dòng. |

Ba ca mới: (a) 6 side → 4 + `+2 cũ: 1✓ 1✗`, running ưu tiên, overflow running/unknown không mất; (b) chỉ latest mở ≤4 agent chung pool, phiên khác/hidden chỉ count, lỗi/exit/state unknown đúng; (c) child không quota/chữ đang chạy/nhãn dư, thiếu vẫn ?, elapsed tăng rồi cố định, quota Claude/GPT giữ nguyên sample. Không thêm ca thứ tư.

Hand có một lỗi thao tác đường dẫn exit 1 và một lượt test 14/15 do fixture timestamp khiến recent side bị hidden; đã sửa fixture và chạy hẹp xanh trước bàn giao. Log hẹp cuối được lưu; [report hand](../panel-gon/hand-report.md) ghi cả lượt đỏ. Node warning MODULE_TYPELESS_PACKAGE_JSON có từ setup hiện hữu; không đổi package để dọn warning. Không có lượt full thứ hai.

## Hai lỗi full và ranh giới

1. [dsh.py:73](../../../hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/dsh.py#L73) còn `hybrid-hands-hand-ext/0.27.0`; [test_hand_ext_dsh.py:475](../../../hybrid-hands/tests/test_hand_ext_dsh.py#L475) so bằng manifest 0.28.0. Đây là blocker version đã phát hiện trước full. Brief cấm sửa lib/hand_ext và test ngoài panel nên không đồng bộ hộ, không lách test hoặc lùi version.
2. [test_hh_ps_codex.py:122](../../../hybrid-hands/tests/test_hh_ps_codex.py#L122) chỉ nhận `reset HH:MM`; fixture [NOW=time.time()](../../../hybrid-hands/tests/fixtures/hh_ps/fixture.py#L25), reset ở NOW+3600. Full chạy 23:19 +07 ngày 07/11 nên output hợp lệ là `reset 08/11 00:19`. [timeutil.py](../../../hybrid-hands/plugins/hybrid-hands/lib/hh_ps/timeutil.py) chọn dd/mm khi khác ngày. Kết luận từ log + đọc code, không chạy thêm test; test/file renderer nằm ngoài scope và giữ nguyên.

Full chưa xanh nên không gọi marketplace update/plugin update/install hoặc Paseo plugin reload. [9 bản ghi trước](../panel-gon/installed-before.json) và [đọc lại sau](../panel-gon/installed-not-updated.json) đều đăng ký 0.27.0 ở user/project/local; folderVersion sau là 0.28.0 vì source đã bump. Không tuyên bố bản cài 0.28.0. Không sửa installed_plugins.json/settings/config bằng tay.

## Nguồn native và metadata chưa có

Runtime metadata qua SDK CLI: RPC có 20 session, 5 subagent, 17 hand, 61 orphan record upstream; renderer không dựng orphan. Paseo `listProviderSubagents` cho parent hiện tại có 1 native child, exact ID không xuất hiện trong snapshot (`native_in_tree=0`). Không đọc timeline/transcript để kiểm việc này. Snapshot hiện tại chỉ đủ Claude subagents và hand/side sessions; panel sẵn chung pool nếu native được cấp qua JSON, nhưng task này chưa bổ sung pipeline đó.

[render.py:54](../../../hybrid-hands/plugins/hybrid-hands/lib/hh_ps/render.py#L54) và :75 cũng chưa xuất exit_code/exit cho hand/subagent; schema panel nhận optional này nhưng không thể phân loại bằng evidence bị thiếu. Source status hiện có vẫn được dùng, unknown giữ ?. Cần gói có quyền sửa nguồn/tests để đóng các mục này; task panel-gon không mở rộng phạm vi.

## Mẫu panel trước/sau

Đây là cùng snapshot RPC thật, đã bỏ tên/ID/đường dẫn/mô tả trước khi lưu hoặc dựng. [Verifier](../panel-gon/qa-render.mjs) chạy JSX SessionBlock thật bằng host stub React Native, không phải ảnh màn hình app; panel đang chạy chưa reload. Toàn bộ [trước](../panel-gon/panel-before.txt) / [sau](../panel-gon/panel-after.txt), trích cây đầu:

Trước:

```text
▾ ● Phiên 1 (root session) MODEL/EFFORT claude-opus-5-5/high · rảnh · ~$0.84 · Claude 5h ? · tuần 13.5% · riêng ~0.1% tuần · chạy 6p · kết thúc đang chạy
  ● phiên phụ Phụ 11 (side session) MODEL/EFFORT gpt-6.1-sol/high · rảnh · ~$0.41 · GPT 5h ? · tuần 14.0% · chạy 4p · kết thúc đang chạy
  ▾ ● phiên phụ Phụ 12 (side session) MODEL/EFFORT gpt-6.1-sol/high · rảnh · ~$0.39 · GPT 5h ? · tuần 14.0% · chạy 4p · kết thúc đang chạy
    • codex MODEL/EFFORT gpt-6.1-sol/low · Hand 1 · xong · ~$0.06 · GPT 5h ? · tuần 14.0% · 16s · 2026-11-07 23:08
```

Sau:

```text
▾ ● Phiên 1 · claude-opus-5-5·high · 6p · ~$0.84 · Claude 5h ? · tuần 13.5% · GPT 5h ? · tuần 14.0%
  ● Phụ 12 · gpt-6.1-sol·high · 4p · ~$0.39
    ✓ Hand 1 · gpt-6.1-sol·low · 16s · ~$0.06
  ● Phụ 11 · gpt-6.1-sol·high · 4p · ~$0.41
```

Fixture công khai 6 phiên phụ / 6 agent ở latest, model/plan/name đều là placeholder; sau dùng selector/formatter của UI (mẫu trước đầy đủ trong [log fixture](../panel-gon/hand-samples.log)):

```text
● main-fixture · fixture-model·low · 1g · ~$0.12 · Fixture 5h 12.0% · tuần 34.0%
    1 subagent: 1✓ 0✗
  ● side-0 · fixture-model·low · 1g · ~$0.01
    ● worker-0 · fixture-model·low · 40p · ~$0.01
    ✓ worker-5 · fixture-model·low · 15p · ~$0.01
    ✓ worker-4 · fixture-model·low · 14p · ~$0.01
    ✓ worker-3 · fixture-model·low · 13p · ~$0.01
    2 subagent: 2✓ 0✗
  ✓ side-5 · fixture-model·low · 15p · ~$0.01
  ✓ side-4 · fixture-model·low · 14p · ~$0.01
  ✓ side-3 · fixture-model·low · 13p · ~$0.01
  +2 cũ: 1✓ 1✗
```

## Điều phối và phần chưa kiểm chứng

Dùng ngoại lệ A của [ext-hand SKILL.md](../../../hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md) và [paseo SKILL.md](../../../hybrid-hands/plugins/hybrid-hands/skills/paseo/SKILL.md): Sol trên Paseo, repo order codex/gpt-6.1-sol/low, native tools hỗ trợ model/effort. Một hand native `panel_impl`, fork_turns=none, full brief 7 mục và luật dữ liệu; executor không recursion/giao tiếp phiên khác, thực chạy 1 dưới cap mặc định 4. Hand đã completed và Sol review; giữ history, không archive parent. Native không có run/meta/report/ledger hand-ext; token/quota/USD~ không được runtime cấp nên `?`, không dùng số hand-ext khác gán sang native.

Chưa kiểm GUI/điện thoại, plugin sau reload, bản cài 0.28.0, native trong panel, hay lượt full xanh. [plan-con-mo](plan-con-mo.md) có mục provider codex runtime còn enabled chưa giải quyết; đây là config/daemon ngoài scope panel, không sửa hoặc reload daemon. Các tiến trình verifier/test do phiên này tạo đã kết thúc, client đóng, esbuild service dừng. Không commit/push, không xoá/di chuyển output/llm, không mở auth/.env hoặc dùng API key.
