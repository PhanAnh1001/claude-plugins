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
