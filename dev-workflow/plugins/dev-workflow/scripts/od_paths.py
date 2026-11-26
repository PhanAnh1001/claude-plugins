"""Pure helpers for `dw onedrive` remote paths: parse `<alias>:<sub/path>`, validate, encode.

Only aliases configured in `[onedrive].folders` are accepted, so every operation stays inside
the folders the project declared.
"""
from __future__ import annotations

import base64
import unicodedata
from dataclasses import dataclass
from urllib.parse import quote

ALIAS_SEPARATOR = ":"
PATH_SEPARATOR = "/"
# Characters OneDrive / SharePoint reject in file and folder names.
FORBIDDEN_NAME_CHARS = frozenset('"*:<>?\\|')
RESERVED_SEGMENTS = frozenset({".", ".."})
FORBIDDEN_NAME_ENDINGS = (".", " ")
SHARE_ID_PREFIX = "u!"  # Graph shares API: "u!" + unpadded base64url of the sharing URL
BASE64_PADDING = "="
UNICODE_FORM = "NFC"


class PathError(ValueError):
    """A remote path is malformed or uses an alias that is not configured."""


@dataclass(frozen=True)
class RemotePath:
    alias: str
    parts: tuple[str, ...]
    trailing_slash: bool = False

    @property
    def subpath(self) -> str:
        return PATH_SEPARATOR.join(self.parts)

    def display(self) -> str:
        return f"{self.alias}{ALIAS_SEPARATOR}{self.subpath}"

    def child(self, name: str) -> "RemotePath":
        return RemotePath(self.alias, (*self.parts, validate_name(name)))

    def parent(self) -> "RemotePath":
        return RemotePath(self.alias, self.parts[:-1])


def validate_name(name: str) -> str:
    """Return the NFC form of one path segment or raise PathError."""
    normalized = unicodedata.normalize(UNICODE_FORM, name)
    if normalized in RESERVED_SEGMENTS:
        raise PathError(f"'{normalized}' segments are not allowed")
    bad = sorted(set(normalized) & FORBIDDEN_NAME_CHARS)
    if bad:
        raise PathError(f"name '{normalized}' contains forbidden characters: {' '.join(bad)}")
    if normalized.endswith(FORBIDDEN_NAME_ENDINGS):
        raise PathError(f"name '{normalized}' must not end with a dot or a space")
    return normalized


def parse_remote(spec: str, folders: dict[str, str]) -> RemotePath:
    """Parse `<alias>:<path>`; the alias must be a key of `folders`."""
    alias, separator, raw_path = spec.partition(ALIAS_SEPARATOR)
    if not separator:
        raise PathError(f"remote path '{spec}' must look like <alias>:<path>")
    if alias not in folders:
        known = ", ".join(sorted(folders)) or "none configured"
        raise PathError(f"unknown alias '{alias}' (configured: {known})")
    if raw_path.startswith(PATH_SEPARATOR):
        raise PathError("absolute paths are not allowed; the path is relative to the alias folder")
    parts = tuple(validate_name(part) for part in raw_path.split(PATH_SEPARATOR) if part)
    return RemotePath(alias, parts, trailing_slash=raw_path.endswith(PATH_SEPARATOR))


def encode_path(parts: tuple[str, ...]) -> str:
    """URL-encode every segment and join with '/' for Graph path addressing."""
    return PATH_SEPARATOR.join(quote(part, safe="") for part in parts)


def share_id(sharing_url: str) -> str:
    """Encode a sharing or web URL as a Graph share id (`u!` + unpadded base64url)."""
    encoded = base64.urlsafe_b64encode(sharing_url.encode("utf-8")).decode("ascii")
    return SHARE_ID_PREFIX + encoded.rstrip(BASE64_PADDING)
