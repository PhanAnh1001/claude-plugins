## Tóm tắt

**Kết quả: xong một phần.** Native child 0.29.0 và addon panel đã được triển khai, review và có bằng chứng metadata live thành công.
Nhóm thay đổi: hh_ps thêm native/exit/tổng máy; Paseo thêm màu/giờ kết thúc/phần riêng; pane sửa tương thích; contract và release lên 0.29.0.
Còn 6 registry worktree ở 0.27.0 dù cả 10 thư mục nguồn đều là 0.29.0; CLI update chưa sửa được lệch này.
Full suite chạy đúng một lần, 417 OK, nhưng addon đến **trong lúc full đang chạy**; không có final full bao phủ addon.
Sau addon đã chạy kiểm tra hẹp, typecheck và build; không chạy lại full để giữ giới hạn một lần.
Paseo hh-tree đã reload, enabled/running; chưa xác minh GUI thiết bị hay ảnh điện thoại.
USD~ là ước tính subscription offline, không phải hóa đơn. GPT tổng tuần và phần riêng chưa đủ nguồn vẫn `?`.
Không commit/push, sửa registry/config thủ công, restart daemon hay dọn output.

## Quyết định và phạm vi

Native chỉ lấy metadata rollout cố định `~/.codex-hand/sessions`, không cần daemon/RPC làm nguồn. Parent thread từ session_meta được đối chiếu pinned Sol rollout về sid canonical. Child nằm trong Session.subagents, không tạo run/meta/report/token ledger hand-ext. task_complete/completed là xong; failed/errored/cancelled hoặc exit khác 0 là lỗi; unknown giữ `?`, không suy từ im lặng/mtime.

Panel giữ 4 phiên phụ, pool 4 agent, lựa chọn phiên gần nhất và số đếm phần ẩn; bỏ orphan. Mỗi dòng có USD~, provider và usage.week_pct riêng, không thay bằng quota tài khoản. Giờ kết thúc local HH:MM, thêm dd/mm nếu khác ngày; không hiện giờ bắt đầu. Màu theo trạng thái, có fallback xanh dương tương phản nếu accent không xanh. hh-tree-pane chỉ sửa tương thích một file, không nhận thiết kế addon.

`machine_usage` độc lập cây đang hiển thị. Claude dùng tổng hợp tuần cục bộ; GPT đọc token delta metadata ở sessions và archived_sessions, khử trùng thread trong cửa sổ tuần hiện tại; thiếu cửa sổ/giá/nguồn giữ unknown, không cộng trùng ledger/rollout. Giá từ nguồn canonical, không suy quota GPT. Xem [quyết định](../native-child/decision.md), [24 file](../native-child/changed-files.json) và [patch phạm vi](../native-child/task-changes.patch).

## Từng file thay đổi

