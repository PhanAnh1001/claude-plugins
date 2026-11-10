## Tóm tắt

- **Kết quả: xong gói 5.3**, 14 file đổi; chưa commit/push, chưa áp diff sang repo chính.
- `hh_ps/codex.py`, `limits.py`: đọc sổ/rollout ghim, ước tính USD và lấy mẫu hạn mức GPT 5h/tuần còn hiệu lực.
- `hh_ps/models.py`, `tree.py`: mang dữ liệu Codex vào cây, giữ % tài khoản riêng với phần tiêu tuần Claude/Go.
- `hh_ps/render.py`, `compact.py`, `text_render.py`: JSON tương ứng, cột ~$USD/% GPT và dòng reset.
- `hh_ps/constants.py`, `hh-tree-pane/hooks/tree.ts`: provider/chú giải tài khoản, đồng bộ USD/% và dòng GPT trên pane.
- `paseo-hh-tree/shared/tree.ts`, `client/format.ts`, `client/LimitsBlock.tsx`: nhận schema, format USD/% và mở bộ lọc GPT 5h.
- `skills/paseo/SKILL.md` mục 4: model gpt-6.1-sol, codex đã disabled, codex-hand dùng ~/.codex-hand, không có lệnh quota Paseo.
- `tests/test_hh_ps_codex.py`: đúng **1 test mới**, sổ giả + Sol ghim + schema ordinal thật; không parse hội thoại.
- **3 lượt dsh đều hand-ext exit 0**, Sol tự review; đã sửa cả lỗi ordinal chỉ lộ khi chạy thật.
- Test: **393 full xanh, đúng 1 lần** trước fix ordinal; sau fix **87 test hẹp xanh, exit 0**; TS syntax 4 file xanh.
- Live cuối tại cwd repo chính: hai lệnh exit 0; GPT tuần **4%**, reset **09/11 13:19**; sol-53 **~$2,97**, cả 5 Sol có USD trong JSON.
- Còn cho Opus: tích hợp diff; chưa typecheck đủ dependency/kiểm UI điện thoại. Nguồn thật chỉ có tuần, nên 5h unknown; chi tiết, report và output ở dưới.

## Phạm vi và brief

Worktree Sol: `/Users/anhtp/app/claude-plugins-wt/sol-53`, nhánh `side/sol-53`, base `d734eb7537f118d7dffa21e455dff9ccddcc78d0`. Bắt đầu sạch. Chỉ thay đổi gói 5.3 và mục 4 skill Paseo; không commit/push.

Sol tự đọc plan mục 5 (Q5a–Q5c, 5.2, 5.3, 5.5), toàn bộ `limits.py`, `week.py`, `tree.py`, `render.py`, `text_render.py`, cùng `compact.py`, `models.py`, `registry_source.py`, `side_session/tokens.py`, giá mặc định và schema sổ Codex. Không có AGENTS.md/CLAUDE.md áp cho vùng sửa; hai file trong dev-workflow nằm ngoài phạm vi.

Áp dụng skill [ext-hand](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md): brief 7 mục, chạy hand cách ly, Sol tự review từng diff. Ba brief tự chứa nằm trong worktree:

- [Brief triển khai](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/sol-53-brief.md).
- [Brief sửa sau review](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/sol-53-fix-brief.md).
- [Brief sửa schema ordinal phát hiện khi live](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/sol-53-ordinal-brief.md).

Patch tổng gồm **14 file, kể cả 2 file mới**: [sol-53-final.patch](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/sol-53-final.patch). Sol đã chạy `git apply --check /Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/sol-53-final.patch` tại cwd repo chính, **exit 0**, chỉ kiểm tra, chưa áp. Không dùng git diff tracked đơn lẻ để tích hợp vì sẽ thiếu hai file mới.

## Thay đổi theo file

Các đường dẫn dưới tính từ worktree Sol.

