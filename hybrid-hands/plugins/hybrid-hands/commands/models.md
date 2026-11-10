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

## 2. Chỉ có `set`: wizard nhiều màn hình

Khi `$ARGUMENTS` là đúng `set`, không có cờ hay đối số khác, chọn tầng → provider → account → model → effort + chế độ Hand rồi ghi một lần. Tối đa **5 lần AskUserQuestion nối tiếp**; options của màn hình sau được tạo sau khi nhận câu trả lời màn hình trước, không đặt câu hỏi động trong cùng một lần gọi.

0. Chạy `"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models options --json` để lấy dữ liệu chỉ đọc. Dùng đúng `providers`, `profiles`, `accounts`, `hand_backends`, `hand_modes` trong JSON; không dùng `presets`, không tự đặt model/account hay đọc file tài khoản. Lệnh lỗi thì báo rồi dừng.

Giữ trạng thái riêng cho từng tầng đã tích trong trí nhớ đến khi ghi: provider, account slot (chỉ Claude), model, effort và backend/chế độ (chỉ Hand). Mỗi câu có header tương ứng `Brain`, `Phiên phụ`, `Hand`; câu chế độ dùng header `Chế độ` (≤12 ký tự). Giữ ánh xạ nhãn hiển thị → giá trị JSON gốc; hậu tố “(đang dùng)” chỉ để hiển thị, không đưa vào đối số. “Other” do công cụ cung cấp, không thêm thành option riêng; chỉ chấp nhận giá trị gốc thuộc danh sách JSON của câu đó (provider dùng ánh xạ Claude → `claude`, GPT → `codex`, DeepSeek → `dsh`). Ở mọi màn hình, hủy, thiếu câu trả lời hoặc Other ngoài danh sách thì dừng, không ghi và không hỏi bổ sung. Danh sách cần dùng rỗng/không hợp lệ thì báo lỗi và dừng, không tự đoán.

1. **Màn hình 1 — Tầng:** gọi AskUserQuestion với một câu, header `Tầng`, `multiSelect: true`, hỏi “Sửa tầng nào? (tích nhiều ô)”. Có đúng ba lựa chọn:
   - `Brain chính`: description là cấu hình hiện tại từ `profiles.brain` (provider/model/effort/account).
   - `Phiên phụ`: description là cấu hình hiện tại từ `profiles.side`.
   - `Hand`: description là danh sách `hand_backends` hiện tại gọn (backend/model/effort).
   Không tích ô nào hoặc hủy thì báo “Không đổi cấu hình” rồi dừng.
