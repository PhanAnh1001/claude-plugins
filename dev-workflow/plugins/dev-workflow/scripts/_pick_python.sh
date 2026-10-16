# Shared by `dw`, `session-start.sh` and `skill-notice.sh` (fallback only; sourced, not executed).
# dw_pick_python sets the array DW_PYTHON to a command that runs Python >= 3.11 (needs tomllib):
#   1. the first of DW_PYTHON_CANDIDATES on PATH that can `import tomllib`;
#   2. otherwise `uv run --no-project --python 3.11 python` when `uv` is on PATH
#      (only checked for existence here; uv may download Python on first real use);
#   3. otherwise it returns 1 and leaves DW_PYTHON empty.

DW_PYTHON_CANDIDATES=(python3 python3.13 python3.12 python3.11)
DW_UV_PYTHON_VERSION="3.11"

dw_pick_python() {
  DW_PYTHON=()
  local candidate
  for candidate in "${DW_PYTHON_CANDIDATES[@]}"; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import tomllib' >/dev/null 2>&1; then
      DW_PYTHON=("$candidate")
      return 0
    fi
  done
  if command -v uv >/dev/null 2>&1; then
    DW_PYTHON=(uv run --no-project --python "$DW_UV_PYTHON_VERSION" python)
    return 0
  fi
  return 1
}
