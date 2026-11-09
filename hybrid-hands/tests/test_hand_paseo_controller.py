"""Three offline controller groups; synthetic public transport and process evidence."""
import argparse
from dataclasses import replace
from pathlib import Path
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'plugins/hybrid-hands/lib'))
from hand_ext import config, parallel, run_cmd, cli, isolation
from hand_ext.execution_state import Invocation, Attempt, ExecutionStore, StateConflict, _plain
from hand_ext.execution_supervisor import ExecutionSupervisor, ProcessIdentity, Quiescence
from hand_ext.execution_admission import AdmissionController, AdmissionFull, AdmissionDenied
from hand_ext.paseo_controller import (PaseoController, FreshPolicy, PaseoUnavailable,
    ExecutionUnresolved, cmd_managed_run, terminal_evidence, build_gateway)
from hand_ext.paseo_completion import CompletionService
from hand_ext.paseo_gateway import Gateway, ProtocolError
from hand_ext.paseo_transport import PaseoTransport


class Ops:
    def reconcile(self, identity):
        return Quiescence(True, 'fixture group reaped', time.time())


class FinishingWorker:
    def __init__(self, store, supervisor, completion):
        self.store, self.supervisor, self.completion = store, supervisor, completion
        self.hooks = {}; self.calls = 0; self.status="ok"; self.capacity=False
        completion.attach(self)
    def start(self, invocation, attempt, brief):
        self.calls += 1
        file = Path(invocation.isolated_cwd) / 'file.txt'
        file.write_text(file.read_text() + 'epoch' + str(self.calls) + '\n')
        self.supervisor.register_writer(attempt.key, ProcessIdentity(111,111,'fixture'), 'fixture')
        r = self.store.get(attempt.key)
        r.receipt = dict(r.receipt or {}, usage_observation={'capacity_failure':self.capacity}, worker_run_dir=str(Path(invocation.fixed_options['run_dir']) / attempt.attempt_id))
        self.store.compare_and_swap(r.key,r.revision,r)
        self.supervisor.record_outcome_once(attempt.key,dict(status=self.status,backend_exit_code=0,
            provenance='fixture',usage=None,final_text='synthetic result'))
        self.reconcile(attempt.key)
    def reconcile(self,key):
        from types import SimpleNamespace
        for kind, hook in self.hooks.items():
            r = self.store.get(key)
            if r.settle_keys.get(kind,{}).get('state') == 'completed': continue
            token = kind + '-fixture-' + key.attempt_id
            r.settle_keys[kind] = dict(key=token,state='in_progress')
            r = self.store.compare_and_swap(key,r.revision,r)
            refs = hook(key,token,r,SimpleNamespace(quiescent=True))
            r = self.store.get(key); r.artifacts[kind] = refs
            r.settle_keys[kind] = dict(key=token,state='completed')
            self.store.compare_and_swap(key,r.revision,r)
        self.settlement_callback(key)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name).resolve()
        self.repo=self.root/'repo'; self.repo.mkdir()
        for args in (['init','-q'],['config','user.name','Fixture'],['config','user.email','fixture@example.invalid']):
            subprocess.run(['git','-C',str(self.repo),*args],check=True,capture_output=True)
        (self.repo/'file.txt').write_text('baseline\n')
        subprocess.run(['git','-C',str(self.repo),'add','file.txt'],check=True)
        subprocess.run(['git','-C',str(self.repo),'commit','-qm','fixture'],check=True)
        self.cfg=config.load_config(self.repo)
        self.cfg=replace(self.cfg,order=['codex'], machine_state_dir=self.root/'machine',
            runs_dir=self.root/'runs',worktree_root=self.root/'worktrees',
            ledger=self.root/'ledger.json',quota_state=self.root/'quota.json',
            go_usage_ledger=self.root/'go.jsonl',go_usage_summary=self.root/'go-summary.json',
            max_parallel=1,paseo={'state_root':str(self.root/'state')})
        self.store=ExecutionStore(self.root/'state')
        for target, value in ((parallel,'pool_root'),):
            p=patch.object(target,value,return_value=self.root/'pool');p.start();self.addCleanup(p.stop)
        p=patch('hand_ext.paseo_controller.load_config',return_value=self.cfg);p.start();self.addCleanup(p.stop)
        self.backend=argparse.Namespace(name='codex')
        p=patch.object(run_cmd,'auto_preflight',side_effect=lambda cfg,**kw:iter([(self.backend,'codex','')]))
        self.preflight=p.start();self.addCleanup(p.stop)

    def intent(self):
        ctx=isolation.prepare(self.cfg,self.repo,str(uuid.uuid4()),self.root/'prep',isolation.IsolationChoice('worktree'))
        opts=run_cmd.with_sandbox(self.cfg,'codex')
        inv=Invocation(str(uuid.uuid4()),parallel.scope_digest(self.repo),'canonical-parent','parent-agent',
            'codex','gpt',opts['model'],opts['effort'],'managed',str(self.repo),str(ctx.run_cwd),
            dict(run_dir=str(self.root/'worker'),sandbox=self.cfg.sandbox,timeout_s=1,max_tokens=100,options=opts),('repo:*',))
        attempt=Attempt(inv.invocation_id,str(uuid.uuid4()),1,str(uuid.uuid4()))
        r=self.store.create_intent(inv,attempt)
        r.receipt={'controller':dict(version=1,policy_root=str(self.repo),backend='codex')}
        self.store.compare_and_swap(r.key,r.revision,r)
        supervisor=ExecutionSupervisor(self.store,Ops())
        admission=AdmissionController(self.store,supervisor,FreshPolicy(self.store))
        completion=CompletionService(self.store,supervisor,admission)
        completion.bind(attempt.key,ctx,ledger_path=self.cfg.ledger,registry_dir=self.root/'registry')
        return inv,attempt,supervisor,admission,completion

    def managed_cli(self, statuses, *, order=('codex',), capacity_first=False, extra=(), fail_create=False):
        from hand_ext.paseo_controller import records_for
        from hand_ext.backends import get_backend
        package=(Path(__file__).parent/'fixtures/hand_paseo/transport/package').resolve()
        unique=str(uuid.uuid4())
        cfg=replace(self.cfg,order=list(order),runs_dir=self.root/unique/'runs',
                    paseo={'state_root':str(self.root/unique/'state')})
        cfg.backends={name:dict(opts) for name,opts in cfg.backends.items()}
        cfg.backends['dsh'].update(capacity_wait_min_lines=1,capacity_wait_seconds=0)
        calls=[]; launched=[]
        def factory(cfg,store):
            def client(request):
                command=request['command'];calls.append(command)
                result=dict(ok=True,targetKey=transport.target_key)
                if command=='create' and fail_create:
                    return {'ok':False,'code':'TRANSPORT_UNRESOLVED'}
                if command=='probe':result['providers']=['hh-hand-codex','hh-hand-dsh']
                if command=='parent':result.update(parentAgentId='parent-agent',projectId='project')
                if command=='send':
                    record=records_for(store,request['gatewayEnv']['HYBRID_HANDS_INVOCATION_ID'])[-1]
                    supervisor=ExecutionSupervisor(store,Ops())
                    admission=AdmissionController(store,supervisor,FreshPolicy(store))
                    completion=CompletionService(store,supervisor,admission)
                    worker=FinishingWorker(store,supervisor,completion)
                    worker.status=statuses[len(launched)]
                    worker.capacity=capacity_first and not launched
                    launched.append(record.invocation.backend)
                    gateway=Gateway(store,admission,worker,invocation_id=record.invocation.invocation_id,
                                    completion=completion,wait_seconds=1)
                    try:
                        gateway.handle('session/prompt',dict(sessionId=record.invocation.invocation_id,
                            messageId=request['messageId'],prompt=[dict(type='text',text=request['brief'])]))
                    except ProtocolError as error:
                        if error.code!=-32011:raise
                return result
            transport=PaseoTransport(package,{'kind':'instance','home':str(self.root/'daemon')},
                client_factory=lambda *args:client,store=store)
            return transport
        brief=self.root/'cli-brief.md';brief.write_text('Self-contained synthetic CLI brief')
        args=cli._parser().parse_args(['run','--brief',str(brief),'--cwd',str(self.repo),
                                      '--no-apply',*extra])
        out=io.StringIO();err=io.StringIO()
        with patch('hand_ext.paseo_controller.transport_from_config',side_effect=factory), \
             patch('hand_ext.paseo_controller.load_config',return_value=cfg), \
             patch.object(run_cmd,'auto_preflight',side_effect=lambda c,**kw:iter([(get_backend(c.order[0]),c.order[0],'')])), \
             patch.dict(os.environ,{'PASEO_AGENT_ID':'parent-agent'}), \
             patch('sys.stdout',out),patch('sys.stderr',err):
            code=cmd_managed_run(cfg,args,mode='paseo-required')
        return code,calls,launched,out.getvalue(),err.getvalue()

    def test_modes_default_and_only_predispatch_same_backend_fallback(self):
        with patch.object(run_cmd,'_cmd_shell_run',return_value=12) as shell:
            self.assertEqual(run_cmd.cmd_run(self.cfg,argparse.Namespace()),12)
            shell.assert_called_once()
        args=cli._parser().parse_args(['run','--brief','unused','--mode','auto'])
        with patch('hand_ext.paseo_controller.transport_from_config',side_effect=PaseoUnavailable('missing')), \
             patch.object(run_cmd,'_cmd_shell_run',return_value=0) as shell:
            self.assertEqual(cmd_managed_run(self.cfg,args,mode='auto'),0)
            self.assertEqual(shell.call_args.args[1].backend,'auto')
            self.assertEqual(shell.call_args.args[0].order,['codex'])
            self.assertEqual(cmd_managed_run(self.cfg,args,mode='paseo-required'),1)
            self.assertEqual(shell.call_count,1)
            anchored=replace(self.cfg,order=['dsh','codex','claude-v1'])
            self.assertEqual(cmd_managed_run(anchored,args,mode='auto'),0)
            self.assertEqual(shell.call_args.args[0].order,['codex','claude-v1'])
            explicit=argparse.Namespace(**dict(vars(args),backend='codex'))
            self.assertEqual(cmd_managed_run(anchored,explicit,mode='auto'),0)
            self.assertEqual(shell.call_args.args[1].backend,'codex')
        from unittest.mock import Mock
        unavailable=Mock();unavailable.probe_capabilities.return_value={'ok':False,'code':'BRIDGE_UNAVAILABLE'}
        with self.assertRaises(PaseoUnavailable):
            PaseoController(self.cfg,self.store,unavailable).preflight('codex','parent')
        from shared_config import load_config as load_shared
        invalid = load_shared(self.repo)
        invalid.effective['ext_hand']['mode'] = 'wrong'
        with patch('shared_config.load_config',return_value=invalid):
            with self.assertRaises(ValueError):config.load_config(self.repo)
        parsed=cli._parser().parse_args(['provider','setup','--home',str(self.root/'paseo')])
        with patch('hand_ext.paseo_provider.setup_provider',return_value={'ok':True}) as setup:
            with patch('sys.stdout',new=io.StringIO()): self.assertEqual(cli.cmd_provider(self.cfg,parsed),0)
            self.assertFalse(setup.call_args.kwargs['apply'])

    def test_managed_success_real_completion_fresh_guards_and_pool(self):
        code,calls,launched,out,err=self.managed_cli(['ok'])
        self.assertEqual(code,0,err);self.assertEqual(launched,['codex'])
        self.assertIn('report: ',out);self.assertIn('epoch: 1',out)
        code,calls,launched,out,err=self.managed_cli(['quota_exhausted','ok'],order=('codex','dsh'))
        self.assertEqual(code,0,err);self.assertEqual(launched,['codex','dsh'])
        code,calls,launched,out,err=self.managed_cli(['failed','quota_exhausted'],order=('dsh','codex'),capacity_first=True)
        self.assertEqual(code,7,err);self.assertEqual(launched,['dsh','dsh'])
        code,calls,launched,out,err=self.managed_cli([],extra=('--max-tokens','-1'))
        self.assertEqual(code,2,err);self.assertEqual(launched,[])
        self.assertFalse(any(c in calls for c in ('workspace','create','send')))
        with patch.object(isolation,'resolve_choice',side_effect=isolation.IsolationError('fixture')):
            code,calls,launched,out,err=self.managed_cli([])
        self.assertEqual(code,2,err)
        self.assertFalse(any(c in calls for c in ('workspace','create','send')))
        inv,a,sup,admission,completion=self.intent()
        worker=FinishingWorker(self.store,sup,completion)
        gateway=Gateway(self.store,admission,worker,invocation_id=inv.invocation_id,wait_seconds=1,completion=completion)
        package=Path(__file__).parent/'fixtures/hand_paseo/transport/package'
        calls=[]
        def client(request):
            command=request['command'];calls.append(command)
            result={'ok':True,'targetKey':transport.target_key}
            if command=='probe':result['providers']=['hh-hand-codex']
            if command=='parent':result.update(parentAgentId='parent-agent',projectId='project')
            if command=='send':
                gateway.handle('session/prompt',dict(sessionId=inv.invocation_id,
                    messageId=request['messageId'],prompt=[dict(type='text',text=request['brief'])]))
            return result
        transport=PaseoTransport(package.resolve(),{'kind':'instance','home':str(self.root/'daemon')},
            client_factory=lambda *args:client,store=self.store)
        # Independent frontend has no daemon process authority.
        front=PaseoController(self.cfg,self.store,transport,completion=CompletionService(self.store,ExecutionSupervisor(self.store),admission))
        parent=front.preflight('codex','parent-agent')
        record=front.dispatch(inv,a,'fresh synthetic brief',parent)
        self.assertTrue(terminal_evidence(record));self.assertEqual(worker.calls,1)
        self.assertIn('create',calls); self.assertIn('send',calls)
        self.assertGreaterEqual(self.preflight.call_count,2)
        front.approve_review(a.key)
        front.archive(a.key)
        self.assertEqual(self.store.get(a.key).state,'archived')
        next_record=front.followup(a.key,'second self-contained brief')
        self.assertEqual(next_record.attempt.epoch,2)
        self.assertEqual(next_record.attempt.agent_id,record.attempt.agent_id)
        self.assertEqual(next_record.attempt.workspace_id,record.attempt.workspace_id)
        self.assertNotEqual(next_record.attempt.request_key,a.request_key)
        self.assertEqual(worker.calls,2)
        self.assertEqual(calls.count('create'),1)
        patch_text=Path(next_record.artifacts['finalize']['result']['patch_path']).read_text()
        self.assertIn('+epoch2',patch_text)
        self.assertNotIn('+epoch1',patch_text)
        archive_calls=calls.count('archive')
        with self.assertRaises(StateConflict):front.archive(a.key)
        self.assertEqual(calls.count('archive'),archive_calls)
        # Policy is rerun even for cached result; no additional slot is reserved.
        self.preflight.side_effect=lambda *args,**kw:iter([(None,'codex','quota')])
        with self.assertRaises(ProtocolError) as error:
            gateway.handle('session/prompt',dict(sessionId=inv.invocation_id,messageId=a.request_key,prompt=[dict(type='text',text='fresh synthetic brief')]))
        self.assertEqual(error.exception.data['exit_code'],7)
        self.preflight.side_effect=lambda *args,**kw:iter([(self.backend,'codex','')])
        # Capacity is a distinct exit 8 before create/send.
        other=replace(inv,fixed_options=_plain(inv.fixed_options),invocation_id=str(uuid.uuid4()),resource_claims=('dependency:other',))
        oa=Attempt(other.invocation_id,str(uuid.uuid4()),1,str(uuid.uuid4()))
        self.store.create_intent(other,oa)
        always=AdmissionController(self.store,sup,lambda i,a:True)
        always.admit(other,oa,max_parallel=1)
        new=replace(inv,fixed_options=_plain(inv.fixed_options),invocation_id=str(uuid.uuid4()),resource_claims=('dependency:new',))
        na=Attempt(new.invocation_id,str(uuid.uuid4()),1,str(uuid.uuid4()))
        with self.assertRaises(AdmissionFull):always.admit(new,na,max_parallel=1)

    def test_schema_failure_and_offline_recovery(self):
        from hand_ext.paseo_recovery import recover
        inv,a,sup,admission,completion=self.intent()
        admission.admit(inv,a,max_parallel=1)
        r=self.store.get(a.key)
        r.attempt=replace(r.attempt,workspace_id='invalid-bound-id')
        r.receipt['transport']={'pending':'workspace'}
        self.store.compare_and_swap(a.key,r.revision,r)
        proof=dict(ok=False,code='REQUEST_SCHEMA_REJECTED',notSent=True,
                   schema='WorkspaceCreateRequestSchema',issues=[dict(path=['workspaceId'],code='invalid_format')])
        before=self.store.get(a.key).to_dict()
        validator=lambda _:proof
        args=cli._parser().parse_args(['managed','recover','--cwd',str(self.repo),'--key',
                                      f'{a.invocation_id}:{a.attempt_id}:1'])
        with patch('hand_ext.paseo_recovery.recover',side_effect=lambda store,key,source,package,**kw:
                   recover(store,key,source,package,validator=validator,**kw)), patch('sys.stdout',io.StringIO()):
            self.assertEqual(cli.cmd_managed(self.cfg,args),0)
        self.assertEqual(before,self.store.get(a.key).to_dict())
        with self.assertRaises(StateConflict):
            recover(self.store,a.key,self.root,None,apply=True,validator=validator)
        with self.assertRaises(StateConflict):
            recover(self.store,a.key,self.repo,None,apply=True,validator=lambda _:dict(ok=True))
        r=self.store.get(a.key);r.receipt['transport']['cancelPending']=False
        r=self.store.compare_and_swap(a.key,r.revision,r)
        with self.assertRaises(StateConflict):recover(self.store,a.key,self.repo,None,apply=True,validator=validator)
        r.receipt['transport'].pop('cancelPending');self.store.compare_and_swap(a.key,r.revision,r)
        r=self.store.get(a.key);r.receipt['transport']['workspaceId']='other-workspace'
        r=self.store.compare_and_swap(a.key,r.revision,r);before=r.to_dict();pool=list(parallel.durable_reservations())
        with self.assertRaisesRegex(StateConflict,'transport binding mismatch'):
            recover(self.store,a.key,self.repo,None,apply=True,validator=validator)
        self.assertEqual(before,self.store.get(a.key).to_dict());self.assertEqual(pool,list(parallel.durable_reservations()))
        r.receipt['transport']['workspaceId']=r.attempt.workspace_id
        self.store.compare_and_swap(a.key,r.revision,r);args.apply=True
        with patch('hand_ext.paseo_recovery.recover',side_effect=lambda store,key,source,package,**kw:
                   recover(store,key,source,package,validator=validator,**kw)), patch('sys.stdout',io.StringIO()):
            self.assertEqual(cli.cmd_managed(self.cfg,args),0)
            failed=self.store.get(a.key);self.assertEqual(cli.cmd_managed(self.cfg,args),0)
        self.assertEqual(failed.to_dict(),self.store.get(a.key).to_dict())
        self.assertEqual(failed.state,'failed');self.assertEqual(failed.outcome,dict(status='failed',backend_exit_code=1,
            quiescent=True,provenance='pre_dispatch_schema',reason='invalid_bound_workspace_id'))
        self.assertIsNone(failed.reservation);self.assertEqual(list(parallel.durable_reservations()),[])
        self.assertEqual(failed.to_dict(),recover(self.store,a.key,self.repo,None,apply=True).to_dict())
        # Rejected send may have an assigned message ID but no delivery or process.
        inv,a,sup,admission,completion=self.intent();admission.admit(inv,a,max_parallel=1)
        package=Path(__file__).parent/'fixtures/hand_paseo/transport/package'
        proof=dict(proof,schema='SendAgentMessageRequestSchema')
        transport=PaseoTransport(package.resolve(),{'kind':'instance','home':'/fake'},
            client_factory=lambda *_:lambda _:proof,store=self.store)
        r=self.store.get(a.key);r.receipt['transport']={'createConfirmed':True,'messageId':a.request_key}
        self.store.compare_and_swap(a.key,r.revision,r)
        result=transport._mutate(a.key,'send',brief='synthetic')
        front=PaseoController(self.cfg,self.store,transport,completion=completion)
        self.assertTrue(front._schema_failed(a.key,result,'send'))
        failed=self.store.get(a.key)
        self.assertIsNone(failed.receipt['transport']['pending']);self.assertEqual(failed.state,'failed')
        self.assertIsNone(failed.writer);self.assertIsNone(failed.process)
        self.assertFalse(failed.receipt['transport'].get('sendConfirmed'))
        self.assertEqual(front.dispatch(inv,a,'synthetic',{}).state,'failed')
        self.assertEqual(list(parallel.durable_reservations()),[])

    def test_postdispatch_ambiguity_retains_identity_and_followup_needs_review(self):
        with patch.object(parallel,'pool_root',return_value=self.root/'cli-ack-pool'):
            code,calls,launched,out,err=self.managed_cli([],fail_create=True)
            self.assertEqual(code,1,err);self.assertEqual(launched,[])
            self.assertIn('state-root: ',err);self.assertIn('invocation: ',err)
            self.assertIn('attempt: ',err);self.assertIn('epoch: 1',err)
        inv,a,sup,admission,completion=self.intent()
        package=Path(__file__).parent/'fixtures/hand_paseo/transport/package'
        calls=[]
        def client(r):
            calls.append(r['command'])
            if r['command']=='create':return {'ok':False,'code':'TRANSPORT_UNRESOLVED'}
            return dict(ok=True,targetKey=transport.target_key,projectId='project',parentAgentId='parent-agent',providers=['hh-hand-codex'])
        transport=PaseoTransport(package.resolve(),{'kind':'instance','home':str(self.root/'daemon')},client_factory=lambda *args:client,store=self.store)
        front=PaseoController(self.cfg,self.store,transport,supervisor=sup,admission=admission,completion=completion)
        parent=front.preflight('codex','parent-agent')
        for _ in range(2):
            with self.assertRaises(ExecutionUnresolved):front.dispatch(inv,self.store.get(a.key).attempt,'brief',parent)
        self.assertEqual(calls.count('create'),1)
        self.assertEqual(calls.count('send'),0)
        self.assertTrue(self.store.get(a.key).reservation)
        with self.assertRaises(StateConflict):front.followup(a.key,'new brief')
        with self.assertRaises(AdmissionDenied):build_gateway(self.store,'not-found')
        # Even a valid binding never permits a mismatching model/account.
        self.assertFalse(FreshPolicy(self.store)(replace(inv,fixed_options=_plain(inv.fixed_options),model='arbitrary'),a))
        r=self.store.get(a.key); saved=r.receipt.pop('completion')
        self.store.compare_and_swap(r.key,r.revision,r)
        with self.assertRaises(AdmissionDenied):build_gateway(self.store,inv.invocation_id)
        # Capacity continuation is narrowly authorized by measured runner evidence,
        # inherits the original baseline, and does not assert a human review.
        r=self.store.get(a.key)
        options=run_cmd.with_sandbox(self.cfg,'dsh')
        fixed=_plain(inv.fixed_options);fixed['options']=options
        dsh=replace(inv,fixed_options=fixed,invocation_id=str(uuid.uuid4()),backend='dsh',
                    account_alias='dsh',model=options['model'],effort=options.get('effort','off'))
        fixed['options']['effort']=dsh.effort
        dsh=replace(dsh,fixed_options=fixed)
        da=Attempt(dsh.invocation_id,str(uuid.uuid4()),1,str(uuid.uuid4()))
        dr=self.store.create_intent(dsh,da)
        dr.receipt={'controller':dict(version=1,policy_root=str(self.repo),backend='dsh'),
                    'completion':dict(saved,go_ledger=str(self.root/'go.jsonl'),go_summary=str(self.root/'go.json')),
                    'usage_observation':{'capacity_failure':True}}
        dr.outcome=dict(status='failed',quiescent=True)
        dr.quiescence=dict(confirmed=True,evidence='fixture reaped',observed_at=time.time())
        dr.state='awaiting_review'
        dr.settle_keys={k:dict(state='completed',key=k) for k in ('finalize','report','ledger','go_ledger','usage_state')}
        self.store.compare_and_swap(dr.key,dr.revision,dr)
        with patch.object(front,'dispatch',side_effect=lambda i,a,b,p:self.store.get(a.key)), \
             patch.object(front.admission,'admit'):
            next_record=front.continue_capacity(da.key,'continue self-contained synthetic brief')
        self.assertEqual(next_record.attempt.epoch,2)
        self.assertEqual(next_record.receipt['completion']['context']['baseline_tree'],saved['context']['baseline_tree'])
        self.assertNotIn('review',self.store.get(da.key).artifacts)
        dcfg=replace(self.cfg,order=['dsh'])
        with patch('hand_ext.paseo_controller.load_config',return_value=dcfg):
            self.assertTrue(FreshPolicy(self.store)(dsh,next_record.attempt))

if __name__=='__main__':unittest.main()
