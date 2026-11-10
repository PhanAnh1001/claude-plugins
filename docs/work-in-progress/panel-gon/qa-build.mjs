import {writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {compileDirectoryPlugin} from '/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli/node_modules/@getpaseo/server/dist/server/server/plugins/compiler-build.js';
import {loadEsbuild} from '/Users/anhtp/.nvm/versions/node/v24.19.0/lib/node_modules/@getpaseo/cli/node_modules/@getpaseo/server/dist/server/server/plugins/compiler-esbuild.js';
const started=Date.now();
try {
const result=await compileDirectoryPlugin('/Users/anhtp/app/claude-plugins/hybrid-hands/paseo-hh-tree','0.15.0');
const artifact={ok:true,compiler:'Paseo 0.15.0 compileDirectoryPlugin',id:result.manifest.id,elapsed_ms:Date.now()-started};
for(const key of ['clientBundle','serverBundle']) artifact[key]={bytes:Buffer.byteLength(result[key]??''),sha256:createHash('sha256').update(result[key]??'').digest('hex')};
if(!artifact.clientBundle.bytes||!artifact.serverBundle.bytes)throw Error('Missing bundle');
writeFileSync(new URL('./final-build.json',import.meta.url),JSON.stringify(artifact,null,2)+'\n');
console.log(JSON.stringify(artifact));

} finally { loadEsbuild().stop(); }
