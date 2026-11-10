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
