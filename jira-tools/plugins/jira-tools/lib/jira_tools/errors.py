"""Lỗi người dùng xử lý được của CLI Jira, kèm mã thoát tương ứng.

Tách riêng để ``payloads`` (hàm thuần) và ``client`` (mạng) dùng chung mà không import vòng.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

EXIT_OK: Final = 0
EXIT_API_ERROR: Final = 1
#: Thiếu cấu hình bắt buộc (token, tham số sai dạng).
EXIT_CONFIG_ERROR: Final = 2
#: Tên transition truyền vào không khớp transition nào đang mở cho issue.
EXIT_NO_MATCH: Final = 3


class JiraCliError(Exception):
    """Lỗi đã biết: ``main`` in thông báo ra stderr và trả ``exit_code``."""

    exit_code: int = EXIT_API_ERROR


class ConfigError(JiraCliError):
    """Thiếu token hoặc tham số sai dạng — không phải lỗi từ phía Jira."""

    exit_code = EXIT_CONFIG_ERROR


class TransitionNotFound(JiraCliError):
    """Tên transition không khớp; thông báo kèm danh sách hợp lệ để gõ lại ngay."""

    exit_code = EXIT_NO_MATCH

    def __init__(self, target_name: str, available: Sequence[str]) -> None:
        listing = "\n".join(f"  - {name}" for name in available) or "  (không có transition nào)"
        super().__init__(f"Không có transition nào tên {target_name!r}. Đang mở:\n{listing}")
        self.target_name = target_name
        self.available = list(available)


class CommentNotStored(JiraCliError):
    """Jira nhận lời gọi nhưng đọc lại không thấy comment — không được báo thành công giả."""

    def __init__(self, key: str, detail: str) -> None:
        super().__init__(
            f"{key}: trạng thái đã chuyển nhưng comment KHÔNG được lưu ({detail}). "
            f"Đăng lại bằng lệnh: comment {key} --body '...'"
        )
        self.key = key


class WorklogNotVerified(JiraCliError):
    """Jira nhận worklog nhưng đọc lại không thấy đúng kết quả — không được báo thành công giả."""

    def __init__(self, key: str, detail: str) -> None:
        super().__init__(
            f"{key}: worklog chưa được xác nhận ({detail}). "
            f"Kiểm lại bằng lệnh: get {key} --json (khối fields.timetracking)"
        )
        self.key = key
