# hh-tree-pane

Mod Claude Code: pane cạnh khung chat trong terminal, hiển thị cây phiên của hybrid-hands
(phiên brain → subagent → lượt hand ngoài) lấy từ `hh-ps --since 3h --json`, làm mới theo chu kỳ max(30 giây, 3 × thời gian chạy trước), tối đa 120 giây; lỗi/timeout giãn gấp đôi tới trần.

- Mỗi dòng phiên/subagent/hand/side provider hiện model, effort, USD~, quota tài khoản 5h/tuần, ended hoặc `đang chạy`, elapsed. Elapsed đang chạy tăng theo thời gian; ended cố định thời lượng khi xong. Không hiện giờ bắt đầu; JSON/meta giữ started. Legacy thiếu nguồn hiện `?`.
- Quota từ cache/sample sẵn có; thiếu thì `?`, không suy token/USD thành quota GPT. Phần riêng hand tuần chỉ hiện khi có nguồn và có nhãn riêng. Khối hạn mức tài khoản giữ 5h/tuần và reset nếu biết.
- USD~ là ước tính offline subscription, không phải hoá đơn. Nguồn duy nhất là [`config/model-prices.json`](../plugins/hybrid-hands/config/model-prices.json), override `HYBRID_HANDS_PRICING_FILE`; cache Claude dùng giá cấu hình, model lạ không fallback. Không hiện token trong pane.
- Phiên mở pane (`▶`) đứng đầu, phiên phụ lồng dưới cha. Mặc định đủ việc chạy/vừa xong theo since, không gấp 3 việc hay ẩn cây đã xong. Không hiển thị nhóm orphan hand-ext; `hh-ps` text/JSON vẫn giữ orphan.
- Giờ kết thúc theo giờ máy; không biết thì `?`. Dòng con giữ trạng thái lỗi nếu có, không bịa mốc ended cho lượt mất dấu.
- Poll tự động bỏ qua pane không `isShown` hoặc không `isPlaced` qua `$.ui.panes()`; mở phiên và lệnh `/hh-tree` làm mới ngay nếu không bận. Chu kỳ được tính từ lúc lần chạy trước kết thúc.
- Lệnh `/hh-tree` mở lại pane. Terminal cần rộng từ khoảng 110 cột.

Contract đầy đủ: [README hybrid-hands, mục 6](../README.md#6-theo-dõi-phiên-và-hand-hh-ps).

## Bật cho mọi phiên

Thêm thư mục này vào `CLAUDE_CODE_PLUGIN_DIRS` trong khối `env` của `~/.claude/settings.json`:

```json
{ "env": { "CLAUDE_CODE_PLUGIN_DIRS": "~/app/claude-plugins/hybrid-hands/hh-tree-pane" } }
```

Phiên mở sau đó tự nạp mod; sửa file trong thư mục thì phiên đang chạy tự nạp lại.

## Kiểm tra

`claude plugin validate ~/app/claude-plugins/hybrid-hands/hh-tree-pane`

Test định dạng dòng: `node --experimental-strip-types --test hybrid-hands/hh-tree-pane/tests/tree.test.ts` (chạy từ gốc repo).