| File | Thay đổi và lý do |
|---|---|
| [hybrid-hands/plugins/hybrid-hands/lib/hh_ps/codex.py](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/plugins/hybrid-hands/lib/hh_ps/codex.py) (mới) | Đọc sổ Codex theo run_id; USD Sol từ rollout ghim × cùng giá; lấy mẫu tài khoản mới nhất theo timestamp từng cửa sổ; lọc metadata trước giải mã, chỉ home .codex-hand và kiểm containment. |
| [hybrid-hands/plugins/hybrid-hands/lib/hh_ps/models.py](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/plugins/hybrid-hands/lib/hh_ps/models.py) | Thêm Usage.usd_estimated/gpt_5h_pct/gpt_week_pct và HandRun.usage để giữ dữ liệu đã enrich tới renderer. |
| [hybrid-hands/plugins/hybrid-hands/lib/hh_ps/constants.py](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/plugins/hybrid-hands/lib/hh_ps/constants.py) | Provider Codex và chú giải `% GPT = tài khoản`. |
| [hybrid-hands/plugins/hybrid-hands/lib/hh_ps/limits.py](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/plugins/hybrid-hands/lib/hh_ps/limits.py) | Dòng GPT 5h/tuần cạnh Claude, account-only, bỏ cửa sổ đã reset hoặc không biết reset. |
| [hybrid-hands/plugins/hybrid-hands/lib/hh_ps/tree.py](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/plugins/hybrid-hands/lib/hh_ps/tree.py) | Gắn usage cho hand/Sol; chỉ áp công thức Claude tuần cho provider Claude; đưa mẫu GPT vào snapshot. |
| [hybrid-hands/plugins/hybrid-hands/lib/hh_ps/render.py](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/plugins/hybrid-hands/lib/hh_ps/render.py) | JSON có các trường Codex tương ứng và dùng HandRun.usage thay vì tính lại rồi mất USD. |
| [hybrid-hands/plugins/hybrid-hands/lib/hh_ps/compact.py](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/plugins/hybrid-hands/lib/hh_ps/compact.py) | Cột ~$USD, mẫu % GPT riêng, `?` khi thiếu giá và formatter dòng hạn mức/reset. |
| [hybrid-hands/plugins/hybrid-hands/lib/hh_ps/text_render.py](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/plugins/hybrid-hands/lib/hh_ps/text_render.py) | In khối Hạn mức vào output cây CLI. |
| [hybrid-hands/paseo-hh-tree/shared/tree.ts](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/paseo-hh-tree/shared/tree.ts) | Schema nhận thêm cờ USD ước tính và hai trường % tài khoản. |
| [hybrid-hands/paseo-hh-tree/client/format.ts](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/paseo-hh-tree/client/format.ts) | Hiện ~$USD/?, mẫu GPT 5h/tuần và dòng GPT chỉ tổng tài khoản. |
| [hybrid-hands/paseo-hh-tree/client/LimitsBlock.tsx](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/paseo-hh-tree/client/LimitsBlock.tsx) | Mở bộ lọc cho GPT 5h, tránh trường hợp Python có dữ liệu nhưng panel bỏ dòng đó. |
| [hybrid-hands/hh-tree-pane/hooks/tree.ts](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/hh-tree-pane/hooks/tree.ts) | Đồng bộ cột USD/% và dòng GPT 5h/tuần cho pane còn lại, thêm chú giải tài khoản. |
| [hybrid-hands/plugins/hybrid-hands/skills/paseo/SKILL.md](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/plugins/hybrid-hands/skills/paseo/SKILL.md) | Chỉ mục 4: model gpt-6.1-sol, codex mặc định đã disabled trong ~/.paseo/config.json, codex-hand dùng ~/.codex-hand, Paseo 0.15.0 không có lệnh usage/quota. |
| [hybrid-hands/tests/test_hh_ps_codex.py](/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/tests/test_hh_ps_codex.py) (mới) | Đúng một test method, fixture HOME/sổ/registry/rollout ghim giả; kiểm dòng GPT, USD/% hand, USD/token Sol, JSON, lọc hội thoại và envelope ordinal. |

