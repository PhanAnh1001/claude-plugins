"""Cấu hình, xác thực và tầng HTTP tới Jira Server REST v2.

Chỉ dùng ``urllib`` của thư viện chuẩn: CLI phải chạy được bằng bất kỳ ``python3`` nào, không
phụ thuộc venv nào và không cần cài thêm dependency.
"""

from __future__ import annotations

import json
import os
import shutil
import ssl
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from jira_tools.config import (
    DEFAULT_API_PREFIX,
    PLUGIN_ROOT,
    SECRETS_FILE_NAME,
    JiraConfig,
    Profile,
    read_secret_pat,
)
from jira_tools.errors import ConfigError, JiraCliError

TOKEN_ENV_VAR: Final = "JIRA_PAT"
#: Biến chuẩn OpenSSL: đã đặt thì tôn trọng nó, không ép CA bundle của profile.
SSL_CERT_FILE_ENV_VAR: Final = "SSL_CERT_FILE"
KEYCHAIN_TIMEOUT_SECONDS: Final = 5.0

#: Trần thời gian mỗi lời gọi HTTP: Jira on-prem thỉnh thoảng treo, không để CLI treo theo.
REQUEST_TIMEOUT_SECONDS: Final = 30.0

#: PAT phân giải muộn — hàm không tham số trả PAT, gọi ngay trước khi phát request.
TokenProvider = Callable[[], str]

CLI_PATH: Final = PLUGIN_ROOT / "bin" / "jira-cli"


def token_missing_help(profile: Profile) -> str:
    """Cách tạo/lưu PAT cho đúng host của profile — không hardcode host nào."""
    service = profile.keychain_service or "<keychain_service>"
    return (
        f"Thiếu Personal Access Token cho profile {profile.name!r}: {TOKEN_ENV_VAR} trống, "
        f"config/{SECRETS_FILE_NAME} không có PAT và không đọc được Keychain (service {service}).\n"
        f"  1) Tạo PAT: {profile.base_url}/secure/ViewProfile.jspa → tab 'Personal Access Tokens' "
        "→ 'Create token'.\n"
        f'  2) Lưu vào Keychain: security add-generic-password -a "$USER" -s {service} -w '
        "'<PAT>' -U\n"
        f"  hoặc dùng một lần:  {TOKEN_ENV_VAR}='<PAT>' {CLI_PATH} whoami"
    )


#: Gợi ý theo mã HTTP — cùng một body lỗi của Jira nghĩa rất khác nhau tuỳ mã.
HTTP_STATUS_HINTS: Final[dict[int, str]] = {
    401: "PAT sai hoặc đã hết hạn — tạo lại tại <host>/secure/ViewProfile.jspa.",
    403: "PAT hợp lệ nhưng tài khoản không đủ quyền cho thao tác này.",
    404: "Không tồn tại, hoặc token không có quyền nhìn thấy nó (Jira trả 404 thay vì 403).",
}


def read_keychain_token(service: str) -> str | None:
    """PAT trong macOS Keychain, hoặc ``None``. Nuốt mọi lỗi: đây chỉ là đường fallback."""
    if not shutil.which("security"):
        return None
    account = os.environ.get("USER", "")
    command = ["security", "find-generic-password", "-a", account, "-s", service, "-w"]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=KEYCHAIN_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def resolve_token(
    config: JiraConfig,
    profile: Profile,
    env: Mapping[str, str] | None = None,
) -> str:
    """``JIRA_PAT`` > ``config/secrets.json`` > Keychain; thiếu cả ba thì thoát 2."""
    environ = os.environ if env is None else env
    token = (environ.get(TOKEN_ENV_VAR) or "").strip()
    if token:
        return token
    token = read_secret_pat(config, profile.name) or ""
    if token:
        return token
    if profile.keychain_service:
        # Tra ``read_keychain_token`` qua global lúc gọi để test monkeypatch được module này.
        token = (read_keychain_token(profile.keychain_service) or "").strip()
        if token:
            return token
    raise ConfigError(token_missing_help(profile))


