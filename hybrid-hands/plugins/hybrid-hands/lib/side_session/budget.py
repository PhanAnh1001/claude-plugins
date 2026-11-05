"""Run the configured day-budget guard `budget_check_cmd` (no shell, hard timeout)."""
from __future__ import annotations

import subprocess
from dataclasses import dataclass

from . import constants as C
from .config import SideConfig

BUDGET_FAILED_CODE = -1


@dataclass(frozen=True)
class BudgetResult:
    code: int
    stdout: str = ""
    error: str = ""

    @property
    def refused(self) -> bool:
        return self.code != 0


def check(cfg: SideConfig) -> BudgetResult:
    """Exit code of the guard; a command that cannot run is a failure (non-zero)."""
    if not cfg.budget_check_cmd:
        return BudgetResult(0)
    try:
        done = subprocess.run(cfg.budget_check_cmd, cwd=str(cfg.repo), capture_output=True,
                              text=True, timeout=C.BUDGET_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return BudgetResult(BUDGET_FAILED_CODE,
                            error=f"không chạy được {cfg.budget_check_cmd[0]}: {exc}")
    return BudgetResult(done.returncode, stdout=done.stdout)


def daystop(result: BudgetResult, exempt: bool) -> bool:
    return not exempt and result.code == C.BUDGET_DAYSTOP_CODE