Phải đổi bốn file TypeScript vì các consumer cũ chỉ lọc cửa sổ tuần và chưa biết trường mẫu GPT; chỉ sửa Python sẽ không hiện đủ trên panel. `week.py` được đọc để bám cách Claude nhưng không cần sửa. Không đổi lib/hand_ext, lib/side_session, statusline, plan, version hay config Paseo thật.

## Quyết định thiết kế Sol tự chọn

1. **USD và % là hai loại số khác nhau.** USD là ước tính từ giá Q5b, có `~` và JSON `usd_estimated:true`. `% GPT` là mẫu mức sử dụng **tài khoản** tại nguồn của hand/rollout, không phải phần trăm riêng phiên đã tiêu. Không có tỷ lệ GPT USD/1% đáng tin trong schema 5.2 nên không tự suy ra. `week_pct` vẫn dành cho phần hạn mức tuần của Claude/Go.
2. **Nguồn mỗi dòng:** hand lấy cost_usd/windows của chính run_id trong sổ, chỉ codex_home=.codex-hand. Sol chỉ lấy rollout đã ghim trong side state, không tìm rollout mới nhất để gán cho phiên. Đọc ghim qua helper read-only, không sửa state/side_session. Không có ghim hay số liệu thì để unknown.
3. **Giá:** dùng price_for/estimate_cost đã có của hand_ext; lấy backends.codex.price_per_mtok đã merge defaults (2,00 / 0,10 / 10,00 USD/1M). Công thức trừ cached khỏi input trước khi tính giá input thường. Giá null/không hợp lệ cho USD unknown, không tự bù giá mặc định khi người dùng đã đặt null. Đây không phải tiền hoá đơn subscription.
4. **Dòng tài khoản:** chọn mẫu mới nhất theo timestamp giữa sổ và mọi rollout hợp lệ trong .codex-hand, riêng từng cửa sổ. Không gán % máy này/máy khác khi nguồn không có. Dòng/giá trị % có resets_at<=now hoặc không biết reset bị ẩn; không giả 0. Cửa sổ chưa có mẫu không được bịa.
5. **Giới hạn dữ liệu:** cố định Path.home()/.codex-hand; không dùng CODEX_HOME hoặc backend home để chuyển tài khoản panel. Từ chối home/sessions/rollout symlink ra ngoài. Chỉ giải mã envelope event_msg với payload token_count; bỏ response_item/hội thoại trước json.loads. Không đọc session_meta vì panel đã có rollout ghim, không cần dò phiên. Lọc header hỗ trợ metadata ordinal của rollout thật.
6. **JSON tương thích:** chỉ bổ sung usd_estimated và gpt_* khi có, giữ hình dạng Usage cũ của Claude/Go. Limit dùng plan GPT, window 5h/tuần, total_pct/resets_at/source và null machine split.
7. **Không thêm cache hay API:** panel chỉ đọc file, không fetch quota, không gọi API và không sửa config. Cần đọc lại side state để lấy ghim vì adapter cũ chưa mang trường này; tránh mở phạm vi lib/side_session.

## Review của Sol

Sol tự review toàn bộ 14 file, kể cả file mới không xuất trong git diff mặc định; không giao hand review thay mình.

- Lượt 1 chưa chấp nhận: chuẩn hoá token Sol sai tên khóa làm JSON token thành 0 dù USD đúng; latest token_count thiếu usage còn giữ số cũ; home redirect/symlink và hint anywhere chưa đủ chặn nguồn/hội thoại; chú giải % và câu trạng thái Paseo chưa đúng.
- Lượt 2 sửa các lỗi trên, tăng assert trong cùng test duy nhất. `costText` thiếu giá đã được hand sửa trước lúc trả lượt 1 nên Sol không giao sửa lại.
- Live sau lượt 2 phát hiện tất cả Sol usage=null: regex header quá chặt, bỏ metadata `ordinal` thật. Sol chỉ xem prefix envelope và tên khóa, không in nội dung hội thoại; mọi pin có file tồn tại, trong đúng .codex-hand nhưng số header match bằng 0. Đã giao lượt 3 thêm ordinal và tái hiện bằng dữ liệu giả trước khi sửa.
- Không còn phát hiện code cần sửa sau review cuối; trạng thái kiểm chứng live cuối được ghi ở phần riêng.

