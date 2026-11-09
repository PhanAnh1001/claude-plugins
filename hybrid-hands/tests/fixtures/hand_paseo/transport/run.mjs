// Public fake data only. Persist calls so independent bridge processes model ACK loss.
import {readFile, writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const {handleRequest, validatePackage} = await import(pathToFileURL(process.argv[2]));
await validatePackage(process.argv[3]);
const file = process.argv[4];
const state = JSON.parse(await readFile(file, 'utf8'));
let input=''; for await (const x of process.stdin) input+=x;
const request=JSON.parse(input);
const save=async()=>writeFile(file,JSON.stringify(state));
const mutate=async(name,args,fn)=>{
  state.calls.push({name,args}); fn(); await save();
  if(state.lose===name){state.lose=null;await save();throw new Error('PRIVATE ERROR MUST NOT ESCAPE');}
};
const client={
  async fetchAgent({agentId}) {return {agent:state.agents[agentId]??null};},
  async fetchWorkspaces(options){
    if('includeArchived' in options.filter) throw new Error('invented option');
    return {entries:Object.values(state.workspaces).filter(x=>!x.archivedAt),pageInfo:{nextCursor:null}};
  },
  async listAvailableProviders(){return {providers:[{provider:'hh-hand-codex',available:true}]};},
  async createWorkspace(options){await mutate('createWorkspace',options,()=>{
    state.workspaces[options.workspaceId]={id:options.workspaceId,projectId:options.source.projectId,
      workspaceDirectory:options.source.path};
  });return {workspace:state.workspaces[options.workspaceId]};},
  async createAgent(wire){
    const options={...wire,...wire.config};await mutate('createAgent',options,()=>{
    state.agents[options.agentId]={id:options.agentId,provider:options.provider,cwd:options.cwd,
      workspaceId:options.workspaceId,model:options.model,thinkingOptionId:options.thinkingOptionId,labels:{'paseo.parent-agent-id':options.callerAgentId},archivedAt:null};
  });return state.agents[options.agentId];},
  async sendMessage(agentId,text,options){await mutate('sendMessage',{agentId,text,options},()=>{
    state.entries.push({item:{type:'user_message',messageId:options.messageId}});
  });return {};},
  async fetchAgentTimeline(agentId){return {agentId,entries:state.entries};},
  async cancelAgent(agentId){await mutate('cancelAgent',{agentId},()=>{});},
  async archiveAgent(agentId){await mutate('archiveAgent',{agentId},()=>{
    state.agents[agentId].archivedAt='2026-11-09T00:00:00Z';
  });return {archivedAt:state.agents[agentId].archivedAt};},
  async inspectWorkspaceRecovery(workspaceId){return state.recovery??{workspaceId,kind:'unavailable',reason:'workspace_not_archived'};},
  async restoreWorkspace(workspaceId){await mutate('restoreWorkspace',{workspaceId},()=>{state.workspaces[workspaceId].archivedAt=null;});},
  async refreshAgent(agentId){await mutate('refreshAgent',{agentId},()=>{state.agents[agentId].archivedAt=null;});},
};
// Explicit injectable boundary: production loads official schemas, this fake checks
// the wire contract fields used by the synthetic lifecycle.
const schema = required => ({safeParse(value) {
  const issues=required.filter(k=>typeof value[k] !== 'string').map(k=>({path:[k],code:'invalid_type'}));
  return issues.length ? {success:false,error:{issues}} : {success:true,data:value};
}});
const schemas={WorkspaceCreateRequestSchema:schema(['requestId','workspaceId']),
  AgentCreateRequestSchema:{safeParse(value) {return schema(['provider','cwd']).safeParse(value.config??{});}},
  SendAgentMessageRequestSchema:schema(['requestId','text','agentId'])};
const result=await handleRequest(client,request,state.target,schemas);
await save();
process.stdout.write(JSON.stringify(result));
