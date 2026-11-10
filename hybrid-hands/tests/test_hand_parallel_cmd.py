"""Parallel opt-in CLI using temporary public configuration only."""
import contextlib, io, json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"))
from hand_ext.cli import main

class ParallelCommandTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve(); self.config = self.root / '.claude/hybrid-hands.json'
        # Offline label: never read a real ~/.claude*/.claude.json or ~/.codex-hand in tests.
        env = patch.dict(os.environ, {'HYBRID_HANDS_CONFIG': str(self.root / 'global.json'),
                                      'HYBRID_HANDS_ACCOUNT_LABEL_OFFLINE': '1'})
        env.start(); self.addCleanup(env.stop)
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(['parallel-subagents', '--cwd', str(self.root), *args])
        return code, out.getvalue(), err.getvalue()
    def test_on_preserves_order_and_fallback_status(self):
        self.config.parent.mkdir(); self.config.write_text('{"before":{},"parallel_subagents":{"sibling":"Việt","enabled":false},"after":{}}')
        self.assertEqual(self.run_cli('on')[0], 0)
        self.assertEqual(self.config.read_text(), json.dumps({'before':{}, 'parallel_subagents':{'sibling':'Việt','enabled':True}, 'after':{}}, ensure_ascii=False, indent=2)+'\n')
        linked = self.root / 'linked'; linked.mkdir()
        with patch('hand_ext.config.git_toplevel', return_value=linked), patch('hand_ext.config.main_repo_root', return_value=self.root):
            self.assertIn(str(self.config), self.run_cli('on')[1])
            status = json.loads(self.run_cli('--json')[1])
            self.assertEqual(status.pop('brain_account_label'), 'claude v1 ? ?')
            self.assertEqual(status.pop('backend_account_label'), 'claude v1 ? ?')
            self.assertEqual(status, {'parallel_subagents':True,'source':'repo','file':str(self.config), 'backend':'claude-v1','model':'claude-opus-5-5','effort':'low','backend_source':'plugin','brain_account':'v1','brain_account_source':'plugin','account_mismatch':False})
        self.config.unlink(); (self.root / 'global.json').write_text('{"parallel_subagents":{"enabled":true}}')
        code, out, err = self.run_cli('--json')
        self.assertEqual((code, json.loads(out)['parallel_subagents'], json.loads(out)['source']), (0, False, 'global'))
        self.assertIn('bỏ qua global', err)
    def test_accounts_lists_claude_then_gpt(self):
        rows = json.loads(self.run_cli('accounts', '--json')[1])
        self.assertEqual([(r['index'], r['backend'], r['label'], r['selected']) for r in rows],
                         [(1, 'claude-v1', 'claude v1 ? ?', True), (2, 'claude-v2', 'claude v2 ? ?', False),
                          (3, 'codex', 'gpt v1 ? ?', False)])
    def test_on_tty_pick_and_bad_choice(self):
        with patch('hand_ext.parallel_cmd._is_tty', return_value=True):
            with patch('builtins.input', return_value='9'):
                self.assertEqual(self.run_cli('on')[0], 2); self.assertFalse(self.config.exists())
            with patch('builtins.input', return_value='2'):
                self.assertEqual(self.run_cli('on')[0], 0)
        data = json.loads(self.config.read_text())
        self.assertEqual((data['parallel_subagents']['backend'], data['main_session']['claude_account']), ('claude-v2', 'v2'))
    def test_off_creates_and_is_idempotent(self):
        self.assertIn('nguồn: default', self.run_cli()[1])
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['parallel', '--cwd', str(self.root), '--json']), 0)
        self.assertIn('mở phiên mới để hook nạp luật', self.run_cli('off')[1])
        before = self.config.read_bytes(); self.assertEqual(self.run_cli('off')[0], 0)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertIs(json.loads(before)['parallel_subagents']['enabled'], False)
    def test_invalid_config_unchanged(self):
        self.config.parent.mkdir()
        for raw in (b'{broken', b'[]', b'{"parallel_subagents":null}'):
            self.config.write_bytes(raw); code, _, err = self.run_cli('on')
            self.assertNotEqual(code, 0); self.assertIn(str(self.config), err)
            self.assertEqual(self.config.read_bytes(), raw)

    def test_backend_selection_and_invalid_no_write(self):
        code, out, _ = self.run_cli('on', '--backend', 'claude-v2', '--json')
        self.assertEqual((code, json.loads(out)['backend'], json.loads(out)['backend_source']), (0, 'claude-v2', 'repo'))
        self.assertEqual(json.loads(self.config.read_text())['parallel_subagents']['backend'], 'claude-v2')
        before = self.config.read_bytes()
        self.assertEqual(self.run_cli('--backend', 'unknown')[0], 2)
        self.assertEqual(self.config.read_bytes(), before)

    def test_account_sets_brain_and_backend_atomically(self):
        code, out, _ = self.run_cli('on', '--account', 'v2', '--json')
        status = json.loads(out)
        self.assertEqual((code, status['backend'], status['brain_account'], status['account_mismatch']), (0, 'claude-v2', 'v2', False))
        self.assertEqual(json.loads(self.config.read_text())['main_session'], {'claude_account': 'v2'})
        before = self.config.read_bytes()
        for args in (('--account', 'v9'), ('--account', 'v2', '--backend', 'claude-v1')):
            self.assertEqual(self.run_cli('on', *args)[0], 2)
            self.assertEqual(self.config.read_bytes(), before)
