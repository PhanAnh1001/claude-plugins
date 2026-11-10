import {readFileSync,writeFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {resolve} from 'node:path';
const require=createRequire('/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli/package.json');
const {build,stop}=require('esbuild');
const repo='/Users/anhtp/app/claude-plugins';
const theme={colors:Object.fromEntries(['foreground','foregroundMuted','accent','statusSuccess','statusWarning','statusDanger','border'].map(k=>[k,k]))};
const stub={name:'qa-native',setup(b){b.onResolve({filter:/^(react-native|react\/jsx-runtime)$/},a=>({path:a.path,namespace:'qa'}));b.onLoad({filter:/.*/,namespace:'qa'},a=>({contents:a.path==='react-native'?`export const View='View',Text='Text',Pressable='Pressable';`:`export const Fragment='Fragment';export const jsx=(type,props)=>({type,props});export const jsxs=jsx;`,loader:'js'}));}};
function inline(v){if(v==null||typeof v==='boolean')return '';if(Array.isArray(v))return v.map(inline).join('');if(typeof v==='string'||typeof v==='number')return String(v);if(typeof v.type==='function')return inline(v.type(v.props));return inline(v.props.children);}
function lines(v,indent=0){if(v==null||typeof v==='boolean')return [];if(Array.isArray(v))return v.flatMap(n=>lines(n,indent));if(typeof v==='string'||typeof v==='number')return [' '.repeat(indent)+String(v)];if(typeof v.type==='function')return lines(v.type(v.props),indent);if(v.type==='Text')return [' '.repeat(indent)+inline(v.props.children)];return lines(v.props.children,indent+Math.round((v.props.style?.paddingLeft??0)/8));}
async function render(directory,tree){
 const built=await build({entryPoints:[resolve(directory,'client/SessionBlock.tsx')],bundle:true,write:false,format:'cjs',platform:'node',jsx:'automatic',plugins:[stub],logLevel:'silent'});
 const module={exports:{}};new Function('module','exports',built.outputFiles[0].text)(module,module.exports);
 const {nestSessions}=await import(`${repo}/hybrid-hands/paseo-hh-tree/client/nest.ts`);
 const nested=nestSessions(tree.sessions);const props={depth:0,theme,compact:true,now:Date.parse(tree.generated_at),expanded:{},onToggle(){}};
 return [...nested.roots.flatMap(session=>lines(module.exports.SessionBlock({...props,session}))),...lines(module.exports.OrphanSideBlock({...props,sessions:nested.orphanSides}))].join('\n')+'\n';
}
try {
 const tree=JSON.parse(readFileSync(new URL('./runtime-sanitized.json',import.meta.url),'utf8'));
 const before=await render(`${repo}/docs/work-in-progress/panel-gon/baseline/hybrid-hands/paseo-hh-tree`,tree);
 const after=await render(`${repo}/hybrid-hands/paseo-hh-tree`,tree);
 writeFileSync(new URL('./panel-before.txt',import.meta.url),before);writeFileSync(new URL('./panel-after.txt',import.meta.url),after);
 console.log(JSON.stringify({source:'real hh-tree.get metadata, sanitized before render',renderer:'SessionBlock actual JSX via native host stubs; no device screenshot',before_lines:before.trim().split('\n').length,after_lines:after.trim().split('\n').length}));
}finally{stop();}
