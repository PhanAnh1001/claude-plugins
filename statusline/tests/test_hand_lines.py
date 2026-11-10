"""hand_lines subagent cap; fake snapshot only."""
import sys
import unittest
from _support import SCRIPTS_DIR
sys.path.insert(0, str(SCRIPTS_DIR))
import hand_lines


def snapshot(agents):
    return {"sessions": [{"session_id": "main", "subagents": agents}]}


class SubagentCapTests(unittest.TestCase):
    def test_five_agents_show_running_then_newest_plus_summary(self):
        agents = [{"agent_id": f"a{i}", "started_at": i, "status": "running" if i in (1, 2) else "done"}
                  for i in range(1, 6)]
        lines = hand_lines.render(snapshot(agents), "main")[1:]
        self.assertEqual([l.split(" | ")[0].split()[-1] for l in lines[:3]], ["a2", "a1", "a5"])
        self.assertEqual(lines[3], "· ↳ +2 subagent")

    def test_three_agents_no_summary(self):
        agents = [{"agent_id": f"a{i}", "started_at": i} for i in range(3)]
        lines = hand_lines.render(snapshot(agents), "main")
        self.assertEqual(len(lines), 4)
        self.assertNotIn("+", lines[-1].split(" | ")[0])


if __name__ == "__main__":
    unittest.main()
