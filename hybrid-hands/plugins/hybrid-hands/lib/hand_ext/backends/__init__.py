"""Lazy backend registry: module backends/<name>.py, class <Name>Backend."""
from __future__ import annotations

import importlib

from .base import Backend

KNOWN_BACKENDS = ("dsh", "codex", "claude", "claude-main", "gemini")
# Backends removed from the plugin; old configs may still name them in `order`.
REMOVED_BACKENDS = ("opencode",)
# Names that do not map to their own module/class (hyphen, or a shared implementation).
MODULE_OVERRIDES = {"claude-main": ("claude", "ClaudeMainBackend")}


class BackendUnavailable(Exception):
    """Backend name unknown or its module is not written yet."""


def get_backend(name: str) -> Backend:
    if name not in MODULE_OVERRIDES and not name.isidentifier():
        raise BackendUnavailable(f"tên backend không hợp lệ: {name!r}")
    if name in REMOVED_BACKENDS:
        raise BackendUnavailable(f"backend {name!r} không hỗ trợ (đã gỡ, dùng dsh)")
    module_name, class_name = MODULE_OVERRIDES.get(
        name, (name, f"{name.capitalize()}Backend"))
    try:
        module = importlib.import_module(f"{__name__}.{module_name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"{__name__}.{module_name}":
            raise BackendUnavailable(f"backend {name!r} chưa có (thiếu backends/{module_name}.py)")
        raise
    cls = getattr(module, class_name, None)
    if cls is None:
        raise BackendUnavailable(
            f"backends/{module_name}.py thiếu lớp {class_name}")
    return cls()
