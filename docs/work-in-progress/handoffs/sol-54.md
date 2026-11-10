## Tóm tắt

- Kết quả: **xong gói 5.4**, statusline **0.19.1**; Sol đã review diff. Có 1 test hiệu năng nền đỏ trên cả bản gốc.
- `statusline/plugins/statusline/scripts/gpt_usage.py`: parser chỉ đọc sổ GPT, lọc `.codex-hand`, quota mới nhất và USD hôm nay.
- `statusline/plugins/statusline/scripts/statusline.sh`: thêm hàng GPT sau Go, dùng helper màu/căn cột hiện có.
- `statusline/tests/test_limit_table.py`: đúng **1 test method mới**, gộp main/reset hết hạn/mẫu cũ hoặc thiếu sổ.
- `statusline/plugins/statusline/.claude-plugin/plugin.json`: bump patch 0.19.0 → 0.19.1, mô tả GPT.
- `statusline/.claude-plugin/marketplace.json`: bổ sung mô tả GPT.
- `statusline/README.md`: cập nhật version, thứ tự bảng, nguồn và quy tắc thiếu dữ liệu.
- `statusline/plugins/statusline/skills/setup/SKILL.md`: mô tả hàng GPT, không cần setup mới.
- Kiểm chứng: test hẹp cuối **5/5**, exit **0**; full suite chạy **đúng 1 lần**, **186/187**, exit **1**; baseline hiệu năng riêng **0/1**, exit **1**.
- Smoke từ repo chính, entry mới trong worktree: exit **0**, `GPT 5h:-- | 7d:3% | hôm nay ~$?`; sổ thật có 1/2 lượt hôm nay chưa biết cost.
- Hand-ext: **1 lượt auto → dsh**, exit **0**, 7 file áp thành công; không fallback, không hỏi duyệt, không commit/push.
- Còn lại: Opus áp patch vào nhánh chính nếu nhận; theo dõi lỗi hiệu năng nền và dữ liệu thiếu giá trong kiểm thực tế 5.6. Chưa update plugin đã cài.

## Phạm vi và cách giao

- Worktree Sol: `/Users/anhtp/app/claude-plugins-wt/sol-54`, nhánh `side/sol-54`, base `31659910c5dc9a8905f30d58b3d2ec247b43fc37`.
- Đã đọc plan mục 5, Q5a–Q5c, 5.2 và 5.4; đọc entry statusline, ledger Claude hiện hữu, helper bảng, Go, test hiện hữu, README và schema/nơi ghi sổ Codex trước khi viết brief. Không có AGENTS.md/CLAUDE.md áp dụng ở gốc/nhánh statusline; hai file trong dev-workflow không áp dụng.
- Dùng workflow [hybrid-hands:ext-hand](/Users/anhtp/app/claude-plugins-wt/sol-54/hybrid-hands/plugins/hybrid-hands/skills/ext-hand/SKILL.md:65).
- [Brief 7 mục, có file:dòng và tiêu chí trước khi giao](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/brief.md).
- Mức tối thiểu, đúng 1 method mới, 3 phase trong cùng method. Không chạy test hybrid-hands; không sửa code hybrid-hands hay plugin khác.

## Thay đổi theo file

