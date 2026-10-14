#!/bin/bash
# Dựng lại certs/jira-ca-bundle.pem = CA của certifi + một CA trung gian.
# Cần khi host Jira chỉ gửi leaf cert mà thiếu CA trung gian; Python không tự tải CA qua AIA như
# curl trên macOS. Không bao giờ tắt verify.
#
# Dùng: build-ca-bundle.sh [URL_CA_TRUNG_GIAN]
#   URL lấy theo thứ tự: tham số thứ nhất > biến JIRA_CA_INTERMEDIATE_URL > mặc định bên dưới.
#   Tìm URL đúng cho host của bạn: openssl s_client -connect <host>:443 -showcerts </dev/null
#   rồi xem mục "CA Issuers" (AIA) của leaf cert.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERTS="$ROOT/certs"
# Mặc định: CA trung gian công khai GlobalSign GCC R46 AlphaSSL CA 2025.
DEFAULT_INTERMEDIATE_URL="http://secure.globalsign.com/cacert/gsgccr46alphasslca2025.crt"
INTERMEDIATE_URL="${1:-${JIRA_CA_INTERMEDIATE_URL:-$DEFAULT_INTERMEDIATE_URL}}"
mkdir -p "$CERTS"

certifi_bundle() {
  python3 -m certifi 2>/dev/null && return 0
  if command -v uv >/dev/null 2>&1; then
    uv run --quiet --no-project --with certifi python -m certifi && return 0
  fi
  python3 -m pip install --user --quiet certifi && python3 -m certifi
}

BASE_BUNDLE="$(certifi_bundle)"
curl -sSf "$INTERMEDIATE_URL" -o "$CERTS/intermediate-ca.der"
openssl x509 -inform DER -in "$CERTS/intermediate-ca.der" -out "$CERTS/intermediate-ca.pem"
cat "$BASE_BUNDLE" "$CERTS/intermediate-ca.pem" > "$CERTS/jira-ca-bundle.pem"
echo "Đã ghi $CERTS/jira-ca-bundle.pem"
