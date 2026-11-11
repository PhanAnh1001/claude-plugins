"""Render hook policy from one stable body and a repository-scoped mode.

This changes instructions only; it does not admit agents or modify configuration.
The shell retains jq's SessionStart envelope for byte compatibility.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from shared_config import GlobalConfigError, load_config
from hand_ext.config import load_config as load_ext_config

MODE_KEY = "parallel_subagents.enabled"
NORMAL_PROMPT = "POLICY: xem SessionStart và AGENTS.md. Hand theo ext_hand.order (pick trước native); brain không tự tra cứu; cấm hiện .env/token/credential."
AGENTS_REFERENCE = "Xem AGENTS.md mục Phạm vi và vai trò / Luật dữ liệu chung."


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


def mode_config(cwd: Path) -> tuple[str, int, str, dict, str]:
    """Return the enabling repository path and actual cap, or normal policy.

    The shared loader enforces the boolean and source boundary for all consumers.
    Hook failure is deliberately softer than CLI failure, with no raw exception
    text (which could echo a supplied configuration value) in stderr.
    """
    try:
        result = load_config(cwd)
        if (result.effective["parallel_subagents"]["enabled"] is True
                and result.sources.get(MODE_KEY) == "repo"):
            backend = result.effective["parallel_subagents"]["backend"]
            options = load_ext_config(known_root=result.root, config_file=Path(result.paths["repo"]["path"])).options(backend)
            account = result.effective["parallel_subagents"].get(
                "account", backend[len(CLAUDE_PREFIX):] if backend.startswith(CLAUDE_PREFIX) else "")
            return result.paths["repo"]["path"], result.effective["ext_hand"]["max_parallel"], backend, options, account
    except (GlobalConfigError, OSError, ValueError, TypeError, KeyError):
        print("warning: hybrid-hands: không đọc được cấu hình policy; dùng policy thường", file=sys.stderr)
    return "", 0, "", {}, ""


CLAUDE_PREFIX = "claude-"


def account_rule(account: str, backend: str) -> str:
    """Native Agent needs brain and hand on the same Claude account."""
    if not backend.startswith(CLAUDE_PREFIX):
        return f"Tài khoản brain `{account}`."
    if backend != CLAUDE_PREFIX + account:
        return (f"Tài khoản brain `{account}` khác backend subagent `{backend}`: subagent native không chạy; "
                f"dùng `hand-ext run --backend {backend}`; đề nghị người dùng chốt "
                f"`hand-ext parallel-subagents --account {account}|{backend[len(CLAUDE_PREFIX):]}`.")
    return (f"Tài khoản brain `{account}`: nếu phiên brain hiện tại không chạy trên `{account}` (pick trả native false do khác account) "
            f"thì dùng `hand-ext run --backend claude-{account}` và đề nghị người dùng mở phiên brain mới bằng "
            f"`side-session start --main --provider claude --account {account}`.")


def parallel_rules(rules: str, limit: int, backend: str, options: dict, account: str) -> str:
    """Replace only delegation/review sections; retain shared laws verbatim."""
    data_rules = rules.split("   LUẬT DỮ LIỆU:", 1)[1].split("## Chọn hand theo tài khoản", 1)[0]
    continuation = rules.split("LUẬT TIẾP VIỆC", 1)[1].split("LUẬT REVIEW:", 1)[0]
    brain_context = rules.split("LUẬT NGỮ CẢNH BRAIN", 1)[1]
    delegation = f"""Thiếu PHẠM VI GHI thì hand coi là CHỈ ĐỌC (fail-closed).

Brain chia brief thành các gói độc lập khác file và giao subagent theo backend `{backend}` (model `{options.get("model", "")}`, effort `{options.get("effort", options.get("variant", ""))}`) song song tối đa {limit} (ext_hand.max_parallel thực = {limit}, giới hạn 1..4). Tổng native + hand-ext không vượt giới hạn này; cùng file hoặc phụ thuộc phải tuần tự. Đây là luật điều phối; admission thực nằm ngoài mode này. Brain viết tiêu chí trước khi giao và review code hand mình giao; không giao hand review hand khác. Hand executor làm trực tiếp, không hand-ext/side-session/subagent/recursion/giao tiếp phiên khác. L2/L3 vẫn cần người dùng duyệt.

Luôn chạy `hand-ext pick --json --backend {backend}` trước mỗi lượt giao để biết backend/model/effort/account, native/native_reason và giữ guard v1 ≥8%/ngày (thiếu nguồn cũng chặn). Nếu pick trả `native: true`, backend claude-vN dùng native Agent `hybrid-hands:hand`; backend codex dùng native Codex theo luật ngoại lệ A (fork_turns=none, brief tự chứa, luật dữ liệu nguyên văn). Chỉ native khi đúng account và đủ capability; không tự áp native cho account khác. Nếu native false hoặc thiếu capability thì dùng `hand-ext run --backend {backend}` để wrapper enforce guard và thực thi gói việc đó. Guard chặn hoặc exit 7 thì không spawn, ghi yêu cầu để brain quyết; không tự đổi backend/config/order. Không dùng run như preflight giả rồi spawn writer trùng. Unknown sau spawn phải reconcile/wait, không tạo duplicate writer. Exit 8 chờ slot; không tự đổi slots/config. Completed giữ tab/history, không archive parent. Native không tạo run/meta/report/token ledger hand-ext; thiếu token/USD~/quota ghi `?`, không suy quota. {account_rule(account, backend)}

"""
    review = "LUẬT REVIEW: Brain review code hand mình giao, đọc git diff --stat trước rồi hunk quyết định đúng sai; không giao hand review hand khác. Phát hiện lỗi thì giao lại hand mình đã giao rồi review lại.\n\n"
    return (delegation + "   LUẬT DỮ LIỆU:" + data_rules
            + "LUẬT TIẾP VIỆC" + continuation + review + "LUẬT NGỮ CẢNH BRAIN" + brain_context)


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
    source, limit, backend, options, account = mode_config(cwd)
    mode_line = f"chế độ parallel_subagents bật bởi {source}\n" if source else ""
    if hook == "prompt":
        if not source:
            return NORMAL_PROMPT
        return mode_line + (f"POLICY: xem SessionStart. Brain giao subagent backend {backend} khác file song song ≤ {limit}, "
                            "cùng file/phụ thuộc tuần tự; brain review code hand mình giao. "
                            f"hand-ext pick --json --backend {backend} trước mỗi lượt giao; guard v1 thiếu nguồn/chặn thì không spawn. "
                            + account_rule(account, backend) + " Brain không tự tra cứu; cấm hiện .env/token/credential.")
    rules = (root / "lib/policy_rules.txt").read_text(encoding="utf-8").rstrip("\n")
    if source:
        rules = parallel_rules(rules, limit, backend, options, account)
    rules = shorten_rules(rules, cwd)
    brief = (root / "templates/hand-brief.md").read_text(encoding="utf-8").rstrip("\n")
    return (mode_line + "POLICY hybrid-hands - KHUÔN BRIEF (bắt buộc khi gọi Agent với hybrid-hands:hand và khi viết brief cho hand-ext; điền đủ các mục, ngắn gọn):\n"
            + brief + "\n" + rules + "\n"
            + f"Lệnh của plugin (nếu không có trong PATH thì gọi bằng đường dẫn tuyệt đối): {root}/bin/hand-ext, {root}/bin/side-session, {root}/bin/hh-ps, {root}/bin/cc-switch")


if __name__ == "__main__":
    print(render(sys.argv[1], Path(sys.argv[2]), sys.stdin.read()))
