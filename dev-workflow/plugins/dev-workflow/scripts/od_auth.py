"""Microsoft identity platform sign-in for `dw onedrive`: device code flow, refresh, token store.

Only the refresh token is persisted (Keychain on macOS, else a 0600 JSON file); the access
token stays in memory. No token value is ever printed, logged or put in an exception message.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol, TextIO

from od_http import Transport, form_body, send

LOGIN_BASE = "https://login.microsoftonline.com"
DEVICE_CODE_PATH = "oauth2/v2.0/devicecode"
TOKEN_PATH = "oauth2/v2.0/token"
SCOPES = "offline_access Files.ReadWrite.All User.Read"
DEVICE_CODE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"
REFRESH_GRANT = "refresh_token"
SLOW_DOWN_EXTRA_SECONDS = 5  # RFC 8628 section 3.5: add 5 s to the interval on slow_down
DEFAULT_POLL_INTERVAL_SECONDS = 5
DEFAULT_DEVICE_CODE_LIFETIME_SECONDS = 900

ERROR_PENDING = "authorization_pending"
ERROR_SLOW_DOWN = "slow_down"
ERROR_EXPIRED = "expired_token"
ERROR_DECLINED = "authorization_declined"

KEYCHAIN_SERVICE = "dev-workflow-onedrive"
SECURITY_BIN = "security"
STORE_ENV = "DW_ONEDRIVE_TOKEN_STORE"
STORE_DIR_ENV = "DW_ONEDRIVE_TOKEN_DIR"
STORE_FILE = "file"
CONFIG_DIR_NAME = "dev-workflow"
TOKEN_FILE_PREFIX = "onedrive-token-"
TOKEN_FILE_HASH_CHARS = 16
FILE_MODE = 0o600
DIR_MODE = 0o700
SECURITY_TIMEOUT_SECONDS = 15
SECURITY_INTERACTIVE_LINE_LIMIT = 4096  # `security -i` truncates longer input lines (measured)
KEYCHAIN_CHUNK_CHARS = 3000  # well under the line limit once the command text is added
KEYCHAIN_CHUNK_SEPARATOR = "#"
KEYCHAIN_CHUNKS_KEY = "chunks"


class AuthError(Exception):
    """Sign-in failed, was declined or expired, or no stored sign-in exists."""


class TokenStore(Protocol):
    def load(self) -> str | None: ...
    def save(self, refresh_token: str) -> None: ...
    def delete(self) -> bool: ...


def account_key(tenant: str, client_id: str) -> str:
    return f"{tenant}:{client_id}"


class FileTokenStore:
    def __init__(self, directory: Path, tenant: str, client_id: str) -> None:
        digest = hashlib.sha256(account_key(tenant, client_id).encode("utf-8")).hexdigest()
        self.directory = directory
        self.path = directory / f"{TOKEN_FILE_PREFIX}{digest[:TOKEN_FILE_HASH_CHARS]}.json"

    def load(self) -> str | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        token = data.get("refresh_token") if isinstance(data, dict) else None
        return token if isinstance(token, str) and token else None

    def save(self, refresh_token: str) -> None:
        self.directory.mkdir(mode=DIR_MODE, parents=True, exist_ok=True)
        os.chmod(self.directory, DIR_MODE)
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, FILE_MODE)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"refresh_token": refresh_token}, handle)
        os.chmod(self.path, FILE_MODE)

    def delete(self) -> bool:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return False
        return True


Runner = Callable[[list[str], "str | None"], "subprocess.CompletedProcess[str]"]


def _security_runner(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([SECURITY_BIN, *args], input=stdin, capture_output=True, text=True,
                          timeout=SECURITY_TIMEOUT_SECONDS, check=False)


class KeychainTokenStore:
    """macOS Keychain via `security`; the secret goes through stdin (`security -i`), not argv.

    `security -i` truncates input lines at ~4096 bytes, so the base64 secret is split into chunk
    items `<account>#<i>`; the item `<account>` holds `{"chunks": n}`.
    """

    def __init__(self, tenant: str, client_id: str, runner: Runner | None = None) -> None:
        self.account = account_key(tenant, client_id)
        self._runner = runner or _security_runner

    def _run(self, args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return self._runner(args, stdin)

    def _chunk_account(self, index: int) -> str:
        return f"{self.account}{KEYCHAIN_CHUNK_SEPARATOR}{index}"

    def _find(self, account: str) -> str | None:
        result = self._run(["find-generic-password", "-a", account, "-s", KEYCHAIN_SERVICE, "-w"])
        return result.stdout.strip() if result.returncode == 0 else None

    def _remove(self, account: str) -> bool:
        return self._run(["delete-generic-password", "-a", account, "-s", KEYCHAIN_SERVICE]).returncode == 0

    def _chunk_count(self) -> int:
        raw = self._find(self.account)
        try:
            count = json.loads(raw).get(KEYCHAIN_CHUNKS_KEY) if raw else None
        except (ValueError, AttributeError):
            return 0
        return count if isinstance(count, int) and count > 0 else 0

    def load(self) -> str | None:
        count = self._chunk_count()
        if not count:
            return None
        parts = [self._find(self._chunk_account(i)) for i in range(count)]
        if any(part is None for part in parts):
            return None
        try:
            data = json.loads(base64.b64decode("".join(parts)).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        token = data.get("refresh_token") if isinstance(data, dict) else None
        return token if isinstance(token, str) and token else None

    def _add_line(self, account: str, value: str) -> str:
        line = f"add-generic-password -U -a '{account}' -s '{KEYCHAIN_SERVICE}' -w '{value}'\n"
        if len(line.encode("utf-8")) >= SECURITY_INTERACTIVE_LINE_LIMIT:
            raise AuthError("Keychain command line too long")
        return line

    def save(self, refresh_token: str) -> None:
        secret = base64.b64encode(json.dumps({"refresh_token": refresh_token}).encode("utf-8")).decode("ascii")
        chunks = [secret[i:i + KEYCHAIN_CHUNK_CHARS] for i in range(0, len(secret), KEYCHAIN_CHUNK_CHARS)]
        old_count = self._chunk_count()
        lines = [self._add_line(self._chunk_account(i), chunk) for i, chunk in enumerate(chunks)]
        lines.append(self._add_line(self.account, json.dumps({KEYCHAIN_CHUNKS_KEY: len(chunks)})))
        result = self._run(["-i"], stdin="".join(lines))
        if result.returncode != 0:
            raise AuthError("could not save the sign-in to the macOS Keychain")
        for index in range(len(chunks), old_count):
            self._remove(self._chunk_account(index))

    def delete(self) -> bool:
        for index in range(self._chunk_count()):
            self._remove(self._chunk_account(index))
        return self._remove(self.account)


def default_token_dir() -> Path:
    explicit = os.environ.get(STORE_DIR_ENV)
    if explicit:
        return Path(explicit)
    base = os.environ.get("XDG_CONFIG_HOME")
    return (Path(base) if base else Path.home() / ".config") / CONFIG_DIR_NAME


def open_token_store(tenant: str, client_id: str) -> TokenStore:
    use_file = os.environ.get(STORE_ENV) == STORE_FILE or shutil.which(SECURITY_BIN) is None
    if use_file or sys.platform != "darwin":
        return FileTokenStore(default_token_dir(), tenant, client_id)
    return KeychainTokenStore(tenant, client_id)


@dataclass
class TokenResult:
    access_token: str
    refresh_token: str | None


def _endpoint(tenant: str, path: str) -> str:
    return f"{LOGIN_BASE}/{tenant}/{path}"


def _token_result(payload: dict) -> TokenResult:
    access = payload.get("access_token")
    if not isinstance(access, str) or not access:
        raise AuthError("token response has no access token")
    refresh = payload.get("refresh_token")
    return TokenResult(access, refresh if isinstance(refresh, str) and refresh else None)


def _error_text(payload: dict, fallback: str) -> str:
    code = payload.get("error") or fallback
    description = str(payload.get("error_description") or "").splitlines()
    return f"{code}: {description[0]}" if description else str(code)


def device_code_login(transport: Transport, tenant: str, client_id: str, *, out: TextIO = sys.stderr,
                      sleep: Callable[[float], None] = time.sleep,
                      clock: Callable[[], float] = time.monotonic) -> TokenResult:
    """Run the OAuth 2.0 device code flow; print the user instructions to `out`."""
    headers, body = form_body({"client_id": client_id, "scope": SCOPES})
    response = send(transport, "POST", _endpoint(tenant, DEVICE_CODE_PATH), headers, body, sleep)
    payload = response.json()
    if not response.ok or "device_code" not in payload:
        raise AuthError(f"device code request failed: {_error_text(payload, str(response.status))}")
    print(payload.get("message") or f"Open {payload.get('verification_uri')} and enter {payload.get('user_code')}",
          file=out, flush=True)
    interval = float(payload.get("interval") or DEFAULT_POLL_INTERVAL_SECONDS)
    deadline = clock() + float(payload.get("expires_in") or DEFAULT_DEVICE_CODE_LIFETIME_SECONDS)
    fields = {"grant_type": DEVICE_CODE_GRANT, "client_id": client_id, "device_code": payload["device_code"]}
    while True:
        sleep(interval)
        token_headers, token_body = form_body(fields)
        reply = send(transport, "POST", _endpoint(tenant, TOKEN_PATH), token_headers, token_body, sleep)
        data = reply.json()
        if reply.ok:
            return _token_result(data)
        error = data.get("error")
        if error == ERROR_PENDING and clock() < deadline:
            continue
        if error == ERROR_SLOW_DOWN and clock() < deadline:
            interval += SLOW_DOWN_EXTRA_SECONDS
            continue
        if error in (ERROR_PENDING, ERROR_SLOW_DOWN, ERROR_EXPIRED):
            raise AuthError("the sign-in code expired; run login again")
        if error == ERROR_DECLINED:
            raise AuthError("sign-in was declined")
        raise AuthError(f"sign-in failed: {_error_text(data, str(reply.status))}")


def refresh_access_token(transport: Transport, tenant: str, client_id: str, refresh_token: str,
                         sleep: Callable[[float], None] = time.sleep) -> TokenResult:
    headers, body = form_body({"grant_type": REFRESH_GRANT, "client_id": client_id,
                               "refresh_token": refresh_token, "scope": SCOPES})
    response = send(transport, "POST", _endpoint(tenant, TOKEN_PATH), headers, body, sleep)
    payload = response.json()
    if not response.ok:
        raise AuthError(f"stored sign-in no longer works ({_error_text(payload, str(response.status))}); "
                        "run `dw onedrive login`")
    return _token_result(payload)


class Session:
    """Lazily turns the stored refresh token into an in-memory access token; saves rotated tokens."""

    def __init__(self, transport: Transport, tenant: str, client_id: str, store: TokenStore,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self._transport, self._tenant, self._client_id = transport, tenant, client_id
        self._store, self._sleep = store, sleep
        self._access: str | None = None

    @property
    def store(self) -> TokenStore:
        return self._store

    def adopt(self, result: TokenResult) -> None:
        self._access = result.access_token
        if result.refresh_token:
            self._store.save(result.refresh_token)

    def access_token(self) -> str:
        if self._access:
            return self._access
        refresh = self._store.load()
        if not refresh:
            raise AuthError("not signed in; run `dw onedrive login`")
        self.adopt(refresh_access_token(self._transport, self._tenant, self._client_id, refresh, self._sleep))
        return self._access  # type: ignore[return-value]
