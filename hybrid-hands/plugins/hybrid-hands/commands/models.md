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

## 2. Chỉ có `set`: chọn từ danh sách

Khi `$ARGUMENTS` là đúng `set`, không có cờ hay đối số khác:

1. Chạy `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models options --json` để lấy danh sách chỉ đọc. Dùng đúng dữ liệu JSON trả về, không tự đặt model/effort/account hay đọc file tài khoản.
2. Dùng AskUserQuestion hỏi “Cấu hình tầng nào?”, chọn một trong ba mục `tiers`: label = `label`, description = `current`; giữ `value` để xác định tầng.
3. Thực hiện nhánh tương ứng bên dưới. Mọi câu hỏi chọn một mục (`multiSelect: false`). Mỗi câu tối đa 4 lựa chọn theo thứ tự JSON; nếu dư, người dùng nhập mục còn lại qua “Other”. Giữ ánh xạ từ nhãn sang giá trị gốc; “Other” phải xác định được giá trị trong danh sách trả về. Không tự chọn thay người dùng; nếu hủy hoặc chưa xác định được lựa chọn thì dừng, không ghi.

### Brain hoặc side

- Hỏi chọn model bằng AskUserQuestion: mỗi lựa chọn là một cặp provider:model từ `providers.claude.models` rồi `providers.codex.models`. Label = model, description = provider; thêm “(đang dùng)” cho mục khớp cả provider và model trong `profiles.<tier>`.
- Hỏi tiếp bằng một lần AskUserQuestion gồm câu effort và, chỉ khi provider đã chọn là `claude`, câu account. Effort lấy từ `providers.<provider>.efforts` (tối đa 4). Account lấy từ `accounts`, label = `label`, đánh dấu “(đang dùng)” ở mục có `selected: true`; dùng `slot` của mục chọn, không suy slot từ label.
- Chạy đúng lệnh với các giá trị người dùng vừa chọn, quote từng đối số bằng shell quoting an toàn:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models set --<tier> '<provider>:<model>:<effort>[@<slot>]'
```

`<tier>` chỉ là `brain` hoặc `side`; chỉ nối `@<slot>` khi provider là `claude`. Codex không hỏi account và không có hậu tố account.

### Hand

- Dùng AskUserQuestion chọn backend từ `hand_backends`: label = `value`, description = model và effort hiện tại. Giữ `provider` của backend đã chọn.
- Dùng một lần AskUserQuestion hỏi model và effort từ `providers.<provider>.models` / `providers.<provider>.efforts`. Nếu provider chỉ có một model thì dùng model đó và bỏ câu hỏi model; vẫn hỏi effort. Mỗi câu tối đa 4 lựa chọn, dư dùng “Other” như trên.
- Chạy đúng lệnh với các giá trị đã chọn, quote từng đối số bằng shell quoting an toàn:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models set --hand '<backend>=<model>:<effort>'
```

Lựa chọn trong danh sách là xác nhận của người dùng. Không hỏi xác nhận thêm, không chạy thêm dry-run, không tự thêm cờ hoặc đổi hand-order.

## 3. Các đối số khác: chuyển nguyên cho CLI

Với `set` kèm cờ, `unset`, `options`, `--dry-run`, `--json` hoặc các đối số khác, chuyển nguyên `$ARGUMENTS`:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models $ARGUMENTS
```

Không tự thêm cờ hoặc suy ra thay đổi. Chỉ chạy `unset` khi người dùng nêu rõ; chỉ gỡ cả tầng `brain|side|hand`, không gỡ từng backend. Dry-run không ghi cấu hình.

In kết quả lệnh. Ghi thành công thì nhắc: “mở phiên mới để áp dụng”; không đổi model/account phiên đang chạy. Nếu bất kỳ lệnh nào báo lỗi, báo thông báo lỗi rồi dừng; không tự sửa config hay chạy lại.
