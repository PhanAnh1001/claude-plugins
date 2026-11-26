"""Tests for scripts/od_graph.py and the onedrive.py CLI (fake transport, no network)."""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import _support
import onedrive
from dw_config import load_config
from od_graph import SIMPLE_UPLOAD_MAX_BYTES, UPLOAD_CHUNK_BYTES, GraphClient, UploadPlan
from od_http import HttpResponse
from od_paths import parse_remote, share_id

URL = "https://contoso.sharepoint.com/:f:/s/team/EAbc"
FOLDERS = {"luxian": URL}
BASE = "https://graph.microsoft.com/v1.0/drives/D/items/ROOT"
UPLOAD_URL = "https://upload.example/session"
DOWNLOAD_URL = "https://download.example/file"


def ok(payload: dict, status: int = 200) -> HttpResponse:
    return HttpResponse(status, {}, json.dumps(payload).encode())


class FakeGraph:
    """Answers share resolution, a fixed set of existing paths, folder creation, uploads, downloads."""

    def __init__(self, existing: dict[str, dict] | None = None) -> None:
        self.existing = existing or {}
        self.calls: list[tuple[str, str, dict, bytes | None]] = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, headers, body))
        if "/shares/" in url:
            return ok({"id": "ROOT", "name": "Team", "webUrl": "https://w/team", "parentReference": {"driveId": "D"}})
        if url == UPLOAD_URL:
            return ok({"name": "big.bin", "size": 1}, 202)
        if url == DOWNLOAD_URL:
            return HttpResponse(200, {}, b"\x00raw bytes")
        if url.endswith("/createUploadSession"):
            return ok({"uploadUrl": UPLOAD_URL})
        if "/content?" in url:
            return ok({"name": "a.txt", "size": len(body or b""), "webUrl": "https://w/a.txt"}, 201)
        if method == "POST" and url.endswith("/children"):
            name = json.loads(body)["name"]
            return ok({"id": f"id-{name}", "name": name, "folder": {}, "webUrl": f"https://w/{name}"}, 201)
        if method == "GET":
            key = url.removeprefix(BASE).strip(":/")
            return ok(self.existing[key]) if key in self.existing else ok({"error": {"code": "itemNotFound"}}, 404)
        raise AssertionError(f"unexpected {method} {url}")


def client(fake: FakeGraph) -> GraphClient:
    return GraphClient(fake, lambda: "tok", FOLDERS, sleep=lambda _: None)


class GraphTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _file(self, size: int) -> Path:
        path = self.dir / "a.txt"
        path.write_bytes(b"x" * size)
        return path

    def test_small_put_uses_content_with_conflict_behavior(self) -> None:
        for overwrite, behavior in ((False, "fail"), (True, "replace")):
            fake = FakeGraph()
            local = self._file(10)
            client(fake).upload(UploadPlan(local, 10, parse_remote("luxian:Kế hoạch/a.txt", FOLDERS), overwrite))
            method, url, headers, _ = fake.calls[-1]
            self.assertEqual(method, "PUT")
            self.assertTrue(url.startswith(f"{BASE}:/K%E1%BA%BF%20ho%E1%BA%A1ch/a.txt:/content?"))
            self.assertTrue(url.endswith(f"conflictBehavior={behavior}"))
            self.assertIn(f"/shares/{share_id(URL)}/driveItem", fake.calls[0][1])

    def test_large_put_uses_upload_session_without_authorization(self) -> None:
        size = SIMPLE_UPLOAD_MAX_BYTES + 1
        fake = FakeGraph()
        client(fake).upload(UploadPlan(self._file(size), size, parse_remote("luxian:big.bin", FOLDERS), False))
        session_call = next(c for c in fake.calls if c[1].endswith("/createUploadSession"))
        self.assertEqual(json.loads(session_call[3]), {"item": {"@microsoft.graph.conflictBehavior": "fail"}})
        chunks = [c for c in fake.calls if c[1] == UPLOAD_URL]
        ranges, start = [], 0
        while start < size:
            end = min(start + UPLOAD_CHUNK_BYTES, size) - 1
            ranges.append(f"bytes {start}-{end}/{size}")
            start = end + 1
        self.assertEqual([c[2]["Content-Range"] for c in chunks], ranges)
        self.assertTrue(all("Authorization" not in c[2] for c in chunks))

    def test_mkdir_creates_only_missing_segments(self) -> None:
        fake = FakeGraph({"a": {"id": "id-a", "name": "a", "folder": {}}})
        last = client(fake).mkdir(parse_remote("luxian:a/b/c", FOLDERS))
        created = [json.loads(c[3])["name"] for c in fake.calls if c[0] == "POST"]
        self.assertEqual(created, ["b", "c"])
        self.assertTrue(any(c[1] == f"https://graph.microsoft.com/v1.0/drives/D/items/id-b/children"
                            for c in fake.calls if c[0] == "POST"))
        self.assertEqual(last["id"], "id-c")

    def test_get_downloads_without_authorization(self) -> None:
        fake = FakeGraph({"r.pdf": {"id": "f", "name": "r.pdf", "@microsoft.graph.downloadUrl": DOWNLOAD_URL}})
        sink = io.BytesIO()
        client(fake).download(parse_remote("luxian:r.pdf", FOLDERS), sink)
        self.assertEqual(sink.getvalue(), b"\x00raw bytes")
        download = next(c for c in fake.calls if c[1] == DOWNLOAD_URL)
        self.assertNotIn("Authorization", download[2])


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = _support.write_config(self.root, f'[onedrive]\nclient_id = "app"\nfolders = {{ luxian = "{URL}" }}\n')

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_config_section_is_accepted_without_warnings(self) -> None:
        loaded = load_config(self.config)
        self.assertEqual(loaded.warnings, [])
        self.assertEqual(loaded.get("onedrive.folders"), {"luxian": URL})

    def test_put_dry_run_needs_no_token_or_network(self) -> None:
        local = _support.write_file(self.root, "x.html", "<p>hi</p>")
        transport = mock.Mock(side_effect=AssertionError("network used"))
        out = io.StringIO()
        env = {"DW_ONEDRIVE_TOKEN_STORE": "file", "DW_ONEDRIVE_TOKEN_DIR": str(self.root / "tokens")}
        with mock.patch.dict(os.environ, env), redirect_stdout(out):
            code = onedrive.main(["--config", str(self.config), "put", str(local), "luxian:Kế hoạch/", "--dry-run"],
                                 transport=transport)
        self.assertEqual(code, 0)
        self.assertIn("luxian:Kế hoạch/x.html", out.getvalue())
        transport.assert_not_called()
        self.assertFalse((self.root / "tokens").exists())


if __name__ == "__main__":
    unittest.main()
