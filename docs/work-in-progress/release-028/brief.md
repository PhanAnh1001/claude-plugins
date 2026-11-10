# Brief Sol `release-028`: sửa 2 test lỗi, full xanh, cập nhật bản cài 0.28.0

## Tóm tắt

- Mục tiêu: full suite hybrid-hands xanh ở 0.28.0, rồi cập nhật bản cài mọi scope và reload plugin Paseo.
- Lane: L0. Không có lựa chọn giải pháp.
- Nguồn: bàn giao `docs/work-in-progress/handoffs/panel-gon.md` (mục "Hai lỗi full và ranh giới") và log `docs/work-in-progress/panel-gon/full-hybrid-hands.log`.

## Việc

1. `test_hand_ext_dsh.VersionTest.test_user_agent_matches_plugin_version`: `dsh.USER_AGENT` còn `0.27.0`, manifest đã là `0.28.0`. Sửa nguồn User-Agent cho khớp manifest. Nếu đọc version từ manifest gọn và an toàn thì làm theo cách đó để lần sau không lệch nữa.
2. `test_hh_ps_codex.CodexPanelTest.test_codex_usd_pct_samples_and_gpt_account_limits`: regex `reset \d\d:\d\d` fail khi mốc reset rơi sang ngày khác, khi đó output là `reset 08/11 00:19`. Test phụ thuộc giờ chạy. Cố định `now` trong test, hoặc cho regex nhận được phần ngày tuỳ chọn. Không đổi hành vi render.
3. Chạy full suite đúng một lần: `python3 -m unittest discover -s hybrid-hands/tests -q`. Full xanh thì làm tiếp 2 bước:
   - Cập nhật bản cài mọi scope bằng CLI như các đợt trước (`hybrid-hands/README.md`). Kiểm lại các record đều là 0.28.0.
   - Rebuild và reload plugin Paseo `paseo-hh-tree` (chỉ reload plugin, KHÔNG `paseo daemon restart`).
4. Thêm dòng changelog vào mục 0.28.0 nếu việc 1 đổi cách lấy version.

## PHẠM VI GHI

`hybrid-hands/plugins/hybrid-hands/lib/hand_ext/backends/dsh.py` (hoặc nơi định nghĩa USER_AGENT), `hybrid-hands/tests/test_hh_ps_codex.py`, `hybrid-hands/plugins/hybrid-hands/CHANGELOG.md` (mục 0.28.0), bàn giao `docs/work-in-progress/handoffs/release-028.md` + `.done`, log ở `docs/work-in-progress/release-028/`.

## KHÔNG ĐƯỢC ĐỤNG

Panel và hiển thị (`paseo-hh-tree/`, `hh-tree-pane/`, `lib/hh_ps/render.py`), `statusline/`, `AGENTS.md`. Các file cấm theo `AGENTS.md`: `.claude/hybrid-hands.json`, `~/.codex-hand/config.toml`, `~/.claude/settings.json`, `~/.paseo/config.json`, credential. Không sửa tay `installed_plugins.json`: CLI không cập nhật được record nào thì ghi vào bàn giao. Không `paseo daemon restart`. Không commit/push. Không xoá/di chuyển `output/llm/`. Giữ mọi thay đổi chưa commit.

## LUẬT BẮT BUỘC (chép nguyên văn vào brief hand ngoài)

Không in/hiện giá trị `.env`, token, credential ở bất kỳ tầng nào; công cụ của plugin (`hand-ext doctor/run`, đọc hạn mức) được đọc file auth nội bộ, chỉ không được in giá trị. Brief giao hand ngoài chép nguyên văn luật này.
Không đọc `.env` bằng lệnh hay tool hiện giá trị: `cat`, `head`, `tail`, `grep`, `sed`, `awk`, `less`, `more`, `rg`, `Read`, kể cả có che phần sau dấu `=`.
Không đọc hay in token, auth.json, file credential. Không giao hand ngoài việc cần secret hay dữ liệu khách hàng. Chỉ dùng code và fixtures giả công khai được; không đọc transcript/log thật. Không gọi API trả phí, không tạo hay dùng API key.

## KIỂM CHỨNG

- Mức test: tối thiểu, không thêm test mới.
- Trong lúc làm: chạy riêng 2 test trên.
- Cuối: chạy full đúng một lần.
- Xong khi: full xanh, mọi record bản cài 0.28.0, plugin Paseo đã reload.

## TRẢ VỀ

Bàn giao mở bằng `## Tóm tắt`: file đổi, lệnh và kết quả thật (số test, exit code), trạng thái từng record bản cài, kết quả reload Paseo, phần chưa kiểm chứng.
