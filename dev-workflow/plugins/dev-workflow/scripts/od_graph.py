"""Microsoft Graph operations for `dw onedrive`: resolve folders, list, mkdir -p, upload, download.

Each configured folder is a sharing or web URL resolved through `/shares/{id}/driveItem`; children
are addressed as `/drives/{driveId}/items/{itemId}:/{path}:`.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Callable
from urllib.parse import quote

from od_http import HttpResponse, Transport, json_body, send
from od_paths import RemotePath, encode_path, share_id

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
CONFLICT_PARAM = "@microsoft.graph.conflictBehavior"
CONFLICT_FAIL = "fail"
CONFLICT_REPLACE = "replace"
DOWNLOAD_URL_KEY = "@microsoft.graph.downloadUrl"
NEXT_LINK_KEY = "@odata.nextLink"
SIMPLE_UPLOAD_MAX_BYTES = 4 * 1024 * 1024  # Graph: PUT /content supports files up to 4 MiB
UPLOAD_CHUNK_UNIT = 320 * 1024  # upload session chunks must be multiples of 320 KiB
UPLOAD_CHUNK_BYTES = 10 * UPLOAD_CHUNK_UNIT
STATUS_NOT_FOUND = 404
STATUS_CONFLICT = 409
OCTET_STREAM = "application/octet-stream"


class GraphError(Exception):
    """Graph answered with an error status, or the remote state conflicts with the request."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"{status} {code}: {message}")
        self.status, self.code, self.message = status, code, message


def graph_error(response: HttpResponse) -> GraphError:
    error = response.json().get("error") or {}
    message = str(error.get("message") or "").splitlines()
    return GraphError(response.status, str(error.get("code") or "error"), message[0] if message else "")


@dataclass(frozen=True)
class FolderRoot:
    drive_id: str
    item_id: str
    name: str
    web_url: str


@dataclass(frozen=True)
class UploadPlan:
    local: Path
    size: int
    target: RemotePath
    overwrite: bool


def is_folder(item: dict[str, Any]) -> bool:
    return "folder" in item or "folder" in (item.get("remoteItem") or {})