- `AGENTS.md`: Contract dữ liệu và panel 0.29.0.
- `hybrid-hands/README.md`: Hướng dẫn nguồn native và addon panel.
- `hybrid-hands/hh-tree-pane/hooks/tree.ts`: Tương thích native status/exit/unknown; không đổi bố cục addon.
- `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md`: Lịch sử release 0.29.0.
- `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json`: Phiên bản plugin 0.29.0.
- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/tree.py`: Ghép native và tổng usage vào snapshot.
- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/models.py`: Field mặc định tương thích cho status/exit/machine usage.
- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/usage_enrichment.py`: Enrichment usage và nguồn tổng hợp.
- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/render.py`: Xuất JSON native/exit/machine usage.
- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/compact.py`: Phân loại trạng thái native cho compact output.
- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/registry_source.py`: Giữ exit code từ registry.
- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/text_render.py`: Hiển thị trạng thái native trong text.
- `hybrid-hands/tests/test_hh_ps.py`: Cập nhật assertion các khóa JSON hiện có.
- `hybrid-hands/paseo-hh-tree/OVERVIEW.md`: Contract panel và nguồn dữ liệu.
- `hybrid-hands/paseo-hh-tree/shared/tree.ts`: Kiểu dữ liệu native/machine usage cho panel.
- `hybrid-hands/paseo-hh-tree/client/SessionBlock.tsx`: Dòng session, trạng thái, giờ kết thúc và usage riêng.
- `hybrid-hands/paseo-hh-tree/client/ChildRows.tsx`: Dòng child, trạng thái, giờ kết thúc và usage riêng.
- `hybrid-hands/paseo-hh-tree/client/compact.test.ts`: Ca panel native và addon.
- `hybrid-hands/paseo-hh-tree/client/TreeView.tsx`: Khối tổng tuần toàn máy ở đầu panel/sidebar.
- `hybrid-hands/paseo-hh-tree/client/compact.ts`: Pool và số đếm native/trạng thái.
- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/native_source.py`: Đọc metadata native cục bộ, gắn parent canonical.
- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/machine_usage.py`: Tổng tuần độc lập cây hiển thị, khử trùng thread GPT.
- `hybrid-hands/tests/test_hh_ps_native.py`: Hai ca Python native giả lập.
- `hybrid-hands/paseo-hh-tree/client/ColoredText.tsx`: Màu Text lồng nhau và fallback sáng/tối.

## Kiểm tra đã chạy

Các kết quả dưới đây do Sol cung cấp và kiểm chứng; hand tài liệu không chạy lại test/build/install.

| Lệnh/kiểm tra | Kết quả |
|---|---|
| `python3 -m unittest discover -s hybrid-hands/tests -q` | Một lần duy nhất, 417 OK, 47.303s; bắt đầu trước addon, không phải final full sau addon |
| `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hh_ps*.py'` | Sau addon: 90 OK, 1.838s |
| `node --experimental-strip-types --test client/*.test.ts` | Sau addon: 17 OK |
| `npm run typecheck` | Exit 0 |
| `node --experimental-strip-types --test hybrid-hands/hh-tree-pane/tests/tree.test.ts` | 3/3 |
| Paseo `compileDirectoryPlugin` | Exit 0; client 24821 bytes, server 16014 bytes |
| Scoped `git diff --check`, JSON, liên kết nội bộ | Đạt |
| `claude plugin validate hybrid-hands/plugins/hybrid-hands` | Exit 0, profile local mặc định; advisory LICENSE/icon sẵn có, ngoài phạm vi |

Có đúng 3 ca mới ban đầu (Python 2, panel 1), thêm 1 ca panel cho addon, tổng 4. Lỗi narrow ban đầu do expected JSON keys đã sửa trong assertion hiện có; narrow cuối xanh. Bằng chứng: [full JSON](../native-child/full-hybrid-hands.json), [full log](../native-child/full-hybrid-hands.log), [Python narrow](../native-child/python-narrow.log), [panel](../native-child/panel-addon-tests.log), [typecheck](../native-child/panel-addon-typecheck.log), [build](../native-child/paseo-build-final.json).

## Cài đặt và phần còn lại

Cả 10 lệnh `claude plugin update hybrid-hands@hybrid-hands-local --scope ... --json` exit 0; không đồng nghĩa cả 10 registry đã cập nhật.

| Scope/đích | Registry | Folder source |
|---|---|---|
| user | 0.29.0 | 0.29.0 |
| project ai-comic-video | 0.29.0 | 0.29.0 |
| project live-tiktok-games | 0.29.0 | 0.29.0 |
| local ai-luxian | 0.29.0 | 0.29.0 |
| project worktree RV-12c | 0.27.0 | 0.29.0 |
| project worktree RV-10b | 0.27.0 | 0.29.0 |
| project worktree WP-11 | 0.27.0 | 0.29.0 |
| project worktree RV-10c | 0.27.0 | 0.29.0 |
| project worktree RV-13 | 0.27.0 | 0.29.0 |
| project worktree RV-14 | 0.27.0 | 0.29.0 |

Update worktree báo up_to_date 0.29 nhưng registry vẫn 0.27. Thử install RV-12c báo already-installed 0.27 và đề nghị update; update với cwd/env chuẩn hóa vẫn không đổi. Không uninstall hay sửa settings/registry thủ công. [Tổng hợp](../native-child/installation-summary.json), [registry cuối](../native-child/installed-final.json), [lệnh update](../native-child/installation-commands.json), [install thử](../native-child/worktree-install-attempt.json), [update cwd thử](../native-child/worktree-update-cwd-attempt.json).

