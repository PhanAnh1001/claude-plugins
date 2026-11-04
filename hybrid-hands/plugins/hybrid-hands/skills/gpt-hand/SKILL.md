---
name: gpt-hand
description: Giao một việc code hoặc tài liệu tự chứa cho hand GPT-6.1 Sol Flex qua Codex bằng lệnh hand-gpt - viết brief vào file, estimate, báo bảng chi phí, chờ duyệt khi từ approval_usd, run nền, đọc report, brain tự review diff, báo USD thật; xử lý flex_rejected, capped; cài đặt lần đầu. Từ khoá kích hoạt - "hand GPT", "hand-gpt", "GPT-6.1", "Sol Flex", "Codex", "giao GPT", "hand rẻ", "estimate hand", "chi phí hand".
---

# Hand GPT (hand-gpt)

## Tóm tắt

- **Dùng khi:** việc code/tài liệu tự chứa, phạm vi file rõ: sửa hay viết script, viết test, refactor trong vài file, soát hay sửa tài liệu, đọc code trả lời câu hỏi.
- **Không dùng khi:** cần tool riêng của Claude Code (Chrome, MCP, Skill, đọc ảnh, SendMessage), chạy lệnh trả phí của dự án, cần hook của repo bảo vệ → dùng `hybrid-hands:hand`.
- **Chuỗi bước:** brief vào file → `hand-gpt estimate` → bảng chi phí trong chat → (duyệt nếu từ `approval_usd`) → `hand-gpt run` chạy nền → đọc report → brain review diff → báo USD thật.
- **Luật cứng:** Codex không chịu hook của Claude Code, nên brief chép nguyên văn luật cấm (nhất là cấm đọc `.env`) và PHẠM VI GHI hẹp; tối đa 2 lệnh trả phí cùng lúc.

## 1. Cài đặt lần đầu (mỗi máy)

1. `hand-gpt setup` (tạo cấu hình, `CODEX_HOME` riêng `~/.codex-hand`).
2. Người dùng tự chạy trong terminal riêng (agent không chạy, không thấy key): `CODEX_HOME=~/.codex-hand codex login --with-api-key`.
3. `hand-gpt doctor` tới khi đạt.

Cấu hình dự án ở `.claude/hybrid-hands.json`, mục `gpt_hand` (mặc định model gpt-6.1-sol, tầng Flex, `effort` medium, `max_usd` 1.0, `approval_usd` 1.5).

Nếu `hand-gpt` không có trong PATH, gọi bằng đường dẫn tuyệt đối `${CLAUDE_PLUGIN_ROOT}/bin/hand-gpt`.

## 2. Một lượt giao việc

1. **Brief:** viết theo khuôn 7 mục (MỤC TIÊU, NGỮ CẢNH, PHẠM VI GHI, KHÔNG ĐƯỢC ĐỤNG, LUẬT BẮT BUỘC, KIỂM CHỨNG, TRẢ VỀ) vào file tạm trong scratchpad, ví dụ `<scratchpad>/brief-<nhãn>.md`. LUẬT BẮT BUỘC chép nguyên văn từ AGENTS.md/CLAUDE.md của repo, luôn có câu cấm đọc `.env`; PHẠM VI GHI liệt kê từng file.
2. **Estimate:** `hand-gpt estimate --brief <file> [--effort E] [--max-usd X] [--cwd D]`.
3. **Bảng chi phí trong chat (luôn báo):** model, việc gì, effort, token ước, trần `--max-usd`, đơn giá có nguồn, tổng USD dự kiến, tổng đã chi trong sổ `output/llm/codex_usage.json`.
4. **Ngưỡng:** trần tối đa từ `approval_usd` trở lên → chờ người dùng đồng ý trong chat, rồi thêm `--approved`. Dưới ngưỡng → báo bảng rồi chạy luôn. Không chia nhỏ việc để lách ngưỡng.
5. **Run nền:** tool Bash với `run_in_background`:
   `hand-gpt run --brief <file> --label <nhãn> [--cwd D] [--effort E] [--max-usd X] [--timeout-min M] [--sandbox S] [--approved]`
   Chờ thông báo khi lệnh thoát; không viết vòng chờ riêng.
6. **Đọc kết quả:** khối tóm tắt cuối output và `report.md` theo đường dẫn được in.
7. **Review:** brain tự `git diff` các file hand đã đổi; lỗi thì một lượt `run` mới với brief gọn chép sẵn phát hiện (hand GPT không nhận SendMessage).
8. **Báo USD thật:** từ khối tóm tắt hoặc `hand-gpt report [--since D] [--label L]`.

## 3. Xử lý lỗi

- **`flex_rejected`** (Flex hết chỗ hoặc bị từ chối): không tự chuyển sang giá standard; giao lại việc cho `hybrid-hands:hand`. Chỉ dùng `--allow-standard` khi người dùng đồng ý (giá cao hơn, báo lại bảng chi phí).
- **`capped`** (chạm trần `max_usd`): đọc report xem phần đã xong; muốn chạy tiếp thì báo bảng mới, xét ngưỡng lại.
- **Lỗi khác hoặc `doctor` không đạt:** dùng `hybrid-hands:hand` làm dự phòng, báo người dùng kèm output thật.
