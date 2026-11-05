"""One error type carrying the process exit code and output stream."""
from __future__ import annotations

from .constants import EXIT_USAGE


class CcSwitchError(Exception):
    def __init__(self, message: str, code: int = EXIT_USAGE,
                 to_stdout: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.to_stdout = to_stdout
