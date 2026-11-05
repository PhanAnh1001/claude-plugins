"""Thin wrappers around `screen`. Only touches screens named by side-session."""
from __future__ import annotations

import shlex
import subprocess


def screen_ids() -> dict[str, str]:
    """name -> `pid.name` of every running screen."""
    out = subprocess.run(["screen", "-ls"], capture_output=True, text=True)
    ids: dict[str, str] = {}
    for line in out.stdout.splitlines():
        token = line.strip().split("\t")[0].strip()
        if "." in token and token.split(".", 1)[0].isdigit():
            ids[token.split(".", 1)[1]] = token
    return ids


def screen_names() -> set[str]:
    return set(screen_ids())


def quit(name: str) -> bool:
    """Quit screen `name` by its exact `pid.name`: `screen -S side-x` alone is ambiguous
    while `side-x-watch` runs, and screen then refuses to quit either."""
    full = screen_ids().get(name)
    if full is None:
        return False
    return run(quit_cmd(full)) == 0


def is_alive(name: str) -> bool:
    return name in screen_names()


def start_cmd(name: str, argv: list[str], cwd: str, env: dict[str, str] | None = None,
              unset: tuple[str, ...] = ()) -> list[str]:
    """screen -dmS NAME sh -c 'cd DIR && [unset VARS;] [ENV=..] exec ARGV'."""
    env_part = " ".join(f"{k}={shlex.quote(v)}" for k, v in (env or {}).items())
    unset_part = "".join(f"unset {shlex.quote(var)}; " for var in unset)
    inner = (f"cd {shlex.quote(cwd)} && {unset_part}{env_part + ' ' if env_part else ''}"
             f"exec {shlex.join(argv)}")
    return ["screen", "-dmS", name, "sh", "-c", inner]


def quit_cmd(name: str) -> list[str]:
    return ["screen", "-S", name, "-X", "quit"]


def run(cmd: list[str]) -> int:
    return subprocess.run(cmd).returncode