| File | Thay đổi và vị trí |
|---|---|
| [gpt_usage.py](/Users/anhtp/app/claude-plugins-wt/sol-54/statusline/plugins/statusline/scripts/gpt_usage.py:30) | Parser mới 153 dòng, stdlib; nguồn sổ ở dòng 30, đọc JSONL từng dòng ở 85, kiểm cửa sổ ở 101, chọn mẫu/cộng USD ở 112. Không import hybrid-hands, không đọc rollout/tài khoản `.codex`, không mạng, không ghi file. |
| [statusline.sh](/Users/anhtp/app/claude-plugins-wt/sol-54/statusline/plugins/statusline/scripts/statusline.sh:231) | `build_gpt_cells` gọi parser, chỉ đưa số đã validate vào helper cũ; `build_limit_table` ở 298 chèn hàng GPT sau Go; nối dữ liệu ở 323. Không thay helper màu/bảng hay logic các đoạn cũ. |
| [test_limit_table.py](/Users/anhtp/app/claude-plugins-wt/sol-54/statusline/tests/test_limit_table.py:94) | Một method mới `test_gpt_row_uses_latest_quota_sample_and_today_cost`; fixture account cũ, hôm qua/tương lai, dòng hỏng/thiếu ended, thứ tự thời gian đảo, ISO khác timezone máy; kiểm quota/USD, thứ tự, căn cột, hết reset, quá 24h và thiếu sổ. |
| [plugin.json](/Users/anhtp/app/claude-plugins-wt/sol-54/statusline/plugins/statusline/.claude-plugin/plugin.json:3) | 0.19.1, description thêm GPT; marketplace không có trường version riêng cần đồng bộ. |
| [marketplace.json](/Users/anhtp/app/claude-plugins-wt/sol-54/statusline/.claude-plugin/marketplace.json:11) | Description thêm nguồn GPT và USD ước tính. |
| [README.md](/Users/anhtp/app/claude-plugins-wt/sol-54/statusline/README.md:9) | Version hiện hành, bảng dòng ở 41, giải thích nguồn/thiếu số ở 111, cây file. Sol sửa thêm sau review: câu cũ gọi Go là dòng cuối và làm rõ bỏ qua từng dòng lỗi. |
| [setup/SKILL.md](/Users/anhtp/app/claude-plugins-wt/sol-54/statusline/plugins/statusline/skills/setup/SKILL.md:44) | Điều kiện hiện GPT, nguồn, không cần setup mới; ghi chú chỉ đọc ở 76. |

`gpt_usage.py` là file **untracked mới** trong worktree Sol; khi lấy patch phải gồm file này. Các artifact điều phối nằm trong `output/` bị ignore, không đưa vào patch sản phẩm. Không stage/commit/push.

## Quyết định thiết kế Sol tự chọn

1. Dùng một hàng GPT của bảng hiện có, sau Go/trước nhóm phiên và skill: `5h | 7d | hôm nay ~$...`. Nhãn dim, phần trăm cùng ngưỡng xanh <50 / vàng ≥50 / đỏ ≥80; làm tròn số như quota live. Không in giờ reset GPT để giữ ngắn. Helper hiện tại căn theo độ rộng hiển thị, không có cơ chế cắt theo terminal width; giữ nguyên helper đó.
2. Parser Python stdlib riêng trong statusline, đọc `${HYBRID_HANDS_STATE_DIR:-$HOME/.hybrid-hands}/codex_usage.jsonl`; biến override giống Go để cô lập fixture. Giá/tokens không được tính lại; chỉ dùng `cost_usd` từ sổ.
3. Chỉ nhận schema 1 và `codex_home=.codex-hand`, ended hợp lệ không ở tương lai. Chọn mẫu `windows` dict có ended lớn nhất, không theo thứ tự dòng và không lấy lại % từ mẫu cũ khi cửa sổ mới nhất null/hỏng/hết reset. Mẫu tuổi ≥86400 giây thì ẩn cả hàng. Cửa sổ không dùng được hiện `--`, không hiện % cũ.
4. USD là ngày lịch máy, từ 0h tới now; cộng mọi cost hợp lệ của account này trong khoảng đó, kể cả dòng không có quota dùng được. Nếu có cost thiếu/null/sai trong ngày thì `~$?`, không đưa tổng thiếu thành tổng đầy đủ; không có lượt hôm nay nhưng mẫu hôm qua còn trong 24h thì `~$0.00`. Đây theo quyết định Q5b thiếu giá thì `?`.
5. ISO có offset/Z hoặc epoch được chấp nhận; ISO không offset hiểu là giờ máy. Không nhận bool/số âm/không hữu hạn; % vượt 100 bị bỏ. Dòng lỗi nhận diện/ended/JSON bỏ qua, trường số lỗi không làm hỏng trường còn hợp lệ. Sổ thiếu/lỗi hoặc parser thất bại không làm statusline thất bại.

## Các lượt hand-ext và report

Chỉ có **1 lượt**:

```sh
/Users/anhtp/app/claude-plugins/hybrid-hands/plugins/hybrid-hands/bin/hand-ext run --backend auto --brief /Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/brief.md --cwd /Users/anhtp/app/claude-plugins-wt/sol-54 --label sol-54-gpt-statusline --timeout-min 60
```