## Các lượt hand-ext

Binary cho cả ba lượt: `/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin/hand-ext`. Đều `run --backend auto --cwd /Users/anhtp/app/claude-plugins-wt/sol-53 --brief <brief ở trên> --label <label>`. Không dùng sub-agent tool, không mở side-session mới.

| Lượt | Backend, exit, thời gian | Token input / cached input / output | Patch và report |
|---|---|---|---|
| sol-53-gpt-panel, timeout-min 60 | dsh, exit 0, 1173,8 s | 17.783.184 / 17.581.824 / 77.829 | 14 file, áp ok; [report](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/hand-ext/20261107-144107-234848-sol-53-gpt-panel-dsh/report.md) |
| sol-53-review-fixes, timeout-min 40 | dsh, exit 0, 457,5 s | 3.732.772 / 3.629.184 / 33.558 | 5 file, áp ok; [report](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/hand-ext/20261107-150204-024887-sol-53-review-fixes-dsh/report.md) |
| sol-53-ordinal-fix, timeout-min 20 | dsh, exit 0, 558,1 s | 414.635 / 379.136 / 13.499 | 2 file, áp ok; [report](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/hand-ext/20261107-151339-944614-sol-53-ordinal-fix-dsh/report.md) |

Cả ba lượt model deepseek-v4.1-flash, cách ly worktree tạm và đã dọn. Không có fallback codex/claude-main, không có 429/quota/capped/timeout ở cả ba lượt này. Go thật sau mỗi lượt: 3% 5h reset 16:53, 23% tuần reset 09/11 07:00, 11% tháng reset 04/12 15:17; ước tính sổ lần lượt ~9%/~31% và ~10%/~31% (5h/tuần); lượt 3 cũng ~10%/~31%.

## Kiểm chứng và số lượt chạy

- Đúng **1 test method mới** (Sol đếm AST). Không thêm test vào các file test cũ.
- Lượt hand 1: test mới riêng 1 test xanh một lần; `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hh_ps*.py'` chạy **5 lượt**, mỗi lượt exit 0 / 87 test. Thời gian lần lượt 1,697 / 1,741 / 1,727 / 1,715 / 1,819 giây. Ghi đủ lượt thay vì chỉ chép kết quả cuối report.
- Lượt hand 1: `node --experimental-strip-types --test hybrid-hands/paseo-hh-tree/client/format.test.ts` hai lượt, mỗi lượt exit 0 / 7 test; tương tự `hybrid-hands/hh-tree-pane/tests/tree.test.ts` hai lượt, mỗi lượt exit 0 / 3 test.
- Lượt hand 2: test hẹp thêm `-v` một lượt (87 xanh, 1,712 s), rồi lệnh không `-v` một lượt (87 xanh, 1,773 s); pane tree.test.ts một lượt exit 0 / 3 test. Không có test fail ở hai lượt đầu. Audit nằm tại output/llm/sol-53-hand1-test-audit.json và sol-53-hand2-test-audit.json.
- Lượt hand 3: sửa fixture ordinal trước, chạy `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hh_ps_codex.py' 2>&1 | tail -40` → **1 test FAIL có chủ đích**, tái hiện `(12.5,34.0)!=(44,55)`. Mã thoát riêng unittest không được thu vì có pipe qua tail; không tính pipeline là chứng cứ pass.
- Lượt hand 3 sau sửa: lệnh test hẹp pipe qua `tail -20` rồi sau reflow fixture qua `tail -6`, mỗi lượt **87 test OK**, 1,772 s và 1,786 s. Audit: output/llm/sol-53-hand3-test-audit.json.
- **Sol kiểm trạng thái cuối trực tiếp**, không pipe: `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hh_ps*.py'` → **exit 0, 87 test, 1,763 s**. [Log](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/sol-53-final-narrow-tests.log). Đếm AST sau fix vẫn đúng 1 test method mới.
- Sol: lệnh `node -` nhận script stdin dùng TypeScript transpileModule bằng compiler có sẵn trong package Paseo cài global, kiểm cú pháp **4 file TS/TSX, exit 0, 0 lỗi**. Đây là syntax check, không phải full dependency typecheck; không cài thêm dependency.
- Sol: `env -u CODEX_SANDBOX python3 -m unittest discover -s hybrid-hands/tests -q` — **đúng một lượt, exit 0, 393 test, 49,237 s**. [Log](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/sol-53-full-tests.log).
- Thứ tự cần nói rõ: bộ đầy đủ chạy sau review lượt 2, trước live; live mới lộ lỗi ordinal. Giữ yêu cầu không lặp bộ đầy đủ; bản sửa ordinal sau đó được kiểm bằng test hẹp và chạy thật, ghi kết quả bổ sung bên dưới.
- `git diff --check`: exit 0. Sol không lặp bộ đầy đủ; mọi lượt lặp bên hand được liệt kê đầy đủ ở đây.

