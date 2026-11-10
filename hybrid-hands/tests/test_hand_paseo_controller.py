"""Three offline controller groups; synthetic public transport and process evidence."""
import argparse
from dataclasses import replace
from pathlib import Path
import io
import hashlib
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
from hand_ext.paseo_transport import PaseoTransport, TransportError


class Ops:
    def reconcile(self, identity):
        return Quiescence(True, 'fixture group reaped', time.time())


class FinishingWorker:
    def __init__(self, store, supervisor, completion):
        self.store, self.supervisor, self.completion = store, supervisor, completion
        self.hooks = {}; self.calls = 0; self.status="ok"; self.capacity=False
        completion.attach(self)
    def start(self, invocation, attempt, brief):
        from hand_ext.paseo_prompt import prompt_path
        assert brief == prompt_path(self.store.get(attempt.key)).read_bytes().decode()
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
        self.schedule_archive = CompletionService._schedule_archive
        archive = patch.object(CompletionService, '_schedule_archive')
        archive.start(); self.addCleanup(archive.stop)
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
                if command in ('archive', 'reopen'):
                    result['state'] = {'archive':'archived', 'reopen':'reopened'}[command]
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
        unavailable.probe_capabilities.return_value={'ok':True,'providers':['hh-hand-codex']}
        with self.assertRaisesRegex(PaseoUnavailable, '^PARENT_REQUIRED$'):
            PaseoController(self.cfg,self.store,unavailable).preflight('codex',None)
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
        failures = {'archive': 1, 'reopen': 1}
        def client(request):
            command=request['command'];calls.append(command)
            result={'ok':True,'targetKey':transport.target_key}
            if failures.get(command, 0):
                failures[command] -= 1
                return {'ok': False, 'code': 'RAW_SECRET_DIAGNOSTIC'}
            if command=='reconcile':result['state']='unresolved'
            if command=='probe':result['providers']=['hh-hand-codex']
            if command=='parent':result.update(parentAgentId='parent-agent',projectId='project')
            if command=='send':
                from hand_ext.paseo_prompt import escape
                envelope = ('<paseo-system version="1" kind="agent-message" source-agent-id="' +
                    escape(inv.parent_paseo_agent_id) + '" message-id="' + request['messageId'] +
                    '">\n' + escape(request['brief']) + '\n</paseo-system>')
                try:
                    gateway.handle('session/prompt',dict(sessionId=inv.invocation_id,
                        messageId=request['messageId'],prompt=[dict(type='text',text=envelope)]))
                except ProtocolError as error:
                    if error.code != -32011: raise
            if command in ('archive', 'reopen'):
                result['state'] = {'archive':'archived', 'reopen':'reopened'}[command]
            return result
        transport=PaseoTransport(package.resolve(),{'kind':'instance','home':str(self.root/'daemon')},
            client_factory=lambda *args:client,store=self.store)
        # Independent frontend has no daemon process authority.
        front=PaseoController(self.cfg,self.store,transport,completion=CompletionService(self.store,ExecutionSupervisor(self.store),admission))
        parent=front.preflight('codex','parent-agent')
        self.assertFalse(transport._read((a.invocation_id, a.attempt_id, a.epoch))['settled'])
        with self.assertRaises(StateConflict): front.archive(a.key)
        worker.status = 'failed'
        record=front.dispatch(inv,a,'fresh synthetic brief',parent)
        self.assertTrue(terminal_evidence(record));self.assertEqual(worker.calls,1)
        self.assertIn('create',calls); self.assertIn('send',calls)
        self.assertGreaterEqual(self.preflight.call_count,2)
        for field, value in (('reservation', {'held': True}), ('settle_keys', {}),
                             ('quiescence', {'confirmed': False, 'evidence': ''})):
            unfinished = replace(record, **{field: value})
            self.assertFalse(terminal_evidence(unfinished))
        self.assertEqual(record.outcome['status'], 'failed')
        self.assertEqual(record.receipt['lifecycle_error']['code'], 'ARCHIVE_UNRESOLVED')
        self.assertNotIn('RAW_SECRET', str(record.receipt))
        with self.assertRaises(StateConflict): front.followup(a.key, 'review required')
        with self.assertRaises(ExecutionUnresolved): front.archive(a.key)  # Unknown ACK.
        front.archive(a.key)
        self.assertEqual(self.store.get(a.key).state,'archived')
        self.assertNotIn('review', self.store.get(a.key).artifacts)
        front.archive(a.key)  # Idempotent exact child + workspace observation.
        self.assertTrue(transport.archive_child((a.invocation_id, a.attempt_id, a.epoch))['ok'])
        before = self.store.get(a.key)
        with patch.object(transport, '_mutate', side_effect=TransportError('RAW_SECRET')):
            with self.assertRaises(ExecutionUnresolved): front.archive(a.key)
        after = self.store.get(a.key)
        self.assertEqual((after.state, after.outcome, after.settle_keys), ('archived', before.outcome, before.settle_keys))
        self.assertNotIn('RAW_SECRET', str(after.receipt))
        front.archive(a.key); self.assertNotIn('lifecycle_error', self.store.get(a.key).receipt)
        front.approve_review(a.key)
        for _ in range(2):
            with self.assertRaises(ExecutionUnresolved):
                front.followup(a.key, 'second self-contained brief')
            from hand_ext.paseo_controller import records_for
            self.assertEqual(len(records_for(self.store, inv.invocation_id)), 1)
            self.assertTrue(self.store.get(a.key).artifacts['review']['approved'])
            self.assertIsNone(self.store.get(a.key).reservation)
        is_dir = Path.is_dir
        with patch.object(Path, 'is_dir', lambda path: False if str(path) == inv.isolated_cwd else is_dir(path)):
            with self.assertRaises(ExecutionUnresolved):
                front.followup(a.key, 'second self-contained brief')
        self.assertEqual(len(records_for(self.store, inv.invocation_id)), 1)
        legacy=self.store.get(a.key); legacy.receipt['transport'].pop('lifecycle'); self.store.compare_and_swap(a.key,legacy.revision,legacy)
        self.assertIn('lifecycle',transport.ensure_workspace(a.key,parent,inv.isolated_cwd))
        next_record=front.followup(a.key,'second self-contained brief')
        self.assertEqual(next_record.attempt.epoch,2)
        from hand_ext.paseo_completion import deferred_archive
        next_record.state='awaiting_review'; self.store.compare_and_swap(next_record.key,next_record.revision,next_record)
        with patch('hand_ext.paseo_transport.PaseoTransport',return_value=transport), patch('hand_ext.paseo_completion.subprocess.run',side_effect=lambda args,**kw: deferred_archive(args[-2],args[-1])):
            self.schedule_archive(completion,next_record.key); completion._archive_threads[next_record.key].join(3)
        self.assertEqual(self.store.get(next_record.key).state,'archived')
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

    def test_gateway_rejection_settles_without_worker(self):
        from hand_ext.paseo_controller import persist_prompt
        inv,a,sup,admission,completion = self.intent(); admission.admit(inv,a,max_parallel=1)
        r=self.store.get(a.key)
        r.attempt=replace(r.attempt,target_key='target',project_id='project',workspace_id='workspace',agent_id='child')
        r.receipt['transport']=dict(targetKey='target',projectId='project',workspaceId='workspace',agentId='child',
            parentAgentId=inv.parent_paseo_agent_id,messageId=a.request_key,briefDigest=hashlib.sha256(b'pinned').hexdigest(),sendConfirmed=True)
        self.store.compare_and_swap(a.key,r.revision,r); persist_prompt(r,'pinned')
        worker=FinishingWorker(self.store,sup,completion)
        gateway=Gateway(self.store,admission,worker,invocation_id=inv.invocation_id,completion=completion)
        params=dict(sessionId=inv.invocation_id,messageId=a.request_key,prompt=[dict(type='text',text='wrong')])
        for field in ('gateway_claim','worker_owner','worker_run_dir'):
            for value in (None, '', 'existing'):
                r=self.store.get(a.key); r.receipt[field]=value; self.store.compare_and_swap(a.key,r.revision,r)
                before=self.store._path(a.key).read_bytes()
                with self.assertRaises(ProtocolError): gateway.handle('session/prompt',params)
                self.assertEqual(self.store._path(a.key).read_bytes(),before)
                r=self.store.get(a.key); r.receipt.pop(field); self.store.compare_and_swap(a.key,r.revision,r)
        with self.assertRaises(ProtocolError): gateway.handle('session/prompt',params)
        self.assertIn('prompt_rejection',self.store.get(a.key).receipt)
        package=Path(__file__).parent/'fixtures/hand_paseo/transport/package'
        transport=PaseoTransport(package.resolve(),{'kind':'instance','home':str(self.root/'daemon')},store=self.store)
        transport.target_key='target'  # synthetic binding
        result=transport.wait_child(a.key,0,require_settlement=True)
        self.assertEqual(result['outcome']['status'],'failed'); self.assertEqual(worker.calls,0)
        params['prompt'][0]['text']='pinned'
        with self.assertRaises(ProtocolError): gateway.handle('session/prompt',params)
        self.assertEqual(worker.calls,0)

    def test_legacy_attestation_fences_and_completion(self):
        from hand_ext.paseo_recovery import recover
        from hand_ext.post_hoc_reverify import bindings
        from hand_ext.process_containment import OSIdentity
        inv, a, sup, admission, completion = self.intent()
        admission.admit(inv, a, max_parallel=1)
        r = self.store.get(a.key)
        self.store.bind_placement(a.key, r.revision, dict(target_key='target',
            project_id='project', workspace_id='workspace', agent_id='agent'))
        sup.register_writer(a.key, ProcessIdentity(91001, 91001, 'opaque'), 'worker')
        r = self.store.get(a.key); r.process['supervisor_id'] = '91002'
        r.state = 'unresolved'; r.pending_outcome = dict(status='cancelled', backend_exit_code=143)
        r.receipt.update(worker_owner='worker', worker_run_dir=str(self.root/'legacy-run'))
        r.receipt['transport'] = dict(targetKey='target', projectId='project',
            workspaceId='workspace', agentId='agent', requestKey=a.request_key,
            messageId=a.request_key, cwd=inv.isolated_cwd,
            parentAgentId=inv.parent_paseo_agent_id, sendConfirmed=True,
            gatewayEnv=dict(HYBRID_HANDS_INVOCATION_ID=inv.invocation_id,
                            HYBRID_HANDS_EXECUTION_ROOT=str(self.store.root)))
        r.receipt['containment'] = dict(binding=bindings(r))
        self.store.compare_and_swap(a.key, r.revision, r)
        class Table:
            rows = {}; dirty = False; group = False
            def identity(self, pid): return self.rows.get(pid)
            def snapshot(self): return self.rows.copy()
            def group_present(self, pgid): return self.group
            def marker_matches(self, pid, invocation): return self.dirty
        table = Table(); path = self.store._path(a.key)
        def run(apply=False, **kw):
            return recover(self.store, a.key, self.repo, None, apply=apply,
                           legacy_attest=True, reason=kw.pop('reason', 'operator checked'),
                           process_table=table, **kw)
        original = path.read_bytes(); run(); self.assertEqual(path.read_bytes(), original)
        # Older receipts have no containment binding; public placement/request
        # still must pin the exact immutable invocation before any OS proof.
        saved = self.store.get(a.key); legacy = self.store.get(a.key)
        legacy.receipt['containment'] = {}
        legacy.receipt['transport'] = dict(targetKey='target', projectId='project',
            workspaceId='workspace', agentId='agent', requestKey=a.request_key,
            messageId=a.request_key, cwd=inv.isolated_cwd,
            parentAgentId=inv.parent_paseo_agent_id, sendConfirmed=True,
            gatewayEnv=dict(HYBRID_HANDS_INVOCATION_ID=inv.invocation_id,
                            HYBRID_HANDS_EXECUTION_ROOT=str(self.store.root)))
        self.store.compare_and_swap(a.key, legacy.revision, legacy); run()
        saved.revision = self.store.get(a.key).revision
        self.store.compare_and_swap(a.key, saved.revision, saved)
        table.rows = {91002:OSIdentity(91002, 'new-birth', 'SECRET_ARGV', 1, os.getuid())}
        run(owner_os_start='90')  # Explicit prior owner birth proves PID reuse.
        table.rows = {}
        for bad in ('reason', 'owner', 'root', 'group', 'marker', 'scan', 'binding', 'complete', 'incomplete', 'fatal', 'gateway', 'completion', 'owner_binding', 'reservation_key', 'pool', 'latest'):
            with self.subTest(bad=bad):
                saved = self.store.get(a.key)
                if bad in ('binding', 'complete', 'incomplete', 'fatal', 'gateway', 'completion', 'owner_binding', 'reservation_key'):
                    changed = self.store.get(a.key)
                    if bad == 'binding': changed.receipt['containment']['binding']['process']['pid'] = 5
                    elif bad == 'complete': changed.receipt['containment'].update(inventory_complete=True)
                    elif bad == 'incomplete': changed.receipt['containment'].update(inventory_complete=False)
                    elif bad == 'fatal': changed.receipt['containment']['first_fatal'] = 'scan'
                    elif bad == 'gateway': changed.receipt['transport']['gatewayEnv'] = {}
                    elif bad == 'completion': changed.receipt['completion']['context']['worktree'] = str(self.repo)
                    elif bad == 'owner_binding': changed.writer['owner_id'] = 'other'
                    else: changed.reservation['reservation_id'] = 'other'
                    self.store.compare_and_swap(a.key, changed.revision, changed)
                table.rows = {91002:OSIdentity(91002, '90', 'owner', 1, os.getuid())} if bad == 'owner' else {91001:OSIdentity(91001, '100', 'root', 1, os.getuid())} if bad == 'root' else {91003:OSIdentity(91003, '101', 'child', 1, os.getuid())} if bad in ('marker', 'scan') else {}
                table.group, table.dirty = bad == 'group', bad == 'marker'
                pool = next(parallel.pool_root().glob('*/reservation-*.json'))
                pool_bytes = pool.read_bytes()
                if bad == 'pool': pool.write_text('{}')
                if bad == 'latest':
                    newer = Attempt(inv.invocation_id, 'newer', 2, 'newer-request')
                    self.store.create_intent(inv, newer)
                before = path.read_bytes()
                with patch.object(table, 'snapshot', side_effect=PermissionError('SECRET_ENV_ARGV')) if bad == 'scan' else patch.object(table, 'dirty', table.dirty):
                    with self.assertRaises(StateConflict) as caught: run(True, reason='' if bad == 'reason' else 'operator checked')
                self.assertNotIn('SECRET_ENV_ARGV', str(caught.exception))
                self.assertEqual(path.read_bytes(), before)
                if bad == 'pool': pool.write_bytes(pool_bytes)
                if bad == 'latest': self.store._path(newer.key).unlink()
                if bad in ('binding', 'complete', 'incomplete', 'fatal', 'gateway', 'completion', 'owner_binding', 'reservation_key'):
                    saved.revision = self.store.get(a.key).revision
                    self.store.compare_and_swap(a.key, saved.revision, saved)
        table.rows = {}; table.group = table.dirty = False
        calls = []
        def race():
            calls.append(1)
            if len(calls) == 2:
                changed = self.store.get(a.key)
                self.store.compare_and_swap(a.key, changed.revision, changed)
            return {}
        with patch.object(table, 'snapshot', race), self.assertRaises(StateConflict): run(True)
        self.assertTrue(self.store.get(a.key).reservation)
        # Simulate a crash after a durable report sink, before its hook receipt.
        report_calls = []
        original_report = CompletionService._report
        def crash_report(service, *args):
            report_calls.append(1)
            original_report(service, *args)
            raise RuntimeError('SECRET_ENV_ARGV')
        with patch.object(CompletionService, '_report', crash_report):
            partial = run(True)
        self.assertTrue(partial.reservation)
        from hand_ext.legacy_attestation import attested
        for field, value in (('owner', {}), ('root', {}), ('group', 'present'),
                             ('marker_matches', 1), ('authoritative', False), ('method', 'other')):
            corrupt = self.store.get(a.key)
            corrupt.receipt['legacy_attestation']['evidence'][field] = value
            corrupt.quiescence['details'][field] = value
            self.assertFalse(attested(corrupt))
        with patch.object(CompletionService, '_report', side_effect=AssertionError('no replay')) as replay:
            result = run(True)
        replay.assert_not_called()
        self.assertEqual(report_calls, [1])
        self.assertEqual((result.outcome['status'], result.quiescence['confirmed'], result.quiescence['details']['attested']), ('cancelled', False, True))
        self.assertIsNone(result.reservation); self.assertEqual(len(result.settle_keys), 5)
        before = path.read_bytes(); run(True); self.assertEqual(path.read_bytes(), before)

    def test_cancelled_post_hoc_proof_dry_run_refusal_and_settlement(self):
        from dataclasses import asdict
        import copy
        from hand_ext.paseo_recovery import recover
        from hand_ext.post_hoc_reverify import bindings
        from hand_ext.process_containment import OSIdentity
        inv, a, sup, admission, completion = self.intent()
        admission.admit(inv, a, max_parallel=1)
        r = self.store.get(a.key)
        r = self.store.bind_placement(a.key, r.revision, dict(target_key='target',
                 project_id='project', workspace_id='workspace', agent_id='agent'))
        sup.register_writer(a.key, ProcessIdentity(91001, 91001, 'opaque'), 'worker')
        r = self.store.get(a.key)
        root = OSIdentity(91001, '100', 'root', 1, os.getuid())
        owner = OSIdentity(91002, '90', 'owner', 1, os.getuid())
        r.process['supervisor_id'] = str(owner.pid)
        r.state = 'unresolved'
        r.pending_outcome = dict(status='cancelled', backend_exit_code=143,
                                provenance='runner', usage=None, final_text='')
        r.receipt.update(worker_owner='worker', worker_run_dir=str(self.root/'worker-run'))
        proof = dict(inventory_complete=True, root=asdict(root), root_reaped=True,
                     owner=asdict(owner), protected=[asdict(owner)], inventory=[asdict(root)])
        proof['binding'] = bindings(r)
        r.receipt['containment'] = proof
        self.store.compare_and_swap(a.key, r.revision, r)
        class Table:
            rows = {}
            dirty = False
            def snapshot(self): return self.rows.copy()
            def identity(self, pid): return self.rows.get(pid)
            def marker_matches(self, pid, invocation): return self.dirty
        table = Table()
        def run(apply=False):
            return recover(self.store, a.key, self.repo, None, apply=apply, process_table=table)
        state_path = self.store._path(a.key)
        original = state_path.read_bytes()
        run(); self.assertEqual(state_path.read_bytes(), original)
        # Each negative proof must retain byte-identical state and reservation.
        for bad in ('legacy', 'root-live', 'owner-live', 'marker', 'scan-error', 'binding', 'revision'):
            r = self.store.get(a.key); saved = copy.deepcopy(r.receipt['containment'])
            if bad == 'legacy': r.receipt['containment'].pop('inventory')
            if bad == 'binding': r.receipt['containment']['binding']['attempt']['request_key'] = 'wrong'
            if bad in ('legacy', 'binding'): self.store.compare_and_swap(a.key, r.revision, r)
            table.rows = {root.pid:root} if bad == 'root-live' else {owner.pid:owner} if bad == 'owner-live' else {}
            if bad == 'marker': table.rows = {91003:OSIdentity(91003, '101', 'child', 1, os.getuid())}
            table.dirty = bad == 'marker'
            before = state_path.read_bytes()
            if bad == 'scan-error':
                context = patch.object(table, 'snapshot', side_effect=PermissionError('SECRET_SENTINEL'))
            elif bad == 'revision':
                from hand_ext.post_hoc_reverify import ReverifyOps
                old = ReverifyOps.reconcile
                def race(ops, process):
                    ops.first_revision = -1
                    return old(ops, process)
                context = patch.object(ReverifyOps, 'reconcile', race)
            else: context = patch.object(table, 'dirty', table.dirty)
            with context, self.assertRaises(StateConflict): run(True)
            self.assertEqual(state_path.read_bytes(), before, bad)
            self.assertTrue(self.store.get(a.key).reservation)
            if bad in ('legacy', 'binding'):
                r = self.store.get(a.key); r.receipt['containment'] = saved
                self.store.compare_and_swap(a.key, r.revision, r)
        newer = Attempt(inv.invocation_id, 'newer', 2, 'newer-request')
        self.store.create_intent(inv, newer)
        before = state_path.read_bytes()
        with self.assertRaises(StateConflict): run(True)
        self.assertEqual(state_path.read_bytes(), before)
        self.assertTrue(self.store.get(a.key).reservation)
        self.store._path(newer.key).unlink()  # Remove only this synthetic epoch fixture.
        r = self.store.get(a.key)
        r.receipt['containment']['owner_done'] = dict(worker_owner='worker', key=_plain(a.key))
        self.store.compare_and_swap(a.key, r.revision, r)
        table.rows = {owner.pid:owner}; table.dirty = False
        # A revision that changes during the proof scan, on the still-unsettled
        # fixture, is fenced in dry run and apply: the external CAS is the only
        # state change; nothing settles and the reservation is retained.
        for apply in (False, True):
            calls = []
            def racing_snapshot():
                if not calls:  # One external CAS bumps the revision mid-scan.
                    r = self.store.get(a.key)
                    r.quiescence = dict(qa_revision_race=True)
                    self.store.compare_and_swap(a.key, r.revision, r)
                calls.append(1)
                return {}
            before = self.store.get(a.key)
            with patch.object(table, 'snapshot', racing_snapshot), self.assertRaises(StateConflict):
                run(apply)
            self.assertEqual((len(calls), apply), (1, apply))
            after = self.store.get(a.key)
            self.assertEqual(after.revision, before.revision + 1, apply)
            self.assertEqual((after.state, after.outcome, after.pending_outcome, after.quiescence,
                              after.settle_keys, after.artifacts, bool(after.reservation)),
                             (before.state, before.outcome, before.pending_outcome,
                              dict(qa_revision_race=True), before.settle_keys, before.artifacts, True), apply)
            r = self.store.get(a.key); r.quiescence = None  # Drop the synthetic marker.
            self.store.compare_and_swap(a.key, r.revision, r)
        before = state_path.read_bytes(); run()
        self.assertEqual(state_path.read_bytes(), before)
        result = run(True)
        self.assertEqual(result.outcome['status'], 'cancelled')
        self.assertEqual(result.outcome['backend_exit_code'], 143)
        self.assertIsNone(result.reservation)
        self.assertEqual(len(result.settle_keys), 5)
        self.assertTrue(all(m['state'] == 'completed' for m in result.settle_keys.values()))
        settled = state_path.read_bytes(); run(True)
        self.assertEqual(state_path.read_bytes(), settled)

    def test_prompt_rejection_recovery(self):
        from hand_ext.paseo_recovery import recover
        inv,a,_,admission,_ = self.intent(); admission.admit(inv,a,max_parallel=1)
        r = self.store.get(a.key)
        r.attempt = replace(r.attempt,target_key='target',project_id='project',workspace_id='workspace',agent_id='child')
        r.receipt.update(gateway_claim='old-gateway', transport=dict(
            targetKey='target',projectId='project',workspaceId='workspace',agentId='child',
            parentAgentId=inv.parent_paseo_agent_id,messageId=a.request_key,
            briefDigest='digest',sendConfirmed=True,pending=None))
        self.store.compare_and_swap(a.key,r.revision,r)
        proof = dict(ok=True,targetKey='target',agentId='child',workspaceId='workspace',messageId=a.request_key,status='error')
        before=self.store._path(a.key).read_bytes(); pool=list(parallel.durable_reservations())
        for bad in (dict(proof,status='idle'),dict(proof,agentId='other'),dict(ok=False)):
            with self.assertRaises(StateConflict): recover(self.store,a.key,self.repo,None,apply=True,validator=lambda _,b=bad:b)
            self.assertEqual(self.store._path(a.key).read_bytes(),before)
            self.assertEqual(list(parallel.durable_reservations()),pool)
        for claim in (None, '', 'old-gateway'):
            r=self.store.get(a.key); r.receipt.update(gateway_claim=claim, prompt_rejection=dict(reason='gateway_prompt_fence_rejected',epoch=a.epoch,request_key=a.request_key))
            self.store.compare_and_swap(a.key,r.revision,r); blocked=self.store._path(a.key).read_bytes()
            with self.assertRaises(StateConflict): recover(self.store,a.key,self.repo,None,apply=True,validator=lambda _:proof)
            self.assertEqual((self.store._path(a.key).read_bytes(),list(parallel.durable_reservations())),(blocked,pool))
        r=self.store.get(a.key); r.receipt.pop('prompt_rejection'); r.receipt['gateway_claim']='old-gateway'; self.store.compare_and_swap(a.key,r.revision,r)
        before=self.store._path(a.key).read_bytes()
        recover(self.store,a.key,self.repo,None,validator=lambda _:proof)
        self.assertEqual(self.store._path(a.key).read_bytes(),before)
        for field in ('worker_owner','process','outcome','pending_outcome'):
            r=self.store.get(a.key)
            if field == 'worker_owner': r.receipt[field]='worker'
            else: setattr(r,field,{'status':'uncertain'})
            self.store.compare_and_swap(a.key,r.revision,r); blocked=self.store._path(a.key).read_bytes()
            with self.assertRaises(StateConflict): recover(self.store,a.key,self.repo,None,apply=True,validator=lambda _:proof)
            self.assertEqual(self.store._path(a.key).read_bytes(),blocked)
            r=self.store.get(a.key)
            if field == 'worker_owner': r.receipt.pop(field)
            else: setattr(r,field,None)
            # Restore the synthetic fixture; production outcomes are immutable.
            from hand_ext.execution_state import atomic_json
            atomic_json(self.store._path(a.key),r.to_dict())
        failed=recover(self.store,a.key,self.repo,None,apply=True,validator=lambda _:proof)
        self.assertEqual(failed.state,'failed'); self.assertFalse(list(parallel.durable_reservations()))
        self.assertEqual(failed.to_dict(),recover(self.store,a.key,self.repo,None,apply=True).to_dict())

    def test_failed_create_recovery_exact_proof(self):
        from hand_ext.paseo_recovery import recover
        inv,a,_,admission,_ = self.intent(); admission.admit(inv,a,max_parallel=1)
        r = self.store.get(a.key)
        r.attempt = replace(r.attempt,target_key='target',project_id='project',workspace_id='workspace',agent_id='child')
        r.receipt['transport'] = dict(pending='create',workspaceConfirmed=True,agentKey='key',targetKey='target',projectId='project',workspaceId='workspace',agentId='child',parentAgentId=inv.parent_paseo_agent_id)
        self.store.compare_and_swap(a.key,r.revision,r)
        proof = dict(ok=True,targetKey='target',agentId='child',agentKey='key',workspaceId='workspace',phase='failed',outcomeUnknown=False,inFlight=None,absence='AGENT_NOT_FOUND')
        for field,value in (('workspaceConfirmed',False),('createConfirmed',False),('messageId','sent')):
            r=self.store.get(a.key); r.receipt['transport'][field]=value; self.store.compare_and_swap(a.key,r.revision,r)
            before=self.store._path(a.key).read_bytes()
            with self.assertRaises(StateConflict): recover(self.store,a.key,self.repo,None,apply=True,validator=lambda _:proof)
            self.assertEqual(self.store._path(a.key).read_bytes(),before)
            r=self.store.get(a.key); r.receipt['transport'].pop(field); r.receipt['transport']['workspaceConfirmed']=True; self.store.compare_and_swap(a.key,r.revision,r)
        before = self.store._path(a.key).read_bytes(); pool = list(parallel.durable_reservations())
        for invalid in (dict(proof,outcomeUnknown=True),dict(proof,agentKey='other'),dict(ok=False)):
            with self.assertRaises(StateConflict): recover(self.store,a.key,self.repo,None,apply=True,validator=lambda _,p=invalid:p)
            self.assertEqual(self.store._path(a.key).read_bytes(),before); self.assertEqual(list(parallel.durable_reservations()),pool)
        recover(self.store,a.key,self.repo,None,validator=lambda _:proof)
        self.assertEqual(self.store._path(a.key).read_bytes(),before)
        failed = recover(self.store,a.key,self.repo,None,apply=True,validator=lambda _:proof)
        self.assertEqual(failed.state,'failed'); self.assertEqual(list(parallel.durable_reservations()),[])
        self.assertEqual(failed.to_dict(),recover(self.store,a.key,self.repo,None,apply=True).to_dict())

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
            return dict(ok=True,state='reopened' if r['command']=='reopen' else 'verified',targetKey=transport.target_key,projectId='project',parentAgentId='parent-agent',providers=['hh-hand-codex'])
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
        dr.state='archived'
        dr.settle_keys={k:dict(state='completed',key=k) for k in ('finalize','report','ledger','go_ledger','usage_state')}
        self.store.compare_and_swap(dr.key,dr.revision,dr)
        with patch.object(front,'dispatch',side_effect=lambda i,a,b,p:self.store.get(a.key)), \
             patch.object(front.admission,'admit'):
            next_record=front.continue_capacity(da.key,'continue self-contained synthetic brief')
        self.assertEqual(next_record.attempt.epoch,2)
        self.assertEqual(next_record.receipt['completion']['context']['baseline_tree'],saved['context']['baseline_tree'])
        self.assertNotIn('review',self.store.get(da.key).artifacts)
        self.assertIn('reopen', calls)
        dcfg=replace(self.cfg,order=['dsh'])
        with patch('hand_ext.paseo_controller.load_config',return_value=dcfg):
            self.assertTrue(FreshPolicy(self.store)(dsh,next_record.attempt))

if __name__=='__main__':unittest.main()