2. **Màn hình 2 — Provider:** một lần AskUserQuestion, mỗi tầng đã tích một câu, `multiSelect: false`, hỏi provider muốn dùng. Brain/Phiên phụ có `Claude`, `GPT`; Hand có `Claude`, `GPT`, `DeepSeek`. Đánh dấu “(đang dùng)” cho provider hiện tại từ `profiles.brain`/`profiles.side`. Lưu provider cho từng tầng, giữ nguyên lựa chọn tầng.
3. **Màn hình 3 — Account:** chỉ hỏi các tầng vừa chọn Claude; một lần AskUserQuestion, mỗi tầng một câu `multiSelect: false`. Options lấy từ `accounts`: label = `label`, description = `slot`, ánh xạ về `slot`. Với Brain/Phiên phụ, đánh dấu “(đang dùng)” theo `profiles.<brain|side>.account` chỉ khi provider hiện tại của profile là `claude`. Chỉ có một account thì tự dùng slot đó và bỏ câu; không còn câu nào thì bỏ màn hình. Provider khác không hỏi hay gắn account. Giữ tất cả lựa chọn trước đó.
4. **Màn hình 4 — Model:** trước hết xác định backend của mỗi Hand từ provider/account: Claude → `claude-<slot>`, GPT → `codex`, DeepSeek → `dsh`; tìm cấu hình hiện tại theo `hand_backends[].value` tương ứng. Chỉ hỏi tầng mà `providers.<provider>.models` có nhiều hơn một model: một lần AskUserQuestion, mỗi tầng một câu `multiSelect: false`. Options lấy từ danh sách models, tối đa bốn model đầu theo thứ tự JSON; model còn lại nhập bằng Other và vẫn phải thuộc danh sách đầy đủ đó. Đánh dấu “(đang dùng)” khi trùng model hiện tại của profile hoặc backend Hand vừa xác định. Chỉ có một model thì tự dùng và bỏ câu; không còn câu nào thì bỏ màn hình. Lưu model, giữ provider/account và các tầng trước đó.
5. **Màn hình 5 — Effort + Chế độ:** một lần AskUserQuestion, mọi tầng đã tích mỗi tầng một câu `multiSelect: false`. Options lấy từ `providers.<provider>.efforts` (tối đa bốn), đánh dấu “(đang dùng)” khi trùng effort hiện tại của profile/backend tương ứng. Lưu effort, giữ toàn bộ lựa chọn trước đó.
   Nếu đã tích Hand với provider Claude hoặc GPT, thêm ngay trong **cùng lần AskUserQuestion này** một câu header `Chế độ`, `multiSelect: false`, hỏi “Hand chạy kiểu nào?” với hai lựa chọn:
   - `Native subagent`: description “chạy trong phiên khi cùng tài khoản và đủ capability”, ánh xạ thành `native`.
   - `Terminal hand`: description “luôn chạy qua hand-ext run”, ánh xạ thành `terminal`.
   Đánh dấu “(đang dùng)” theo `hand_modes.<provider>` từ JSON; `hand_backends[].mode` cho biết chế độ của từng backend. Lưu giá trị chế độ cho Hand. DeepSeek (`dsh`) luôn terminal, bỏ câu Chế độ. Khi hỏi chế độ, toàn màn hình có tối đa bốn câu (ba tầng effort và một chế độ); không mở thêm lần hỏi.
6. **Kiểm tra và ghi:** gom đối số theo thứ tự Brain, Phiên phụ, Hand, chỉ gồm các tầng đã tích:
   - Brain → `--brain <model>:<effort>[@<slot>]`.
   - Phiên phụ → `--side <model>:<effort>[@<slot>]`.
   - Hand → `--hand <backend>=<model>:<effort>`; nếu đã có câu Chế độ, thêm `--hand-mode native|terminal` theo lựa chọn. Với `dsh`, không thêm `--hand-mode`.
   `--hand-mode` áp cho provider của các `--hand` cùng lệnh: `native` ghi `ext_hand.native.<claude|codex> = auto`, `terminal` ghi `off`; `dsh` + `native` bị CLI từ chối với exit 2. Chỉ thêm `@<slot>` khi provider là Claude. Chạy **đúng một lệnh**, quote an toàn từng đối số:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models set <args...>
```

`<args...>` là danh sách đã gom, không phải chuỗi shell để thực thi trực tiếp. Không tự thêm cờ hoặc đổi hand-order. Lựa chọn là xác nhận để ghi: không dry-run, không hỏi lại; mọi thay đổi được ghi atomic một lần.

7. In kết quả; ghi thành công nhắc “mở phiên mới để áp dụng”. Lỗi thì báo rồi dừng, không tự sửa config hay chạy lại.

## 3. Các đối số khác: chuyển nguyên cho CLI

Với `set` kèm cờ, `unset`, `options`, `--dry-run`, `--json` hoặc các đối số khác, chuyển nguyên `$ARGUMENTS`:

```sh
"${CLAUDE_PLUGIN_ROOT}/bin/hand-ext" models $ARGUMENTS
```

Không tự thêm cờ hoặc suy ra thay đổi. Chỉ chạy `unset` khi người dùng nêu rõ; chỉ gỡ cả tầng `brain|side|hand`, không gỡ từng backend. Dry-run không ghi cấu hình.

In kết quả lệnh. Ghi thành công thì nhắc: “mở phiên mới để áp dụng”; không đổi model/account phiên đang chạy. Nếu bất kỳ lệnh nào báo lỗi, báo thông báo lỗi rồi dừng; không tự sửa config hay chạy lại.
