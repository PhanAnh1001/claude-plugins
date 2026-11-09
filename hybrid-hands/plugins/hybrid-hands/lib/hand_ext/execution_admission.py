"""Cross-process admission for durable writers and compatibility shell slots."""
from dataclasses import dataclass, asdict
import hashlib
import json
import re
from . import parallel
from .execution_state import ExecutionKey, StateConflict, atomic_json

class AdmissionFailure(RuntimeError):
    def __init__(self, kind, holding_key=None):
        self.kind, self.holding_key = kind, holding_key
        super().__init__(kind)

def admission_diagnostic(exc):
    from .execution_state import _plain
    kinds = {'invocation_writer', 'claims_conflict', 'pool_full'}
    key = exc.holding_key
    safe_key = (isinstance(key, ExecutionKey) and type(key.epoch) is int
                and 0 < key.epoch <= 2147483647
                and all(isinstance(v, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', v)
                        for v in (key.invocation_id, key.attempt_id)))
    return dict(code='AdmissionFull' if isinstance(exc, AdmissionFull) else 'AdmissionConflict',
                kind=exc.kind if exc.kind in kinds else 'admission_unavailable',
                holding_key=_plain(key) if safe_key else None)


class AdmissionFull(AdmissionFailure): pass
class AdmissionConflict(AdmissionFailure): pass
class AdmissionDenied(RuntimeError): pass

@dataclass(frozen=True)
class Reservation:
    reservation_id: str
    key: ExecutionKey
    scope_id: str
    claims: tuple
    store_root: str = ""
    @classmethod
    def from_dict(cls, data):
        try:
            data = dict(data); data['key'] = ExecutionKey(**data['key']); data['claims'] = tuple(data['claims'])
            return cls(**data)
        except (TypeError, ValueError, KeyError):
            raise StateConflict('invalid reservation evidence') from None

def canonical_claims(invocation):
    """Repo and file claims collapse worktrees; dependency IDs are global.

    repo:* reserves the whole source repo. file:dir reserves that path and
    descendants. Absolute file paths must be within the source worktree.
    """
    from pathlib import Path
    import subprocess
    source = Path(invocation.source_cwd).resolve()
    worktree, common = source, source
    try:
        result = subprocess.run(['git','rev-parse','--show-toplevel','--path-format=absolute','--git-common-dir'],
                                cwd=source, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            top, gitdir = result.stdout.strip().splitlines()
            worktree, common = Path(top).resolve(), Path(gitdir).resolve()
    except (OSError, ValueError, subprocess.TimeoutExpired): pass
    claims = []
    for claim in invocation.resource_claims:
        if not isinstance(claim, str) or not claim: raise ValueError('invalid claim')
        if claim.startswith('dependency:'):
            claims.append(claim); continue
        if claim in ('repo:*', 'repo:', '*'):
            claims.append(f'repo:{common}:*'); continue
        if claim.startswith('repo:'):
            raise ValueError('repo claim must use repo:*')
        file = claim.removeprefix('file:')
        path = Path(file)
        path = path.resolve() if path.is_absolute() else (source / path).resolve()
        try: relative = path.relative_to(worktree)
        except ValueError: raise ValueError('claim escapes source worktree')
        claims.append(f'repo:{common}:file:{relative}')
    return tuple(sorted(set(claims)))


def claims_overlap(left, right):
    for a in left:
        for b in right:
            if a == b: return True
            if a.startswith('dependency:') or b.startswith('dependency:'): continue
            if a.endswith(':*') and b.startswith(a[:-1]): return True
            if b.endswith(':*') and a.startswith(b[:-1]): return True
            if b.startswith(a.rstrip('/') + '/') or a.startswith(b.rstrip('/') + '/'): return True
    return False

class AdmissionController:
    def __init__(self, store, supervisor, policy_checker):
        self.store, self.supervisor, self.policy_checker = store, supervisor, policy_checker
    def admit(self, invocation, attempt, *, max_parallel):
        limit = parallel.validate_limit(max_parallel)
        scope = parallel.canonical_scope(invocation.scope_id)
        if not callable(self.policy_checker) or self.policy_checker(invocation, attempt) is not True:
            raise AdmissionDenied('explicit policy allow required')
        limit_reader = getattr(self.policy_checker, 'max_parallel', None)
        if callable(limit_reader):
            limit = min(limit, parallel.validate_limit(limit_reader(invocation)))
        self.store.create_intent(invocation, attempt) # intent precedes every network operation
        claims = canonical_claims(invocation)
        rid = hashlib.sha256(json.dumps(asdict(attempt.key), sort_keys=True).encode()).hexdigest()
        reservation = Reservation(rid, attempt.key, invocation.scope_id, claims, str(self.store.root))
        with parallel.pool_lock():
            try:
                existing = list(parallel.durable_reservations())
            except (OSError, ValueError):
                raise StateConflict('pool authority unavailable') from None
            for _, data in existing:
                other = Reservation.from_dict(data)
                if other.key == attempt.key:
                    if other.store_root != str(self.store.root): raise AdmissionConflict('execution belongs to another durable store')
                    # Repair interrupted write after durable reservation but before store CAS.
                    r = self.store.get(attempt.key)
                    if not r.reservation:
                        r.reservation = asdict(other); r.state = 'admitted'
                        self.store.compare_and_swap(r.key, r.revision, r)
                    return other
                if other.key.invocation_id == invocation.invocation_id:
                    self._reject(attempt.key, 'invocation_writer', other.key)
                if claims_overlap(other.claims, claims):
                    self._reject(attempt.key, 'claims_conflict', other.key)
            directory = parallel.pool_scope(invocation.scope_id)
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if parallel.shell_count(directory) + sum(parallel.canonical_scope(d['scope_id']) == scope for _,d in existing) >= limit:
                self._reject(attempt.key, 'pool_full', next((Reservation.from_dict(d).key for _, d in existing
                             if parallel.canonical_scope(d['scope_id']) == scope), None), full=True)
            r = self.store.get(attempt.key)
            if r.outcome is not None: raise AdmissionConflict('attempt already finished')
            # Durable reservation first: interruption can leak capacity, never duplicate writers.
            atomic_json(directory / f'reservation-{rid}.json', asdict(reservation))
            r.reservation = asdict(reservation); r.state = 'admitted'
            self.store.compare_and_swap(r.key, r.revision, r)
        return reservation
    def _reject(self, key, kind, holding_key, *, full=False):
        from .legacy_attestation import never_admitted
        from .execution_state import _plain
        import time
        with self.store.locked():
            r = self.store._read(self.store._path(key))
            try:
                never_admitted(self.store, r)
            except StateConflict:
                # Inherited placement or uncertain authority cannot be labelled
                # never-admitted; still reject before reserving or dispatching.
                raise (AdmissionFull if full else AdmissionConflict)(kind, holding_key) from None
            r.state = 'not_admitted'
            r.outcome = dict(status='not_admitted', backend_exit_code=8,
                             reason=kind, holding_key=_plain(holding_key))
            r.finished_at = time.time()
            r.revision += 1
            atomic_json(self.store._path(key), r.to_dict())
        raise (AdmissionFull if full else AdmissionConflict)(kind, holding_key)

    def reconcile_legacy(self, observations):
        """Register observed legacy writers, even above cap; observations never imply death.

        Items supply invocation/attempt; terminal removal requires release with
        authoritative supervisor quiescence, never disappearance from a snapshot.
        """
        results = []
        for item in observations:
            invocation, attempt = item['invocation'], item['attempt']
            self.store.create_intent(invocation, attempt)
            claims = canonical_claims(invocation)
            rid = hashlib.sha256(json.dumps(asdict(attempt.key),sort_keys=True).encode()).hexdigest()
            reservation = Reservation(rid, attempt.key, invocation.scope_id, claims, str(self.store.root))
            with parallel.pool_lock():
                directory = parallel.pool_scope(invocation.scope_id)
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                path = directory / f'reservation-{rid}.json'
                if path.exists():
                    reservation = Reservation.from_dict(json.loads(path.read_text()))
                    if reservation.store_root != str(self.store.root): raise AdmissionConflict('legacy execution belongs to another store')
                else: atomic_json(path, asdict(reservation))
                r = self.store.get(attempt.key)
                if not r.reservation:
                    r.reservation = asdict(reservation); r.state = 'unresolved'
                    self.store.compare_and_swap(r.key, r.revision, r)
            results.append(reservation)
        return results
    def release(self, reservation, *, outcome, artifacts_settled):
        with parallel.pool_lock():
            r = self.store.get(reservation.key)
            if not artifacts_settled or not r.outcome or r.outcome != outcome or not r.outcome.get('quiescent'):
                raise AdmissionConflict('authoritative outcome and settlement required')
            from .legacy_attestation import settlement_authorized
            if not settlement_authorized(self.supervisor, r.key): raise AdmissionConflict('writer still unresolved')
            r = self.store.get(r.key)
            from .legacy_attestation import attested
            if attested(r):
                path = parallel.pool_scope(reservation.scope_id) / f'reservation-{reservation.reservation_id}.json'
                try:
                    if json.loads(path.read_text()) != json.loads(json.dumps(asdict(reservation))):
                        raise StateConflict('pool reservation mismatch')
                except (OSError, ValueError):
                    raise StateConflict('pool reservation unavailable') from None
            if r.reservation and json.dumps(r.reservation, sort_keys=True) != json.dumps(asdict(reservation), sort_keys=True): raise StateConflict('reservation mismatch')
            r.reservation = None; r.state = 'awaiting_review'
            self.store.compare_and_swap(r.key, r.revision, r)
            path = parallel.pool_scope(reservation.scope_id) / f'reservation-{reservation.reservation_id}.json'
            path.unlink(missing_ok=True) # data only; lock inodes are never unlinked
            import os
            fd = os.open(path.parent, os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
