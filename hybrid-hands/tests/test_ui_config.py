"""ui.<component>.enabled toggles: precedence and invalid values."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from shared_config import load_config  # noqa: E402


class UiConfigTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        env = patch.dict(os.environ, HOME=str(self.root), HYBRID_HANDS_CONFIG='global.json')
        env.start()
        self.addCleanup(env.stop)

    def _load(self, global_cfg, repo_cfg=None):
        (self.root / 'global.json').write_text(json.dumps(global_cfg))
        if repo_cfg is not None:
            repo = self.root / '.claude/hybrid-hands.json'
            repo.parent.mkdir(exist_ok=True)
            repo.write_text(json.dumps(repo_cfg))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            result = load_config(self.root)
        return result, err.getvalue()

    def test_global_false_and_repo_override(self):
        off = {'ui': {'hh_tree': {'enabled': False}}}
        result, _ = self._load(off)
        self.assertIs(result.effective['ui']['hh_tree']['enabled'], False)
        self.assertEqual(result.sources['ui.hh_tree.enabled'], 'global')
        self.assertEqual(result.sources['ui.hh_panel.enabled'], 'plugin')
        result, _ = self._load(off, {'ui': {'hh_tree': {'enabled': True}}})
        self.assertIs(result.effective['ui']['hh_tree']['enabled'], True)
        self.assertEqual(result.sources['ui.hh_tree.enabled'], 'repo')

    def test_non_bool_warns_and_keeps_default(self):
        result, err = self._load({'ui': {'hh_tree': {'enabled': 'no-SECRET'}}})
        self.assertIs(result.effective['ui']['hh_tree']['enabled'], True)
        self.assertEqual(result.sources['ui.hh_tree.enabled'], 'plugin')
        self.assertIn('ui.hh_tree.enabled', err)
        self.assertNotIn('SECRET', err)


if __name__ == '__main__':
    unittest.main()
