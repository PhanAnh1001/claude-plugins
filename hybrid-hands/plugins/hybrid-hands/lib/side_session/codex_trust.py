"""Ghi mục trust cho workdir vào `<codex_home>/config.toml` trước khi mở phiên Codex.

Codex TUI hỏi "Trust this folder?" với thư mục chưa được tin; phiên chạy không người trực
sẽ kẹt ở câu hỏi đó. Chỉ nối thêm bảng `[projects."<workdir>"]` khi config chưa có bảng
ấy, không định dạng lại phần còn lại của file.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10 trở xuống không có tomllib
    tomllib = None

CONFIG_FILE = "config.toml"
PROJECTS_KEY = "projects"
TRUST_KEY = "trust_level"
TRUST_LEVEL = "trusted"
# Prelude chạy trong screen ngay trước `exec codex`, nên chỉ ghi khi thật sự mở phiên.
PRELUDE_CODE = (
    "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); "
    "from side_session.codex_trust import ensure_codex_trust; "
    "ensure_codex_trust(Path(sys.argv[2]), sys.argv[3])"
)


def _table_header(workdir: str) -> str:
    return f"[{PROJECTS_KEY}.{json.dumps(workdir)}]"


def _matches_header(line: str, header: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith(header):
        return False
    rest = stripped[len(header):].strip()
    return not rest or rest.startswith("#")


def _has_project_table(text: str, workdir: str) -> bool:
    if tomllib is not None:
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError:
            pass  # config hỏng: vẫn dò header bằng chuỗi để không thêm trùng
        else:
            projects = data.get(PROJECTS_KEY)
            return isinstance(projects, dict) and workdir in projects
    header = _table_header(workdir)
    return any(_matches_header(line, header) for line in text.splitlines())


def ensure_codex_trust(codex_home: Path, workdir: str) -> bool:
    """Thêm trust cho `workdir` nếu chưa có; trả về True khi config.toml vừa được ghi."""
    path = codex_home / CONFIG_FILE
    old = path.read_text(encoding="utf-8") if path.is_file() else ""
    if _has_project_table(old, workdir):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        if old and not old.endswith("\n"):
            fh.write("\n")
        fh.write(f'{_table_header(workdir)}\n{TRUST_KEY} = "{TRUST_LEVEL}"\n')
    return True


def prelude_argv(codex_home: Path, workdir: str) -> list[str]:
    """argv của prelude: nạp module này từ lib của plugin rồi ghi trust."""
    lib = Path(__file__).resolve().parents[1]
    return [sys.executable, "-c", PRELUDE_CODE, str(lib), str(codex_home), workdir]
