---
description: Xem model ba tầng hoặc chọn cấu hình theo repo từ danh sách
argument-hint: "[set [FLAGS]|unset brain|side|hand|options] [--dry-run] [--json]"
allowed-tools: Bash, AskUserQuestion
---

Không đối số chỉ xem model/effort/account ba tầng; `set` không cờ mở danh sách chọn cấu hình. Các đối số khác chuyển nguyên cho CLI. Chạy bằng tool Bash tại cwd repo hiện tại theo đúng một trong ba luồng dưới đây.

## 1. Không đối số: chỉ xem

Khi `$ARGUMENTS` rỗng, chạy:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models
```

In kết quả, không hỏi và không ghi cấu hình.

## 2. Chỉ có `set`: chọn trên một màn hình

Khi `$ARGUMENTS` là đúng `set`, không có cờ hay đối số khác:

1. Chạy `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models options --json` để lấy danh sách chỉ đọc. Dùng đúng dữ liệu JSON trả về, không tự đặt model/account hay đọc file tài khoản.
2. Gọi AskUserQuestion **đúng một lần**, gồm đủ 4 câu dưới đây trên cùng màn hình. Mọi câu đều `multiSelect: false`, tối đa 4 lựa chọn theo thứ tự nêu dưới đây; mục dư nhập qua “Other” do công cụ cung cấp, không thêm “Other” thành một lựa chọn riêng.
   - **Tầng** — header `Tầng`, hỏi “Cấu hình tầng nào?”: ba mục `tiers`, label = `label`, description = `current`; giữ `value` để xác định tầng.
   - **Model** — header `Model`, hỏi “Chọn model nào? DeepSeek chỉ dùng cho tầng Hand, nhập qua Other.”: lấy `providers.claude.models` rồi `providers.codex.models`; label = model, description = provider. Thêm hậu tố `(brain: đang dùng)` và/hoặc `(side: đang dùng)` nếu khớp cả provider và model trong `profiles.brain` / `profiles.side`. Model `providers.dsh.models` chỉ cho tầng Hand và nhập qua “Other”.
   - **Effort** — header `Effort`, hỏi “Chọn effort nào? DeepSeek off nhập qua Other.”: bốn lựa chọn `low`, `medium`, `high`, `max`; description tương ứng “Mức low”, “Mức medium”, “Mức high”, “GPT: xhigh”. CLI chuẩn hoá Codex `max` thành `xhigh`; không tự alias effort khác.
   - **Account** — header `Account`, hỏi “Chọn tài khoản nào?”: lấy `accounts`, label = `label`, thêm hậu tố `(đang dùng)` cho mục `selected: true`; description ghi “chỉ áp cho Claude; GPT/DeepSeek bỏ qua; với Hand chọn backend claude-vN”. Giữ `slot` của mục chọn, không suy slot từ label.
3. Map nhãn về giá trị gốc qua ánh xạ đã giữ, bỏ hậu tố đánh dấu. Với “Other”, tầng/model/account phải xác định được trong danh sách JSON; model DeepSeek chỉ hợp lệ ở tầng Hand. Effort phải thuộc `providers.<provider>.efforts` của model đã chọn, hoặc là `max` cho Codex (CLI chuẩn hoá thành `xhigh`); DeepSeek `off` nhập qua “Other”. Không tự chọn thay người dùng. Hủy, thiếu câu trả lời hoặc không xác định được lựa chọn thì dừng, không ghi và không mở câu hỏi bổ sung.
4. Chạy đúng **một lệnh** ghi với các giá trị đã chọn, quote từng đối số bằng shell quoting an toàn (kể cả giá trị nhập qua “Other”):

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models set --tier '<tier>' --model '<model>' --effort '<effort>' --account '<slot>'
```

Luôn truyền `--account`: CLI tự bỏ qua với GPT/DeepSeek và in cảnh báo “account chỉ áp cho Claude, đã bỏ qua”. Với Hand Claude, slot chọn backend `claude-vN`; GPT chọn backend `codex`, DeepSeek chọn `dsh`. Không tự thêm cờ hoặc đổi hand-order.

Lựa chọn trên màn hình là xác nhận để ghi: không chạy thêm dry-run, không hỏi xác nhận thêm. In kết quả; ghi thành công nhắc “mở phiên mới để áp dụng”. Lỗi thì báo rồi dừng, không tự sửa config hay chạy lại.

## 3. Các đối số khác: chuyển nguyên cho CLI

Với `set` kèm cờ, `unset`, `options`, `--dry-run`, `--json` hoặc các đối số khác, chuyển nguyên `$ARGUMENTS`:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models $ARGUMENTS
```

Không tự thêm cờ hoặc suy ra thay đổi. Chỉ chạy `unset` khi người dùng nêu rõ; chỉ gỡ cả tầng `brain|side|hand`, không gỡ từng backend. Dry-run không ghi cấu hình.

In kết quả lệnh. Ghi thành công thì nhắc: “mở phiên mới để áp dụng”; không đổi model/account phiên đang chạy. Nếu bất kỳ lệnh nào báo lỗi, báo thông báo lỗi rồi dừng; không tự sửa config hay chạy lại.
