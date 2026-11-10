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

1. Chạy `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models options --json` để lấy dữ liệu chỉ đọc. Dùng đúng JSON trả về, không tự đặt model/account hay đọc file tài khoản. Lệnh lỗi thì báo rồi dừng.
2. Gọi AskUserQuestion **đúng một lần**, gồm đủ 4 câu dưới đây trên cùng màn hình. Mọi câu đều `multiSelect: false`; options lấy nguyên các mục trong nhóm `presets` tương ứng theo đúng thứ tự, label = `label`, description = `description`, không tự thêm/bớt mục. Mỗi nhóm tối đa 4 mục, mục đầu là “Giữ nguyên”; “Other” do công cụ cung cấp, không thêm thành lựa chọn riêng. Giữ ánh xạ lựa chọn về `args` của preset.
   - **Brain chính** — header `Brain`, options = `presets.brain`. Hỏi: “Chọn cho từng tab; tab để Giữ nguyên thì không đổi. Brain chính dùng cấu hình nào? Other: nhập model:effort[@vN], ví dụ claude-haiku-5-5:low@v1; GPT max = xhigh.”
   - **Phiên phụ** — header `Phiên phụ`, options = `presets.side`. Hỏi: “Phiên phụ dùng cấu hình nào? Other: nhập model:effort[@vN], ví dụ claude-haiku-5-5:low@v1; GPT max = xhigh.”
   - **Hand Claude** — header `Hand Claude`, options = `presets.hand_claude`. Hỏi: “Hand Claude dùng cấu hình nào? Other: nhập claude-vN=model:effort; nhiều mục cách nhau bằng dấu phẩy.”
   - **Hand GPT/DeepSeek** — header `Hand GPT`, options = `presets.hand_other`. Hỏi: “Hand GPT/DeepSeek dùng cấu hình nào? Other: nhập codex=model:effort hoặc dsh=model:effort; nhiều mục cách nhau bằng dấu phẩy.”
3. Gom đối số của cả 4 câu theo thứ tự trên thành một danh sách:
   - Chọn preset: nối nguyên `args` của preset đó; “Giữ nguyên” có `args` rỗng.
   - Other ở Brain: thêm `--brain` và nguyên text nhập; ở Phiên phụ: thêm `--side` và nguyên text nhập.
   - Other ở hai nhóm Hand: tách text theo dấu phẩy, trim khoảng trắng ở mỗi mục; với từng mục thêm `--hand` và mục đó. Ngoài thao tác tách/trim này, không tự sửa text người dùng nhập; để CLI validate.
   - Hủy, thiếu câu trả lời hoặc không xác định được lựa chọn thì dừng, không ghi và không hỏi bổ sung.
4. Nếu danh sách args rỗng (tất cả “Giữ nguyên”), báo “Không đổi cấu hình” và không chạy lệnh ghi. Ngược lại chạy **đúng một lệnh**, quote từng đối số bằng shell quoting an toàn, kể cả text nhập qua Other:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models set <args...>
```

`<args...>` là danh sách đã gom, không phải chuỗi shell để thực thi trực tiếp. Không tự thêm cờ hoặc đổi hand-order. Các lựa chọn trên màn hình là xác nhận để ghi: không dry-run, không hỏi lại; mọi thay đổi được ghi atomic một lần.

5. In kết quả; ghi thành công nhắc “mở phiên mới để áp dụng”. Lỗi thì báo rồi dừng, không tự sửa config hay chạy lại.

## 3. Các đối số khác: chuyển nguyên cho CLI

Với `set` kèm cờ, `unset`, `options`, `--dry-run`, `--json` hoặc các đối số khác, chuyển nguyên `$ARGUMENTS`:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models $ARGUMENTS
```

Không tự thêm cờ hoặc suy ra thay đổi. Chỉ chạy `unset` khi người dùng nêu rõ; chỉ gỡ cả tầng `brain|side|hand`, không gỡ từng backend. Dry-run không ghi cấu hình.

In kết quả lệnh. Ghi thành công thì nhắc: “mở phiên mới để áp dụng”; không đổi model/account phiên đang chạy. Nếu bất kỳ lệnh nào báo lỗi, báo thông báo lỗi rồi dừng; không tự sửa config hay chạy lại.
