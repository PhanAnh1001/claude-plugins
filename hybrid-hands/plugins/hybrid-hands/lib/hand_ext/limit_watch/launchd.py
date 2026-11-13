"""User LaunchAgent, no shell, no RunAtLoad or backlog inference calls."""
from __future__ import annotations

import os
import plistlib
import subprocess
import sys
import tempfile
from pathlib import Path

LABEL = 'local.hybrid-hands.limit-watch'


def plist_path():
    return Path.home() / 'Library/LaunchAgents' / (LABEL + '.plist')


def installed():
    return plist_path().is_file()


def install():
    if sys.platform != 'darwin':
        raise ValueError('launchd_requires_macos')
    path = plist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    binary = Path(__file__).resolve().parents[3] / 'bin/hand-ext'
    payload = dict(Label=LABEL, ProgramArguments=[sys.executable, str(binary), 'limit-watch', 'tick'],
                   StartCalendarInterval=[dict(Minute=m) for m in (0, 15, 30, 45)],
                   ProcessType='Background', EnvironmentVariables=dict(
                       PATH=os.environ.get('PATH', '/usr/bin:/bin'), HOME=str(Path.home())))
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.'+LABEL)
    try:
        with os.fdopen(fd, 'wb') as stream:
            plistlib.dump(payload, stream)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    domain = f'gui/{os.getuid()}'
    subprocess.run(['launchctl', 'bootout', domain+'/'+LABEL], capture_output=True, timeout=8)
    result = subprocess.run(['launchctl', 'bootstrap', domain, str(path)],
                            capture_output=True, timeout=8)
    if result.returncode:
        path.unlink(missing_ok=True)
        raise ValueError('launchctl_bootstrap_failed')


def remove():
    path = plist_path()
    # Bootout can terminate the tick running inside this job. Remove the file
    # first so a confirmed one-shot completion also stays off after next login.
    path.unlink(missing_ok=True)
    if sys.platform == 'darwin':
        # A missing job is already off; do not expose launchctl's arbitrary text.
        result = subprocess.run(['launchctl', 'bootout', f'gui/{os.getuid()}/'+LABEL],
                                capture_output=True, timeout=8)
        if result.returncode not in (0, 3, 113):
            # Verify absence instead of assuming every bootout failure is harmless.
            check = subprocess.run(['launchctl', 'print', f'gui/{os.getuid()}/'+LABEL],
                                   capture_output=True, timeout=8)
            if check.returncode == 0:
                raise ValueError('launchctl_bootout_unconfirmed')
