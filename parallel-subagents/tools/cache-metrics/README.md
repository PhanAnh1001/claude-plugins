# cache-metrics

Bộ công cụ đo prompt cache của Claude Code từ transcript cục bộ (`~/.claude/projects`), dùng để so sánh trước/sau khi cài policy parallel-subagents 2.1.0 (mốc mặc định 2026-11-02T12:00 giờ local). Một lịch launchd chạy đo lại một lần vào 2026-11-16 09:07, ghi `out/followup-<ngày>.md` và gửi thông báo macOS. Công cụ chỉ in số liệu, không in nội dung hội thoại; thư mục này không thuộc phần plugin được ship.

## Thành phần

| File | Vai trò |
|---|---|
| `compare_periods.py` | Bảng Markdown TRƯỚC/SAU mốc `--cutoff` cho subagent và main: request, cache hit, chi phí quy đổi/request, resume, miss RESUME và TOOL DÀI (Bash) 5-60 phút, ngữ cảnh lúc resume, hand mỗi phiên. Cảnh báo khi mẫu SAU < 2.000 request subagent. |
| `compact_cache.py` | Tổng quan cache, sự kiện compact, tham số B/S/g, phân bố ngữ cảnh, A/B theo ngày. |
| `resume_miss.py` | Phân loại miss lớn 5-60 phút của subagent (RESUME / TOOL DÀI / KHÁC); cung cấp bộ quét cho `compare_periods.py`. |
| `run_followup.sh` | Chạy cả ba script, ghi `out/followup-<YYYY-MM-DD>.md`, gửi thông báo. `--once` tự gỡ lịch sau khi chạy. |
| `install_schedule.sh` | Sinh plist `com.parallel-subagents.cache-metrics-followup` trong `~/Library/LaunchAgents` và nạp bằng `launchctl bootstrap`. |
| `out/` | Kết quả và log launchd (bị gitignore). |

## Chạy tay

```bash
python3 -I compare_periods.py                       # mốc mặc định
python3 -I compare_periods.py --cutoff 2026-11-02T12:00 --out out/compare.md
python3 -I compact_cache.py --projects-dir ~/.claude/projects --out out/compact.txt
python3 -I resume_miss.py --out out/resume.txt
./run_followup.sh                                   # cả ba, khoảng 35 giây với ~57k request
```

Chỉ dùng thư viện chuẩn Python (chạy được với `/usr/bin/python3` 3.9).

## Đặt và gỡ lịch

```bash
./install_schedule.sh                    # 2026-11-16 09:07 giờ local
./install_schedule.sh 2026-11-20 08:30   # ngày/giờ khác
./install_schedule.sh --uninstall
launchctl print gui/$(id -u)/com.parallel-subagents.cache-metrics-followup
```

Plist trỏ tới đường dẫn tuyệt đối của `run_followup.sh` trên máy hiện tại; chuyển thư mục repo thì cài lại.

## Hạn chế

- Máy tắt vào giờ hẹn: launchd không chạy bù. Máy ngủ: lần chạy dồn lại và thực hiện khi máy thức dậy.
- `StartCalendarInterval` không có năm và lặp hằng năm; vì vậy lịch gọi `run_followup.sh --once` để tự gỡ agent và xóa plist sau lần chạy đầu.
- Hệ số chi phí là bội số giá input (read 0,05 opus-5-5, 0,025 fable-5-1, 0,1 model khác; write 5m 1,25; write 1h 2; output 5), cần cập nhật khi bảng giá đổi.
- Giai đoạn được gán theo timestamp từng request; một hand được tính vào giai đoạn chứa request đầu tiên của nó.
