"""macOS heat guard. Never print process arguments or profile paths."""
import argparse
from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time

POLL_SECONDS = 30
DEFAULT_CPU = 60


def capture(argv: list[str]) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=10)
    if result.returncode:
        if any(word in result.stderr.lower() for word in ('operation not permitted', 'permission denied')):
            raise PermissionError
        raise RuntimeError(f'{argv[0]} unavailable ({result.returncode})')
    return result.stdout


def processes() -> list[dict]:
    rows = []
    for line in capture(['ps', '-axo', 'pid=,ppid=,pgid=,etime=,%cpu=,comm=,args=']).splitlines():
        fields = line.split(None, 5)
        if len(fields) != 6:
            continue
        pid, ppid, pgid, elapsed, cpu, command = fields
        days, _, clock = elapsed.rpartition('-')
        parts = list(map(int, clock.split(':')))
        seconds = sum(v * 60 ** i for i, v in enumerate(reversed(parts)))
        rows.append(dict(pid=int(pid), ppid=int(ppid), pgid=int(pgid),
                         age=seconds + int(days or 0) * 86400,
                         cpu=float(cpu), command=command))
    return rows


def browser_profile(row: dict) -> str:
    command = row['command']
    if 'Google Chrome' not in command or not re.search(r'--headless(?:=\S+)?(?:\s|$)', command):
        return ''
    try:
        args = shlex.split(command)
    except ValueError:
        return ''
    profile = ''
    for i, arg in enumerate(args):
        if arg.startswith('--user-data-dir='):
            profile = arg.split('=', 1)[1]
        elif arg == '--user-data-dir' and i + 1 < len(args):
            profile = args[i + 1]
    resolved = str(Path(profile).resolve()) if profile else ''
    return resolved if resolved.startswith(('/private/tmp/', '/private/var/folders/')) else ''


def no_clients(row: dict) -> bool:
    """Unknown ports, pipe transport or lsof failures prohibit reaping."""
    command = row['command']
    match = re.search(r'--remote-debugging-port=(\d+)(?:\s|$)', command)
    if not match or int(match[1]) == 0 or '--remote-debugging-pipe' in command:
        return False
    result = subprocess.run(['lsof', '-nP', f'-iTCP:{match[1]}', '-sTCP:ESTABLISHED', '-t'],
                            capture_output=True, text=True, timeout=10)
    if any(word in result.stderr.lower() for word in ('operation not permitted', 'permission denied')):
        raise PermissionError
    return result.returncode == 1 and not result.stdout and not result.stderr


def eligible(rows: list[dict], min_age: float, client_check=no_clients) -> list[dict]:
    return [r for r in rows if r['ppid'] == 1 and r['age'] >= min_age
            and browser_profile(r) and client_check(r)]


def reap(dry_run: bool, min_age: float = 600) -> None:
    for row in eligible(processes(), min_age):
        print(f"orphan pid={row['pid']} age_seconds={row['age']} dry_run={dry_run}")
        if dry_run:
            continue
        # Revalidate exact identity and CDP immediately before signalling.
        fresh = next((r for r in processes() if r['pid'] == row['pid']), None)
        if fresh and fresh['command'] == row['command'] and eligible([fresh], min_age):
            try:
                os.kill(row['pid'], signal.SIGTERM)
            except ProcessLookupError:
                pass


def classify(cpu: float, max_cpu: float, thermal: bool = False) -> str:
    return 'hot' if thermal else 'busy' if cpu >= max_cpu else 'ok'


def status(max_cpu: float = DEFAULT_CPU) -> dict:
    rows = processes()
    cpu = sum(r['cpu'] for r in rows) / (os.cpu_count() or 1)
    thermal = None
    speed = None
    if sys.platform == 'darwin':
        try:
            output = capture(['pmset', '-g', 'therm'])
            match = re.search(r'CPU_Speed_Limit\s*=\s*(\d+)', output)
            speed = int(match[1]) if match else None
            thermal = bool(speed is not None and speed < 100 or
                           re.search(r'(?:thermal|performance) warning level\s*=\s*[1-9]', output, re.I))
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            pass
    browsers = [r for r in rows if browser_profile(r)]
    return dict(state=classify(cpu, max_cpu, thermal is True), cpu_pct=round(cpu, 2),
                load_1_5=list(os.getloadavg()[:2]), cpu_speed_limit=speed,
                thermal_warning=thermal, headless=len(browsers),
                orphans=len(eligible(rows, 0)),
                top=[dict(pid=r['pid'], cpu=r['cpu']) for r in sorted(rows, key=lambda r: -r['cpu'])[:5]])


def gate(max_cpu: float, wait: bool, deadline: float) -> int:
    while True:
        snapshot = status(max_cpu)
        if snapshot['state'] == 'ok':
            return 0
        if not wait or time.monotonic() >= deadline:
            return 1
        time.sleep(min(POLL_SECONDS, max(0, deadline - time.monotonic())))


