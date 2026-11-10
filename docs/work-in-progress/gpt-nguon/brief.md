# Brief Sol `gpt-nguon`: lấp các chỗ `?` của GPT và quota 5h trên panel

## Tóm tắt

- Mục tiêu: panel Paseo, hh-ps và statusline hiện số thật thay cho `?` ở 4 chỗ:
  1. Dòng tổng `GPT máy này tuần ~$?`.
  2. `GPT riêng ? tuần` trên từng dòng phiên/subagent Codex.
  3. `GPT 5h ?`.
  4. `Claude 5h ?`.
  Chỉ hiện số khi có nguồn đo thật. Nguồn không có thì giữ `?` và ghi lý do vào bàn giao.
- Lane: L1 có lựa chọn giải pháp (chọn nguồn). Bàn giao mở bằng tóm tắt quyết định ≤1 trang.
- Phiên brain có thể bị cắt khi daemon Paseo restart sau phiên này. Bàn giao phải tự đủ, đọc được mà không cần hỏi lại.

## Ngữ cảnh

- Bàn giao `docs/work-in-progress/handoffs/native-child.md`, mục "Bằng chứng live":
  - GPT total null vì độ phủ nguồn bảo thủ.
  - Phần riêng GPT null, không suy từ token/USD.
  - Quota GPT 5h null, tuần 16%. Claude 5h `?`.
- Ứng viên nguồn để Sol kiểm, đều do Sol tự đọc metadata thật:
  - Sự kiện `token_count` trong rollout Codex dưới `~/.codex-hand` có `rate_limits` (primary/secondary `used_percent`, `window_minutes`, `resets_at`).
  - Rollout có token theo từng lượt. Cộng chúng theo giá ở `config/model-prices.json` cho ra USD~ tuần của máy.
  - Phần riêng của một phiên = `used_percent` ở sự kiện cuối trừ ở sự kiện đầu trong cùng cửa sổ reset, gắn nhãn `riêng (đo)`. Đây là số đo từ nguồn quota, không suy từ token.
  - Claude 5h lấy từ cache/sample sẵn có của statusline hoặc hh-ps.
- Luật `AGENTS.md`:
  - USD~ là ước tính offline subscription, không phải hoá đơn.
  - Quota 5h/tuần lấy cache/sample sẵn có, thiếu thì `?`.
  - Không suy token/USD thành quota GPT.
  - Phần riêng tuần chỉ hiện khi có nguồn và nhãn riêng.
  - Nguồn giá duy nhất là `config/model-prices.json`.

## PHẠM VI GHI

- `hybrid-hands/plugins/hybrid-hands/lib/hh_ps/`, `lib/hand_ext/codex_usage.py`, `lib/usage_pricing.py` nếu cần, và test tương ứng trong `hybrid-hands/tests/` (fixture giả).
- `hybrid-hands/paseo-hh-tree/`: chỉ sửa nếu cần hiển thị nhãn mới. Giữ dòng gọn và màu hiện có.
- `statusline/`: chỉ sửa nếu dùng chung nguồn và đang hiện `?` cùng chỗ. Có sửa thì chạy test statusline.
- Mục contract trong `AGENTS.md`/`hybrid-hands/README.md`; `plugin.json` + `CHANGELOG.md` mục 0.30.0 (statusline bump riêng nếu có sửa).
- Bàn giao `docs/work-in-progress/handoffs/gpt-nguon.md` + `.done`, log ở `docs/work-in-progress/gpt-nguon/`.

## KHÔNG ĐƯỢC ĐỤNG

Các file cấm theo `AGENTS.md`: `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `~/.paseo/config.json`, `installed_plugins.json`, credential. Không `paseo daemon restart`. Không commit/push (Opus commit sau). Không xoá/di chuyển `output/llm/`. Không gọi API trả phí.

## LUẬT BẮT BUỘC (chép nguyên văn vào brief hand ngoài)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

Sol tự đọc metadata rollout/usage thật để chọn nguồn và kiểm chứng. Không chép nội dung hội thoại vào bàn giao. Không giao hand đọc rollout thật.

## KIỂM CHỨNG

- Mức test: tối thiểu. Tối đa 3 ca test:
  - (a) Fixture rollout giả có `rate_limits` đầu/cuối → phần riêng GPT đúng và có nhãn; khác cửa sổ reset → `?`.
  - (b) Tổng USD~ GPT tuần của máy cộng đúng theo bảng giá; model lạ → `?`, không fallback.
  - (c) Quota 5h có sample → hiện số; không có → `?`.
- Trong lúc làm: test hẹp, typecheck/build panel.
- Cuối, đúng một lần: full suite hybrid-hands, cộng statusline nếu có sửa. Full xanh thì làm tiếp:
  - Cập nhật bản cài bằng CLI và reload plugin Paseo (không restart daemon).
  - Chạy `hh-ps --once`, lưu mẫu đã làm sạch: trước có `?`, sau có số.
- Xong khi: 3 ca đạt, full xanh, bản cài 0.30.0, mẫu thật.

## TRẢ VỀ

Bàn giao mở bằng `## Tóm tắt`: nguồn chọn cho từng chỗ `?`, chỗ nào vẫn `?` và vì sao, file đổi, lệnh và kết quả thật, bản cài, mẫu, phần chưa kiểm chứng.