- Exit **0**, backend **dsh**, model **deepseek-v4.1-flash**, status **ok**, thời gian **1721.6 s** (~28 phút 42 giây).
- Run ID `20261107-150042-146270-sol-54-gpt-statusline-dsh`.
- [report.md của hand](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/20261107-150042-146270-sol-54-gpt-statusline-dsh/report.md), [events.jsonl](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/20261107-150042-146270-sol-54-gpt-statusline-dsh/events.jsonl), [meta.json](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/20261107-150042-146270-sol-54-gpt-statusline-dsh/meta.json), [changes.patch của hand](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/20261107-150042-146270-sol-54-gpt-statusline-dsh/changes.patch).
- Patch áp thành công 7 file vào worktree Sol, worktree hand đã dọn. `changes.patch` của hand chưa gồm chỉnh README nhỏ của Sol sau review; lấy diff cuối từ worktree Sol.
- Tokens: input **3,668,490**, cached_input **3,552,896** (nằm trong input), output **42,382**.
- Hạn mức Go thật harness báo: **3% 5h** reset 16:53, **23% tuần** reset 09/11 07:00, **11% tháng** reset 04/12 15:17. Dự phòng từ sổ ~10% 5h/~31% tuần; không dùng dự phòng thay số thật.
- Không 429/quota/fallback, không timeout. Meta ghi sandbox_requested `workspace-write`, sandbox_mode `danger-full-access` vì đang trong seatbelt ngoài của Sol; không đổi sandbox Sol.

## Review của Sol

- Đã tự đọc toàn bộ parser mới, diff shell/test/tài liệu/metadata; không giao hand review thay Sol.
- Chấp nhận code: nguồn GPT chỉ là ledger, account đúng, phần trăm từ mẫu cuối theo ended, loại reset độc lập, tổng ngày local, fail-open, không đưa nội dung tùy ý của ledger thành shell/ANSI.
- Ghép bảng dùng nguyên `rate_limit_segment`, `col_for_pct`, `join_cells`, `table_print`; thứ tự các đoạn cũ giữ nguyên. Các test cũ về thứ tự/căn cột đi qua, ngoài lỗi hiệu năng không liên quan nêu dưới.
- Test mới đúng 1 method; baseline có 186 method, bản này 187. Có fixture lỗi quan trọng và không truy cập sổ/credential thật trong test.
- Tìm thấy 1 lỗi tài liệu: README còn gọi Go là dòng cuối. Sol đã sửa vị trí Go và làm rõ skip từng dòng JSON lỗi. Không có sửa code sau test cuối của hand.
- `git diff --check`: exit **0**. Parser mới còn untracked đã được đọc riêng; không bỏ sót do `git diff` không hiện file mới.

## Kiểm chứng và mọi lượt test

Lệnh test hẹp chung của hand:

```sh
python3 -m unittest discover -s statusline/tests -p 'test_limit_table.py' -v
```

| Giờ máy 07/11 | Kiểm tra | Exit thực của kiểm tra | Số test / kết quả |
|---|---|---:|---|
| 15:14:29 | Bash syntax rồi `python3 -m py_compile ...gpt_usage.py` trước unittest | 1 | 0 test: bị chặn tạo pycache ngoài sandbox; unittest chưa chạy |
| 15:14:44 | Test hẹp lần 1 | 1 | 5 test: 4 đạt, 1 đỏ do regex bỏ sót padding |
| 15:15:09 | Sửa regex, test hẹp lần 2 | 0 | 5/5, 2.063 s |
| 15:22:44 | Thêm fixture thiếu ended trong cùng method, test hẹp lần 3 | 0 | 5/5, 2.086 s |
| 15:25:19 | Làm offset fixture khác timezone máy trên mọi máy, test hẹp lần 4 | 0 | 5/5, 2.051 s |
| 15:26:21 | Syntax Bash/Python, JSON metadata, test hẹp lần 5 | 0 | 5/5, 2.089 s |
| Cuối phiên Sol | Full suite **đúng 1 lần** | **1** | **187 test, 186 đạt / 1 đỏ**, 36.736 s |
| Sau full suite | Riêng test hiệu năng trên **HEAD gốc** chưa sửa | **1** | **1 test đỏ**, 7.022 s |

