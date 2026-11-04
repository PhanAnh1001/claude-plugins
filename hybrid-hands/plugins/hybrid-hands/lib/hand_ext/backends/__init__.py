"""Lazy backend registry: module backends/<name>.py, class <Name>Backend."""
from __future__ import annotations

import importlib

from .base import Backend

KNOWN_BACKENDS = ("codex", "claude", "dsh", "opencode", "gemini")


class BackendUnavailable(Exception):
    """Backend name unknown or its module is not written yet."""


def get_backend(name: str) -> Backend:
    if not name.isidentifier():
        raise BackendUnavailable(f"tên backend không hợp lệ: {name!r}")
    try:
        module = importlib.import_module(f"{__name__}.{name}")
    except ModuleNotFoundError as exc:
        if exc.name == f"{__name__}.{name}":
            raise BackendUnavailable(f"backend {name!r} chưa có (thiếu backends/{name}.py)")
        raise
    cls = getattr(module, f"{name.capitalize()}Backend", None)
    if cls is None:
        raise BackendUnavailable(f"backends/{name}.py thiếu lớp {name.capitalize()}Backend")
    return cls()
