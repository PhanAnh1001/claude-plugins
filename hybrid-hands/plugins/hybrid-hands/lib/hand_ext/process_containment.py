"""Bounded best-effort containment. Environment bytes never leave this module."""
from __future__ import annotations

import ctypes
import errno
from dataclasses import dataclass, asdict
import os
from pathlib import Path
import sys

MARKER = 'HYBRID_HANDS_INVOCATION_ID'
SNAPSHOT_INTERVAL = .05
TERM_WAIT = .3
VERIFY_WAIT = .5
DIAGNOSTIC_LIMIT = 64
METHOD = 'root_group+tracked_tree+env_marker'


@dataclass(frozen=True)
class OSIdentity:
    pid: int
    start: str
    comm: str
    ppid: int
    uid: int
    zombie: bool = False

    def matches(self, other: OSIdentity | None) -> bool:
        return other is not None and (self.pid, self.start, self.uid) == (
            other.pid, other.start, other.uid)


def procargs_marker(data: bytes, marker: bytes) -> bool:
    """KERN_PROCARGS2: argc, executable, padding, argc argv, NUL env entries."""
    if len(data) < 4:
        raise ValueError('invalid process arguments')
    argc = int.from_bytes(data[:4], sys.byteorder, signed=True)
    if argc < 1:
        raise ValueError('invalid process arguments')
    pos = data.index(b'\0', 4) + 1
    while pos < len(data) and data[pos] == 0:
        pos += 1
    for _ in range(argc):
        pos = data.index(b'\0', pos) + 1
    return marker in data[pos:].split(b'\0')


