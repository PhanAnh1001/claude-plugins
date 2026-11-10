## Tóm tắt

- **Kết quả: xong một phần.** Source hybrid-hands 0.30.0 và statusline 0.21.0 đã triển khai, Sol review xong; chưa đạt gate full xanh để cài/reload.
- GPT tổng tuần dùng token delta rollout quan sát được: mẫu checkout từ `?` → **~$75.60**; không cộng ledger trùng, không fallback model lạ.
- GPT riêng dùng chênh quota tuần cùng reset, nhãn `riêng (đo)`: 11/26 dòng đo được, ví dụ **1.0%**, có cả 0.0% hợp lệ; 15 dòng chưa đủ nguồn giữ `?`.
- GPT 5h vẫn `?`: metadata thật chỉ có primary `window_minutes=10080`, không có sample 300 phút. Claude 5h vẫn `?`: cache hết hạn/cũ, không có live sample hợp lệ.
- Đổi 25 file: nguồn/test hh_ps, nhãn panel, adapter/statusline, contract và release; danh sách và lý do ở dưới.
- 3 ca chấp nhận đạt; panel 17/17, typecheck/build đạt; full statusline 187 OK. Full hybrid-hands duy nhất: **420 test, 1 failure**.
- Failure là Limit Claude 5h cũ còn tồn tại khi enrichment chạy lại; đã sửa và chạy hẹp regression 2 + chấp nhận 3 đều OK. **Không có full sau sửa**.
- Bản cài user còn hybrid-hands **0.29.0**, statusline **0.20.0**; folder source 0.30.0/0.21.0. Không update CLI/reload do brief yêu cầu full xanh trước bước này.
- Có mẫu nguồn thật đã làm sạch trước/sau; chưa xác minh bản cài sau update, RPC/GUI/điện thoại. Opus cần bố trí lượt kiểm full tiếp theo rồi cài/reload nếu xanh.

## Quyết định nguồn

| Chỗ cần lấp | Nguồn chọn | Điều kiện và kết quả thực tế |
|---|---|---|
| GPT máy này tuần USD~ | Token counter delta có timestamp trong cửa sổ reset quota tuần hiện tại; fixed `~/.codex-hand/sessions` + `archived_sessions` | Khử trùng thread/event; không cộng lại ledger. Thread chỉ metadata không làm hỏng tổng observed. Thiếu baseline/timestamp/giá hợp lệ hoặc nguồn không đọc được → unknown. Mẫu sau 75.603681 USD~. |
| GPT riêng tuần của session/native | `rate_limits` weekly `used_percent` cuối trừ đầu trong chính rollout | Ít nhất 2 sample explicit 10080 phút, timestamp hợp lệ, quota không giảm, cùng reset hiện tại xuyên suốt khoảng đo. Qua reset/thiếu sample hoặc rollout không pin được → `?`. Source JSON `codex_rate_limits_delta`; không đánh dấu ước tính quota. |
| GPT 5h | Account sample của cửa sổ 300 phút | Toàn bộ 4.052 event tại audit đầu chỉ có primary 10080 phút; không đổi nhãn tuần thành 5h. Legacy account sample thiếu duration giữ mapping cũ primary/secondary; measured riêng không dùng inference legacy. |
| Claude 5h | Shared helper cache `.statusline-cache.json` hoặc live `.hh-claude-rate-limit.json` | Kiểm số, freshness 1.800 giây, reset còn hiệu lực và phù hợp 5h; chấp nhận reset ISO/numeric. Cache thật không còn hiệu lực; live sample không có. Không suy hoặc tạo sample mới. |

Quyết định ngắn: [decision.md](../gpt-nguon/decision.md). Giá duy nhất vẫn là `hybrid-hands/plugins/hybrid-hands/config/model-prices.json`; không đổi bảng giá. Mọi USD~ là ước tính offline subscription, không phải hóa đơn. Tổng observed chỉ bao phủ token events cục bộ có nguồn, không bảo đảm toàn bộ hoạt động tài khoản. Phép đo `riêng (đo)` là biến động quota tài khoản trong khoảng phiên, có thể gồm các phiên chạy đồng thời; không phải phân bổ độc quyền cho một phiên. Không suy quota GPT từ token/USD.

