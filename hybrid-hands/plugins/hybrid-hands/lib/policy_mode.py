"""Render hook policy from one stable body and the repository profile role table.

This changes instructions only; it does not admit agents or modify configuration.
The shell retains jq's SessionStart envelope for byte compatibility.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from shared_config import GlobalConfigError, load_config
from hand_ext.profiles import ProfileError, profile_table
from disk_reminder import disk_reminder

AGENTS_REFERENCE = "Xem AGENTS.md mục Phạm vi và vai trò / Luật dữ liệu chung."
PROFILES_HELP = ("Ba profile: claude-mono (mọi vai Claude), gpt-mono (mọi vai GPT/Codex, chrome Claude), "
                 "hybrid (gpt-mono + super brain Claude v2 mở brain Sol bằng side-session).")
HYBRID = "hybrid"
ROLE_ENV = "HYBRID_HANDS_ROLE"  # do `side-session start` đặt cho phiên nó mở
ROLE_SUPER, ROLE_BRAIN = "super", "brain"
ROLE_NAMES = {ROLE_SUPER: "super brain", ROLE_BRAIN: "brain"}
MAX_PARALLEL = 4  # pool chung native + hand-ext, giới hạn cứng của plugin
FAIL_EXITS = "1/4/6"  # hand-ext run thoát mã này = hỏng, được nâng bậc
NO_ESCALATE_EXITS = "7/8/9"  # hạ tầng/slot/an toàn: không nâng bậc
DATA_MARK, ACCOUNT_MARK = "   LUẬT DỮ LIỆU:", "## Chọn hand theo tài khoản"
CONT_MARK, REVIEW_MARK, CONTEXT_MARK = "LUẬT TIẾP VIỆC", "LUẬT REVIEW:", "LUẬT NGỮ CẢNH BRAIN"
REVIEW_RULE = ("LUẬT REVIEW: Brain review code hand mình giao, đọc git diff --stat trước rồi hunk quyết định đúng sai; "
               "không giao hand review hand khác. Phát hiện lỗi thì giao lại hand mình đã giao rồi review lại.\n\n")


def payload_cwd(payload: str) -> Path:
    """Use only a nonempty string cwd; malformed payloads use environment fallback."""
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        data = None
    cwd = data.get("cwd") if isinstance(data, dict) else None
    if not isinstance(cwd, str) or not cwd.strip() or "\x00" in cwd:
        cwd = os.environ.get("CLAUDE_PROJECT_DIR") or os.environ.get("PWD") or os.getcwd()
    return Path(cwd)


def profile_state(cwd: Path) -> tuple[str, dict, str]:
    """Return (profile, role table, error); error is a ProfileError message or a config warning."""
    try:
        cfg = load_config(cwd).effective
        return cfg.get("profile", ""), profile_table(cfg), ""
    except ProfileError as exc:
        return "", {}, str(exc)
    except (GlobalConfigError, OSError, ValueError, TypeError, KeyError):
        print("warning: hybrid-hands: không đọc được cấu hình policy", file=sys.stderr)
        return "", {}, "Không đọc được cấu hình hybrid-hands; kiểm bằng `hand-ext config --json` rồi `hand-ext profile set <tên>`."


def session_role(profile: str, table: dict) -> str:
    """HYBRID_HANDS_ROLE when valid for this profile; else hybrid → super (user-opened), mono → brain."""
    marker = os.environ.get(ROLE_ENV, "")
    if marker in ROLE_NAMES and marker in table:
        return marker
    return ROLE_SUPER if profile == HYBRID else ROLE_BRAIN


def _cell(spec: dict) -> str:
    owner = "GPT" if spec["provider"] == "codex" else "Claude"
    return f"{owner} {spec['account']} {spec['model']} {spec['effort']}"


def role_table_lines(table: dict) -> list[str]:
    lines = [f"{role}: {_cell(table[role])}" for role in ("super", "brain", "code") if role in table]
    for role in ("collect", "chrome"):
        lines.append(f"{role} B1/B2: {_cell(table[role + '.1'])} / {_cell(table[role + '.2'])}")
    return lines


BRAIN_RULES = ("Giao việc (brain): trước mỗi lượt chạy `hand-ext pick --role code|collect|chrome [--tier 1|2] --json`; "
               "`native` true → subagent native đúng model/effort pick trả (Claude: tool Agent `hybrid-hands:hand` với "
               "`model` = `agent_model` và `effort`); `native` false → `hand-ext run --role … --tier …`. "
               f"Song song ≤ {MAX_PARALLEL} khác file; cùng file/phụ thuộc tuần tự. Brain review việc mình giao.\n"
               "Thang thu thập: gói ít code bắt đầu B1, gói cần viết script bắt đầu B2; B1 hỏng → chạy lại đúng một lần ở B2 "
               "bằng subagent mới, brief chép phần đã đạt và chỉ giao phần thiếu; B2 hỏng → dừng báo. Hỏng = subagent báo "
               f"chưa xong, `hand-ext run` thoát {FAIL_EXITS}, hoặc brain kiểm mẫu không đạt. Không nâng khi thoát "
               f"{NO_ESCALATE_EXITS} hay vi phạm an toàn. Sau mỗi lượt native collect/chrome ghi "
               "`hand-ext ladder log --role … --tier … --result ok|fail`.\n")
SUPER_RULE = ("Vai super brain: viết/duyệt spec và plan, mở phiên brain bằng `side-session start`, "
              "review bàn giao `.done`; không code, không giao subagent code.\n"
              "Việc code và thu thập dữ liệu giao cho phiên brain; super brain không gọi `hand-ext pick/run`.\n")
QUOTA_RULE = ("Hết quota: không đổi tài khoản; phiên trong Paseo có limit-watch thì đăng ký checkpoint để chạy tiếp khi "
              "quota về, không thì ghi checkpoint và dừng báo người dùng.\n")


def profile_delegation(profile: str, table: dict) -> str:
    """Delegation block for exactly one role, generated from the profile's role table."""
    role = session_role(profile, table)
    work = SUPER_RULE if role == ROLE_SUPER else BRAIN_RULES
    return (f"PROFILE {profile} — vai phiên này: {ROLE_NAMES[role]}.\n"
            + "\n".join(role_table_lines(table)) + "\n"
            "Thiếu PHẠM VI GHI thì hand coi là CHỈ ĐỌC (fail-closed).\n" + work + QUOTA_RULE + "\n")


