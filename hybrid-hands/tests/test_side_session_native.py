"""Native reads through the real Node bridge, using only a synthetic client."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/hybrid-hands/lib"))
from side_session import paseo

# "omitted" mirrors the installed client leaving archivedAt undefined for an
# active agent; null and undefined both mean unarchived.
def archived_field(value) -> str:
    return "" if value == "omitted" else f",archivedAt:{value or 'null'}"


OWNERS = [{"agentId": "side", "workspaceId": "private", "role": "side", "status": "done", "sendPending": False}]

ACTIVE_STATE = '{kind:"unavailable",workspaceId:"private",reason:"workspace_not_archived"}'
# Fake revive client: first inspect returns the recovery state, later ones the active
# state the installed client reports once the workspace exists again.
REVIVE_CLIENT = '''import {appendFileSync} from "node:fs";
const record=(...a)=>appendFileSync(new URL("../../calls",import.meta.url),a.join(":")+"\\n");
let inspects=0;
const entries=SHARED?[{agent:{id:"main",workspaceId:"private"}}]:[];
export const connectToDaemon=async()=>({close:async()=>{},
fetchAgent:async()=>({agent:{id:"side",status:"idle",workspaceId:"private"@ARCHIVED@}}),
fetchWorkspaces:async()=>({entries:[{id:"private",workspaceKind:"worktree",workspaceDirectory:"/side",projectRootPath:"/repo"}],pageInfo:{nextCursor:null}}),
fetchAgents:async()=>({entries,pageInfo:{nextCursor:null}}),
inspectWorkspaceRecovery:async(w)=>{record("inspect",w);inspects++;
return inspects===1?@RECOVERY@:@ACTIVE_STATE@},
restoreWorkspace:async(w)=>{record("restore",w,inspects)},
archiveWorkspace:async(w)=>{record("archive",w);return {archivedAt:"2026-11-09T00:00:00Z"}}});'''
# Fake rearchive client: an active agent must never reach cancel/archiveAgent.
# SHARED and @OWN@ are replaced per case.
REARCHIVE_CLIENT = '''import {appendFileSync} from "node:fs";
const record=(id)=>appendFileSync(new URL("../../calls",import.meta.url),id+"\\n");
export const connectToDaemon=async()=>{const entries=SHARED?[{agent:{id:"main",workspaceId:"private"}}]:[];return {close:async()=>{},
fetchAgent:async()=>({agent:{id:"side",status:"idle",workspaceId:"@OWN@"@ARCHIVED@}}),
inspectWorkspaceRecovery:async()=>({kind:"unavailable",reason:"workspace_not_archived",workspaceId:"private"}),
fetchWorkspaces:async()=>({entries:[{id:"private",workspaceKind:"worktree",workspaceDirectory:"/side",projectRootPath:"/repo"}],pageInfo:{nextCursor:null}}),
fetchAgents:async()=>({entries,pageInfo:{nextCursor:null}}),
cancelAgent:async()=>record("cancel"),archiveAgent:async()=>record("archiveAgent"),
archiveWorkspace:async(w)=>{record("archive:"+w);return {archivedAt:"2026-11-09T00:00:00Z"}}};}'''

@unittest.skipUnless(shutil.which("node"), "Node unavailable")
class NativeReads(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        utils = root / "dist/utils"
        utils.mkdir(parents=True)
        (root / "package.json").write_text('{"type":"module"}')
        (utils / "daemon-target.js").write_text('export const selectDaemonTarget=()=>({kind:"instance",home:"/fake"});')
        (utils / "client.js").write_text('''import {appendFileSync} from "node:fs";
const record=(...args)=>appendFileSync(new URL("../../calls",import.meta.url),JSON.stringify(args)+"\\n");
export const connectToDaemon=async()=>({close:async()=>{},
listProviderSubagents:async(p)=>{record("list",p);return {parentAgentId:p,subagents:[{id:"child",parentAgentId:p}],error:p==="error"?"private error message":null}},
fetchProviderSubagentTimeline:async(p,c,o)=>{record("timeline",p,c,o);return {parentAgentId:p,subagentId:c,rows:[{seq:1}],endCursor:{epoch:"e",seq:1},error:p==="timeline-error"?"DAEMON_FAILED":null}}
});''')
        patch = mock.patch.object(paseo, "cli_package_root", return_value=root)
        patch.start()
        self.addCleanup(patch.stop)
        self.root = root
        self.calls = root / "calls"
    def test_project_grouping(self):
        client = Path(self.tmp.name) / "dist/utils/client.js"
        client.write_text('''export const connectToDaemon=async()=>({close:async()=>{},
addProject:async(p)=>({project:{projectId:p==="/repo"?"repo-id":null}}),
createWorkspace:async({source:s})=>{if(s.projectId!=="repo-id"||s.path!=="/side")throw Error();return {workspace:{id:"w"}}},
createAgent:async(a)=>({id:"a",workspaceId:a.workspaceId}),fetchAgent:async()=>({})});''')
        self.assertEqual(paseo._call("start", {"projectRoot": "/repo", "source": {"kind": "directory", "path": "/side"}}, timeout=3)["workspaceId"], "w")
        with self.assertRaises(paseo.PaseoError) as caught:
            paseo._call("start", {"projectRoot": "/invalid"}, timeout=3)
        self.assertEqual(caught.exception.code, "PROJECT_REGISTRATION_FAILED")
    def test_success(self):
        self.assertEqual(paseo.subagents("parent", "home:/fake")["subagents"][0]["id"], "child")
        result = paseo.subagent_timeline("parent", "child", "home:/fake")
        self.assertEqual((result["parentAgentId"], result["subagentId"], result["rows"], result["endCursor"]), ("parent", "child", [{"seq": 1}], {"epoch": "e", "seq": 1}))
        self.assertEqual([json.loads(x) for x in self.calls.read_text().splitlines()], [["list", "parent"], ["list", "parent"], ["timeline", "parent", "child", {"limit": 100}]])

    def test_private_workspace_cleanup(self):
        client = Path(self.tmp.name) / "dist/utils/client.js"
        for expected, code, calls in [
            (None, "WORKSPACE_ID_MISMATCH", []),
            ("main-workspace", "WORKSPACE_ID_MISMATCH", []),
            ("private", None, ["cancel", "side"]),
        ]:
            self.calls.write_text("")
            client.write_text('''import {appendFileSync} from "node:fs";
const record=(id)=>appendFileSync(new URL("../../calls",import.meta.url),id+"\\n");
export const connectToDaemon=async()=>({close:async()=>{},
fetchAgent:async()=>({agent:{id:"side",status:"running",workspaceId:"private"}}),
cancelAgent:async()=>record("cancel"),archiveAgent:async(id)=>{record(id);return {archivedAt:"2026-11-08T00:00:00Z"}},
archiveWorkspace:async()=>{throw Error("finish must retain workspace")}});''')
            request = {"agentId": "side", "expectedWorkspaceId": expected}
            if code:
                with self.assertRaises(paseo.PaseoError) as caught:
                    paseo._call("finish", request, timeout=3)
                self.assertEqual(caught.exception.code, code)
            else:
                self.assertTrue(paseo._call("finish", request, timeout=3)["agentArchived"])
            self.assertEqual(self.calls.read_text().splitlines(), calls)

        # Exact membership protects shared workspaces; local kinds and same repo paths qualify.
        for mode, code in [("ok", None), ("checkout", None),
                           ("local_checkout", None),
                           ("directory", None),
                           ("unknown", None),
                           ("root", None),
                           ("path", "WORKSPACE_PATH_MISMATCH"),
                           ("cursor", "WORKSPACE_DIRECTORY_UNCONFIRMED"),
                           ("duplicate", "WORKSPACE_DIRECTORY_UNCONFIRMED"),
                           ("shared", "WORKSPACE_SHARED"), ("closed", "WORKSPACE_SHARED"),
                           ("sibling-archived", "WORKSPACE_SHARED"), ("archived", None)]:
            self.calls.write_text("")
            client.write_text(REARCHIVE_CLIENT.replace("@OWN@", "private")
                .replace("@ARCHIVED@", archived_field('"2026-11-09T00:00:00Z"'))
                .replace("SHARED", str(mode in ("shared", "closed", "sibling-archived")).lower())
                .replace('id:"main",workspaceId:"private"', 'id:"main",workspaceId:"private",status:"closed"' if mode == "closed" else 'id:"main",workspaceId:"private",archivedAt:"2026-11-09T00:00:00Z"' if mode == "sibling-archived" else 'id:"main",workspaceId:"private"')
                .replace('fetchWorkspaces:async()=>({entries:[{id:"private",workspaceKind:"worktree",workspaceDirectory:"/side",projectRootPath:"/repo"}],pageInfo:{nextCursor:null}}),',
                  '''fetchWorkspaces:async({includeBackground,page})=>{
if(!includeBackground||page.limit!==200)throw Error();
const entry={id:"private",workspaceKind:MODE,workspaceDirectory:MODE==="path"?"/other":"/side",projectRootPath:MODE==="root"?"/side":"/repo"};
if(["ok","root","path","cursor","duplicate","shared","closed","sibling-archived","archived"].includes(MODE))entry.workspaceKind="worktree";
return {entries:MODE==="archived"?[]:page.cursor?[entry]:MODE==="duplicate"?[entry]:[],pageInfo:MODE==="cursor"?{}:{nextCursor:page.cursor?null:"next"}};},
inspectWorkspaceRecovery:async()=>MODE==="archived"?{kind:"recoverable",action:"unarchive",workspaceId:"private"}:{kind:"unavailable",reason:"workspace_not_archived",workspaceId:"private"},'''.replace("MODE", json.dumps(mode))))
            request = {"agentId": "side", "expectedWorkspaceId": "private",
                       "privateWorkspace": True, "workdir": "/side", "workspaceOwners": OWNERS}
            if code:
                with self.assertRaises(paseo.PaseoError) as caught:
                    paseo._call("rearchive", request, timeout=3)
                self.assertEqual(caught.exception.code, code)
            else:
                self.assertTrue(paseo._call("rearchive", request, timeout=3)["archived"])
            self.assertEqual(self.calls.read_text().splitlines(), ["archive:private"] if mode in ("ok", "checkout", "local_checkout", "directory", "unknown", "root") else [])

        # Same IDs through tidy: empty local/worktree, closed owned sibling, unknown blocks.
        for mode in ("local", "worktree", "closed", "unknown", "archived", "main", "active", "empty_error", "empty_done", "empty_stopped", "empty_unknown", "empty_running", "empty_pending", "missing_proof"):
            self.calls.write_text("")
            (self.root / "kept").mkdir(exist_ok=True)
            client.write_text("""import {appendFileSync} from 'node:fs';