## File thay đổi và lý do

| File | Lý do |
|---|---|
| `AGENTS.md` | Contract nguồn usage 0.30.0, measured/observed và giới hạn nguồn. |
| `hybrid-hands/README.md` | Ghi nguồn, điều kiện unknown, legacy account và nhãn đo. |
| `hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json` | Source version 0.30.0. |
| `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md` | Mục release 0.30.0. |
| `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/models.py` | Thêm cuối Usage `week_pct_source` default rỗng. |
| `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/codex.py` | Validate account windows; đo quota cùng rollout/reset; dùng model thực khi tính USD pinned rollout. |
| `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/native_source.py` | Giữ metadata rate limits và gắn phép đo cho native child. |
| `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/machine_usage.py` | Tổng observed delta, bỏ poisoning bởi thread chỉ metadata; không có event vẫn unknown. |
| `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/usage_enrichment.py` | Claude 5h cache/live hợp lệ, Limit chung và invalidation khi enrichment lại; giữ measured source. |
| `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/live_rate.py` | Parse ISO/numeric reset và bỏ sample future/stale/out-of-range. |
| `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/render.py` | JSON chỉ thêm measured source khi có, giữ tương thích shape cũ. |
| `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/compact.py` | Nhãn text `riêng (đo)`. |
| `hybrid-hands/tests/test_hh_ps_gpt_nguon.py` | Đúng 3 phương thức test chấp nhận, fixtures giả. |
| `hybrid-hands/paseo-hh-tree/shared/tree.ts` | Optional measured source trong schema. |
| `hybrid-hands/paseo-hh-tree/client/format.ts` | Helper nhãn measured/unknown. |
| `hybrid-hands/paseo-hh-tree/client/compact.ts` | Dùng nhãn mới; giữ màu/layout/pool/counts. |
| `hybrid-hands/paseo-hh-tree/client/compact.test.ts` | Mở rộng assertion test sẵn có, không thêm test method. |
| `statusline/plugins/statusline/.claude-plugin/plugin.json` | Source version 0.21.0 và description nguồn mới. |
| `statusline/plugins/statusline/CHANGELOG.md` | Release riêng 0.21.0. |
| `statusline/plugins/statusline/scripts/shared_usage.py` | Adapter dùng parser chung, deadline 0.75 giây, fail-open. |
| `statusline/plugins/statusline/scripts/gpt_usage.py` | Quota ledger/rollout mới nhất theo từng cửa sổ; USD hôm nay vẫn ledger-only. |
| `statusline/plugins/statusline/scripts/statusline.sh` | Claude thiếu payload 5h có thể dùng shared sample hợp lệ với dấu `~`. |
| `statusline/plugins/statusline/scripts/hand_lines.py` | Hiện phần riêng và nhãn đo trên dòng phiên/hand. |
| `statusline/tests/test_limit_table.py` | Mở rộng test có sẵn cho rollout tuần không có ledger, không gán sang 5h. |
| `statusline/tests/test_statusline.py` | Mở rộng test có sẵn cho cache Claude 5h hợp lệ/hết hạn. |

Danh sách máy đọc: [changed-files.json](../gpt-nguon/changed-files.json); patch gồm cả 2 file mới: [task-changes.patch](../gpt-nguon/task-changes.patch). Các file log/report trong thư mục gpt-nguon và handoff này là bằng chứng điều phối, không nằm trong 25 file sản phẩm. Không sửa các thay đổi docs chưa commit có sẵn của người khác.

## Kiểm chứng thực chạy