## Mọi lần kẹt, hỏi duyệt, lỗi sandbox

- Không hỏi người dùng duyệt, không có approval request/rejection; không bỏ việc vì chờ xác nhận.
- Lượt hand 1: stderr cảnh báo `permission: unknown preset "danger-full-access" (known: read-only, workspace-write)`, 1 entry không activate. Đây là 4.13 thuộc gói sol-412-414; không sửa trong worktree này. Hand vẫn làm được shell, test và patch.
- Meta hand ghi requested workspace-write, thực tế danger-full-access dưới CODEX_SANDBOX=seatbelt của Sol. Seatbelt ngoài vẫn giới hạn quyền ghi. Không tự đổi sandbox của Sol.
- Lượt hand 1: `python3 -m py_compile .../codex.py` exit 1, PermissionError `[Errno 1] Operation not permitted` khi ghi `/Users/anhtp/Library/Caches/com.apple.python/Users/anhtp/.hybrid-hands/worktrees/sol-53-20261107-144107-234848-sol-53-gpt-panel-dsh`. Hand đổi sang compile() trong bộ nhớ, thành công. Không xin thêm quyền, không sửa cache hệ thống.
- Lượt hand 3 lặp lại lỗi py_compile ghi cache hệ thống: `compile exit:1`, PermissionError vào `/Users/anhtp/Library/Caches/com.apple.python/Users/anhtp/.hybrid-hands/worktrees/sol-53-20261107-151339-944614-sol-53-ordinal-fix-dsh`; cũng chuyển compile() trong bộ nhớ thành công. Không xin quyền. Stderr khởi động lượt 2 và 3 đều rỗng, không còn cảnh báo preset ở hai lượt đó.
- Các lệnh test có pipe qua tail trong lượt 3 không cho mã thoát unittest độc lập; Sol đã chạy trực tiếp một lượt cuối, exit 0 / 87 test. Lỗi regression đỏ là chủ đích, không bị bỏ qua.
- Không typecheck toàn package vì thiếu dependency node_modules trong worktree; dùng test formatter/pane và syntax check có sẵn. Chưa kiểm UI trên điện thoại hay cài/reload plugin thật.
- Lần live đầu exit 0 nhưng **không đạt tính năng Sol USD** do ordinal. Đã ghi nhận và sửa, không coi exit 0 là đủ.
- Không đọc/in .env, auth.json, token hay credential; hand chỉ dùng dữ liệu giả, không được giao dữ liệu home thật. Không đọc ~/.codex thật hay nội dung hội thoại rollout. Các dòng prefix dùng để chẩn đoán chỉ gồm timestamp/ordinal/type/payload và tên khóa.

## Output thật tại repo chính và giới hạn kiểm chứng

