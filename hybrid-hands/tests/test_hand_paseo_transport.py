"""Offline official bridge contract: three focused groups, no daemon/model calls."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid
from dataclasses import replace
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext.execution_admission import AdmissionController, Reservation
from hand_ext.execution_state import ExecutionStore, Invocation, Attempt
from hand_ext.paseo_transport import PaseoTransport, TransportError

FIXTURE = Path(__file__).parent / 'fixtures/hand_paseo/transport'
BRIDGE = Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib/hand_ext/paseo_bridge.mjs'

@unittest.skipUnless(shutil.which('node'), 'Node >=22 required')
class PaseoTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cwd = self.root / 'isolated'; self.cwd.mkdir()
        self.target = {'kind':'instance','home':'/fake/paseo'}
        self.file = self.root / 'fake.json'
        self.state = {'target':self.target,'agents':{'parent':{'id':'parent','workspaceId':'parent-ws'}},
            'workspaces':{'parent-ws':{'id':'parent-ws','projectId':'verified-project','workspaceDirectory':'/fake/parent'}},
            'calls':[],'entries':[]}
        self.write(self.state)
        self.store = ExecutionStore(self.root / 'store')
        self.key = ('invocation','attempt',1)
        invocation = Invocation('invocation','scope','canonical',parent_paseo_agent_id='parent',
            isolated_cwd=str(self.cwd), backend='codex', model='gpt-test', effort='low')
        attempt = Attempt(*self.key, request_key=str(uuid.uuid4()))
        with patch('hand_ext.parallel.pool_root', return_value=self.root/'pool'):
            AdmissionController(self.store, None, lambda *_: True).admit(invocation, attempt, max_parallel=4)
        self.authority()
        self.transport = PaseoTransport(FIXTURE/'package',self.target,self.factory,store=self.store)

    def write(self, state): self.file.write_text(json.dumps(state))
    def read(self): return json.loads(self.file.read_text())
    def factory(self, package_root, target):
        def call(request):
            # The persisted intent/IDs must precede even the fake network operation.
            if request['command'] in ('workspace','create','send','cancel','archive','reopen'):
                receipt = self.store.get(self.key).receipt['transport']
                self.assertTrue(receipt.get('cancelPending') if request['command']=='cancel'
                    else receipt['pending']==request['command'])
                self.assertTrue(receipt['workspaceId']); self.assertTrue(receipt['agentId'])
                if request['command']=='send': self.assertTrue(receipt['messageId'])
            p = subprocess.run(['node',str(FIXTURE/'run.mjs'),str(BRIDGE),str(package_root),str(self.file)],
                input=json.dumps(request),capture_output=True,text=True,timeout=5)
            self.assertEqual(p.returncode,0,p.stderr)
            return json.loads(p.stdout)
        return call
    def authority(self):
        r=self.store.get(self.key)
        r.quiescence={'confirmed':True,'evidence':'owned group stopped/reaped'}
        r.artifacts['review']={'approved':True}
        self.store.compare_and_swap(self.key,r.revision,r)
    def placement(self):
        project=self.transport.verify_parent('parent')
        return self.transport.ensure_workspace(self.key,project,self.cwd)
    def child(self):
        placement=self.placement()
        self.assertTrue(placement.get('ok', placement.get('workspaceConfirmed')))
        return self.transport.create_child(self.key,placement,caller_agent_id='parent',provider_id='hh-hand-codex')

    def test_own_placement_caller_archive_reopen_same_ids(self):
        self.assertIn('hh-hand-codex',self.transport.probe_capabilities()['providers'])
        self.assertTrue(self.child()['ok'])
        before=self.store.get(self.key).attempt
        self.assertRegex(before.workspace_id, r'^wks_[a-f0-9]{16}$')
        r=self.store.get(self.key); r.quiescence=None
        self.store.compare_and_swap(self.key,r.revision,r)
        self.assertTrue(self.transport.send_prompt(self.key,'fresh brief')['ok'])
        self.authority()
        self.assertTrue(self.transport.cancel_child(self.key)['ok'])
        self.assertTrue(self.transport.archive_child(self.key)['ok'])
        self.assertTrue(self.transport.reopen_child(self.key)['ok'])
        self.assertEqual(before,self.store.get(self.key).attempt)
        calls=self.read()['calls']
        created=next(x['args'] for x in calls if x['name']=='createAgent')
        self.assertEqual(created['callerAgentId'],'parent')
        self.assertEqual(created['model'],'gpt-test')
        self.assertEqual(created['thinkingOptionId'],'low')
        self.assertEqual(created['env']['HYBRID_HANDS_EXECUTION_ROOT'],str(self.store.root))
        self.assertEqual(created['env']['HYBRID_HANDS_INVOCATION_ID'],'invocation')
        self.assertNotEqual(created['workspaceId'],'parent-ws')
        for name in ('initialPrompt','autoArchive','background'): self.assertNotIn(name,created)
        sent=next(x['args'] for x in calls if x['name']=='sendMessage')
        self.assertEqual(sent['options']['activeTurnBehavior'],'steer')
        self.assertEqual(sent['options']['messageId'],self.store.get(self.key).attempt.request_key)
        for x in calls:
            if x['name'] in ('archiveAgent','refreshAgent','cancelAgent'):
                self.assertEqual(x['args']['agentId'],before.agent_id)
        self.assertFalse(any(x['name']=='restoreWorkspace' for x in calls))
        # Controller reopens prior epoch while its durable quiescence is known,
        # then settles/releases it before admitting a new prompt epoch.
        old=self.store.get(self.key); old.outcome={'quiescent':True}
        self.store.compare_and_swap(self.key,old.revision,old)
        supervisor=SimpleNamespace(reconcile=lambda key: SimpleNamespace(confirmed=True))
        with patch('hand_ext.parallel.pool_root', return_value=self.root/'pool'):
            admission=AdmissionController(self.store,supervisor,lambda *_:True)
            admission.release(Reservation.from_dict(old.reservation), outcome=old.outcome, artifacts_settled=True)
            attempt=replace(old.attempt,attempt_id='followup',epoch=2,request_key=str(uuid.uuid4()))
            admission.admit(old.invocation,attempt,max_parallel=4)
        self.key=('invocation','followup',2)
        project=self.transport.verify_parent('parent')
        p=self.transport.ensure_workspace(self.key,project,self.cwd)
        self.assertTrue(p['workspaceConfirmed'])
        bound=self.transport.create_child(self.key,p,caller_agent_id='parent',provider_id='hh-hand-codex')
        self.assertTrue(bound['createConfirmed'])
        state=self.read(); state['lose']='sendMessage'; self.write(state)
        self.assertFalse(self.transport.send_prompt(self.key,'new epoch brief')['ok'])
        self.assertFalse(self.transport.send_prompt(self.key,'new epoch brief')['ok'])
        self.assertEqual(self.transport.reconcile(self.key)['state'],'delivered')
        self.assertTrue(self.transport.send_prompt(self.key,'new epoch brief')['ok'])
        before_wait=len(self.read()['calls'])
        self.assertEqual(self.transport.wait_child(self.key,0)['state'],'unresolved')
        self.assertEqual(len(self.read()['calls']),before_wait)
        settled=self.store.get(self.key); settled.outcome={'quiescent':True,'backend_exit_code':0}
        settled.quiescence={'confirmed':True,'evidence':'fake owned group stopped/reaped'}
        self.store.compare_and_swap(self.key,settled.revision,settled)
        self.assertEqual(self.transport.wait_child(self.key,0)['state'],'completed')
        self.assertEqual(len(self.read()['calls']),before_wait)
        after=self.store.get(self.key)
        self.assertEqual(after.attempt.agent_id,before.agent_id)
        self.assertEqual(after.attempt.workspace_id,before.workspace_id)
        calls=self.read()['calls']
        self.assertEqual(sum(x['name']=='createAgent' for x in calls),1)
        self.assertEqual(sum(x['name']=='createWorkspace' for x in calls),1)
        messages=[x['args']['options']['messageId'] for x in calls if x['name']=='sendMessage']
        self.assertEqual(len(messages),2); self.assertEqual(len(set(messages)),2)

    def test_lost_create_and_send_ack_reconcile_without_duplicates(self):
        state=self.read(); state['lose']='createWorkspace'; self.write(state)
        self.assertFalse(self.placement()['ok'])
        self.assertFalse(self.placement()['ok'])
        self.assertEqual(self.transport.reconcile(self.key)['state'],'workspace_verified')
        p=self.transport._read(self.key)
        state=self.read(); state['lose']='createAgent'; self.write(state)
        self.assertFalse(self.transport.create_child(self.key,p,caller_agent_id='parent',provider_id='hh-hand-codex')['ok'])
        self.assertFalse(self.transport.create_child(self.key,p,caller_agent_id='parent',provider_id='hh-hand-codex')['ok'])
        self.assertEqual(self.transport.reconcile(self.key)['state'],'child_verified')
        state=self.read(); state['lose']='sendMessage'; self.write(state)
        self.assertFalse(self.transport.send_prompt(self.key,'brief')['ok'])
        self.assertTrue(self.transport.cancel_child(self.key)['ok'])
        self.assertEqual(self.store.get(self.key).receipt['transport']['pending'],'send')
        self.assertFalse(self.transport.send_prompt(self.key,'brief')['ok'])
        self.assertEqual(self.transport.reconcile(self.key)['state'],'delivered')
        self.assertTrue(self.transport.send_prompt(self.key,'brief')['ok'])
        calls=self.read()['calls']
        for name in ('createWorkspace','createAgent','sendMessage'):
            self.assertEqual(sum(x['name']==name for x in calls),1)
        self.assertIsNone(self.store.get(self.key).receipt['transport']['pending'])

    def test_wrong_target_parent_missing_cwd_and_recovery_block_before_mutation(self):
        self.assertTrue(self.child()['ok'])
        baseline=len(self.read()['calls'])
        with self.assertRaisesRegex(TransportError,'PROVIDER_MISMATCH'):
            self.transport.create_child(self.key,self.transport._read(self.key),caller_agent_id='parent',provider_id='hh-hand-dsh')
        self.assertEqual(len(self.read()['calls']),baseline)
        self.assertTrue(self.transport.archive_child(self.key)['ok'])
        baseline=len(self.read()['calls'])
        state=self.read(); state['recovery']={'workspaceId':self.store.get(self.key).attempt.workspace_id,
            'kind':'recoverable','action':'restore'}; self.write(state)
        self.assertFalse(self.transport.reopen_child(self.key)['ok'])
        self.assertEqual(len(self.read()['calls']),baseline)
        r=self.store.get(self.key); r.receipt['transport']['pending']=None
        self.store.compare_and_swap(self.key,r.revision,r)
        state=self.read(); state['target']={'kind':'instance','home':'/wrong'}; self.write(state)
        self.assertFalse(self.transport.send_prompt(self.key,'brief')['ok'])
        self.assertEqual(len(self.read()['calls']),baseline)
        # Unknown intent needs reconcile, never release/reset to retry automatically.
        state=self.read(); state['target']=self.target; self.write(state)
        self.assertEqual(self.transport.reconcile(self.key)['state'],'unresolved')
        r=self.store.get(self.key); r.receipt['transport']['pending']=None
        self.store.compare_and_swap(self.key,r.revision,r)
        state=self.read(); aid=self.store.get(self.key).attempt.agent_id
        state['agents'][aid]['labels']['paseo.parent-agent-id']='wrong'; self.write(state)
        self.assertFalse(self.transport.cancel_child(self.key)['ok'])
        self.assertEqual(len(self.read()['calls']),baseline)
        r=self.store.get(self.key); r.receipt['transport']['pending']=None
        self.store.compare_and_swap(self.key,r.revision,r)
        self.cwd.rmdir()
        with self.assertRaisesRegex(TransportError,'CWD_MISSING'): self.transport.reopen_child(self.key)
        self.assertEqual(len(self.read()['calls']),baseline)
        # Package mismatch rejected before connecting.
        with self.assertRaisesRegex(TransportError,'PACKAGE_UNSUPPORTED'):
            PaseoTransport(self.root,self.target)

if __name__ == '__main__': unittest.main()