class GraphClient:
    def __init__(self, transport: Transport, token: Callable[[], str], folders: dict[str, str],
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._transport, self._token, self._folders, self._sleep = transport, token, folders, sleep
        self._roots: dict[str, FolderRoot] = {}

    # --- low level -------------------------------------------------------------------------
    def _call(self, method: str, url: str, payload: Any = None, *, body: bytes | None = None,
              headers: dict[str, str] | None = None) -> HttpResponse:
        request_headers = {"Authorization": f"Bearer {self._token()}", **(headers or {})}
        if payload is not None:
            extra, body = json_body(payload)
            request_headers.update(extra)
        url = url if url.startswith("https://") else GRAPH_BASE + url
        return send(self._transport, method, url, request_headers, body, self._sleep)

    def _json(self, method: str, url: str, payload: Any = None) -> dict[str, Any]:
        response = self._call(method, url, payload)
        if not response.ok:
            raise graph_error(response)
        return response.json()

    def root(self, alias: str) -> FolderRoot:
        if alias not in self._roots:
            item = self._json("GET", f"/shares/{share_id(self._folders[alias])}/driveItem")
            source = item.get("remoteItem") or item
            drive_id = (source.get("parentReference") or {}).get("driveId")
            if not drive_id:
                raise GraphError(0, "noDrive", f"could not find the drive of alias '{alias}'")
            self._roots[alias] = FolderRoot(drive_id, source["id"], item.get("name", ""), item.get("webUrl", ""))
        return self._roots[alias]

    def item_url(self, path: RemotePath) -> str:
        root = self.root(path.alias)
        base = f"/drives/{root.drive_id}/items/{root.item_id}"
        return f"{base}:/{encode_path(path.parts)}:" if path.parts else base

    def get_item(self, path: RemotePath) -> dict[str, Any] | None:
        response = self._call("GET", self.item_url(path))
        if response.status == STATUS_NOT_FOUND:
            return None
        if not response.ok:
            raise graph_error(response)
        return response.json()

    # --- commands --------------------------------------------------------------------------
    def list_children(self, path: RemotePath) -> list[dict[str, Any]]:
        url: str | None = f"{self.item_url(path)}/children"
        items: list[dict[str, Any]] = []
        while url:
            page = self._json("GET", url)
            items.extend(page.get("value") or [])
            url = page.get(NEXT_LINK_KEY)
        return items

    def mkdir(self, path: RemotePath) -> dict[str, Any]:
        """Create every missing folder of `path` (like mkdir -p); return the last folder item."""
        root = self.root(path.alias)
        current: dict[str, Any] = {"id": root.item_id, "webUrl": root.web_url, "folder": {}}
        walked = RemotePath(path.alias, ())
        for name in path.parts:
            walked = walked.child(name)
            existing = self.get_item(walked)
            if existing is None:
                existing = self._create_folder(root.drive_id, current["id"], name, walked)
            if not is_folder(existing):
                raise GraphError(STATUS_CONFLICT, "nameAlreadyExists", f"{walked.display()} is a file, not a folder")
            current = existing
        return current

    def _create_folder(self, drive_id: str, parent_id: str, name: str, walked: RemotePath) -> dict[str, Any]:
        payload = {"name": name, "folder": {}, CONFLICT_PARAM: CONFLICT_FAIL}
        response = self._call("POST", f"/drives/{drive_id}/items/{parent_id}/children", payload)
        if response.status == STATUS_CONFLICT:  # created concurrently: use the existing one
            existing = self.get_item(walked)
            if existing is not None:
                return existing
        if not response.ok:
            raise graph_error(response)
        return response.json()

    def resolve_upload_target(self, local: Path, target: RemotePath) -> RemotePath:
        if target.trailing_slash or not target.parts:
            return target.child(local.name)
        existing = self.get_item(target)
        if existing is not None and is_folder(existing):
            return target.child(local.name)
        return target

    def upload(self, plan: UploadPlan) -> dict[str, Any]:
        behavior = CONFLICT_REPLACE if plan.overwrite else CONFLICT_FAIL
        with plan.local.open("rb") as handle:
            if plan.size <= SIMPLE_UPLOAD_MAX_BYTES:
                return self._simple_upload(plan, behavior, handle.read())
            return self._session_upload(plan, behavior, handle)

    def _simple_upload(self, plan: UploadPlan, behavior: str, data: bytes) -> dict[str, Any]:
        url = f"{self.item_url(plan.target)}/content?{quote(CONFLICT_PARAM)}={behavior}"
        response = self._call("PUT", url, body=data, headers={"Content-Type": OCTET_STREAM})
        if not response.ok:
            raise graph_error(response)
        return response.json()

    def _session_upload(self, plan: UploadPlan, behavior: str, handle: BinaryIO) -> dict[str, Any]:
        session = self._json("POST", f"{self.item_url(plan.target)}/createUploadSession",
                             {"item": {CONFLICT_PARAM: behavior}})
        upload_url = session["uploadUrl"]
        offset, response = 0, HttpResponse(0)
        while offset < plan.size:
            chunk = handle.read(UPLOAD_CHUNK_BYTES)
            if not chunk:
                raise GraphError(0, "shortRead", f"{plan.local} changed size during upload")
            end = offset + len(chunk) - 1
            headers = {"Content-Length": str(len(chunk)), "Content-Range": f"bytes {offset}-{end}/{plan.size}"}
            # The upload URL is pre-authenticated: sending Authorization to it is an error.
            response = send(self._transport, "PUT", upload_url, headers, chunk, self._sleep)
            if not response.ok:
                raise graph_error(response)
            offset = end + 1
        return response.json()

    def download(self, path: RemotePath, sink: BinaryIO) -> int:
        item = self.get_item(path)
        if item is None:
            raise GraphError(STATUS_NOT_FOUND, "itemNotFound", f"{path.display()} does not exist")
        if is_folder(item) or DOWNLOAD_URL_KEY not in item:
            raise GraphError(0, "notAFile", f"{path.display()} is a folder; use ls")
        # The download URL is pre-authenticated: no Authorization header.
        response = send(self._transport, "GET", item[DOWNLOAD_URL_KEY], {}, None, self._sleep)
        if not response.ok:
            raise graph_error(response)
        sink.write(response.body)
        return len(response.body)

    def me(self) -> dict[str, Any]:
        return self._json("GET", "/me")


def file_size(local: Path) -> int:
    return os.stat(local).st_size