Cả hai đợt đều dùng binary **đã sửa của worktree Sol**: `/Users/anhtp/app/claude-plugins-wt/sol-53/hybrid-hands/plugins/hybrid-hands/bin/hh-ps`, cwd `/Users/anhtp/app/claude-plugins`. Không thay binary/config trong repo chính, không áp patch vào đó. Các output được lưu trong worktree Sol.

| Đợt | Lệnh | Exit | Thời gian lệnh | Kết quả |
|---|---|---:|---:|---|
| 15:11, trước fix ordinal | `<binary>`, một lần | 0 | 0,772 s | GPT tuần từ sổ 3%, cả 5 Sol usage=null — phát hiện lỗi, chưa đạt. |
| 15:11, trước fix ordinal | `<binary> --json`, một lần | 0 | 0,352 s | Có hand USD 0.015068; Sol null; stderr rỗng. |
| 15:23, sau fix ordinal | `<binary>`, một lần | 0 | 0,397 s | GPT tuần 4%, Sol ~$2,97/~$0,85, stderr rỗng. |
| 15:23, sau fix ordinal | `<binary> --json`, một lần | 0 | 0,354 s | Cả 5 Sol có USD; hand Codex có USD và %; stderr rỗng. |

**Có hai đợt live (mỗi đợt một lần/lệnh), thay vì chỉ một đợt như dự kiến**: đợt đầu tìm ra lỗi schema thật; đợt sau cần để xác minh sửa đúng. Bộ đầy đủ vẫn chỉ chạy đúng một lần, không lặp sau sửa ordinal. Đây là lệch thứ tự kiểm chứng cần biết khi đọc kết quả full suite.

Output phần GPT nguyên văn từ lệnh cây cuối:

```text
▶ phiên này ● sống ○ đã dừng · giờ = lúc xong · $ ước tính theo giá niêm yết · % = phần hạn mức tuần đã dùng · % GPT = tài khoản
GPT tuần   tổng 4.0% · reset 09/11 13:19
│ ├ ● phụ:sol-54         25p         ~$0.85  GPT 5h ? · tuần 4.0%
│ ├ ● phụ:sol-53         44p         ~$2.97  GPT 5h ? · tuần 4.0%
```

JSON dưới đây là phần GPT trích nguyên giá trị từ output `--json` cuối, generated_at `2026-11-07T15:23:53+07:00` (chỉ bỏ các trường phiên không liên quan):

