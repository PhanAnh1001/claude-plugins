import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext import gc


class GCTest(unittest.TestCase):
    def test_collection_and_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            def git(*args):
                return subprocess.run(['git', '-C', str(root), *args], check=True,
                                      capture_output=True, text=True).stdout
            git('init'); git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                            'commit', '--allow-empty', '-m', 'fixture')
            (root/'tracked').write_text('fixture tracked')
            git('add', 'tracked')
            git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-m', 'tracked')
            cfg = SimpleNamespace(root=root, worktree_root=Path(tmp)/'wt',
                                  machine_state_dir=Path(tmp)/'state', paseo={})
            registry = cfg.machine_state_dir / 'runs'
            registry.mkdir(parents=True)
            for key, status in [('done', 'ok'), ('live', 'running'), ('other', 'ok')]:
                path = cfg.worktree_root / ('repo-' + key)
                git('worktree', 'add', '-b', key, str(path))
                (registry/(key+'.json')).write_text(json.dumps(dict(
                    run_id=key, cwd=str(root if key != 'other' else Path(tmp)),
                    status=status, exit_code=0)))
            before = git('for-each-ref', '--format=%(refname) %(objectname)', 'refs/heads')
            rows = gc.run_gc(cfg)
            self.assertEqual([r['classification'] for r in rows], ['finished', 'unknown', 'unknown'])
            self.assertFalse((cfg.machine_state_dir/'worktree-gc.jsonl').exists())
            done = registry/'done.json'
            data = json.loads(done.read_text())
            done.write_text(json.dumps(dict(data, pid=os.getpid())))
            self.assertEqual(gc.classify(cfg, cfg.worktree_root/'repo-done')['classification'], 'unknown')
            done.write_text(json.dumps(data))
            from hand_ext.execution_state import Invocation, Attempt, ExecutionRecord
            record = ExecutionRecord(Invocation('inv', 'scope', '', source_cwd=str(root),
                isolated_cwd=str(cfg.worktree_root/'repo-done')),
                Attempt('inv', 'attempt', 1, 'request', run_id='done'), state='awaiting_review',
                outcome={'quiescent': True}, quiescence={'confirmed': True, 'evidence': ['fixture']},
                settle_keys={k: {'state': 'completed'} for k in gc.SETTLE_KINDS})
            state = cfg.machine_state_dir/'executions'; state.mkdir()
            import hashlib
            identity = dict(invocation_id='inv', attempt_id='attempt', epoch=1)
            metadata = state/(hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()+'.json')
            metadata.write_text(json.dumps(record.to_dict()))
            done.write_text(json.dumps(dict(data, execution_key=identity)))
            before_files = {p.relative_to(cfg.machine_state_dir): p.read_bytes()
                            for p in cfg.machine_state_dir.rglob('*') if p.is_file()}
            self.assertEqual(gc.run_gc(cfg)[0]['classification'], 'finished')
            self.assertEqual(before_files, {p.relative_to(cfg.machine_state_dir): p.read_bytes()
                             for p in cfg.machine_state_dir.rglob('*') if p.is_file()})
            record.reservation = {'held': True}; metadata.write_text(json.dumps(record.to_dict()))
            self.assertEqual(gc.classify(cfg, cfg.worktree_root/'repo-done')['classification'], 'unknown')
            record.reservation = None; metadata.write_text(json.dumps(record.to_dict()))
            # Newer same-invocation epoch (run_id=None) or same-epoch other attempt blocks; other invocation doesn't.
            for inv, att, epoch, st, res, want in (('inv', 'f', 2, 'running', {'held': True}, 'unknown'),
                    ('inv', 'f', 2, 'intent', None, 'unknown'), ('inv', 'f', 1, 'intent', None, 'unknown'),
                    ('other', 'f', 2, 'running', {'held': True}, 'finished')):
                newer = ExecutionRecord(Invocation(inv, 'scope', ''), Attempt(inv, att, epoch, 'request'), state=st, reservation=res)
                ident = dict(invocation_id=inv, attempt_id=att, epoch=epoch)
                extra = state/(hashlib.sha256(json.dumps(ident, sort_keys=True).encode()).hexdigest()+'.json')
                extra.write_text(json.dumps(newer.to_dict()))
                self.assertEqual(gc.classify(cfg, cfg.worktree_root/'repo-done')['classification'], want)
                extra.unlink()
            with patch.object(gc.isolation, '_remove_worktree', return_value='fixture refusal'):
                self.assertEqual(gc.command(cfg, SimpleNamespace(apply=True, json=True)), 1)
            # Only 0/1 from symbolic-ref are attached/detached; any other status is an unknown HEAD.
            with patch.object(gc.isolation, '_git', return_value=SimpleNamespace(returncode=128)):
                self.assertEqual(gc.classify(cfg, cfg.worktree_root/'repo-done')['classification'], 'unknown')
            self.assertTrue(gc._live(10**100))
            rows = gc.run_gc(cfg)
            original = gc.classify
            def changed(config, path):
                (path/'new').write_text('fixture')
                return original(config, path)
            with patch.object(gc, 'classify', side_effect=changed), patch.object(gc, 'collect', return_value=rows):
                self.assertNotIn('removed', gc.run_gc(cfg, apply=True)[0])
                self.assertEqual(original(cfg, cfg.worktree_root/'repo-done')['classification'], 'dirty')
            (cfg.worktree_root/'repo-done/new').unlink()
            applied = gc.run_gc(cfg, apply=True)
            self.assertTrue(applied[0]['removed'])
            self.assertEqual(before, git('for-each-ref', '--format=%(refname) %(objectname)', 'refs/heads'))
            entry = json.loads((cfg.machine_state_dir/'worktree-gc.jsonl').read_text())
            self.assertTrue(all(k in entry for k in ('time', 'path', 'name', 'head', 'bytes', 'classification')))
            # Detached HEAD: remove drops the only pointer, so eligible only when base_commit == HEAD.
            det = cfg.worktree_root/'repo-det'
            root_commit = git('rev-parse', 'HEAD').strip()
            data = dict(run_id='det', cwd=str(root), status='ok', exit_code=0)
            git('worktree', 'add', '--detach', str(det), 'HEAD')
            (registry/'det.json').write_text(json.dumps(dict(data, base_commit=root_commit)))
            self.assertEqual(gc.classify(cfg, det)['classification'], 'finished')
            (det/'tracked').write_text('fixture edit')
            subprocess.run(['git', '-C', str(det), '-c', 'user.name=Fixture',
                            '-c', 'user.email=fixture@example.invalid', 'commit', '-am', 'after'], check=True)
            self.assertEqual(gc.classify(cfg, det)['reason'], 'detached HEAD moved past recorded base commit')
            self.assertNotIn('det', [r['run_id'] for r in gc.run_gc(cfg, apply=True) if r.get('removed')])
            self.assertTrue(det.is_dir())
            # Dry-run must not rewrite the index when the stat cache is stale (mtime-only touch).
            done = cfg.worktree_root/'repo-done2'
            git('worktree', 'add', '-b', 'done2', str(done))
            (registry/'done2.json').write_text(json.dumps(dict(run_id='done2', cwd=str(root), status='ok',
                                                               exit_code=0)))
            index_arg = ('rev-parse', '--path-format=absolute', '--git-path', 'index')
            index = Path(subprocess.run(['git', '-C', str(done), *index_arg], check=True, capture_output=True,
                                        text=True).stdout.strip())
            self.assertNotEqual(index, Path(git(*index_arg).strip()))  # candidate index, not the main one
            index_bytes = index.read_bytes()
            stale = time.time_ns() - 10**9  # mtime-only touch; content stays identical
            os.utime(done/'tracked', ns=(stale, stale))
            rows = gc.run_gc(cfg, apply=False)
            self.assertEqual({r['name']: r['classification'] for r in rows}['repo-done2'], 'finished')
            self.assertEqual(index.read_bytes(), index_bytes)
            self.assertTrue(done.is_dir())
            # Run artifacts or machine state inside the candidate hold it (metadata paths only).
            meta = dict(run_id='done2', cwd=str(root), status='ok', exit_code=0)
            (registry/'done2.json').write_text(json.dumps(dict(meta, run_dir=str(done/'output/llm/hand-ext/done2'))))
            inside = SimpleNamespace(**dict(vars(cfg), machine_state_dir=done/'state'))
            (inside.machine_state_dir/'runs').mkdir(parents=True)
            (inside.machine_state_dir/'runs/done2.json').write_text(json.dumps(meta))
            for config in (cfg, inside):
                self.assertEqual(gc.classify(config, done)['reason'], 'state or run artifacts inside worktree')


