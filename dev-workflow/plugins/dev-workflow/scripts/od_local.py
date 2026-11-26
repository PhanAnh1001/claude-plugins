"""Local backend for `dw onedrive`: folders synced to this machine by the OneDrive sync client.

An alias whose value starts with `~` or `/` names a synced folder (on macOS usually
`~/Library/CloudStorage/OneDrive-<Org>/...`). Operations are plain file operations; the sync
client uploads the result. Items are returned in the same dict shape as Graph driveItems.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO

from od_graph import STATUS_CONFLICT, STATUS_NOT_FOUND, FolderRoot, GraphError, UploadPlan
from od_paths import RemotePath

GRAPH_PREFIX = "https://"
LOCAL_PREFIXES = ("~", "/")
CLOUDSTORAGE_ENV = "DW_ONEDRIVE_CLOUDSTORAGE_DIR"
DEFAULT_CLOUDSTORAGE_DIR = "~/Library/CloudStorage"
ONEDRIVE_ROOT_GLOB = "OneDrive*"
TEMP_SUFFIX = ".dw-upload"
COPY_CHUNK_BYTES = 1024 * 1024
STATUS_LOCAL_ERROR = 0  # not an HTTP status: local file-system problem
MISSING_ROOT_HINT = ("check that the OneDrive app is signed in and has synced it; for a folder shared with you, "
                     "open its link on the web and choose 'Add shortcut to My files'")


class BackendKind:
    GRAPH = "graph"
    LOCAL = "local"


def backend_kind(value: str) -> str | None:
    """Return the backend for a `[onedrive].folders` value, or None if the value is not usable."""
    if value.startswith(GRAPH_PREFIX):
        return BackendKind.GRAPH
    if value.startswith(LOCAL_PREFIXES):
        return BackendKind.LOCAL
    return None


def local_root(value: str) -> Path:
    return Path(value).expanduser()


def _iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def item_dict(path: Path) -> dict[str, Any]:
    stat = path.stat()
    item: dict[str, Any] = {"name": path.name, "size": stat.st_size,
                            "lastModifiedDateTime": _iso_utc(stat.st_mtime), "webUrl": path.resolve().as_uri()}
    if path.is_dir():
        item["folder"] = {}
    return item


class LocalClient:
    def __init__(self, folders: dict[str, str]) -> None:
        self._roots = {alias: local_root(value) for alias, value in folders.items()}

    def root_dir(self, alias: str) -> Path:
        root = self._roots[alias]
        if not root.is_dir():
            raise GraphError(STATUS_NOT_FOUND, "rootNotFound", f"alias '{alias}' folder {root} does not exist; "
                             f"{MISSING_ROOT_HINT}")
        return root

    def root(self, alias: str) -> FolderRoot:
        root = self.root_dir(alias)
        return FolderRoot("", "", root.name, root.resolve().as_uri())

    def local_path(self, path: RemotePath) -> Path:
        """Join the remote path onto its alias root; reject anything that resolves outside it."""
        root = self.root_dir(path.alias).resolve()
        joined = root.joinpath(*path.parts)
        resolved = joined.resolve()
        if resolved != root and root not in resolved.parents:
            raise GraphError(STATUS_LOCAL_ERROR, "outsideRoot", f"{path.display()} leads outside the alias folder")
        return joined

    def list_children(self, path: RemotePath) -> list[dict[str, Any]]:
        folder = self.local_path(path)
        if not folder.is_dir():
            raise GraphError(STATUS_NOT_FOUND, "itemNotFound", f"{path.display()} is not an existing folder")
        return [item_dict(child) for child in sorted(folder.iterdir()) if not child.name.startswith(".")]

    def mkdir(self, path: RemotePath) -> dict[str, Any]:
        walked = RemotePath(path.alias, ())
        for part in path.parts:
            walked = walked.child(part)
            current = self.local_path(walked)
            if current.exists() and not current.is_dir():
                raise GraphError(STATUS_CONFLICT, "notAFolder", f"{walked.display()} is a file")
            current.mkdir(exist_ok=True)
        return item_dict(self.local_path(path))

    def resolve_upload_target(self, local: Path, target: RemotePath) -> RemotePath:
        if target.trailing_slash or not target.parts or self.local_path(target).is_dir():
            return target.child(local.name)
        return target

    def upload(self, plan: UploadPlan) -> dict[str, Any]:
        dest = self.local_path(plan.target)
        if not dest.parent.is_dir():
            raise GraphError(STATUS_NOT_FOUND, "itemNotFound", f"{plan.target.parent().display()} does not exist; "
                             "pass --mkdir")
        if dest.exists() and not plan.overwrite:
            raise GraphError(STATUS_CONFLICT, "nameAlreadyExists", f"{plan.target.display()} already exists")
        fd, temp = tempfile.mkstemp(prefix=f".{dest.name}.", suffix=TEMP_SUFFIX, dir=dest.parent)
        os.close(fd)
        try:
            shutil.copyfile(plan.local, temp)
            os.replace(temp, dest)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return item_dict(dest)

    def download(self, path: RemotePath, sink: BinaryIO) -> int:
        source = self.local_path(path)
        if not source.exists():
            raise GraphError(STATUS_NOT_FOUND, "itemNotFound", f"{path.display()} does not exist")
        if source.is_dir():
            raise GraphError(STATUS_LOCAL_ERROR, "notAFile", f"{path.display()} is a folder; use ls")
        written = 0
        with source.open("rb") as handle:
            while chunk := handle.read(COPY_CHUNK_BYTES):
                sink.write(chunk)
                written += len(chunk)
        return written


def cloudstorage_dir() -> Path:
    return Path(os.environ.get(CLOUDSTORAGE_ENV) or DEFAULT_CLOUDSTORAGE_DIR).expanduser()


def discover_roots() -> list[tuple[Path, list[Path]]]:
    """OneDrive sync roots under the CloudStorage folder, each with its first-level subfolders."""
    base = cloudstorage_dir()
    if not base.is_dir():
        return []
    found = []
    for root in sorted(base.glob(ONEDRIVE_ROOT_GLOB)):
        if root.is_dir():
            children = [c for c in sorted(root.iterdir()) if c.is_dir() and not c.name.startswith(".")]
            found.append((root, children))
    return found
