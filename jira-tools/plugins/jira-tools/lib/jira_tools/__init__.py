"""CLI Jira Server (REST v2, PAT Bearer) dùng chung cho nhiều dự án.

Chia theo trách nhiệm: ``errors`` (lỗi + mã thoát), ``config`` (host / dự án từ
``config/jira.json``), ``payloads`` (hàm thuần dựng body), ``createmeta`` (createmeta Jira 9),
``client`` (token, SSL, HTTP), ``cli`` (subcommand + hiển thị). Điểm vào là ``bin/jira-cli``.
"""

from __future__ import annotations
