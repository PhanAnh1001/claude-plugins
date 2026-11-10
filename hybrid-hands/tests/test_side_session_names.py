"""Focused naming contracts, using only synthetic state and a public fake client."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'plugins/hybrid-hands/lib'))
from side_session import names, paseo, state
from side_session.cli import build_parser


def session(**over):
    values = dict(name='task', uuid='u', provider='codex', dir='/fake', screen='',
                  watch_screen='', max_tokens=1, started=0, status='done', handoff='',
                  transport='paseo', paseo_agent_id='a', paseo_workspace_id='w', paseo_target='fake')
    return state.SessionState(**(values | over))


class NamesTests(unittest.TestCase):
    def test_format(self):
        for provider, account, suffix in [('codex', 'v1', 'Sol'), ('claude', 'v2', 'Opus v2'),
                                          ('claude', 'v12', 'Opus v12'), ('dsh', 'v1', 'dsh')]:
            with self.subTest(provider=provider, account=account):
                title = names.title(session(name='x' * 100, provider=provider, account=account))
                self.assertEqual(len(title), 60)
                self.assertTrue(title.endswith(f' · {suffix} phụ'))
        for label in ['/private/file', 'task\nbrief', 'api-key-secret']:
            self.assertEqual(names.title(session(name=label)), 'side · Sol phụ')

    def test_retry_bounded_reset_and_main(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()):
            cfg = SimpleNamespace(state_dir=Path(tmp))
            st = session()
            state.save(cfg.state_dir, st)
            with mock.patch.object(paseo, '_call', side_effect=paseo.PaseoError('FAILED')) as call:
                for _ in range(6):
                    names.retry(cfg, st)
                self.assertEqual(call.call_count, 3)
                names.retry(cfg, st, reset=True)
                self.assertEqual(call.call_count, 4)
            with mock.patch.object(paseo, '_call', return_value={'agentNamed': True, 'workspaceNamed': True}) as call:
                names.retry(cfg, st)
                names.retry(cfg, st)
                names.retry(cfg, session(role='main'))
                self.assertEqual(call.call_count, 1)

    def test_manual_dry_apply_guards_and_idempotence(self):
        self.assertFalse(build_parser().parse_args(['tidy', '--names']).apply)
        module = (ROOT / 'plugins/hybrid-hands/lib/side_session/paseo_names.mjs').as_uri()
        script = """
import {nameSession} from MODULE;
for (const mode of ['private','shared','unknown','main','state-main','error']) {
 let writes=[], title='old';
 const agent={id:'a',workspaceId:'w',get title(){return title},role:mode==='main'?'main':''};
 const owner={agentId:'a',workspaceId:'w',role:mode==='state-main'?'main':''};
 const client={fetchAgent:async()=>({agent}), fetchAgents:async()=>({entries:[{agent},
 ...(['shared','unknown'].includes(mode)?[{agent:{id:'b',workspaceId:'w'}}]:[])],pageInfo:{nextCursor:null}}),
 updateAgent:async(id,p)=>{writes.push('agent:'+id);if(mode==='error')throw Error('private detail');title=p.name;},
 setWorkspaceTitle:async(id,t)=>{writes.push('workspace:'+id);return {title:t}}};
 const req={agentId:'a',expectedWorkspaceId:'w',title:'task · Sol phụ',workspaceOwners:[owner]};
 if(mode==='shared')req.workspaceOwners.push({agentId:'b',workspaceId:'w',role:''});
 const dry=await nameSession(client,req);const before=writes.length;
 const applied=await nameSession(client,{...req,apply:true});
 const again=await nameSession(client,{...req,apply:true});
 console.log(JSON.stringify({mode,dry,before,applied,again,writes}));
}
""".replace('MODULE', json.dumps(module))
        proc = subprocess.run(['node', '--input-type=module', '-e', script], capture_output=True, text=True, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for row in map(json.loads, proc.stdout.splitlines()):
            with self.subTest(mode=row['mode']):
                self.assertEqual(row['before'], 0)
                if row['mode'] in ('main', 'state-main'):
                    self.assertEqual(row['writes'], [])
                elif row['mode'] in ('shared', 'unknown'):
                    self.assertEqual(row['writes'], ['agent:a'])
                elif row['mode'] == 'private':
                    self.assertTrue(row['applied']['workspaceNamed'])
                    self.assertEqual(row['writes'].count('agent:a'), 1)
                else:
                    self.assertEqual(row['applied']['warning'], 'NAME_RENAME_FAILED')


def setUpModule():  # keep hh-store revision bumps out of the real ~/.hybrid-hands
    import os as _os, tempfile as _tempfile
    from unittest import mock as _mock
    global _STATE_TMP, _STATE_ENV
    _STATE_TMP = _tempfile.TemporaryDirectory()
    _STATE_ENV = _mock.patch.dict(_os.environ, {"HYBRID_HANDS_STATE_DIR": _STATE_TMP.name})
    _STATE_ENV.start()


def tearDownModule():
    _STATE_ENV.stop()
    _STATE_TMP.cleanup()
