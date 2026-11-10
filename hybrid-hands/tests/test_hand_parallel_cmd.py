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
        env = patch.dict(os.environ, {'HYBRID_HANDS_CONFIG': str(self.root / 'global.json')})
        env.start(); self.addCleanup(env.stop)
    def run_cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(['parallel', '--cwd', str(self.root), *args])
        return code, out.getvalue(), err.getvalue()
    def test_on_preserves_order_and_fallback_status(self):
        self.config.parent.mkdir(); self.config.write_text('{"before":{},"parallel_subagents":{"sibling":"Việt","enabled":false},"after":{}}')
        self.assertEqual(self.run_cli('on')[0], 0)
        self.assertEqual(self.config.read_text(), json.dumps({'before':{}, 'parallel_subagents':{'sibling':'Việt','enabled':True}, 'after':{}}, ensure_ascii=False, indent=2)+'\n')
        linked = self.root / 'linked'; linked.mkdir()
        with patch('hand_ext.config.git_toplevel', return_value=linked), patch('hand_ext.config.main_repo_root', return_value=self.root):
            self.assertIn(str(self.config), self.run_cli('on')[1])
            self.assertEqual(json.loads(self.run_cli('--json')[1]), {'parallel_subagents':True,'source':'repo','file':str(self.config)})
        self.config.unlink(); (self.root / 'global.json').write_text('{"parallel_subagents":{"enabled":true}}')
        code, out, err = self.run_cli('--json')
        self.assertEqual((code, json.loads(out)['parallel_subagents'], json.loads(out)['source']), (0, False, 'global'))
        self.assertIn('bỏ qua global', err)
    def test_off_creates_and_is_idempotent(self):
        self.assertIn('nguồn: default', self.run_cli()[1])
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
