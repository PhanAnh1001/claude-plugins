"""Bounded best-effort containment. Environment bytes never leave this module."""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import os
from pathlib import Path
import sys

MARKER = 'HYBRID_HANDS_INVOCATION_ID'
SNAPSHOT_INTERVAL = .05
TERM_WAIT = .3
VERIFY_WAIT = .5
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
        return other is not None and (self.pid, self.start, self.comm, self.uid) == (
            other.pid, other.start, other.comm, other.uid)


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
    count = libproc.proc_pidinfo(pid, 3, 0, ctypes.byref(info), ctypes.sizeof(info))
    if count != ctypes.sizeof(info):
        if ctypes.get_errno() == 3:
            return None
        raise RuntimeError('process identity unavailable')
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
                        return False
                    raise RuntimeError('marker scan unavailable')
                return procargs_marker(buf.raw[:size.value], marker)
            if sys.platform.startswith('linux'):
                return marker in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0')
            raise RuntimeError('marker scan unavailable')
        except FileNotFoundError:
            return False
        except Exception:
            raise RuntimeError('marker scan unavailable') from None

    def signal(self, identity: OSIdentity, sig: int) -> None:
        # Revalidate immediately before EACH signal, including escalation.
        current = self.snapshot().get(identity.pid)
        if identity.matches(current) and not current.zombie:
            os.kill(identity.pid, sig)


class Descendants:
    def __init__(self, proc, invocation, table=None):
        self.proc, self.invocation = proc, invocation
        self.table = table or ProcessTable()
        self.tracked = {}
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
            self.capture(rows)
        except Exception:
            self.authoritative = False

    def is_protected(self, item: OSIdentity) -> bool:
        protected = self.protected.get(item.pid)
        return item.pid == self.owner_pid or (protected is not None and protected.matches(item))

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

    def capture(self, rows=None):
        try:
            rows = self.table.snapshot() if rows is None else rows
            current = rows.get(self.proc.pid)
            # Popen retains root authority across exec (comm changes), while
            # OS birth time/uid must stay fixed. Signals still compare comm
            # against a fresh, independent snapshot immediately before kill.
            if (self.root and current and self.proc.returncode is None
                    and (self.root.pid, self.root.start, self.root.uid) ==
                    (current.pid, current.start, current.uid)):
                self.root = current
            elif self.root and current and self.proc.returncode is None:
                # A live reused root PID must never certify quiescence.
                # macOS enumeration can omit an unreaped zombie.
                self.authoritative = False
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
        except Exception:
            self.authoritative = False
            return {}

    def live(self) -> list[OSIdentity]:
        rows = self.capture()
        try:
            for item in rows.values():
                if not self.is_protected(item) and item.uid == os.getuid() and not item.zombie:
                    if self.table.marker_matches(item.pid, self.invocation):
                        self.remember(item, rows)
        except Exception:
            self.authoritative = False
        return [i for i in self.tracked.values() if not self.is_protected(i)
                and i.matches(rows.get(i.pid)) and not rows[i.pid].zombie]

    def signal_live(self, sig: int) -> None:
        for item in self.live():
            try:
                self.table.signal(item, sig)
            except ProcessLookupError:
                pass
            except Exception:
                self.authoritative = False

    def verify(self) -> bool:
        live = self.live()
        return self.authoritative and not live
