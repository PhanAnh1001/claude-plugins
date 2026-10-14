"""In kết quả ra stdout — dùng chung giữa ``cli`` và các module lệnh tách riêng (``worklog``).

Tách khỏi ``cli`` để module lệnh dùng được mà không import vòng ``cli`` ↔ module lệnh.
"""

from __future__ import annotations

import json
from typing import Any

from jira_tools.errors import EXIT_OK


def print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def dry_run(method: str, url: str, payload: Any | None) -> int:
    """``--dry-run``: in method + URL (+ body) rồi trả mã 0 — không gọi mạng, không cần PAT."""
    print(f"{method} {url}")
    if payload is not None:
        print_json(payload)
    return EXIT_OK