Một số lệnh hand dùng `; echo EXIT:$?`, nên shell wrapper thoát 0; cột trên là exit thực được `EXIT:` ghi lại. [Chi tiết các lượt từ events](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/hand-checks.json).

Các kiểm tra hẹp bổ sung của hand: `bash -n .../statusline.sh`, Python `compile()` trong bộ nhớ, `jq empty` hai metadata đều exit 0; AST parse exit 0. Hand thử parser bằng fixture tạm cho cost null → `?`, mẫu hôm qua nhưng còn mới → `0.00`, số bool/âm/>100 bị loại và ledger missing im lặng; không thêm method test, không đọc sổ thật.

Full suite Sol dùng đúng lệnh README:

```sh
python3 -m unittest discover -s statusline/tests
```

[Log full suite](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/full-suite.log): `test_week_split_calib.PerformanceTest.test_build_summary_scales` tại dòng 170 mất **6.9666155 s**, ngưỡng **2.0 s**. `week_split.py`, `usage_ledger.py`, `test_week_split_calib.py` không bị sửa.

Để xác minh lỗi nền, trích `git archive HEAD statusline` vào thư mục tạm, chạy chỉ test cũ:

```sh
PYTHONPATH=<baseline>/statusline/tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest test_week_split_calib.PerformanceTest.test_build_summary_scales -v
```

[Log baseline](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/baseline-performance.log): cùng assertion mất **7.001478834 s**, exit unittest **1** (wrapper lưu artifact thoát 0). Xác nhận có từ baseline, không sửa test/ngưỡng/code ngoài phạm vi, không chạy lại full suite. Không chạy bộ hybrid-hands.

## Chạy thật statusline từ repo chính

Chạy **đúng 1 lần** lúc **07/11/2026 15:31:12 +07:00**, cwd `/Users/anhtp/app/claude-plugins`; gọi entry mới `/Users/anhtp/app/claude-plugins-wt/sol-54/statusline/plugins/statusline/scripts/statusline.sh`, **exit 0**, stderr rỗng.

Repo chính chưa có patch nên dùng entry từ worktree đã review; không thay file repo chính hoặc cài/update plugin. Sổ GPT thật vẫn là `/Users/anhtp/.hybrid-hands/codex_usage.jsonl`. Để lần smoke chỉ đọc trạng thái đang dùng: sao chép 4 cache usage Claude có tên xác định vào `CLAUDE_HOME` tạm (cache limit, week summary, Go cache, week samples), tắt `STATUSLINE_GO_LIVE=0`, `STATUSLINE_WEEK_SPLIT_SPAWN=0`; phần ghi cache vốn có của statusline chỉ ghi vào bản sao tạm. Không đọc auth/credential, không mạng, không đọc rollout. Các con số quota/USD không được tạo giả cho smoke.

JSON stdin mẫu:

```json
{"workspace":{"current_dir":"/Users/anhtp/app/claude-plugins"},"cwd":"/Users/anhtp/app/claude-plugins","model":{"display_name":"Opus"},"effort":{"level":"high"}}
```

Output thật (chỉ bỏ ANSI để đọc; giữ văn bản và padding):

```text
anhtp@Trans-MacBook-Pro claude-plugins (feat/ba-tang-opus-sol-dsh)
Opus(high) | tokens:-- | ctx:--
Claude      5h:-                         | 7d:~10% (reset 13/11 13:00 · ~$13.35/1%)
· máy này                                | 7d:~14.3% (T6 12.7% · T7 1.6%)
· máy khác                               | 7d:~0.0%
Go          5h:~3.4% (reset 07/11 16:53) | wk:~23.4% (reset 09/11 07:00) | mo:~11.4% (reset 04/12 15:17)
GPT         5h:--                        | 7d:3%                         | hôm nay ~$?
· luxian-b  Kết nối Chrome    Claude ~5.4% | Go ~10.2%
· 35a653b7  Hiển thị phần t…  Claude ~3.1% | Go ~ 1.2%
· d8b3fdc6                    Claude ~2.2% | Go ~ 1.7%
· 96a17251  Load plugin hyb…  Claude ~0.6% | Go ~ 0.9%
· 7ead8c24  Báo cáo task Ji…  Claude ~0.5% | Go ~ 0.0%
```