def profile_rules(rules: str, delegation: str) -> str:
    """Replace delegation/account/review sections; retain shared laws verbatim."""
    data_rules = rules.split(DATA_MARK, 1)[1].split(ACCOUNT_MARK, 1)[0]
    continuation = rules.split(CONT_MARK, 1)[1].split(REVIEW_MARK, 1)[0]
    brain_context = rules.split(CONTEXT_MARK, 1)[1]
    return (delegation + DATA_MARK + data_rules + CONT_MARK + continuation
            + REVIEW_RULE + CONTEXT_MARK + brain_context)


def prompt_line(profile: str, error: str, table: dict | None = None) -> str:
    if error:
        return f"{error} {PROFILES_HELP} Cấm hiện .env/token/credential."
    role = ROLE_NAMES[session_role(profile, table or {})]
    work = ("mở brain bằng `side-session start`, không code, không pick/run"
            if role == ROLE_NAMES[ROLE_SUPER] else
            f"pick --role trước mỗi lượt giao; song song ≤ {MAX_PARALLEL} khác file; B1 hỏng → B2 một lần")
    return (f"PROFILE {profile}, vai {role}. POLICY: xem SessionStart. {work}; "
            "cấm hiện .env/token/credential.")


def shorten_rules(rules: str, cwd: Path) -> str:
    """Mirror the original shell's exact-paragraph AGENTS reduction."""
    agents_path = cwd / "AGENTS.md"
    if not agents_path.is_file():
        return rules
    try:
        agents = agents_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        agents = ""
    return "".join((AGENTS_REFERENCE if part.strip() and part.strip() in agents else part)
                   + "\n\n" for part in rules.split("\n\n")).rstrip("\n")


def render(hook: str, root: Path, payload: str) -> str:
    cwd = payload_cwd(payload)
    profile, table, error = profile_state(cwd)
    if hook == "prompt":
        return prompt_line(profile, error, table)
    delegation = f"{error}\n{PROFILES_HELP}\n\n" if error else profile_delegation(profile, table)
    rules = (root / "lib/policy_rules.txt").read_text(encoding="utf-8").rstrip("\n")
    rules = shorten_rules(profile_rules(rules, delegation), cwd)
    brief = (root / "templates/hand-brief.md").read_text(encoding="utf-8").rstrip("\n")
    return ("POLICY hybrid-hands - KHUÔN BRIEF (bắt buộc khi gọi Agent với hybrid-hands:hand và khi viết brief cho hand-ext; điền đủ các mục, ngắn gọn):\n"
            + brief + "\n" + rules + "\n"
            + f"Lệnh của plugin (nếu không có trong PATH thì gọi bằng đường dẫn tuyệt đối): {root}/bin/hand-ext, {root}/bin/side-session, {root}/bin/hh-ps, {root}/bin/cc-switch"
            + (f"\n{reminder}" if (reminder := disk_reminder(cwd)) else ""))


if __name__ == "__main__":
    print(render(sys.argv[1], Path(sys.argv[2]), sys.stdin.read()))
