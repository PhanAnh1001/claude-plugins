"""Tests for scripts/od_auth.py (device code flow, refresh rotation, file token store)."""
from __future__ import annotations

import io
import json
import shlex
import subprocess
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from urllib.parse import parse_qs

import _support  # noqa: F401
from od_auth import SECURITY_INTERACTIVE_LINE_LIMIT, FileTokenStore, KeychainTokenStore, Session, device_code_login
from od_http import HttpResponse

ACCESS, REFRESH, ROTATED = "fake-access-AAA", "fake-refresh-BBB", "fake-refresh-CCC"


def reply(status: int, payload: dict) -> HttpResponse:
    return HttpResponse(status, {}, json.dumps(payload).encode())


class ScriptedTransport:
    def __init__(self, replies: list[HttpResponse]) -> None:
        self.replies, self.calls = list(replies), []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, parse_qs((body or b"").decode())))
        return self.replies.pop(0)


class FakeSecurity:
    """In-memory Keychain parsing `security` argv and `-i` stdin lines."""

    def __init__(self) -> None:
        self.items: dict[str, str] = {}
        self.lines: list[str] = []
        self.argv: list[list[str]] = []

    def __call__(self, args, stdin=None):
        self.argv.append(args)
        if args == ["-i"]:
            self.lines += stdin.splitlines(keepends=True)
            for line in stdin.splitlines():
                self._apply(shlex.split(line))
            return subprocess.CompletedProcess(args, 0, "", "")
        return self._apply(args)

    def _apply(self, args):
        rest = [a for a in args[1:] if a not in ("-U", "-w")] if args[0] == "find-generic-password" else [a for a in args[1:] if a != "-U"]
        opts = dict(zip(rest[::2], rest[1::2]))
        account, found = opts.get("-a"), opts.get("-a") in self.items
        if args[0] == "add-generic-password":
            self.items[account] = opts["-w"]
        elif args[0] == "find-generic-password":
            return subprocess.CompletedProcess(args, 0 if found else 44, self.items.get(account, ""), "")
        elif args[0] == "delete-generic-password":
            self.items.pop(account, None)
        return subprocess.CompletedProcess(args, 0 if found or args[0] == "add-generic-password" else 44, "", "")


class AuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = FileTokenStore(Path(self.tmp.name) / "dw", "organizations", "app-id")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_device_code_polls_pending_then_slow_down_and_saves_token_privately(self) -> None:
        transport = ScriptedTransport([
            reply(200, {"device_code": "dc", "message": "Go to https://microsoft.com/devicelogin code XYZ",
                        "interval": 5, "expires_in": 900}),
            reply(400, {"error": "authorization_pending"}),
            reply(400, {"error": "slow_down"}),
            reply(200, {"access_token": ACCESS, "refresh_token": REFRESH}),
        ])
        sleeps: list[float] = []
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            result = device_code_login(transport, "organizations", "app-id", out=err, sleep=sleeps.append)
            Session(transport, "organizations", "app-id", self.store).adopt(result)
        self.assertEqual(sleeps, [5, 5, 10])
        self.assertIn("XYZ", err.getvalue())
        for secret in (ACCESS, REFRESH):
            self.assertNotIn(secret, out.getvalue() + err.getvalue())
        self.assertEqual(self.store.load(), REFRESH)
        self.assertEqual(stat.S_IMODE(self.store.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.store.directory.stat().st_mode), 0o700)

    def test_refresh_rotates_stored_token(self) -> None:
        self.store.save(REFRESH)
        transport = ScriptedTransport([reply(200, {"access_token": ACCESS, "refresh_token": ROTATED})])
        session = Session(transport, "organizations", "app-id", self.store)
        self.assertEqual(session.access_token(), ACCESS)
        self.assertEqual(transport.calls[0][2]["refresh_token"], [REFRESH])
        self.assertEqual(self.store.load(), ROTATED)

    def test_keychain_chunks_long_token_and_prunes_old_chunks(self) -> None:
        fake, long_token = FakeSecurity(), "fake-" + "z" * 10_000
        store = KeychainTokenStore("organizations", "app-id", runner=fake)
        store.save(long_token)
        self.assertEqual(store.load(), long_token)
        store.save(REFRESH)
        self.assertEqual(store.load(), REFRESH)
        self.assertEqual(sorted(fake.items), [store.account, store.account + "#0"])
        self.assertTrue(all(len(line.encode()) < SECURITY_INTERACTIVE_LINE_LIMIT for line in fake.lines))
        self.assertFalse(any(long_token in " ".join(argv) for argv in fake.argv))
        self.assertTrue(store.delete())
        self.assertEqual(fake.items, {})


if __name__ == "__main__":
    unittest.main()