```json
{
  "generated_at": "2026-11-07T15:23:53+07:00",
  "cwd": "/Users/anhtp/app/claude-plugins",
  "limits": [
    {
      "plan": "GPT",
      "window": "tuần",
      "this_machine_pct": null,
      "other_pct": null,
      "total_pct": 4.0,
      "resets_at": "2026-11-09T13:19:15+07:00",
      "source": "codex_rollout",
      "estimated": false
    }
  ],
  "sessions": [
    {
      "side_name": "sol-411",
      "provider": "codex",
      "usage": {
        "read": 83530,
        "cache_read": 5124864,
        "cache_write": null,
        "out": 21143,
        "usd": 0.890976,
        "week_pct": null,
        "week_pct_estimated": false,
        "usd_estimated": true,
        "gpt_week_pct": 3.0
      }
    },
    {
      "side_name": "sol-412-414",
      "provider": "codex",
      "usage": {
        "read": 119118,
        "cache_read": 7007360,
        "cache_write": null,
        "out": 27178,
        "usd": 1.210752,
        "week_pct": null,
        "week_pct_estimated": false,
        "usd_estimated": true,
        "gpt_week_pct": 3.0
      }
    },
    {
      "side_name": "sol-51-52",
      "provider": "codex",
      "usage": {
        "read": 145317,
        "cache_read": 15657472,
        "cache_write": null,
        "out": 56556,
        "usd": 2.421941,
        "week_pct": null,
        "week_pct_estimated": false,
        "usd_estimated": true,
        "gpt_week_pct": 3.0
      }
    },
    {
      "side_name": "sol-53",
      "provider": "codex",
      "usage": {
        "read": 183032,
        "cache_read": 20406912,
        "cache_write": null,
        "out": 56192,
        "usd": 2.968675,
        "week_pct": null,
        "week_pct_estimated": false,
        "usd_estimated": true,
        "gpt_week_pct": 4.0
      }
    },
    {
      "side_name": "sol-54",
      "provider": "codex",
      "usage": {
        "read": 92977,
        "cache_read": 5172224,
        "cache_write": null,
        "out": 14908,
        "usd": 0.852256,
        "week_pct": null,
        "week_pct_estimated": false,
        "usd_estimated": true,
        "gpt_week_pct": 4.0
      }
    }
  ],
  "hand_runs": [
    {
      "run_id": "20261107-145215-993062-sol-412-414-codex-readonly-codex",
      "label": "sol-412-414-codex-readonly",
      "backend": "codex",
      "usage": {
        "read": 5379,
        "cache_read": 29696,
        "cache_write": null,
        "out": 134,
        "usd": 0.015068,
        "week_pct": null,
        "week_pct_estimated": false,
        "usd_estimated": true,
        "gpt_week_pct": 3.0
      }
    },
    {
      "run_id": "20261107-142555-386979-sol-51-52-fallback-codex",
      "label": "sol-51-52-fallback",
      "backend": "codex",
      "usage": {
        "read": 6775,
        "cache_read": 31104,
        "cache_write": null,
        "out": 388,
        "usd": null,
        "week_pct": null,
        "week_pct_estimated": false,
        "usd_estimated": true,
        "gpt_week_pct": 3.0
      }
    },
    {
      "run_id": "20261107-132019-fix-47-48b-codex",
      "label": "fix-47-48b",
      "backend": "codex",
      "usage": {
        "read": 45536,
        "cache_read": 616960,
        "cache_write": null,
        "out": 7003,
        "usd": null,
        "week_pct": null,
        "week_pct_estimated": false,
        "usd_estimated": true
      }
    }
  ]
}
```

- Nguồn thật chỉ có cửa sổ tuần, không có mẫu 5h: account row 5h bị ẩn, trên phiên hiện `5h ?`; **không giả 0**. Nhánh đủ 5h/tuần/reset được kiểm bằng test duy nhất với fixture.
- `%` của từng hand/Sol là snapshot tài khoản tại nguồn riêng nên các phiên cũ có thể 3%, account mới nhất 4%. Không cộng các tỷ lệ đó để tính % tài khoản.
- Sol kiểm thêm phép tính từ token của cả 5 phiên JSON theo 2,00/0,10/10,00 USD/1M, tất cả khớp USD trong sai số 1e-6.
- Hai hand cũ có cost_usd null từ sổ: giữ unknown, không ghi lại hay bịa chi phí lịch sử. Một hand có số thật từ sổ: USD 0.015068, mẫu tuần 3%.
- Cây compact mặc định chỉ chọn các việc con gần nhất nên phần text cuối hiện hai Sol; JSON có đủ năm Sol và ba hand Codex. Quy tắc chọn việc con không đổi.
- [Cây cuối](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/sol-53-live-verified-hh-ps.txt), [JSON cuối](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/sol-53-live-verified-hh-ps.json), [GPT text](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/sol-53-live-verified-gpt.txt), [GPT JSON](/Users/anhtp/app/claude-plugins-wt/sol-53/output/llm/sol-53-live-verified-gpt.json).
- Output đợt lỗi vẫn giữ ở output/llm/sol-53-live-hh-ps.txt và sol-53-live-hh-ps.json, phần GPT ở sol-53-live-gpt.txt/json; không sửa lại bằng output đã sửa.

## Phần Opus còn làm

Áp diff worktree Sol vào nhánh tích hợp khi phù hợp. Chưa deploy/reload/restart Paseo, chưa thay binary main, chưa commit/push. Gói statusline 5.4 và kiểm tích hợp 5.6 nằm ngoài phạm vi này. Nếu cần typecheck đầy đủ hoặc nhìn UI điện thoại, làm ở môi trường có đủ dependency; không cần đổi giải pháp hiện tại để tích hợp gói 5.3.
