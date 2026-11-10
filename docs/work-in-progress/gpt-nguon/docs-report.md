# Báo cáo tài liệu 0.30.0

Đã sửa AGENTS.md (chỉ contract), hybrid-hands/README.md (contract nguồn usage), hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json (0.30.0), hybrid-hands/plugins/hybrid-hands/CHANGELOG.md (thêm đầu 0.30.0, giữ lịch sử). Tạo decision.md trong thư mục này, không dùng số live.

Contract ghi rõ tổng GPT observed token deltas trong weekly quota reset window, dedup và unknown; quota riêng là biến động account sample trong khoảng phiên, có thể gồm đồng thời; source/default/label, cửa sổ GPT 5h và kiểm freshness/reset Claude. Không sửa code/tests/panel/statusline.

Kiểm chứng thực tế:
- `python3 -m json.tool hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json > /dev/null`: exit 0.
- Python Path.exists kiểm target nội bộ canonical pricing và AGENTS.md được nhắc trong contract: đạt. Không thêm/sửa URL liên kết Markdown.
- `git diff --check -- AGENTS.md hybrid-hands/README.md hybrid-hands/plugins/hybrid-hands/.claude-plugin/plugin.json hybrid-hands/plugins/hybrid-hands/CHANGELOG.md docs/work-in-progress/gpt-nguon/decision.md docs/work-in-progress/gpt-nguon/docs-report.md`: exit 0.

Không chạy suite/build/install/live; không đọc metadata/rollout/transcript thật. Runtime token/quota: ?. Cần Sol đối chiếu contract với kết quả implementation/tests thực tế; báo cáo này không xác nhận runtime hay statusline release. Không tạo .done/handoff, không commit/push.

Sau review Sol: làm rõ ở AGENTS/README/changelog/decision rằng account sample có duration tường minh phân loại 5h=300, weekly primary=10080 không đổi nhãn; account rollout legacy thiếu duration giữ primary=5h/secondary=tuần. Chỉ phép đo GPT phần riêng mới bắt buộc duration tuần explicit 10080. Scoped git diff --check chạy lại đạt; không chạy thêm tests/log/source.
