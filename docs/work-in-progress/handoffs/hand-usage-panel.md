## Tóm tắt
- Kết quả: **xong một phần** — tính năng và bản cài chính hoàn tất; còn ngoại lệ full test và CLI worktree bên dưới.
- Quyết định: một bảng giá cấu hình có nguồn/ngày; USD luôn `~`; quota dùng số tài khoản thật, thiếu `?`, không suy quota GPT từ USD.
- UI giữ loại + model/effort, USD, quota, kết thúc/đang chạy, thời lượng; bỏ giờ bắt đầu, giữ started trong metadata/JSON.
- Cả hai panel ẩn hand-ext không rõ cha; hh-ps text/JSON giữ dữ liệu; lượt mới ghi cha canonical, không dùng scope cap làm cha.
- Đổi `lib/hand_ext/*`, `lib/hh_ps/*`, `config/model-prices.json`, `lib/usage_pricing.py`: lifecycle, liên kết cha, token, giá và quota.
- Đổi `hh-tree-pane/*`, `paseo-hh-tree/*`: đủ trường, bỏ nhóm orphan, tương thích nguồn và bản cài.
- Đổi `statusline/.../scripts/*`: adapter hand đọc hh-ps, dùng cùng bảng giá; ledger v4, tối ưu tổng hợp theo ngày.
- Đổi tests, README/skills/CHANGELOG/manifest và AGENTS.md: contract mới; hybrid-hands **0.26.0**, statusline **0.20.0**.
- Full statusline: **187/187 xanh**; full hybrid-hands chạy một lần: **410/411**, lỗi User-Agent đã sửa và test dsh **41/41 xanh**; không chạy full lần hai.
- Test hẹp: hh-ps 88, acceptance 3, quota 39, TypeScript 15 và typecheck xanh; Sol review diff mọi hand.
- Chạy thật hh-ps `--once`/`--json`, RPC Paseo và statusline bản cài: đủ trường, không giờ bắt đầu, Codex không có quota riêng giả.
- CLI đã cập nhật HH user + 2 project + 1 local, statusline user; **5 worktree** vẫn ghi 0.25.3 dù CLI báo up-to-date 0.26.0.
- Giữ nguyên 10 đường dẫn cấu hình được bảo vệ; không commit/push, không sửa registry thủ công; 16 hand đã kết thúc.

## Quyết định giải pháp (L1)

Dữ liệu đi qua snapshot hh-ps chung để CLI, hai panel và adapter statusline dùng cùng lifecycle/model/usage. Registry toàn máy được hợp nhất với meta ở repo/worktree và khử trùng. Transcript Claude cung cấp token/model cho mọi loại subagent, kể cả agent không có metadata cũ. Lượt hand-ext mới ghi started/ended/status/exit/duration/tokens/effort và parent canonical; scope giới hạn song song chỉ là scope, không phải session ID. Các ID provider Codex/Paseo được đối chiếu qua state phiên phụ. Dữ liệu cũ không đủ model hoặc kết thúc giữ `?`.

