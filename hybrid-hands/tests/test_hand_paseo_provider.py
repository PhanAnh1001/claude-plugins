"""Three offline groups; config writes only below TemporaryDirectory."""
import json
from pathlib import Path
import sys
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext.paseo_provider import (PROVIDER_IDS, ProviderError, _package_root,
                                     setup_provider, status_provider, _validate)


FIXTURE = Path(__file__).parent / 'fixtures/hand_paseo/provider/package'


class ProviderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.package = Path(temporary.name) / 'package'
        self.package.mkdir()
        shutil.copyfile(FIXTURE / 'package.json', self.package / 'package.json')
        schema = self.package / 'node_modules/@getpaseo/server/dist/server/server/persisted-config.js'
        schema.parent.mkdir(parents=True)
        shutil.copyfile(FIXTURE.parent / 'schema-marker.js', schema)
        validator = patch('hand_ext.paseo_provider._validate')
        self.validator = validator.start()
        self.addCleanup(validator.stop)

    def setup_provider(self, home, **kwargs):
        kwargs.setdefault('package_root', self.package)
        return setup_provider(home, **kwargs)

    def test_dryrun_does_not_write_or_disclose_config(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp) / 'absent'
            result = self.setup_provider(home)
            self.assertFalse(home.exists())
            self.assertFalse(result['applied'])
            self.assertEqual(len(result['changes']), 4)
            home.mkdir()
            config = {'version': 1, 'agents': {'resumePrompt': 'fixture-private-text',
                      'providers': {'hh-hand-codex': {'env': {'FIXTURE': 'fixture-env-value'},
                      'options': {'fake': 'fixture-option-value'}, 'label': 'fixture-label'}}}}
            path = home / 'config.json'
            path.write_text(json.dumps(config))
            before = path.read_bytes()
            result = self.setup_provider(home)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(home.iterdir()), [path])
            self.assertNotIn('fixture-private-text', json.dumps(result))
            self.assertNotIn('fixture-env-value', json.dumps(result))
            self.assertNotIn('fixture-option-value', json.dumps(result))
            self.assertNotIn('fixture-label', json.dumps(result))
            for update in result['proposed_updates'].values():
                self.assertEqual(set(update), {'command', 'extends', 'enabled'})
                self.assertEqual(update['extends'], 'acp')
                self.assertTrue(update['enabled'])
                self.assertEqual(Path(update['command'][0]).name, 'hand-paseo-acp')

    def test_apply_preserves_keys_and_backs_up_before_atomic_write(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            original = {'version': 1, 'daemon': {'listen': '127.0.0.1:0'},
                        'agents': {'resumeOnStartup': False, 'providers': {
                            'fixture-other': {'label': 'Other fixture', 'extends': 'acp', 'command': ['fixture']},
                            'hh-hand-codex': {'label': 'Preserved label', 'extends': 'acp',
                                              'command': ['old-fixture'], 'enabled': False,
                                              'env': {'FIXTURE': 'fake-env'}, 'options': {'fake': 'fake-option'}}}}}
            path = home / 'config.json'
            path.write_text(json.dumps(original))
            before = path.read_bytes()
            result = self.setup_provider(home, apply=True)
            self.assertTrue(result['applied'])
            self.assertTrue(result['reload_required'])
            self.assertEqual(Path(result['backup_path']).read_bytes(), before)
            self.assertEqual(Path(result['backup_path']).stat().st_mode & 0o777, 0o600)
            updated = json.loads(path.read_text())
            self.assertEqual(updated['daemon'], original['daemon'])
            self.assertFalse(updated['agents']['resumeOnStartup'])
            providers = updated['agents']['providers']
            self.assertEqual(providers['fixture-other'], original['agents']['providers']['fixture-other'])
            self.assertEqual(providers['hh-hand-codex']['label'], 'Preserved label')
            self.assertEqual(providers['hh-hand-codex']['env'], {'FIXTURE': 'fake-env'})
            self.assertEqual(providers['hh-hand-codex']['options'], {'fake': 'fake-option'})
            for name in PROVIDER_IDS:
                self.assertEqual(providers[name]['extends'], 'acp')
                self.assertTrue(providers[name]['enabled'])
                self.assertTrue(Path(providers[name]['command'][0]).is_file())
                self.assertEqual(Path(providers[name]['command'][0]).name, 'hand-paseo-acp')
            files = sorted(home.iterdir())
            again = self.setup_provider(home, apply=True)
            self.assertFalse(again['changed'])
            self.assertFalse(again['applied'])
            self.assertEqual(sorted(home.iterdir()), files)

    def test_catalog_status_and_source_schema_validation(self):
        for available, expected in [(list(PROVIDER_IDS), 'READY'),
                                    ([PROVIDER_IDS[0]], 'PROVIDERS_MISSING')]:
            transport = SimpleNamespace(probe_capabilities=lambda: {'ok': True, 'providers': available})
            result = status_provider(transport)
            self.assertEqual(result['code'], expected)
            self.assertEqual(result['missing'], [x for x in PROVIDER_IDS if x not in available])
        transport = SimpleNamespace(probe_capabilities=lambda: {'ok': False, 'error': 'fixture-private-text'})
        self.assertEqual(status_provider(transport)['code'], 'CATALOG_UNAVAILABLE')
        self.assertNotIn('fixture-private-text', json.dumps(status_provider(transport)))
        root = _package_root(self.package)
        self.assertEqual(json.loads((root / 'package.json').read_text())['version'], '0.15.0')
        sample = {'agents': {'providers': {'hh-hand-codex': {
            'label': 'Fixture', 'extends': 'acp', 'command': ['/fake/acp'], 'enabled': True}}}}
        with patch('hand_ext.paseo_provider.subprocess.run',
                   return_value=SimpleNamespace(returncode=0)) as run:
            _validate(root, sample)
            args, kwargs = run.call_args
            self.assertEqual(args[0][-1], str(root / 'node_modules/@getpaseo/server/dist/server/server/persisted-config.js'))
            self.assertIn('PersistedConfigSchema.safeParse', args[0][-2])
            self.assertEqual(json.loads(kwargs['input']), sample)
            self.assertTrue(kwargs['capture_output'])
            self.assertEqual(kwargs['timeout'], 10)
            run.return_value = SimpleNamespace(returncode=1)
            with self.assertRaisesRegex(ProviderError, '^CONFIG_INVALID$'):
                _validate(root, sample)
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            path = home / 'config.json'
            for invalid in ['[]', '{bad', '{"version":1,"version":2}', '{"version":2}', '{"agents":{"providers":[]}}',
                            '{"agents":{"resumeOnStartup":"bad"}}', '{"unknownKey":true}']:
                path.write_text(invalid)
                with self.assertRaisesRegex(ProviderError, '^CONFIG_INVALID$'):
                    with patch('hand_ext.paseo_provider._validate', side_effect=ProviderError('CONFIG_INVALID')):
                        self.setup_provider(home, apply=True, package_root=root)
                self.assertEqual(path.read_text(), invalid)
                self.assertEqual(list(home.iterdir()), [path])
            package = home / 'wrong-package'
            package.mkdir()
            (package / 'package.json').write_text('{"name":"@getpaseo/cli","version":"0.14.0","type":"module"}')
            with self.assertRaisesRegex(ProviderError, '^PACKAGE_UNSUPPORTED$'):
                self.setup_provider(home, package_root=package)


if __name__ == '__main__':
    unittest.main()
