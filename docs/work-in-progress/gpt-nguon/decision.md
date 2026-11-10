# Quyết định nguồn GPT usage 0.30.0

Tổng GPT machine USD~ chỉ cộng token delta có timestamp quan sát được trong cửa sổ reset quota tuần hiện tại từ hai thư mục cố định `~/.codex-hand/sessions` và `~/.codex-hand/archived_sessions`. Khử trùng thread/event và không cộng lại ledger. Metadata-only thread không làm tổng unknown; không có event trong cửa sổ hoặc nguồn không đủ baseline/timestamp/giá hợp lệ, file không đọc được hay thiếu cửa sổ thì `?`. Giá lấy duy nhất từ canonical model-prices.json, không fallback model lạ.

Phần riêng session pinned rollout/native child dùng chênh lệch weekly used_percent từ ít nhất hai sample rate_limits có timestamp hợp lệ, không giảm và cùng reset còn hiện tại. Source `codex_rate_limits_delta`, estimated false, nhãn `GPT riêng (đo) N% tuần`; thiếu điều kiện hiện `?`. Phép đo là biến động quota tài khoản trong khoảng phiên, có thể chứa hoạt động đồng thời, không quy riêng độc quyền cho phiên.

GPT account có duration tường minh phân loại 5h bằng window_minutes=300, không đổi nhãn primary tuần 10080 phút. Source account rollout legacy thiếu duration giữ tương thích primary=5h/secondary=tuần theo contract cũ. Phép đo GPT phần riêng mới bắt buộc duration tuần tường minh window_minutes=10080. Claude 5h dùng cache/live sẵn có với freshness/reset hiện tại, hỗ trợ numeric/ISO; hết hạn hoặc thiếu thì unknown. Statusline dùng chung helper nguồn usage, release riêng.

USD~ là ước tính offline subscription, không phải hoá đơn. Tổng local observed không bảo đảm bao phủ mọi hoạt động tài khoản. Không suy quota từ token/USD, không đổi colors/layout/counts/pool hay quy ước unknown legacy. Không dùng số live trong quyết định này.