Bảng giá duy nhất là `hybrid-hands/plugins/hybrid-hands/config/model-prices.json`, thay bằng `HYBRID_HANDS_PRICING_FILE` khi cần. Mỗi entry có nguồn/ngày, USD/MTok và giá cache tương ứng; không đoán giá theo họ model khi model lạ. Nguồn công khai đã mở kiểm tra ngày **2026-11-07**: [OpenAI](https://developers.openai.com/api/docs/pricing), [Anthropic](https://platform.claude.com/docs/en/about-claude/pricing), [OpenCode Go](https://dev.opencode.ai/docs/console/go). DeepSeek dùng mức peak bảo thủ đã ghi chú trong JSON. Đây là quy đổi token theo giá công khai, không phải hóa đơn subscription. Backend có override giá theo cấu hình hiện hữu vẫn được hỗ trợ; không sửa cấu hình repo.

Quota 5h/tuần lấy cache/sample mà plugin hiện có cho Claude, tài khoản Codex hand và Go. Thiếu/hết hiệu lực thì `?`. Phần riêng lượt chỉ xuất hiện khi có nguồn phù hợp và ghi nhãn ước tính; hạn mức USD của Go tuyệt đối không áp vào Codex. Ledger máy Go không được dùng thay cho quota tài khoản. Không suy token/USD thành quota GPT.

Bố cục mỗi dòng: loại và tên, model/effort, thời lượng, kết thúc hoặc đang chạy, USD~, quota tài khoản. Thứ tự có thể khác nhẹ giữa các giao diện; không giao diện nào hiện giờ bắt đầu. JSON vẫn giữ started để tính duration. Panel không render orphan; hh-ps vẫn giữ để kiểm tra dữ liệu. Statusline thêm cây phiên hiện tại bằng adapter chỉ đọc, timeout 2 giây/fail-open; `STATUSLINE_HANDS=0` tắt riêng phần này.

## File thay đổi và lý do

Các thay đổi sẵn có của 0.25.3, gồm side-session/policy/parallel hand, được giữ nguyên. Bảng dưới mô tả phần gói usage panel; không coi toàn bộ diff với HEAD là thay đổi mới của gói này.

| File (tương đối repo) | Lý do |
|---|---|
| `AGENTS.md` | Tài liệu sống về vai trò, dữ liệu, canonical pricing, metadata và contract UI. |
| `hybrid-hands/plugins/hybrid-hands/config/model-prices.json` | Giá có source/date, cache và cấu hình chung. |
| `.../lib/usage_pricing.py` | Đọc và tính giá chung, fingerprint cho ledger. |
| `.../lib/hand_ext/run_cmd.py` | Ghi lifecycle cuối lượt vào metadata và gắn phiên gọi đúng. |
| `.../lib/hand_ext/run_registry.py` | Metadata/registry lưu effort, duration và parent. |
| `.../lib/hand_ext/codex_usage.py` | Đọc token/model/effort từ structured Codex usage. |
| `.../lib/hand_ext/go_usage.py` | Tính Go theo giá chung và quota đúng nguồn. |
| `.../lib/hand_ext/config.py`, `constants.py` | Tìm cấu hình worktree/main repo và đường dẫn dữ liệu liên quan. |
| `.../lib/hand_ext/backends/dsh.py` | Đồng bộ User-Agent 0.26.0. |
| `.../lib/hh_ps/models.py` | Thêm model/effort/start/end và quota tài khoản, giữ tương thích constructor. |
| `.../lib/hh_ps/registry_source.py`, `repos.py` | Đọc registry/meta repo-worktree, khử trùng và tìm cha. |
| `.../lib/hh_ps/transcript_source.py`, `claude_source.py` | Nhận mọi loại subagent và lifecycle/model từ transcript. |
| `.../lib/hh_ps/codex.py` | Nhận Codex model/effort từ metadata có cấu trúc. |
| `.../lib/hh_ps/pricing.py`, `week.py` | Dùng giá chung, ledger schema/fingerprint hợp lệ. |
| `.../lib/hh_ps/usage_enrichment.py` | Gắn đúng giá/quota mỗi backend; số thiếu không bịa. |
| `.../lib/hh_ps/tree.py` | Ghép và enrich snapshot; hạn mức riêng Go không áp cho Codex. |
| `.../lib/hh_ps/cli.py`, `selection.py`, `constants.py` | `--once`, hiển thị mọi dòng trong khoảng đang chạy/vừa xong. |
| `.../lib/hh_ps/compact.py`, `render.py`, `text_render.py` | Đủ cột, elapsed tăng khi đang chạy, giữ start trong JSON. |
| `hybrid-hands/hh-tree-pane/hooks/tree.ts`, `register.tsx` | Renderer/schema tương thích, không nhóm orphan, chọn bản hh-ps mới. |
| `hybrid-hands/hh-tree-pane/tests/tree.test.ts` | Điều chỉnh kiểm tra renderer hiện hữu theo contract. |
| `hybrid-hands/paseo-hh-tree/client/ChildRows.tsx`, `SessionBlock.tsx`, `TreeView.tsx`, `format.ts` | Mọi dòng đủ model/effort/giá/quota/end/duration, bỏ orphan. |
| `.../client/format.test.ts` | Điều chỉnh assertion format hiện hữu. |
| `.../server/agent-record.ts`, `hh-ps.ts`, `shared/tree.ts` | Provider nativeHandle, executable resolver và schema. |
| `.../package.json`, `tsconfig.json` | Khai báo kiểu Node để typecheck panel. |
| `hybrid-hands/tests/test_hand_usage_panel.py`, `test_hand_usage_running.py` | Đúng 3 test acceptance mới dùng dữ liệu giả. |
| `hybrid-hands/tests/hand_ext_case.py`, `test_hand_ext_codex.py`, `test_hand_ext_registry.py`, `test_hand_ext_rundir.py` | Điều chỉnh fixture/assertion metadata, caller và lifecycle hiện hữu. |
| `hybrid-hands/tests/test_hh_ps*.py` đã đổi | Điều chỉnh assertion model/giá/quota/hiển thị theo contract mới. |
| `hybrid-hands/README.md`, hai README/OVERVIEW panel | Cách dùng và giới hạn dữ liệu, USD~, không giờ bắt đầu/orphan panel. |
| `.../skills/ext-hand/SKILL.md`, `paseo/SKILL.md`, `side-session/SKILL.md` | Hướng dẫn runtime và contract hand mới. |
| `.../.claude-plugin/plugin.json`, `CHANGELOG.md` | Release hybrid-hands 0.26.0. |
| `statusline/plugins/statusline/scripts/hand_lines.py` | Adapter cây hand chỉ đọc từ hh-ps. |
| `.../scripts/statusline.sh` | Gắn adapter vào statusline phiên hiện tại. |
| `.../scripts/shared_prices.py` | Tìm và dùng bảng giá canonical, không nhân bản giá. |
| `.../scripts/usage_ledger.py`, `go_sessions.py` | Quy đổi giá chung, ledger schema 4 + fingerprint. |
| `.../scripts/week_split.py` | Tổng hợp theo ngày nhanh, giữ đúng lịch/DST. |
| `statusline/tests/_support.py`, `test_go_sessions.py`, `test_session_lines.py`, `test_week_split.py` | Điều chỉnh assertion hiện hữu, dùng fixture giả. |
| `statusline/README.md`, plugin `CHANGELOG.md`, `.claude-plugin/plugin.json` | Contract mới và release 0.20.0. |

Trong bảng, `.../lib` và `.../skills` thuộc `hybrid-hands/plugins/hybrid-hands`; `.../client`, `server`, `shared`, package/tsconfig thuộc `hybrid-hands/paseo-hh-tree`; các dòng script statusline thuộc `statusline/plugins/statusline`.

## Giao hand và review

Giao các brief khác file qua đường dẫn `bin/hand-ext run --backend auto`, chia nhóm độc lập tối đa 4 lượt nền; backend thực tế codex `gpt-6.1-sol` low. Có 16 lượt trong registry mang nhãn `usage-panel-*`, tất cả status `ok`, không còn lượt đang chạy. Brief chép luật dữ liệu nguyên văn, chỉ code/fixture giả công khai. Các vòng tiếp theo sửa kết quả review hoặc lỗi thực tế; cùng file được làm tuần tự. Sol đã đọc/review diff mọi hand; không giao hand review hand khác. Brief/log nằm ở `../hand-usage-panel/`, report từng hand tại đường `report:` trong log; không mở thêm side-session, không gửi tin/dừng các phiên khác.

## Kiểm chứng và ngoại lệ full test

| Lệnh / nhóm | Kết quả thật |
|---|---|
| `python3 -m unittest discover -s hybrid-hands/tests -p 'test_hh_ps*.py' -q` | 88/88, trước vòng full. |
| Acceptance hai file mới | 3/3; chỉ 3 test function mới. |
| `python3 -m unittest discover -s hybrid-hands/tests -q` | **Chạy đúng một lần: 411 test, 1 fail** trong 49.588s. |
| `python3 -m unittest discover -s statusline/tests -q` | **Chạy đúng một lần: 187/187** trong 36.426s. |
| `python3 -m unittest discover -s hybrid-hands/tests -p test_hand_ext_dsh.py -q` | Sau sửa User-Agent: **41/41**. |
| Test hẹp sau sửa quota: panel / usage / codex / limits | **2 + 21 + 1 + 15 = 39/39**. |
| Node test format/nest/tree hiện hữu | **15/15**. |
| `npm run typecheck` tại `hybrid-hands/paseo-hh-tree` | Exit 0. |
| `git diff --check` | Exit 0. |
| Validate hai plugin | Pass; cảnh báo metadata license/icon directory-marketplace không chặn validate. |

**Chưa đạt điều kiện full hybrid-hands xanh.** Lượt full duy nhất lỗi `test_hand_ext_dsh.VersionTest.test_user_agent_matches_plugin_version`: literal User-Agent 0.25.3 chưa theo manifest 0.26.0. Sol bỏ sót hạng mục này khi review release; đã giao hand sửa một dòng và nhóm dsh 41 test xanh. Sau đó runtime còn phát hiện quota Go áp nhầm Codex; hand đã sửa guard và mở rộng assertion của acceptance có sẵn, 39 test hẹp xanh, RPC cuối xác nhận Codex không còn own% giả. Không chạy full lần hai theo yêu cầu “ĐÚNG MỘT LẦN”; vì vậy không khẳng định full suite trên cây cuối đã xanh. Nếu cần chứng nhận full xanh trên cây cuối, Opus cần quyết định một lượt kiểm chứng mới.

Ba ca acceptance:
1. Codex đã xong: có ended + duration cố định + USD ước tính, không nhận phần trăm riêng của Go.
2. Subagent Claude chưa xong: `đang chạy`, sau 10 giây duration tăng 10 giây.
3. Quota thiếu: `?`, không lỗi; sample quá hạn/không hợp lệ không được dùng.

Ca 2 dùng transcript giả. Tại thời điểm kiểm chứng thật không có subagent Claude đang chạy để đo hai lần; không mở thêm phiên chỉ để tạo mẫu. Runtime thật có subagent Claude đã xong.

Log kết quả: `../hand-usage-panel/full-hybrid-hands.log`, `full-statusline.log`, `qa-hh-ps.log`, `qa-acceptance.log`, `release-fix.log`, `quota-scope-fix.log`, `panel-build.log`.

## Kiểm chứng thực tế và output đã ẩn tên/ID

Ngày 2026-11-07, múi giờ Asia/Ho_Chi_Minh. Dùng công cụ runtime đọc usage tổng hợp; không in transcript, auth, credential hay giá trị .env. Những dòng dưới chỉ giữ loại/model/usage/thời gian; tên, ID, mô tả và đường dẫn đã bỏ. Đây là output trích, không phải toàn bộ danh sách.

### hh-ps

Chạy nguồn thật `hybrid-hands/plugins/hybrid-hands/bin/hh-ps --once` và `--json --once`: cả hai exit 0. Snapshot cuối có 18 phiên, 66 lượt; JSON mất khoảng 0.937s. Mọi Codex run có own-week% null; giữ started trong JSON, không có cột start trong text.

```text
LOẠI / TÊN  MODEL/EFFORT  THỜI GIAN  KẾT THÚC (local)  USD  TÀI KHOẢN 5h / tuần
hand-ext/codex [hand] | gpt-6.1-sol/low | 1p | 2026-11-07 21:31 | ~$0.07 | GPT 5h ? · tuần 11.0%
side/codex [Sol] | gpt-6.1-sol/high | 30p | đang chạy | ~$2.86 | GPT 5h ? · tuần 11.0%
subagent/Claude [ẩn tên] | claude-opus-5-5/low | 1p | 2026-11-07 20:32 | ~$0.41 | Claude 5h ? · tuần 13.1% · riêng ~<0.1% tuần
```

Metadata của một hand Codex chính gói này: status `ok`, exit_code `0`, model `gpt-6.1-sol`, effort `low`, có started/ended, duration **192.4175s**, parent tồn tại và khác cap scope. Xem `runtime-meta-check.json`.

### Panel Paseo

Đã chạy `paseo plugin reload hh-tree --json` thành công và gọi thật `hh-tree.get` bằng SDK CLI đang cài, cho agent hiện tại. Output sau lấy từ response thật và hàm format client của panel. RPC trả 19 phiên/51 orphan records; JSON giữ orphan, cả renderer pane lẫn panel không dựng nhóm orphan. Đây là kiểm chứng RPC/renderer, chưa quan sát trực tiếp màn hình thiết bị.

```text
LOẠI | MODEL/EFFORT | USD · TÀI KHOẢN 5h/tuần | KẾT THÚC | ĐÃ CHẠY
side/codex [Sol] | gpt-6.1-sol/high | ~$2.74 · GPT 5h ? · tuần 11.0% | đang chạy | 28p
hand-ext/codex [hand] | gpt-6.1-sol/low | ~$0.07 · GPT 5h ? · tuần 11.0% | 2026-11-07 21:31 | 1p
subagent/parallel-subagents:hand | claude-opus-5-5/low | ~$0.41 · Claude 5h ? · tuần 13.1% · riêng ~<0.1% tuần | 2026-11-07 20:32 | 1p
session/claude [ẩn tên] | claude-opus-5-5/high | ~$3.55 · Claude 5h ? · tuần 13.1% · riêng ~0.3% tuần | đang chạy | 8p
```

Loại `parallel-subagents:hand` ở mẫu là transcript lịch sử có thật; không bật lại plugin parallel-subagents.

### Statusline bản cài

Chạy thật `python3 ~/.claude/plugins/cache/statusline-local/statusline/0.20.0/scripts/hand_lines.py <parent-canonical-id> <repo>`: exit 0, render 9 dòng dưới đúng cha, không cột start. Mẫu rút gọn:

```text
session/codex [ẩn tên/id] | model:gpt-6.1-sol | effort:high | ~$2.8644 | account:GPT | 5h:? | tuần:11% | ended:đang chạy | elapsed:1832s
hand-ext/codex [ẩn tên/id] | model:gpt-6.1-sol | effort:low | ~$0.0729 | account:GPT | 5h:? | tuần:11% | ended:07/11 21:31:56 | elapsed:64s
hand-ext/codex [ẩn tên/id] | model:gpt-6.1-sol | effort:low | ~$0.0360 | account:GPT | 5h:? | tuần:11% | ended:07/11 21:30:11 | elapsed:24s
```

Các artifact whitelist: `runtime-source-check.json`, `runtime-source-sanitized.json`, `runtime-hh-ps-sample.txt`, `runtime-paseo-check.json`, `runtime-paseo-sample.txt`, `runtime-statusline-check.json`, `runtime-statusline-sample.txt`, đều trong `../hand-usage-panel/`. Số phiên/duration có thể khác giữa các lần gọi vì máy tiếp tục chạy.

## Cập nhật bản cài và việc còn mở

Đã refresh marketplace directory `hybrid-hands-local` và `statusline-local`, dùng `claude plugin update <plugin>@<marketplace> --scope <scope> --json` từ cwd tương ứng; không sửa `installed_plugins.json` thủ công.

| Plugin / scope | Kết quả registry đọc lại |
|---|---|
| hybrid-hands / user | 0.26.0 |
| hybrid-hands / project `/Users/anhtp/app/ai-comic-video` | 0.26.0 |
| hybrid-hands / project `/Users/anhtp/app/live-tiktok-games` | 0.26.0 |
| hybrid-hands / local `/Users/anhtp/app/ai-luxian` | 0.26.0 |
| statusline / user | 0.20.0 (trước cập nhật thực tế là 0.19.0) |
| hybrid-hands / project worktree `RV-12c`, `RV-10b`, `WP-11`, `RV-10c`, `RV-13` | **Vẫn 0.25.3** |

Năm worktree nằm dưới `/Users/anhtp/app/live-tiktok-games-wt/`. Đã chạy update từ từng cwd: CLI exit 0 và báo `up_to_date` 0.26.0, nhưng đọc lại registry thì bản ghi worktree vẫn trỏ cache 0.25.3. RV-13 xuất hiện trong khi làm và cũng đã thử cập nhật. Đây là phần CLI chưa xử lý được, để Opus theo dõi; không tự chỉnh registry hoặc cấu hình repo. Inventory/log: `installs-before.json`, `installs-after.json`, `install-update-*.log`.

Bản cache mới được so byte với các file source sửa cuối (quota guard, dsh version, metadata, pricing, statusline adapter/ledger): tất cả khớp, xem `installed-content-check.json`. Panel Paseo đang chạy từ source directory, reload thành công, không restart daemon/phiên khác.

Đọc skill statusline setup và chỉ chạy `bash statusline/plugins/statusline/scripts/install.sh --dry-run`: exit 0, `nothing to do (install is already in place)`. Không chạy install thật. Kiểm hash/absence 10 đường dẫn đã bảo vệ từ đầu: không đổi, gồm settings Claude, config Codex hand và cấu hình hybrid-hands repo/scope liên quan; xem `protected-check.json`. Không commit/push, không dừng/gửi tin phiên phụ khác, không gọi API trả phí hoặc tạo/dùng API key.

Điểm cần Opus đọc: ngoại lệ full test chưa xanh trên cây cuối; năm bản ghi worktree còn cũ; model/end/quota legacy thiếu vẫn `?`; chưa kiểm tra trực quan trên màn hình Paseo. Không còn hand của gói này đang chạy. Hoàn tất bàn giao sẽ tạo `hand-usage-panel.done` theo hợp đồng.
