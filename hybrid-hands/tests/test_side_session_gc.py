"""GC uses only synthetic repositories and mocked runtime metadata."""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from side_session import gc, state
from side_session.config import SideConfig


class GCTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git(self.repo, 'init', '-b', 'main')
        self.git(self.repo, 'config', 'user.email', 'fixture@example.invalid')
        self.git(self.repo, 'config', 'user.name', 'Fixture')
        (self.repo / '.gitignore').write_text('ignored/\n')
        self.git(self.repo, 'add', '.')
        self.git(self.repo, 'commit', '-m', 'initial')
        self.cfg = SideConfig(self.repo, self.root, self.root, 4, 100, 30,
                              state_dir=self.root / 'state', default_base='main')
    def git(self, path, *args):
        return subprocess.check_output(['git', '-C', str(path), *args], stderr=subprocess.DEVNULL)
    def candidate(self, name, status='done', owned=True):
        path = self.root / name
        self.git(self.repo, 'worktree', 'add', '-b', name, str(path), 'main')
        st = state.SessionState(name, name, 'codex', str(path), 'side-' + name, '',
                                100, 1, status, '', worktree=True, base='main')
        if owned:
            with patch.object(state, 'bump_revision'):
                state.save(self.cfg.state_dir, st)
        return path, st
    def test_classes_and_cherry_equivalence(self):
        for name in ('A', 'B', 'C', 'D', 'E', 'équiv\n空'):
            path, _ = self.candidate(name.replace('\n', '-'), status='running' if name == 'D' else 'done', owned=name != 'E')
            if name in ('B', 'équiv\n空'):
                (path / name.replace('\n', '-')).write_text(name)
                self.git(path, 'add', '.')
                self.git(path, 'commit', '-m', name)
            if name == 'C':
                (path / 'untracked\n空').write_text('dirty')
            if name.startswith('équiv'):
                (self.repo / 'independent').write_text('base divergence')
                self.git(self.repo, 'add', '.')
                self.git(self.repo, 'commit', '-m', 'diverge')
                self.git(self.repo, 'cherry-pick', name.replace('\n', '-'))
                self.assertNotEqual(self.git(path, 'rev-parse', 'HEAD'), self.git(self.repo, 'rev-parse', 'HEAD'))
        report = gc.inspect(self.cfg, runtime=lambda *_: True)
        classes = {r['name']: r['class'] for r in report['worktrees']}
        self.assertEqual([classes[n] for n in ('A', 'B', 'C', 'D', 'E', 'équiv-空')], list('ABCDEA'))
        self.assertEqual(report['totals']['eligible'], 2)
    def test_dry_run_and_apply_flags_journal(self):
        path, _ = self.candidate('clean')
        (path / 'ignored').mkdir()
        (path / 'ignored/file').write_bytes(b'123')
        (path / 'ignored/link').symlink_to(self.repo / '.gitignore')
        before = {p: p.read_bytes() for p in self.cfg.state_dir.glob('*.json')}
        refs = self.git(self.repo, 'show-ref')
        with patch.object(gc, 'inspect', wraps=lambda cfg, **kw: gc_inspect(cfg, runtime=lambda *_: True, **kw)):
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(gc.run(self.cfg, SimpleNamespace(fetch=False, name='clean', json=True)), 0)
        row = json.loads(output.getvalue())['worktrees'][0]
        self.assertEqual(row['ignored_bytes'], 3 + (path / 'ignored/link').lstat().st_size)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual(refs, self.git(self.repo, 'show-ref'))
        self.assertTrue(path.is_dir())
        other, _ = self.candidate('unmerged')
        (other / 'new').write_text('new')
        self.git(other, 'add', '.')
        self.git(other, 'commit', '-m', 'unmerged')
        with patch.object(gc, 'inspect', side_effect=lambda cfg, **kw: gc_inspect(cfg, runtime=lambda *_: True, **kw)):
            report = gc.apply(self.cfg)
            self.assertFalse(path.exists())
            self.assertTrue(other.exists())
            gc.apply(self.cfg, include_unmerged=True, prune_branches=True)
        self.assertFalse(other.exists())
        self.git(self.repo, 'rev-parse', '--verify', 'unmerged')
        events = [json.loads(line) for line in (self.cfg.state_dir / 'worktree-gc.jsonl').read_text().splitlines()]
        self.assertEqual([e['class'] for e in events], ['A', 'B'])
        self.assertTrue(all({'timestamp', 'name', 'path', 'branch', 'HEAD', 'bytes', 'class'} <= e.keys() for e in events))
        prune, _ = self.candidate('prune')
        with patch.object(gc, 'inspect', side_effect=lambda cfg, **kw: gc_inspect(cfg, runtime=lambda *_: True, **kw)):
            gc.apply(self.cfg, prune_branches=True)
        self.assertNotIn(b'refs/heads/prune', self.git(self.repo, 'show-ref'))
    def test_unknown_runtime_ownership_and_recheck(self):
        path, st = self.candidate('unknown')
        sockets = "There are screens on:\n\t21239.side-other\t(Detached)\n1 Socket in /fixture/.screen.\n"
        for code, out, err, expected in (
                (1, sockets, '', True), (0, sockets, '', True),
                (1, 'No Sockets found in /fixture/.screen.\n', '', True),
                (1, sockets.replace('side-other', st.screen), '', False),
                (1, sockets.replace('side-other', 'watch-exact'), '', False),
                (2, sockets, '', False), (1, sockets, 'fatal', False),
                (0, 'garbled', '', False)):
            with self.subTest(screen=(code, out, err)), patch.object(
                    gc.subprocess, 'run', return_value=subprocess.CompletedProcess([], code, out, err)):
                self.assertEqual(gc.runtime_ended(replace(st, watch_screen='watch-exact'), [st]), expected)
        for change in ('dirty', 'runtime', 'rename', 'symlink', 'head', 'foreign', 'main'):
            target, target_st = self.candidate('change-' + change)
            calls = []
            def inspect_changed(cfg, **kw):
                if calls:
                    if change == 'dirty':
                        (target / 'dirty').write_text('dirty')
                    elif change == 'rename':
                        target.rename(target.with_name(target.name + '-moved'))
                    elif change == 'symlink':
                        moved = target.with_name(target.name + '-moved')
                        target.rename(moved)
                        target.symlink_to(moved, target_is_directory=True)
                    elif change == 'head':
                        self.git(target, 'commit', '--allow-empty', '-m', 'changed')
                    elif change == 'foreign':
                        (target / '.git').write_text('gitdir: ' + str(self.repo / '.git'))
                    elif change == 'main':
                        with patch.object(state, 'load_all', return_value=[replace(target_st, role='main')]):
                            return gc_inspect(cfg, runtime=lambda *_: True, **kw)
                calls.append(True)
                return gc_inspect(cfg, runtime=lambda *_: change != 'runtime' or len(calls) == 1, **kw)
            with patch.object(gc, 'inspect', side_effect=inspect_changed):
                result = gc.apply(self.cfg, name=target_st.name)
            self.assertTrue(result['worktrees'][0]['result'].startswith('skipped'))
        (path / 'ahead').write_text('unmerged')
        self.git(path, 'add', '.')
        self.git(path, 'commit', '-m', 'ahead')
        with patch.object(state, 'load_all', return_value=[replace(st, base='')]):
            row = gc.inspect(replace(self.cfg, default_base='HEAD'), name=st.name, runtime=lambda *_: True)['worktrees'][0]
            self.assertEqual(row['class'], 'B')
        for runtime, cfg in ((lambda *_: False, self.cfg), (lambda *_: True, replace(self.cfg, default_base='missing'))):
            with patch.object(state, 'load_all', return_value=[replace(st, base='')]):
                self.assertEqual(gc.inspect(cfg, name=st.name, runtime=runtime)['worktrees'][0]['class'], 'D')
        for records in ([st, replace(st, name='shared')], [replace(st, role='main')]):
            with patch.object(state, 'load_all', return_value=records):
                self.assertEqual(gc.inspect(self.cfg, name=st.name, runtime=lambda *_: True)['worktrees'][0]['class'], 'D')
        with patch.object(gc.paseo, 'status', side_effect=gc.paseo.PaseoError('LOOKUP_FAILED')):
            with patch.object(state, 'load_all', return_value=[replace(st, transport='paseo', paseo_agent_id='fake', paseo_workspace_id='fake', paseo_target='fake')]):
                self.assertEqual(gc.inspect(self.cfg, name=st.name)['worktrees'][0]['class'], 'D')


gc_inspect = gc.inspect
