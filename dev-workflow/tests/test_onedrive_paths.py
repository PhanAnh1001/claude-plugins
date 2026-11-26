"""Tests for scripts/od_paths.py (remote path parsing, validation, encoding)."""
from __future__ import annotations

import base64
import unittest

import _support  # noqa: F401  (puts scripts/ on sys.path)
from od_paths import PathError, encode_path, parse_remote, share_id

FOLDERS = {"luxian": "https://contoso.sharepoint.com/:f:/s/team/EAbc"}


class RemotePathTest(unittest.TestCase):
    def test_rejects_unknown_alias_dotdot_and_forbidden_chars(self) -> None:
        for spec in ("other:a", "luxian:a/../b", "luxian:a?b", "luxian:/abs", "luxian:dot.", "nocolon"):
            with self.subTest(spec=spec), self.assertRaises(PathError):
                parse_remote(spec, FOLDERS)

    def test_keeps_vietnamese_names_and_encodes_segments(self) -> None:
        decomposed = "Ke\u0302\u0301 hoa\u0323ch/a b.html"  # NFD input normalises to NFC
        path = parse_remote(f"luxian:{decomposed}/", FOLDERS)
        self.assertEqual(path.parts, ("Kế hoạch", "a b.html"))
        self.assertTrue(path.trailing_slash)
        self.assertEqual(encode_path(path.parts), "K%E1%BA%BF%20ho%E1%BA%A1ch/a%20b.html")

    def test_share_id_is_unpadded_base64url(self) -> None:
        url = "https://contoso.sharepoint.com/:f:/s/team/EAbc?e=x~y>"
        value = share_id(url)
        self.assertTrue(value.startswith("u!"))
        self.assertFalse(set(value[2:]) & set("=+/"))
        body = value[2:]
        self.assertEqual(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode(), url)


if __name__ == "__main__":
    unittest.main()