Artifacts: [runner tái lập](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/smoke.py), [stdin](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/smoke-stdin.json), [stdout ANSI](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/smoke-stdout.ansi.txt), [stdout bỏ màu](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/smoke-stdout.txt), [meta exit/cwd/nguồn](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/smoke-meta.json).

Sol đối chiếu sổ thật chỉ bằng số tổng hợp, không đưa dữ liệu thật cho hand: từ **00:00 +07:00** hôm nay có **2 lượt**, **1 lượt có cost**, **1 lượt cost chưa biết**; tổng phần đã biết **$0.015068** chưa phải tổng đủ. Mẫu quota mới nhất ended **14:52:25 +07:00**, `5h=null`, `7d.used_percent=3`, reset tuần `2026-11-09T06:19:15+00:00`. Vì vậy `5h:--` và `~$?` là đúng dữ liệu hiện có. [Số tổng hợp](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/real-ledger-summary.json).

## Kẹt, hỏi duyệt và sandbox

- **Không hỏi duyệt**; không thao tác bị automatic approval review từ chối; không commit/push; không tạo API key/gọi API trả phí riêng; không mở side-session hay agent phụ.
- Dsh mất ~28 phút 42 giây, nhiều bước đọc/kiểm tra lặp; không đứng ở prompt duyệt. Chỉ 1 run, không cần fallback.
- **Sandbox 1 (hand, 15:14:29):** `python3 -m py_compile` cố ghi `/Users/anhtp/Library/Caches/com.apple.python/...` ngoài vùng cho ghi, `PermissionError: [Errno 1] Operation not permitted`, exit 1; vì dùng `&&`, unittest chưa chạy. Hand chuyển sang `compile()` trong bộ nhớ, exit 0; không xin quyền/nới sandbox.
- **Sandbox 2 (Sol):** lệnh quan sát `ps -axo pid,ppid,etime,state,comm | rg ... | tail ...` báo `zsh: operation not permitted: ps`. Pipeline ngoài trả 0 do lệnh cuối; không có dữ liệu process đọc được. Dùng session/events tiếp để theo dõi, không lặp lại/nới quyền.
- Test hẹp lần đầu đỏ do assertion regex không tính padding, đã sửa và xác minh. Không phải lỗi runtime của feature.
- Full suite đỏ hiệu năng nền, baseline đã tái hiện như trên. Để ngoài phạm vi, ghi cho Opus theo dõi; không nới ngưỡng hay chạy lại full.

## Việc còn lại cho Opus

- Nhận diff cuối từ worktree Sol (gồm parser untracked) để áp sang nhánh brain; report patch của hand thiếu hai chỉnh câu README nhỏ của Sol. Chưa sửa plan/đánh dấu 5.4 tại repo chính vì ngoài phạm vi ghi và brain đang làm việc riêng.
- [Patch cuối đủ 7 file, gồm chỉnh của Sol](/Users/anhtp/app/claude-plugins-wt/sol-54/output/llm/hand-ext/sol-54-orchestration/final-changes.patch): `git apply --stat` xác nhận **7 file, 280 dòng thêm, 15 dòng xoá**; lệnh này chỉ đọc patch, chưa áp repo chính.
- Khi làm 5.6, chú ý sổ hiện có cost null từ lượt trước khi đủ giá; chưa thể nhìn thấy tổng USD dạng số đầy đủ của ngày này. Không ghi đè sổ để làm đẹp output; quota 5h thực tế của mẫu mới nhất cũng null.
- Lỗi performance baseline cần một gói riêng nếu muốn full suite toàn xanh. 5.4 không thay đổi code đó.
- Plugin đã cài trên máy chưa được update, mọi thay đổi sản phẩm vẫn ở worktree Sol, chưa commit/push. Tín hiệu kết thúc theo hợp đồng: `sol-54.done` cùng thư mục bàn giao.