class _BsdInfo(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint32) for name in (
        'flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid', 'ruid',
        'rgid', 'svuid', 'svgid', 'rfu')]
    _fields_ += [('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32)]
    _fields_ += [(name, ctypes.c_uint32) for name in (
        'nfiles', 'pgid', 'pjobc', 'tdev', 'tpgid', 'nice')]
    _fields_ += [('start_sec', ctypes.c_uint64), ('start_usec', ctypes.c_uint64)]


def _mac_info(libproc, pid):
    info = _BsdInfo()
    ctypes.set_errno(0)
    count = libproc.proc_pidinfo(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))
    if count != ctypes.sizeof(info):
        if ctypes.get_errno() == 3:
            return None
        raise OSError(ctypes.get_errno(), 'process identity unavailable')
    return OSIdentity(pid, f'{info.start_sec}:{info.start_usec}',
                      info.comm.decode(errors='replace'), info.ppid, info.uid, info.status == 5)


class ProcessTable:
    """OS boundary; callers receive identities/booleans, never raw env/errors."""
    def snapshot(self) -> dict[int, OSIdentity]:
        if sys.platform == 'darwin':
            libproc = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
            # Same-user enumeration avoids querying other users' private data.
            size = libproc.proc_listpids(4, os.getuid(), None, 0)
            if size <= 0:
                raise RuntimeError('process snapshot unavailable')
            capacity = size + 4096
            pids = (ctypes.c_int * (capacity // ctypes.sizeof(ctypes.c_int)))()
            count = libproc.proc_listpids(4, os.getuid(), pids, capacity)
            if count <= 0 or count >= capacity:
                raise RuntimeError('process snapshot unavailable')
            rows = {}
            for pid in pids[:count // ctypes.sizeof(ctypes.c_int)]:
                if pid:
                    item = _mac_info(libproc, pid)
                    if item:
                        rows[pid] = item
            return rows
        if not sys.platform.startswith('linux'):
            raise RuntimeError('process snapshot unavailable')
        rows = {}
        for path in Path('/proc').iterdir():
            if not path.name.isdigit():
                continue
            try:
                if path.stat().st_uid != os.getuid():
                    continue
                stat = (path / 'stat').read_text()
                end = stat.rindex(')')
                fields = stat[end + 2:].split()
                pid = int(path.name)
                rows[pid] = OSIdentity(pid, fields[19], stat[stat.index('(') + 1:end],
                                       int(fields[1]), os.getuid(), fields[0] == 'Z')
            except FileNotFoundError:
                continue
        return rows

    def identity(self, pid: int) -> OSIdentity | None:
        """Direct birth query; never query a process environment here."""
        if sys.platform == 'darwin':
            return _mac_info(ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True), pid)
        if sys.platform.startswith('linux'):
            path = Path(f'/proc/{pid}')
            try:
                uid = path.stat().st_uid
                stat = (path / 'stat').read_text()
                end = stat.rindex(')')
                fields = stat[end + 2:].split()
                return OSIdentity(pid, fields[19], stat[stat.index('(') + 1:end],
                                  int(fields[1]), uid, fields[0] == 'Z')
            except FileNotFoundError:
                return None
        raise RuntimeError('process identity unavailable')

    def marker_matches(self, pid: int, invocation: str) -> bool:
        marker = (MARKER + '=' + invocation).encode()
        try:
            if sys.platform == 'darwin':
                libc = ctypes.CDLL(None, use_errno=True)
                mib = (ctypes.c_int * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2
                size = ctypes.c_size_t(1024 * 1024)
                buf = ctypes.create_string_buffer(size.value)
                if libc.sysctl(mib, 3, buf, ctypes.byref(size), None, 0):
                    error = ctypes.get_errno()
                    if error == 3:  # ESRCH: raced exit
                        raise ProcessLookupError(error, 'marker process exited')
                    raise OSError(error, 'marker scan unavailable')
                return procargs_marker(buf.raw[:size.value], marker)
            if sys.platform.startswith('linux'):
                return marker in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
            raise RuntimeError('marker scan unavailable')
        except FileNotFoundError:
            raise ProcessLookupError(errno.ESRCH, 'marker process exited') from None
        except OSError as exc:
            error = RuntimeError('marker scan unavailable')
            error.errno = exc.errno
            raise error from None
        except Exception:
            raise RuntimeError('marker scan unavailable') from None

    def group_present(self, pgid: int) -> bool:
        """Read-only group existence probe; permission failures remain uncertain."""
        try:
            os.killpg(pgid, 0)
            return True
        except ProcessLookupError:
            return False

    def signal(self, identity: OSIdentity, sig: int) -> str | None:
        # Revalidate immediately before EACH signal, including escalation.
        current = self.identity(identity.pid)
        if current is None:
            return 'esrch'
        if not identity.matches(current):
            return 'identity_mismatch'
        if not current.zombie:
            os.kill(identity.pid, sig)
        return None


def merge_evidence(previous, current):
    """Retain historical uncertainty and births across independent observations."""
    merged = dict(previous, **current)
    inventory = {(i['pid'], i['start'], i['uid']): i
                 for i in previous.get('inventory', []) + current.get('inventory', [])}
    merged['inventory'] = list(inventory.values())
    merged['inventory_complete'] = (current.get('inventory_complete') is True
                                    and previous.get('inventory_complete') is not False)
    merged['root_reaped'] = bool(previous.get('root_reaped') or current.get('root_reaped'))
    for field in ('binding', 'owner_done', 'first_fatal'):
        if previous.get(field):
            merged[field] = previous[field]
    diagnostics = []
    for detail in previous.get('diagnostics', []) + current.get('diagnostics', []):
        if detail not in diagnostics and len(diagnostics) < DIAGNOSTIC_LIMIT:
            diagnostics.append(detail)
    merged['diagnostics'] = diagnostics
    return merged


class Descendants:
    def __init__(self, proc, invocation, table=None):
        self.proc, self.invocation = proc, invocation
        self.table = table or ProcessTable()
        self.tracked = {}
        self.inventory = {}
        self.diagnostics = []
        self.inventory_complete = True
        # Audit only: retain full identity chains across reparent/marker refresh.
        # Never use historical numeric parent PIDs to authorize discovery/signals.
        self.ancestry: dict[tuple[int, str, str, int], list[tuple[OSIdentity, ...]]] = {}
        self.authoritative = True
        self.root = None
        self.protected = {}
        self.owner_pid = os.getpid()
        try:
            rows = self.table.snapshot()
            self.root = rows.get(proc.pid)
            pid = os.getpid()
            while pid in rows and pid not in self.protected:
                self.protected[pid] = rows[pid]
                pid = rows[pid].ppid
            self.authoritative = self.root is not None and bool(invocation)
            if self.root is None:
                self.inventory_complete = False
                self.failure('initial_snapshot', code='root_missing')
            self.capture(rows)
        except Exception as exc:
            self.inventory_complete = False
            self.failure('initial_snapshot', exc)

    def failure(self, stage, exc=None, item=None, code=None, fatal=True):
        error = getattr(exc, 'errno', None)
        kind = code or ('esrch' if error == errno.ESRCH or isinstance(exc, ProcessLookupError)
                        else 'eperm' if error in (errno.EPERM, errno.EACCES)
                        else 'einval' if error == errno.EINVAL else 'unavailable')
        detail = dict(method=METHOD, stage=stage, error=kind)
        if code == 'exit_or_reused' and error == errno.EINVAL:
            detail.update(error='einval', resolution='gone_or_reused')
        if item is not None:
            detail.update(pid=item.pid, start=item.start)
        if len(self.diagnostics) < DIAGNOSTIC_LIMIT:
            self.diagnostics.append(detail)
        if fatal:
            if not getattr(self, 'first_fatal', None):
                self.first_fatal = detail
            self.authoritative = False

    def details(self):
        return dict(method=METHOD, inventory_complete=self.inventory_complete,
                    inventory=list(self.inventory.values()),
                    root=asdict(self.root) if self.root else None,
                    root_reaped=self.proc.returncode is not None,
                    owner=asdict(self.protected[self.owner_pid]) if self.owner_pid in self.protected else None,
                    protected=[asdict(i) for i in self.protected.values()],
                    diagnostics=list(self.diagnostics),
                    first_fatal=getattr(self, 'first_fatal', None))

    def fresh(self, pid):
        query = getattr(self.table, 'identity', None)
        return query(pid) if query else self.table.snapshot().get(pid)

    def marker(self, item):
        try:
            return self.table.marker_matches(item.pid, self.invocation)
        except Exception as exc:
            try:
                current = self.fresh(item.pid)
                if current is None or not item.matches(current):
                    self.failure('marker', exc, item, code='exit_or_reused', fatal=False)
                    return False
            except Exception as fresh_error:
                self.inventory_complete = False
                self.failure('marker_identity', fresh_error, item)
                return False
            self.inventory_complete = False
            self.failure('marker', exc, item)
            return False

    def is_protected(self, item: OSIdentity) -> bool:
        protected = self.protected.get(item.pid)
        return protected is not None and protected.matches(item)

    def remember(self, item: OSIdentity, rows: dict[int, OSIdentity]) -> None:
        key = (item.pid, item.start, item.comm, item.uid)
        chain = []
        seen = set()
        current = item
        while current is not None and current.pid not in seen:
            chain.append(current)
            seen.add(current.pid)
            current = rows.get(current.ppid)
        observed = tuple(chain)
        history = self.ancestry.setdefault(key, [])
        if observed not in history:
            history.append(observed)
        self.tracked[item.pid] = item
        self.inventory[(item.pid, item.start, item.uid)] = asdict(item)

    def capture(self, rows=None):
        try:
            rows = self.table.snapshot() if rows is None else rows
            current = rows.get(self.proc.pid)
            # Popen retains root authority across exec (comm changes), while
            # OS birth time/uid must stay fixed. Signals revalidate birth
            # with a fresh direct query immediately before kill.
            if (self.root and current and self.proc.returncode is None
                    and (self.root.pid, self.root.start, self.root.uid) ==
                    (current.pid, current.start, current.uid)):
                self.root = current
            elif self.root and current and self.proc.returncode is None:
                # A live reused root PID must never certify quiescence.
                # macOS enumeration can omit an unreaped zombie.
                self.failure('capture', item=current, code='identity_mismatch')
            if self.root:
                self.inventory[(self.root.pid, self.root.start, self.root.uid)] = asdict(self.root)
            parents = {i.pid for i in self.tracked.values() if i.matches(rows.get(i.pid))}
            for pid in parents:
                self.remember(rows[pid], rows)
            if self.root and self.root.matches(rows.get(self.root.pid)):
                parents.add(self.root.pid)
            for _ in range(len(rows)):
                found = [i for i in rows.values() if i.ppid in parents and i.pid not in parents
                         and not self.is_protected(i) and i.uid == os.getuid()]
                if not found:
                    break
                for item in found:
                    self.remember(item, rows)
                    parents.add(item.pid)
            return rows
        except Exception as exc:
            self.inventory_complete = False
            self.failure('capture', exc)
            return {}

    def live(self) -> list[OSIdentity]:
        rows = self.capture()
        for item in rows.values():
            if not self.is_protected(item) and item.uid == os.getuid() and not item.zombie:
                if self.marker(item):
                    self.remember(item, rows)
        return [i for i in self.tracked.values() if not self.is_protected(i)
                and i.matches(rows.get(i.pid)) and not rows[i.pid].zombie]

    def signal_live(self, sig: int) -> None:
        for item in self.live():
            try:
                result = self.table.signal(item, sig)
                if result in ('esrch', 'identity_mismatch'):
                    self.failure('signal', item=item, code=result,
                                 fatal=result == 'identity_mismatch')
            except ProcessLookupError as exc:
                self.failure('signal', exc, item, fatal=False)
            except Exception as exc:
                self.failure('signal', exc, item)

    def verify(self) -> bool:
        live = self.live()
        return self.authoritative and not live
