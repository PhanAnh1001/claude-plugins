"""Three focused naming groups using public fake API only."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch
from test_hand_paseo_transport import PaseoTransportTests
from hand_ext.paseo_names import title_for, names_request, retry_names
from hand_ext.cli import _managed_summary


class ManagedNamesTests(PaseoTransportTests):
    # Reuse setup/helpers without inheriting the transport test cases below.
    def test_format_names(self):
        r = self.store.get(self.key)
        r.receipt = {'controller': {'label': 'x' * 100}}
        state = SimpleNamespace(uuid='canonical', codex_thread_id='', native_session_id='',
                                paseo_agent_id='parent', role='', name='phụ')
        with patch('hh_ps.registry_source.load_ps_config'), patch('side_session.state.load_all', return_value=[state]):
            for backend in ('codex', 'dsh', 'claude-v1', 'claude-v2'):
                with self.subTest(backend=backend):
                    r.invocation = replace(r.invocation, backend=backend)
                    self.assertEqual(len(title_for(r)), 60)
                    self.assertTrue(title_for(r).startswith('phụ › hand ' + backend))
            state.role = 'main'; self.assertTrue(title_for(r).startswith('chính ›'))
            state.role = ''; state.name = '/unsafe'; self.assertTrue(title_for(r).startswith('? ›'))
        with patch('hh_ps.registry_source.load_ps_config'), patch('side_session.state.load_all', return_value=[]):
            self.assertTrue(title_for(r).startswith('? ›'))

    def test_dispatch_retry_and_idempotence(self):
        self.assertTrue(self.child()['ok'])
        state = self.read(); state['agents'][self.store.get(self.key).attempt.agent_id]['title'] = 'old'
        state['fail'] = 'updateAgent'; self.write(state)
        retry_names(self.transport, self.key)
        self.assertIsNone(self.store.get(self.key).receipt['transport'].get('pending'))
        self.assertEqual(_managed_summary(self.store.get(self.key))['naming_warning'], 'NAME_UNRESOLVED')
        state = self.read(); state.pop('fail'); self.write(state)
        retry_names(self.transport, self.key)
        before = len(self.read()['calls']); retry_names(self.transport, self.key)
        self.assertEqual(len(self.read()['calls']), before)
        self.assertTrue(self.transport.send_prompt(self.key, 'synthetic')['ok'])
        for method in ('updateAgent', 'setWorkspaceTitle'):
            with self.subTest(unconfirmed=method):
                state = self.read(); row = self.store.get(self.key)
                state['agents'][row.attempt.agent_id]['title'] = 'old'
                state['workspaces'][row.attempt.workspace_id]['title'] = 'old'
                state['unconfirmed'] = method; self.write(state)
                result = names_request(self.transport, self.key, apply=True)
                self.assertTrue(not result.get('ok') or result.get('warning'))

    def test_manual_dry_run_and_membership(self):
        self.assertTrue(self.child()['ok']); before = len(self.read()['calls'])
        self.assertTrue(names_request(self.transport, self.key)['ok'])
        self.assertEqual(len(self.read()['calls']), before)
        state = self.read(); wid = self.store.get(self.key).attempt.workspace_id
        state['agents'][self.store.get(self.key).attempt.agent_id]['title'] = 'old'
        state['agents']['unknown'] = {'id':'unknown','workspaceId':wid}
        self.write(state)
        result = names_request(self.transport, self.key, apply=True)
        self.assertFalse(result['workspace']['eligible'])
        calls = self.read()['calls'][before:]
        self.assertTrue(any(c['name'] == 'updateAgent' for c in calls))
        self.assertFalse(any(c['name'] == 'setWorkspaceTitle' for c in calls))
        state = self.read(); state['agents'].pop('unknown')
        child = state['agents'][self.store.get(self.key).attempt.agent_id]
        state['agents']['sibling'] = dict(child, id='sibling'); self.write(state)
        original = self.transport._call
        def known(command, request):
            request['ownedChildren'].append(dict(request['ownedChildren'][0], agentId='sibling'))
            return original(command, request)
        with patch.object(self.transport, '_call', side_effect=known):
            self.assertFalse(names_request(self.transport, self.key, apply=True)['workspace']['eligible'])

# Inherited helper methods remain available, inherited tests are not collected.
for _name in list(vars(PaseoTransportTests)):
    if _name.startswith('test_'):
        setattr(ManagedNamesTests, _name, None)
del PaseoTransportTests
