"""Thin HTTP transport for `dw onedrive` on urllib, injectable for tests.

A transport is any callable `(method, url, headers, body) -> HttpResponse`; HTTP error
statuses come back as responses, never as exceptions.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol
from urllib.parse import urlencode

REQUEST_TIMEOUT_SECONDS = 60
RETRY_STATUSES = frozenset({429, 503})  # throttled / unavailable: Graph asks to retry later
MAX_RETRY_AFTER_SECONDS = 30
DEFAULT_RETRY_AFTER_SECONDS = 1
HTTP_ERROR_MIN = 400
JSON_CONTENT_TYPE = "application/json"
FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


class NetworkError(Exception):
    """The request did not get an HTTP response (DNS, TLS, timeout, refused)."""


@dataclass
class HttpResponse:
    status: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    @property
    def ok(self) -> bool:
        return self.status < HTTP_ERROR_MIN

    def json(self) -> Any:
        if not self.body:
            return {}
        try:
            return json.loads(self.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}

    def header(self, name: str) -> str | None:
        lowered = name.lower()
        for key, value in self.headers.items():
            if key.lower() == lowered:
                return value
        return None


class Transport(Protocol):
    def __call__(self, method: str, url: str, headers: dict[str, str], body: bytes | None) -> HttpResponse: ...


def urllib_transport(method: str, url: str, headers: dict[str, str], body: bytes | None) -> HttpResponse:
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return HttpResponse(response.status, dict(response.headers.items()), response.read())
    except urllib.error.HTTPError as exc:
        return HttpResponse(exc.code, dict(exc.headers.items()) if exc.headers else {}, exc.read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NetworkError(f"{method} {url.split('?')[0]} failed: {exc}") from exc


def retry_after_seconds(response: HttpResponse) -> float:
    raw = response.header("Retry-After")
    try:
        value = float(raw) if raw is not None else DEFAULT_RETRY_AFTER_SECONDS
    except ValueError:
        value = DEFAULT_RETRY_AFTER_SECONDS
    return max(0.0, min(value, MAX_RETRY_AFTER_SECONDS))


def send(transport: Transport, method: str, url: str, headers: dict[str, str] | None = None,
         body: bytes | None = None, sleep: Callable[[float], None] = time.sleep) -> HttpResponse:
    """Send once; retry one time on 429/503 after Retry-After (capped)."""
    request_headers = dict(headers or {})
    response = transport(method, url, request_headers, body)
    if response.status in RETRY_STATUSES:
        sleep(retry_after_seconds(response))
        response = transport(method, url, request_headers, body)
    return response


def json_body(payload: Any) -> tuple[dict[str, str], bytes]:
    return {"Content-Type": JSON_CONTENT_TYPE}, json.dumps(payload).encode("utf-8")


def form_body(fields: dict[str, str]) -> tuple[dict[str, str], bytes]:
    return {"Content-Type": FORM_CONTENT_TYPE}, urlencode(fields).encode("ascii")