def build_ssl_context(
    profile: Profile, env: Mapping[str, str] | None = None
) -> ssl.SSLContext | None:
    """CA bundle của profile nếu file tồn tại; ``SSL_CERT_FILE`` đã đặt thì để OpenSSL tự đọc.

    ``None`` nghĩa là dùng context mặc định của ``urllib``. Không bao giờ tắt verify: PAT đi
    trong header, tắt verify là lộ token.
    """
    environ = os.environ if env is None else env
    if (environ.get(SSL_CERT_FILE_ENV_VAR) or "").strip():
        return None
    if profile.ca_bundle is None or not profile.ca_bundle.is_file():
        return None
    return ssl.create_default_context(cafile=str(profile.ca_bundle))


def _jira_error_detail(error: urllib.error.HTTPError) -> str:
    """``errorMessages`` / ``errors`` của Jira ở dạng người đọc được."""
    try:
        body = json.loads(error.read().decode("utf-8", errors="replace"))
    except (ValueError, OSError):
        return ""
    if not isinstance(body, dict):
        return ""
    lines = [str(message) for message in body.get("errorMessages") or ()]
    errors = body.get("errors")
    if isinstance(errors, dict):
        lines.extend(f"{field}: {message}" for field, message in errors.items())
    return "\n".join(f"  {line}" for line in lines)


def format_http_error(error: urllib.error.HTTPError, url: str) -> str:
    parts = [f"Jira trả HTTP {error.code} cho {url}"]
    detail = _jira_error_detail(error)
    if detail:
        parts.append(detail)
    hint = HTTP_STATUS_HINTS.get(error.code)
    if hint:
        parts.append(f"  → {hint}")
    return "\n".join(parts)


@dataclass(frozen=True)
class JiraClient:
    """Lớp gọi REST v2 mỏng. ``token`` chỉ đi vào header, không bao giờ ra stdout/stderr.

    ``token`` nhận **chuỗi PAT hoặc hàm trả PAT**, và hàm đó chỉ được gọi ngay trước khi phát
    request. Nhờ vậy ``url`` / ``browse_url`` — thứ ``--dry-run`` cần — chạy được khi chưa có
    token, còn lỗi thiếu token vẫn nổ đúng lúc sắp gọi mạng với nguyên mã thoát 2.
    """

    base_url: str
    token: str | TokenProvider
    timeout: float = REQUEST_TIMEOUT_SECONDS
    api_prefix: str = DEFAULT_API_PREFIX
    ssl_context: ssl.SSLContext | None = None

    def api(self, path: str) -> str:
        """Path REST đầy đủ: ``api("/myself")`` → ``/rest/api/2/myself``."""
        return f"{self.api_prefix}{path}"

    def url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def browse_url(self, key: str) -> str:
        return self.url(f"/browse/{key}")

    def bearer_token(self) -> str:
        """PAT dùng cho header ``Authorization``; phân giải muộn nếu là hàm."""
        token = self.token
        return token if isinstance(token, str) else token()

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        """Trả JSON đã parse, hoặc ``None`` khi Jira trả body rỗng (PUT issue → 204)."""
        # Phân giải token trước khi dựng request: ``ConfigError`` ở đây là lỗi cấu hình
        # (mã thoát 2), không phải lỗi HTTP.
        bearer = self.bearer_token()
        url = self.url(path)
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, method=method)
        request.add_header("Authorization", f"Bearer {bearer}")
        request.add_header("Accept", "application/json")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(
                request, timeout=self.timeout, context=self.ssl_context
            ) as response:
                body = response.read()
        except urllib.error.HTTPError as error:
            # ``from None``: chuỗi traceback gốc giữ tham chiếu tới Request, vốn mang header
            # Authorization — cắt nó đi để token không bao giờ lọt vào output.
            raise JiraCliError(format_http_error(error, url)) from None
        except OSError as error:
            raise JiraCliError(f"Không gọi được {url}: {error}") from None
        if not body.strip():
            return None
        return json.loads(body.decode("utf-8"))
