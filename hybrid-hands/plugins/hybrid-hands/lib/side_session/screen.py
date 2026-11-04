"""Thin wrappers around `screen`. Only touches screens named by side-session."""
from __future__ import annotations

import shlex
import subprocess


def screen_names() -> set[str]:
    out = subprocess.run(["screen", "-ls"], capture_output=True, text=True)
    names: set[str] = set()
    for line in out.stdout.splitlines():
        token = line.strip().split("\t")[0].strip()
        if "." in token and token.split(".", 1)[0].isdigit():
            names.add(token.split(".", 1)[1])
    return names


def is_alive(name: str) -> bool:
    return name in screen_names()


def start_cmd(name: str, argv: list[str], cwd: str, env: dict[str, str] | None = None) -> list[str]:
    """screen -dmS NAME sh -c 'cd DIR && [ENV=..] exec ARGV' (runs inside screen, not our shell)."""
    env_part = " ".join(f"{k}={shlex.quote(v)}" for k, v in (env or {}).items())
    inner = f"cd {shlex.quote(cwd)} && {env_part + ' ' if env_part else ''}exec {shlex.join(argv)}"
    return ["screen", "-dmS", name, "sh", "-c", inner]


def quit_cmd(name: str) -> list[str]:
    return ["screen", "-S", name, "-X", "quit"]


def run(cmd: list[str]) -> int:
    return subprocess.run(cmd).returncode