| Lệnh/kiểm tra | Kết quả |
|---|---|
| `python3 -m unittest discover -s hybrid-hands/tests -p test_hh_ps_gpt_nguon.py` | 3 OK; (a) measured/unknown qua reset, (b) giá canonical/dedup/empty/unknown model, (c) quota 5h có/không nguồn. |
| Narrow `test_hh_ps_codex.py`, `test_hh_ps_native.py`, `test_hh_ps_limits.py` | 1 + 2 + 15 OK trước full. |
| `node --experimental-strip-types --test hybrid-hands/paseo-hh-tree/client/*.test.ts` | 17/17 OK. |
| `npm run typecheck --prefix hybrid-hands/paseo-hh-tree` | Exit 0. |
| Paseo 0.15.0 `compileDirectoryPlugin` | Exit 0, client 25.066 bytes, server 16.067 bytes. |
| Narrow statusline `test_limit_table.py`, `test_statusline.py` | 5 + 10 OK. |
| `python3 -m unittest discover -s hybrid-hands/tests -q` | **Một lần**, 420 test/63.656s, **1 failure**, exit 1. |
| `python3 -m unittest discover -s statusline/tests -q` | **Một lần**, 187 test/58.630s, OK, exit 0. |
| Sau sửa regression: narrow `test_hand_usage_panel.py` và `test_hh_ps_gpt_nguon.py` | 2 + 3 OK, không chạy full lần hai. |
| `claude plugin validate` hai plugin | Profile local exit 0; advisory LICENSE/icon có sẵn, không xử lý ngoài phạm vi. |
| JSON validity, link nội bộ thay đổi, syntax/py_compile, `git diff --check` | Đạt theo report hand và kiểm Sol. |

Failure full tại `test_hand_usage_panel.HandUsagePanelTest.test_missing_quota_is_unknown`: sau sample Claude 5h=23, cache chuyển invalid nhưng Limit cũ vẫn được đọc. Sửa bằng cách bỏ các Limit do enrichment tự tạo (`claude_5h_cache`/`claude_5h_live`) mỗi pass rồi đọc sample lại; giữ Limit của nguồn caller khác. Test sẵn có kiểm True/nan/inf/101 và expiry đã qua. Không sửa expectation để che lỗi. Core fix này đến **sau full**, nên không claim final full xanh, kể cả narrow đã qua.

Bằng chứng: [core narrow](../gpt-nguon/core-narrow.log), [regression](../gpt-nguon/core-regression.log), [full hybrid-hands](../gpt-nguon/full-hybrid-hands.log), [full statusline](../gpt-nguon/full-statusline.log), [build](../gpt-nguon/paseo-build.json), [static checks](../gpt-nguon/static-checks.json). Báo cáo hand: [core](../gpt-nguon/core-report.md), [presenter](../gpt-nguon/presenter-report.md), [docs](../gpt-nguon/docs-report.md).

## Mẫu thật đã làm sạch

Sol chỉ lấy metadata/usage, không chép nội dung hội thoại vào report. Mẫu JSON nguồn: [trước](../gpt-nguon/before.json), [sau](../gpt-nguon/after-source.json), [tổng hợp live](../gpt-nguon/live-summary.json). Source `hh-ps --once --json` exit 0 trong 4.171 giây; `hh-ps --once` text exit 0. [Text chỉ giữ suffix GPT](../gpt-nguon/hh-ps-once-text-sanitized.txt) đã bỏ tên/đường dẫn.

```text
Trước (metadata nguồn):
GPT máy này tuần ~$? · GPT 5h ? · tuần 17.0%
GPT riêng ? tuần
Sau (checkout, chưa cài/reload):
GPT máy này tuần ~$75.60 · GPT 5h ? · tuần 18.0%
GPT riêng (đo) 1.0% tuần
GPT riêng (đo) 0.0% tuần
Claude máy này tuần ~$201.33 · Claude 5h ? · tuần 14.4%
```

Các dòng panel trên được render bằng helper `panelRows`/`rowText` thực từ metadata đã làm sạch: [trước](../gpt-nguon/panel-before.txt), [sau](../gpt-nguon/panel-after-source.txt). Đây là render helper, **không phải GUI/RPC hay screenshot**; dữ liệu trước không giữ effort/status nên những trường ngoài phạm vi usage có `?` trong bản render trước. Hai thời điểm có thêm usage phát sinh, không dùng chênh tổng USD giữa chúng để chứng minh logic pricing.