class AutoAndPreservedGCTest(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory(); self.addCleanup(holder.cleanup)
        self.tmp = Path(holder.name)
        self.root = self.tmp / 'repo'; self.root.mkdir()
        self.git('init'); (self.root / 'tracked').write_text('fixture')
        self.git('add', 'tracked'); self.git('-c', 'user.name=F', '-c', 'user.email=f@example.invalid',
                                             'commit', '-m', 'fixture')
        self.cfg = SimpleNamespace(root=self.root, worktree_root=self.tmp / 'wt', paseo={},
                                   machine_state_dir=self.tmp / 'state', disk_guard=None,
                                   worktree_gc_auto='finished')
        (self.cfg.machine_state_dir / 'runs').mkdir(parents=True)

    def git(self, *args, cwd=None):
        return subprocess.run(['git', '-C', str(cwd or self.root), *args], check=True,
                              capture_output=True, text=True).stdout.strip()

    def run_worktree(self, run_id, change=None, patch=None):
        """Detached run worktree + registry; optional working change and saved changes.patch."""
        path = self.cfg.worktree_root / ('repo-' + run_id)
        self.git('worktree', 'add', '--detach', str(path), 'HEAD')
        run_dir = self.tmp / 'runs' / run_id; run_dir.mkdir(parents=True)
        (run_dir / 'meta.json').write_text(json.dumps(dict(dirty=False)))
        if change:
            (path / change).write_text('fixture change')
        if patch is not None:
            (run_dir / 'changes.patch').write_bytes(patch)
        (self.cfg.machine_state_dir / 'runs' / (run_id + '.json')).write_text(json.dumps(dict(
            run_id=run_id, cwd=str(self.root), status='ok', exit_code=0, run_dir=str(run_dir),
            base_commit=self.git('rev-parse', 'HEAD'), worktree=str(path))))
        return path

    def test_prepare_auto_collects_finished_and_keeps_dirty(self):
        done, dirty = self.run_worktree('done'), self.run_worktree('dirty', change='new')
        with patch('hand_ext.disk_guard.check_disk', side_effect=RuntimeError('stop after gc')):
            with self.assertRaises(RuntimeError):
                gc.isolation.prepare(self.cfg, self.root, 'next', self.tmp / 'runs/next',
                                     gc.isolation.IsolationChoice('worktree', explicit=True))
        self.assertFalse(done.exists())
        self.assertTrue(dirty.exists())
        with patch.object(gc, 'collect') as scan:  # throttled: no rescan within the interval
            gc.auto_collect(self.cfg)
        scan.assert_not_called()

    def test_registry_kept_while_worktree_exists(self):
        from hand_ext.run_registry import RunRegistry
        path = self.run_worktree('old')
        entry = self.cfg.machine_state_dir / 'runs/old.json'
        entry.write_text(json.dumps(dict(json.loads(entry.read_text()), ended_at=1.0)))
        RunRegistry(self.cfg.machine_state_dir / 'runs', 'new', 'l', 'b', 'm', self.root,
                    self.tmp / 'runs/new')._cleanup(now=10**10)
        self.assertTrue(entry.exists())
        self.git('worktree', 'remove', str(path))  # tmp fixture only
        RunRegistry(self.cfg.machine_state_dir / 'runs', 'new', 'l', 'b', 'm', self.root,
                    self.tmp / 'runs/new')._cleanup(now=10**10)
        self.assertFalse(entry.exists())

    def test_preserved_only_with_include_flag(self):
        probe = self.run_worktree('probe', change='new')
        self.git('add', '-N', 'new', cwd=probe)
        saved = subprocess.run(['git', '-C', str(probe), 'diff', '--binary', '--no-color',
                                '--src-prefix=a/', '--dst-prefix=b/', 'HEAD', '--'],
                               check=True, capture_output=True).stdout
        self.git('reset', '-q', cwd=probe)
        (self.tmp / 'runs/probe/changes.patch').write_bytes(saved)
        self.assertEqual(gc.classify(self.cfg, probe)['classification'], 'preserved')
        self.assertTrue(probe.exists() and gc.run_gc(self.cfg, apply=True) and probe.exists())
        (probe / 'new').write_text('drifted')
        self.assertEqual(gc.classify(self.cfg, probe)['classification'], 'dirty')
        (probe / 'new').write_text('fixture change')
        gc.run_gc(self.cfg, apply=True, include_preserved=True)
        self.assertFalse(probe.exists())


class FailedRunReleaseTest(AutoAndPreservedGCTest):
    """Failed isolated run: worktree removed only when changes.patch provably saves it."""

    def attempt(self, run_id, *, dirty=False, drift=False, keep=False):
        from hand_ext import run_cmd
        path = self.run_worktree(run_id, change='new')
        run_dir = self.tmp / 'runs' / run_id
        (run_dir / 'changes.patch').write_bytes(gc._current_patch(path, self.git('rev-parse', 'HEAD')))
        if drift:
            (path / 'new').write_text('drifted')
        ctx = gc.isolation.IsolationContext('worktree', self.root, path, worktree=path,
                                            worktree_root=self.cfg.worktree_root,
                                            base_commit=self.git('rev-parse', 'HEAD'), dirty=dirty)
        result = SimpleNamespace(ctx=ctx, run_dir=run_dir, kept=True, cleanup_note='',
                                 apply_result=gc.isolation.ApplyResult())
        run_cmd._release_final(result, SimpleNamespace(keep_worktree=keep))
        self.assertTrue((run_dir / 'changes.patch').is_file())
        return path.exists(), result.kept

    def test_release_only_when_patch_matches(self):
        self.assertEqual(self.attempt('saved'), (False, False))
        for kwargs in (dict(drift=True), dict(dirty=True), dict(keep=True)):
            self.assertEqual(self.attempt(next(iter(kwargs)), **kwargs), (True, True), kwargs)