def acquire_lock(handle, deadline: float) -> None:
    while True:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            if time.monotonic() >= deadline:
                raise TimeoutError('browser lock timeout')
            time.sleep(0.1)


def acquire_slot(stack: ExitStack, directory: Path, slots: int, deadline: float) -> None:
    """All callers share numbered locks; slot zero retains the original lock."""
    handles = [stack.enter_context((directory / ('browser.lock' if i == 0 else
               f'browser.{i}.lock')).open('a')) for i in range(slots)]
    while True:
        for handle in handles:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except BlockingIOError:
                continue
        if time.monotonic() >= deadline:
            raise TimeoutError('browser slot timeout')
        time.sleep(0.1)


def cleanup_new_browsers(before: set[int]) -> None:
    """Only new orphan roots with temporary profiles and no CDP clients."""
    candidates = [r for r in eligible(processes(), 0) if r['pid'] not in before]
    for row in candidates:
        fresh = next((r for r in processes() if r['pid'] == row['pid']), None)
        if not fresh or fresh['command'] != row['command'] or not eligible([fresh], 0):
            continue
        try:
            os.kill(fresh['pid'], signal.SIGTERM)
        except ProcessLookupError:
            pass


def browser(command: list[str], minutes: float, slots: int = 1) -> int:
    if command[:1] == ['--']:
        command = command[1:]
    if not command:
        raise ValueError('browser requires -- command')
    if slots < 1:
        raise ValueError('slots must be positive')
    lock = Path.home() / '.hybrid-hands/locks/browser.lock'
    lock.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    deadline = started + minutes * 60
    with ExitStack() as stack:
        acquire_slot(stack, lock.parent, slots, deadline)
        print(f'lock_wait_seconds={time.monotonic() - started:.2f}', flush=True)
        if gate(DEFAULT_CPU, True, deadline):
            return 1
        before = {r['pid'] for r in processes()}
        prefix = ['nice', '-n', '19']
        if sys.platform == 'darwin' and shutil.which('taskpolicy'):
            prefix += ['taskpolicy', '-b']
        child = subprocess.Popen(prefix + command, start_new_session=True)
        def interrupted(signum, frame):
            raise KeyboardInterrupt
        previous = {s: signal.signal(s, interrupted) for s in (signal.SIGINT, signal.SIGTERM)}
        try:
            return child.wait(timeout=max(0.01, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            return 124
        finally:
            # Refuse group cleanup if any Chrome root lacks safe profile/CDP proof.
            try:
                members = [r for r in processes() if r['pgid'] == child.pid]
                chrome = [r for r in members if 'Google Chrome' in r['command']
                          and '--type=' not in r['command']]
                safe = all(browser_profile(r) and no_clients(r) for r in chrome)
                if any('Google Chrome' in r['command'] for r in members) and not chrome:
                    safe = False
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                safe = False
            for sig in (signal.SIGTERM, signal.SIGKILL) if safe else ():
                try:
                    os.killpg(child.pid, sig)
                except ProcessLookupError:
                    break
                if sig == signal.SIGTERM:
                    time.sleep(0.2)
            if child.poll() is None and not safe:
                print('hh-heat: cleanup refused: process/CDP ownership unproven', file=sys.stderr)
            if safe:
                child.wait()
            try:
                cleanup_new_browsers(before)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)


def main() -> int:
    parser = argparse.ArgumentParser(prog='hh-heat')
    sub = parser.add_subparsers(dest='action', required=True)
    st = sub.add_parser('status')
    st.add_argument('--json', action='store_true')
    ga = sub.add_parser('gate')
    ga.add_argument('--max-cpu', type=float, default=DEFAULT_CPU)
    ga.add_argument('--wait', action='store_true')
    ga.add_argument('--timeout-min', type=float, default=20)
    br = sub.add_parser('browser')
    br.add_argument('--slots', type=int, default=os.environ.get('HH_HEAT_BROWSER_SLOTS', '1'))
    br.add_argument('--timeout-min', type=float, default=10)
    br.add_argument('command', nargs=argparse.REMAINDER)
    rp = sub.add_parser('reap')
    rp.add_argument('--dry-run', action='store_true')
    rp.add_argument('--min-age-min', type=float, default=10)
    args = parser.parse_args()
    try:
        if args.action == 'status':
            print(json.dumps(status(), ensure_ascii=False))
        elif args.action == 'gate':
            return gate(args.max_cpu, args.wait, time.monotonic() + args.timeout_min * 60)
        elif args.action == 'browser':
            return browser(args.command, args.timeout_min, args.slots)
        else:
            reap(args.dry_run, args.min_age_min * 60)
        return 0
    except PermissionError:
        print('hh-heat: cần chạy ngoài sandbox (không đủ quyền quan sát/điều khiển tiến trình)', file=sys.stderr)
        return 3
    except (OSError, RuntimeError, ValueError, TimeoutError, subprocess.TimeoutExpired) as exc:
        print(f'hh-heat: {type(exc).__name__}; observation/action unavailable', file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