let archived=MODE==='archived', closed=false;
const record=x=>appendFileSync(new URL('../../calls',import.meta.url),x+'\\n');
export const connectToDaemon=async()=>({close:async()=>{},
fetchAgent:async()=>({agent:{id:'side',workspaceId:'private',archivedAt:closed?'2026-11-09T00:00:00Z':null}}),
fetchAgents:async()=>({entries:['closed','unknown','main','active'].includes(MODE)?[{agent:{id:MODE==='unknown'?'stranger':'side',workspaceId:'private',status:MODE==='active'?'idle':'closed',archivedAt:closed?'2026-11-09T00:00:00Z':null}}]:[],pageInfo:{nextCursor:null}}),
fetchWorkspaces:async()=>({entries:archived?[]:[{id:'private',workspaceKind:MODE,workspaceDirectory:'/side'}],pageInfo:{nextCursor:null}}),
inspectWorkspaceRecovery:async()=>archived?{kind:'recoverable',action:'unarchive',workspaceId:'private'}:{kind:'unavailable',reason:'workspace_not_archived',workspaceId:'private'},
archiveAgent:async id=>{record('agent:'+id);closed=true;return {archivedAt:'2026-11-09T00:00:00Z'}},
archiveWorkspace:async id=>{record('workspace:'+id);archived=true;return {archivedAt:'2026-11-09T00:00:00Z'}}});
""".replace('MODE', json.dumps(mode)))
            request = {"expectedWorkspaceId": "private", "workdir": "/side",
                       "privateWorkspace": True, "workspaceOwners": [{**OWNERS[0],
                           "agentId": "" if mode.startswith("empty_") else "side",
                           "status": mode.removeprefix("empty_") if mode.startswith("empty_") else "done",
                           "sendPending": mode == "empty_pending",
                           "role": "main" if mode == "main" else "side"}]}
            if mode == "missing_proof":
                del request["workspaceOwners"][0]["status"]
            if mode in ("unknown", "main", "active", "empty_unknown", "empty_running", "empty_pending", "missing_proof"):
                with self.assertRaises(paseo.PaseoError):
                    paseo._call("tidy", {**request, "apply": True}, timeout=3)
                self.assertEqual(self.calls.read_text(), "")
                continue
            self.assertEqual(paseo._call("tidy", request, timeout=3)["archived"], mode == "archived")
            self.assertEqual(self.calls.read_text(), "")
            self.assertTrue(paseo._call("tidy", {**request, "apply": True}, timeout=3)["archived"])
            self.assertEqual(self.calls.read_text().splitlines(),
                             (["agent:side"] if mode == "closed" else []) + ([] if mode == "archived" else ["workspace:private"]))
            self.assertTrue((self.root / "kept").is_dir())

    def test_revive_and_rearchive(self):
        client = Path(self.tmp.name) / "dist/utils/client.js"
        # Fake client knobs per case; every mutation is appended to the calls ledger.
        for archived, recovery, expected, calls in [
            ('"2026-11-09T00:00:00Z"', '{}', (False, None), []),
            (None, '{kind:"recoverable",workspaceId:"private",action:"restore"}',
             (None, "WORKSPACE_RECOVERY_UNSUPPORTED"), ["inspect:private"]),
            (None, '{kind:"recoverable",workspaceId:"other",action:"unarchive"}',
             (None, "WORKSPACE_RECOVERY_UNSUPPORTED"), ["inspect:private"]),
            (None, '{kind:"recoverable",workspaceId:"private",action:"unarchive"}',
             (True, None), ["inspect:private", "restore:private:1", "inspect:private"]),
            (None, '{kind:"unavailable",workspaceId:"private",reason:"workspace_not_archived"}',
             (True, None), ["inspect:private"]),
            # archivedAt undefined is unarchived, so the missing recovery client bites.
            ("omitted", '{}', (None, "WORKSPACE_RECOVERY_UNSUPPORTED"), ["inspect:private"]),
        ]:
            self.calls.write_text("")
            client.write_text(REVIVE_CLIENT.replace("SHARED", "false")
                              .replace("@ARCHIVED@", archived_field(archived))
                              .replace("@RECOVERY@", recovery).replace("@ACTIVE_STATE@", ACTIVE_STATE))
            request = {"agentId": "side", "expectedWorkspaceId": "private", "privateWorkspace": True, "workdir": "/side", "workspaceOwners": OWNERS}
            if expected[1]:
                with self.assertRaises(paseo.PaseoError) as caught:
                    paseo._call("revive", request, timeout=5)
                self.assertEqual(caught.exception.code, expected[1])
            else:
                self.assertIs(paseo._call("revive", request, timeout=5)["revived"], expected[0])
            self.assertEqual(self.calls.read_text().splitlines(), calls)
        self.calls.write_text("")
        client.write_text(REVIVE_CLIENT.replace("SHARED", "false").replace("@ARCHIVED@", archived_field(None))
                          .replace("@RECOVERY@", ACTIVE_STATE).replace("@ACTIVE_STATE@", ACTIVE_STATE))
        # The request must echo the agent's own workspace before any mutation.
        with self.assertRaises(paseo.PaseoError) as caught:
            paseo._call("revive", {"agentId": "side", "expectedWorkspaceId": "other"}, timeout=5)
        self.assertEqual(caught.exception.code, "WORKSPACE_ID_MISMATCH")
        self.assertEqual(self.calls.read_text(), "")
        for command, archived, result, calls in [
            # An active (archivedAt null) agent keeps its workspace: no mutation at all.
            ("rearchive", None, (False, None), []),
            # A revived agent archived again is the only case that hides the workspace.
            ("rearchive", '"2026-11-09T00:00:00Z"', (True, None), ["archive:private"]),
        ]:
            self.calls.write_text("")
            client.write_text(REARCHIVE_CLIENT.replace("@OWN@", "private").replace("SHARED", "false")
                              .replace("@ARCHIVED@", archived_field(archived)))
            self.assertIs(paseo._call(command, {"agentId": "side", "expectedWorkspaceId": "private", "privateWorkspace": True, "workdir": "/side", "workspaceOwners": OWNERS},
                                      timeout=5)["archived"], result[0])
            self.assertEqual(self.calls.read_text().splitlines(), calls)
        # Both commands refuse an agent whose own workspace is not the requested one.
        for own in ("other", "main-workspace"):
            for request_command in ("revive", "rearchive"):
                self.calls.write_text("")
                client.write_text(REARCHIVE_CLIENT.replace("SHARED", "false").replace("@OWN@", own)
                                  .replace("@ARCHIVED@", archived_field('"2026-11-09T00:00:00Z"')))
                with self.subTest(own=own, command=request_command):
                    with self.assertRaises(paseo.PaseoError) as caught:
                        paseo._call(request_command,
                                    {"agentId": "side", "expectedWorkspaceId": "private", "privateWorkspace": True, "workdir": "/side", "workspaceOwners": OWNERS}, timeout=5)
                self.assertEqual(caught.exception.code, "WORKSPACE_ID_MISMATCH")
                self.assertEqual(self.calls.read_text(), "")
        # Shared workspace rearchive fails before any mutation, even for archived agents.
        self.calls.write_text("")
        client.write_text(REARCHIVE_CLIENT.replace("@OWN@", "private").replace("SHARED", "true")
                          .replace("@ARCHIVED@", archived_field('"2026-11-09T00:00:00Z"')))
        with self.assertRaises(paseo.PaseoError) as caught:
            paseo._call("rearchive", {"agentId": "side", "expectedWorkspaceId": "private", "privateWorkspace": True, "workdir": "/side", "workspaceOwners": OWNERS}, timeout=5)
        self.assertEqual(caught.exception.code, "WORKSPACE_SHARED")
        self.assertEqual(self.calls.read_text(), "")
        # Restoring is not confirmed while recovery still reports an archived workspace.
        self.calls.write_text("")
        recovery = '{kind:"recoverable",workspaceId:"private",action:"unarchive"}'
        client.write_text(REVIVE_CLIENT.replace("SHARED", "false")
                          .replace("@ARCHIVED@", archived_field(None))
                          .replace("@RECOVERY@", recovery).replace("@ACTIVE_STATE@", recovery))
        with self.assertRaises(paseo.PaseoError) as caught:
            paseo._call("revive", {"agentId": "side", "expectedWorkspaceId": "private", "privateWorkspace": True, "workdir": "/side", "workspaceOwners": OWNERS}, timeout=5)
        self.assertEqual(caught.exception.code, "WORKSPACE_RESTORE_UNCONFIRMED")
        self.assertEqual(self.calls.read_text().splitlines(),
                         ["inspect:private", "restore:private:1", "inspect:private"])

    def test_agent_archive_states_directory(self):
        client = self.root / "dist/utils/client.js"
        first = '{entries:[{agent:{id:"one",workspaceId:"w1",archivedAt:null}}],pageInfo:{nextCursor:"next"}}'
        last = '{entries:[{agent:{id:"two",workspaceId:"w2",archivedAt:"2026-11-09T00:00:00Z"}}],pageInfo:{nextCursor:null}}'
        for second, error in [
            (last, None),
            ('{error:"PRIVATE_ERROR",entries:[],pageInfo:{nextCursor:null}}', "WORKSPACE_DIRECTORY_UNCONFIRMED"),
            ('{entries:[],pageInfo:{nextCursor:"next"}}', "WORKSPACE_DIRECTORY_UNCONFIRMED"),
            (first, "WORKSPACE_DIRECTORY_UNCONFIRMED"),
            ('{entries:[{agent:{id:"two",workspaceId:"w2",archivedAt:7}}],pageInfo:{nextCursor:null}}', "WORKSPACE_DIRECTORY_UNCONFIRMED"),
            ('{entries:[],pageInfo:{}}', "WORKSPACE_DIRECTORY_UNCONFIRMED"),
        ]:
            self.calls.write_text("")
            client.write_text('''import {appendFileSync} from "node:fs";
let page=0;
export const connectToDaemon=async()=>({close:async()=>{},fetchAgents:async(request)=>{
appendFileSync(new URL("../../calls",import.meta.url),JSON.stringify(request)+"\\n");
return page++===0?FIRST:SECOND;}});'''.replace("FIRST", first).replace("SECOND", second))
            if error:
                with self.assertRaises(paseo.PaseoError) as caught:
                    paseo._call("agent-archive-states", timeout=3)
                self.assertEqual(caught.exception.code, error)
            else:
                result = paseo._call("agent-archive-states", timeout=3)
                self.assertEqual(result["agents"], [
                    {"agentId": "one", "workspaceId": "w1", "archivedAt": None},
                    {"agentId": "two", "workspaceId": "w2", "archivedAt": "2026-11-09T00:00:00Z"}])
                self.assertEqual(result["targetKey"], "home:/fake")
            calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
            self.assertEqual(len(calls), 2)
            self.assertEqual([call["filter"] for call in calls], [{"includeArchived": True}] * 2)
            self.assertEqual([call["page"] for call in calls], [{"limit": 200}, {"limit": 200, "cursor": "next"}])

    def test_safe_failures(self):
        for parent, child, code in [("parent", "other", "SUBAGENT_NOT_FOUND"), ("error", "child", "PASEO_ERROR"), ("timeline-error", "child", "DAEMON_FAILED"), (" ", "child", "INVALID_AGENT_ID"), ("parent", "", "INVALID_AGENT_ID")]:
            with self.subTest(parent=parent, child=child), self.assertRaises(paseo.PaseoError) as caught:
                paseo.subagent_timeline(parent, child, "home:/fake")
            self.assertEqual((caught.exception.code, caught.exception.data), (code, {}))
        self.assertEqual([json.loads(x)[0] for x in self.calls.read_text().splitlines()], ["list", "list", "list", "timeline"])

    def test_target_guard(self):
        for command in (lambda: paseo.subagents("parent", "home:/other"), lambda: paseo.subagent_timeline("parent", "child", "home:/other")):
            with self.assertRaises(paseo.PaseoError) as caught:
                command()
            self.assertEqual(caught.exception.code, "TARGET_CHANGED")
        self.assertFalse(self.calls.exists())
