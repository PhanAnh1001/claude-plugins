"""Cross-process admission for durable writers and compatibility shell slots."""
from dataclasses import dataclass, asdict
import hashlib
import json
from . import parallel
from .execution_state import ExecutionKey, StateConflict, atomic_json

class AdmissionFull(RuntimeError): pass
class AdmissionConflict(RuntimeError): pass
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
        data = dict(data); data['key'] = ExecutionKey(**data['key']); data['claims'] = tuple(data['claims'])
        return cls(**data)

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
            existing = list(parallel.durable_reservations())
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
                if other.key.invocation_id == invocation.invocation_id: raise AdmissionConflict('invocation already has a writer')
                if claims_overlap(other.claims, claims): raise AdmissionConflict('overlapping source write claims')
            directory = parallel.pool_scope(invocation.scope_id)
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if parallel.shell_count(directory) + sum(parallel.canonical_scope(d['scope_id']) == scope for _,d in existing) >= limit:
                raise AdmissionFull('common execution pool full')
            r = self.store.get(attempt.key)
            if r.outcome is not None: raise AdmissionConflict('attempt already finished')
            # Durable reservation first: interruption can leak capacity, never duplicate writers.
            atomic_json(directory / f'reservation-{rid}.json', asdict(reservation))
            r.reservation = asdict(reservation); r.state = 'admitted'
            self.store.compare_and_swap(r.key, r.revision, r)
        return reservation
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
            if not self.supervisor.reconcile(r.key).confirmed: raise AdmissionConflict('writer still unresolved')
            r = self.store.get(r.key)
            if r.reservation and json.dumps(r.reservation, sort_keys=True) != json.dumps(asdict(reservation), sort_keys=True): raise StateConflict('reservation mismatch')
            r.reservation = None; r.state = 'awaiting_review'
            self.store.compare_and_swap(r.key, r.revision, r)
            path = parallel.pool_scope(reservation.scope_id) / f'reservation-{reservation.reservation_id}.json'
            path.unlink(missing_ok=True) # data only; lock inodes are never unlinked
            import os
            fd = os.open(path.parent, os.O_RDONLY)
            try: os.fsync(fd)
            finally: os.close(fd)