Audit đầu có 106 rollout, 4.052 token events và 1 thread chưa có token; không thấy unknown model trên delta cần tính giá hay delta không hợp lệ. Chính điều kiện metadata-only thread làm tổng cũ null. [Source audit](../gpt-nguon/source-audit.json). Sau sửa có 26 dòng Codex, 11 measured (9 khác 0, 2 bằng 0); 15 dòng còn unknown vì không có phép đo đủ điều kiện từ rollout tương ứng. Không thay chúng bằng phần trăm tài khoản.

Standalone source `gpt_usage.py` exit 0/0.227s, weekly 18%, 5h trống, today ledger USD~0.05: [statusline source](../gpt-nguon/statusline-source.json). USD hôm nay này chỉ thuộc ledger hand-ext, không phải tổng máy. Không chạy toàn bộ statusline shell trên dữ liệu thật để tránh kích hoạt fetch khác; chỉ kiểm helper nguồn và fixtures.

## Cài đặt, giới hạn và việc còn lại

Không thực hiện CLI update hay `paseo plugin reload` trong lượt này. Nguyên nhân từ brief: “Cuối, đúng một lần: full suite … Full xanh thì làm tiếp: Cập nhật bản cài … reload plugin”. Lần full hybrid-hands đã đỏ; không có quyền bỏ qua điều kiện hoặc chạy full lần hai trong brief này. Không restart daemon.

`claude plugin list --json` xác nhận registry user vẫn hybrid-hands 0.29.0/statusline 0.20.0, còn folder nguồn đã 0.30.0/0.21.0 và readFromFolder trỏ checkout này. Các registry project cũ vẫn có 0.27.0/0.29.0; không sửa registry/settings thủ công hay đi sửa repo khác. [Installation state](../gpt-nguon/installation.json).

Cần một lượt kiểm full tiếp theo được Opus phân công trước khi tuyên bố release hoàn tất; nếu xanh thì dùng CLI update hai plugin và reload riêng hh-tree, sau đó lấy mẫu bản cài/RPC. Chưa xác minh UI điện thoại. `hand_lines.py` có timeout 2 giây sẵn có, trong khi mẫu hh-ps JSON checkout mất 4.171 giây; dòng hand statusline có nguy cơ fail-open do timeout trên bộ dữ liệu lớn và chưa được kiểm live. Không tăng thời gian chặn statusline trong lượt này.

## Điều phối và dữ liệu

Dùng [ext-hand skill](../../../hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md) và [paseo skill](../../../hybrid-hands/plugins/hybrid-hands/skills/paseo/SKILL.md), ngoại lệ A: đã kiểm Paseo env có mặt, order thực codex, model gpt-6.1-sol, effort low, max_parallel=4, tools chọn model/effort độc lập. Ba native executor `fork_turns=none`, full brief 7 mục và luật dữ liệu nguyên văn, tối đa 3 cùng lúc; cùng file chỉ follow-up tuần tự. Sol review toàn bộ hand mình giao. Không hand-ext/fallback/lỗi exit7/8; không tạo run/meta/report/token ledger hand-ext cho native. Runtime token/quota điều phối không được tool cung cấp: `?`.

Hand chỉ dùng code/fixture giả; metadata usage thật do Sol tự đọc và tổng hợp, không giao hand đọc rollout/cache thật. Sol viết bàn giao và mẫu cuối dựa trên số tổng hợp đã kiểm. Không in credential/token/.env; không API trả phí, không commit/push, không sửa config cấm, không bật parallel-subagents, không xoá/di chuyển output/llm. Các tiến trình test/build/CLI do lượt này tạo đều đã kết thúc; ba hand đã completed, giữ history/tab.

Marker `gpt-nguon.done` báo kết thúc lượt làm việc và bàn giao **xong một phần**, không xác nhận gate release đã đạt.
