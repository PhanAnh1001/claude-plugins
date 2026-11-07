"""Luật ngữ cảnh brain (xoay phiên, không tự tra cứu, không hỏi trạng thái) có mặt ở cả hai hook policy."""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

HYBRID_HANDS = Path(__file__).resolve().parents[1]
PLUGIN = HYBRID_HANDS / "plugins" / "hybrid-hands"
SESSION_START = PLUGIN / "scripts" / "session-start-policy.sh"
INJECT = PLUGIN / "scripts" / "inject-policy.sh"
REPORT = HYBRID_HANDS / "docs" / "2026-11-06-brain-token-cost.md"


class BrainContextPolicyTest(unittest.TestCase):
    def _session_start_context(self) -> str:
        out = subprocess.run(
            ["bash", str(SESSION_START)],
            env={"CLAUDE_PLUGIN_ROOT": str(PLUGIN), "PATH": "/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin"},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return json.loads(out)["hookSpecificOutput"]["additionalContext"]

    def test_session_start_has_brain_context_rules(self) -> None:
        text = self._session_start_context()
        self.assertIn("LUẬT NGỮ CẢNH BRAIN", text)
        # A: xoay phiên brain sau mỗi đợt hoặc khi nghỉ quá 1 giờ
        self.assertIn("phiên brain mới", text)
        self.assertIn("quá 1 giờ", text)
        # B: brain không tự tra cứu, review bằng diff --stat rồi đoạn cần thiết
        self.assertIn("không tự tra cứu", text)
        self.assertIn("git diff --stat", text)
        # D: không hỏi trạng thái trong lúc chờ
        self.assertIn("không hỏi trạng thái", text)
        self.assertIn("docs/2026-11-06-brain-token-cost.md", text)
        # luật test tối thiểu: mặc định tối thiểu, mức kỹ chỉ gồm 2 nhóm
        self.assertIn("LUẬT TEST TỐI THIỂU", text)
        self.assertIn("tạo hứng thú", text)
        self.assertIn("bảo mật", text)
        preamble = (PLUGIN / "templates" / "ext-hand-preamble.md").read_text(encoding="utf-8")
        self.assertIn("## Test tối thiểu", preamble)
        self.assertIn("Ngân sách test", preamble)
        self.assertIn("tạo hứng thú", preamble)

    def test_inject_policy_has_short_form_and_stays_short(self) -> None:
        text = subprocess.run(["bash", str(INJECT)], capture_output=True, text=True, check=True).stdout
        for marker in ("phiên brain mới", "tự tra cứu", "không hỏi trạng thái",
                       "Test tối thiểu", "tạo hứng thú", "bảo mật"):
            self.assertIn(marker, text)
        # bắn mỗi prompt nên phải ngắn
        self.assertLess(len(text), 1800)

    def test_report_exists_and_is_anonymous(self) -> None:
        text = REPORT.read_text(encoding="utf-8")
        self.assertTrue(text.lstrip("-\n").count("## Tóm tắt") or "## Tóm tắt" in text)
        for banned in ("live-tiktok", "luxian", "tiktok", "TikTok", "/Users/"):
            self.assertNotIn(banned, text, banned)


if __name__ == "__main__":
    unittest.main()
