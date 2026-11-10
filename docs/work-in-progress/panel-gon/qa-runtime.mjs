import {writeFileSync} from 'node:fs';
import {connectToDaemon} from '/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli/dist/utils/client.js';
import {selectDaemonTarget} from '/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli/dist/utils/daemon-target.js';
const client=await connectToDaemon({target:selectDaemonTarget({}),timeout:15000});
try {
 const result=await client.invokePluginRpc('hh-tree','hh-tree.get',{agentId:process.env.PASEO_AGENT_ID});
 if (!result.ok) throw new Error('TREE_RPC_FAILED');
 const ids=new Map(); const id=(v)=>{if (!v) return null;if(!ids.has(v))ids.set(v,`session-${ids.size+1}`);return ids.get(v)};
 const usage=(u)=>u?Object.fromEntries(['usd','usd_estimated','account_plan','account_5h_pct','account_week_pct','gpt_5h_pct','gpt_week_pct','week_pct','week_pct_estimated'].filter(k=>k in u).map(k=>[k,u[k]])):null;
 const meta=(r)=>Object.fromEntries(['status','state','live','model','effort','started_at','ended_at','last_activity','duration_seconds','exit','exit_code'].filter(k=>k in r).map(k=>[k,r[k]]));
 const sessions=result.tree.sessions.map((s,i)=>({...meta(s),session_id:id(s.session_id),parent_session:id(s.parent_session),name:`Phiên ${i+1}`,side_name:s.side_name?`Phụ ${i+1}`:null,is_main:s.is_main,cwd:'',transcript_path:null,context_tokens:null,token_cap:null,token_ratio:null,project_slug:'sample',usage:usage(s.usage),subagents:s.subagents.map((a,j)=>({...meta(a),agent_id:`agent-${j+1}`,agent_type:`Subagent ${j+1}`,description:'',context_tokens:null,usage:usage(a.usage)})),hand_runs:s.hand_runs.map((r,j)=>({...meta(r),run_id:`hand-${j+1}`,label:`Hand ${j+1}`,backend:r.backend,parent_session:id(r.parent_session),tokens:{input:0,cached_input:0,output:0},pid:null,child_pid:null,usage:usage(r.usage)}))}));
 const safe={schema:result.tree.schema,generated_at:result.tree.generated_at,since_seconds:result.tree.since_seconds,cwd:'',all_projects:false,main_session_id:id(result.tree.main_session_id),limits:result.tree.limits??[],sessions,orphan_runs:[],totals:result.tree.totals};
 writeFileSync(new URL('./runtime-sanitized.json',import.meta.url),JSON.stringify(safe,null,2)+'\n');
 const native=await client.listProviderSubagents(process.env.PASEO_AGENT_ID);
 const summary={rpc_ok:true,sessions:sessions.length,subagents:sessions.reduce((n,s)=>n+s.subagents.length,0),hand_runs:sessions.reduce((n,s)=>n+s.hand_runs.length,0),orphan_count:result.tree.orphan_runs.length,native_error:!!native.error,native_count:native.subagents?.length??0,native_fields:native.subagents?.[0]?Object.keys(native.subagents[0]):[],native_in_tree:(native.subagents??[]).filter(n=>result.tree.sessions.some(s=>s.session_id===n.id||s.subagents.some(a=>a.agent_id===n.id))).length};
 writeFileSync(new URL('./runtime-metadata.json',import.meta.url),JSON.stringify(summary,null,2)+'\n'); console.log(JSON.stringify(summary));
} finally {await client.close();}
