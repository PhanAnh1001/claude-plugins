"""Tests for `side-session attach` with fake screen ids/exec (never runs screen)."""
from __future__ import annotations

import io
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PL = ROOT / "plugins" / "hybrid-hands"
sys.path.insert(0, str(PL / "lib"))

from side_session import attach, cli  # noqa: E402

SCREEN_BIN = "/usr/bin/screen"


class FakeInput:
    """Feeds scripted answers; running out behaves like stdin EOF."""

    def __init__(self, *answers: str) -> None:
        self.answers = iter(answers)
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        try:
            return next(self.answers)
        except StopIteration:
            raise EOFError from None


class AttachPureTest(unittest.TestCase):
    def test_session_targets_filters_watch_and_foreign_screens(self) -> None:
        ids = {
            "side-b": "222.side-b",
            "side-a-watch": "333.side-a-watch",
            "side-a": "111.side-a",
            "main": "444.main",
            "other-side": "555.other-side",
        }
        self.assertEqual(attach.session_targets(ids),
                         [("a", "111.side-a"), ("b", "222.side-b")])

    def test_attach_argv_uses_shared_x_mode(self) -> None:
        self.assertEqual(attach.attach_argv(SCREEN_BIN, "111.side-a"),
                         [SCREEN_BIN, "-x", "111.side-a"])


class RunAttachTest(unittest.TestCase):
    def setUp(self) -> None:
        self.out = io.StringIO()

    def run_attach(self, name, ids, answers=(), code=0):
        exec_fn = mock.Mock(return_value=code)
        input_fn = FakeInput(*answers)
        result = attach.run_attach(
            name,
            ids_fn=mock.Mock(return_value=ids),
            exec_fn=exec_fn,
            input_fn=input_fn,
            print_fn=lambda text="": self.out.write(f"{text}\n"),
            screen_bin=SCREEN_BIN,
        )
        return result, exec_fn, input_fn

    def test_named_session_attaches_exact_pid_name(self) -> None:
        code, exec_fn, _ = self.run_attach(
            "a", {"side-a": "111.side-a", "side-a-watch": "222.side-a-watch"},
            code=7)
        self.assertEqual(code, 7)
        exec_fn.assert_called_once_with([SCREEN_BIN, "-x", "111.side-a"])

    def test_named_session_accepts_prefixed_name(self) -> None:
        code, exec_fn, _ = self.run_attach("side-a", {"side-a": "111.side-a"})
        self.assertEqual(code, 0)
        exec_fn.assert_called_once_with([SCREEN_BIN, "-x", "111.side-a"])

    def test_unknown_name_exits_1_and_lists_running(self) -> None:
        code, exec_fn, _ = self.run_attach("zz", {"side-a": "111.side-a"})
        self.assertEqual(code, 1)
        exec_fn.assert_not_called()
        self.assertIn("không có phiên phụ đang chạy tên zz", self.out.getvalue())
        self.assertIn("Đang chạy: a", self.out.getvalue())

    def test_menu_selects_second_session_then_quits(self) -> None:
        ids = {"side-b": "222.side-b", "side-a": "111.side-a",
               "side-a-watch": "333.side-a-watch"}
        code, exec_fn, input_fn = self.run_attach(None, ids, answers=("2", "q"))
        self.assertEqual(code, 0)
        exec_fn.assert_called_once_with([SCREEN_BIN, "-x", "222.side-b"])
        self.assertIn("1) a", self.out.getvalue())
        self.assertIn("2) b", self.out.getvalue())
        self.assertEqual(input_fn.prompts[0],
                         attach.MENU_PROMPT)

    def test_single_session_still_waits_for_a_choice(self) -> None:
        code, exec_fn, _ = self.run_attach(None, {"side-a": "111.side-a"},
                                           answers=("q",))
        self.assertEqual(code, 0)
        exec_fn.assert_not_called()

    def test_empty_list_refreshes_on_enter_and_sees_new_session(self) -> None:
        exec_fn = mock.Mock(return_value=0)
        input_fn = FakeInput("", "1", "q")
        ids_fn = mock.Mock(side_effect=[{}, {"side-new": "777.side-new"},
                                        {"side-new": "777.side-new"}])
        code = attach.run_attach(None, ids_fn=ids_fn, exec_fn=exec_fn, input_fn=input_fn,
                                 print_fn=lambda text="": self.out.write(f"{text}\n"),
                                 screen_bin=SCREEN_BIN)
        self.assertEqual(code, 0)
        self.assertEqual(ids_fn.call_count, 3)
        exec_fn.assert_called_once_with([SCREEN_BIN, "-x", "777.side-new"])
        self.assertIn("Không có phiên phụ nào đang chạy.", self.out.getvalue())
        self.assertEqual(input_fn.prompts[0], attach.REFRESH_PROMPT)

    def test_invalid_choice_reports_and_asks_again(self) -> None:
        code, exec_fn, _ = self.run_attach(
            None, {"side-a": "111.side-a"}, answers=("abc", "1", "q"))
        self.assertEqual(code, 0)
        exec_fn.assert_called_once_with([SCREEN_BIN, "-x", "111.side-a"])
        self.assertIn("không hợp lệ", self.out.getvalue())

    def test_eof_exits_zero(self) -> None:
        code, exec_fn, _ = self.run_attach(None, {}, answers=())
        self.assertEqual(code, 0)
        exec_fn.assert_not_called()


class AttachCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="side-session-attach-"))
        self._cwd = os.getcwd()
        os.chdir(self.tmp)

    def tearDown(self) -> None:
        os.chdir(self._cwd)
        shutil.rmtree(self.tmp)  # only our own mkdtemp dir

    def run_cli(self, *argv: str) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(list(argv))
        return code, buf.getvalue()

    def test_attach_works_without_config_outside_a_git_repo(self) -> None:
        with mock.patch.dict(os.environ), \
                mock.patch.object(attach, "find_screen", return_value=SCREEN_BIN), \
                mock.patch.object(attach.screen, "screen_ids",
                                  return_value={"side-x": "123.side-x"}), \
                mock.patch.object(attach.subprocess, "call", return_value=0) as call:
            code, _ = self.run_cli("attach", "x")
        self.assertEqual(code, 0)
        call.assert_called_once_with([SCREEN_BIN, "-x", "123.side-x"])
        self.assertFalse((self.tmp / ".claude").exists())

    def test_missing_screen_exits_2(self) -> None:
        with mock.patch.object(attach, "find_screen", return_value=None), \
                mock.patch.object(attach.screen, "screen_ids") as ids:
            code, out = self.run_cli("attach", "x")
        self.assertEqual(code, 2)
        self.assertIn("không tìm thấy", out)
        ids.assert_not_called()


if __name__ == "__main__":
    unittest.main()