`plugin reload hh-tree --json` exit 0; plugin ls sau đó enabled/running, không restart daemon: [reload](../native-child/paseo-reload.json), [trạng thái sau](../native-child/paseo-plugin-after.json).

## Bằng chứng live và render đã làm sạch

Sol tạo child đọc-only cuối, gpt-6.1-sol low, completed. hh-ps --once --json exit 0 trong 2.345s: child dưới Sol canonical, completed, exit_code null. Provider list và hh-tree.get RPC đồng nhất parent/child. Có đúng 5 native child dưới Sol; panel hiện 4 + `1 subagent: 1✓ 0✗`, child cuối có mặt. [Metadata](../native-child/runtime-metadata.json), [hh-ps sample](../native-child/hh-ps-native-sample.json), [RPC](../native-child/panel-rpc.json), [aggregate đã làm sạch](../native-child/runtime-sanitized.json).

Child cuối: read 9392, cached 30336, output 240; USD~ 0.024218. Quota tài khoản GPT 5h null, tuần 16%; phần riêng GPT null, không suy ra từ token/USD. Tổng Claude tuần USD~ 195.771040455, RPC sau 196.926354055 do usage tiếp tục tăng; GPT total null vì coverage nguồn bảo thủ, không phải panel lỗi.

`node docs/work-in-progress/native-child/qa-render.mjs` exit 0 dùng JSX SessionBlock baseline/final thật qua host stubs, cùng snapshot đã làm sạch. Đây là **render metadata, không phải ảnh GUI**: trước 34 dòng, sau 36 do thêm 2 dòng đầu. Trích ngắn:

```text
Trước:
▾ ● Session 2 · claude-opus-5-5·high · 44p · ~$1.66 · Claude 5h ? · tuần 14.0% · GPT 5h ? · tuần 16.0%
    ✓ native-codex · gpt-6.1-sol·low · 10s · ~$0.02
Sau:
Claude máy này tuần ~$195.77 · Claude 5h ? · tuần 14.0%
GPT máy này tuần ~$? · GPT 5h ? · tuần 16.0%
▾ ● Session 2 · claude-opus-5-5·high · 44p · ~$1.66 · Claude riêng ~0.1% tuần
    ✓ native-codex · gpt-6.1-sol·low · 10s · 23:48 · ~$0.02 · GPT riêng ? tuần
```

Text lồng nhau thực tế: running sáng/tối #1565C0/#64B5F6; success #218739/#66BB6A; error #C62828/#EF5350; idle/silent #976500/#FFD54F; unknown/lost #666666/#AAAAAA. ✓ đếm xanh, ✗ đỏ; baseline icon chỉ foreground. [Trước](../native-child/panel-before.txt), [sau](../native-child/panel-after.txt), [màu render](../native-child/color-render.json), [màu addon](../native-child/panel-addon-colors.jsonl). Chưa xác minh screenshot/GUI trên máy hoặc điện thoại.

## Điều phối và giới hạn bàn giao

Áp dụng Ngoại lệ A theo [skill ext-hand](../../../hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md) và [skill paseo](../../../hybrid-hands/plugins/hybrid-hands/skills/paseo/SKILL.md).

Ba native executor hand tự viết phần được giao, fork none, gpt-6.1-sol low; cùng lúc tối đa 3, không vượt cap 4. Có thêm native_source_probe đọc-only đầu và native_final_probe đọc-only cuối, đều completed; tổng đồng thời vẫn tối đa 3. Sol review toàn bộ diff. Không gọi hand-ext, không có lỗi/fallback hand-ext hoặc ledger native. Tổng token/quota điều phối không được cung cấp: `?`.

Cần xử lý lệch 6 registry worktree và quyết định kiểm chứng full sau addon ở vòng được phép tiếp theo. Không coi full 417 trước addon là xác nhận toàn bộ addon. Handoff này không tạo `.done`; Sol tạo marker native-child.done sau khi review; marker kết thúc bàn giao, không khẳng định các mục còn mở đã đạt.
