/* Persistent installation candidate. Requires the consolidated user approval; not executed here. */
'use strict';
var fs=require('fs'),crypto=require('crypto'),cp=require('child_process');
var base='/var/lib/personalhome',hook='/var/lib/webosbrew/init.d/90-personalhome';
var createdBase=false,createdHook=false;
var hookText='#!/bin/sh\numask 077\n/usr/bin/node /var/lib/personalhome/release/bootstrap.js --start > /var/lib/personalhome/boot.log 2>&1 &\n';
function check(v,m){if(!v)throw Error(m);}
function sha(b){return crypto.createHash('sha256').update(b).digest('hex');}
function file(p){var s=fs.lstatSync(p);check(s.isFile()&&!s.isSymbolicLink()&&s.uid===0&&s.nlink===1&&(s.mode&18)===0,'Unsafe source:'+p);return fs.readFileSync(p);}
function directory(p){var s=fs.lstatSync(p);check(s.isDirectory()&&!s.isSymbolicLink()&&s.uid===0&&(s.mode&18)===0,'Unsafe directory:'+p);}
function write(p,b,mode){var fd=fs.openSync(p,'wx',mode);try{var bytes=Buffer.isBuffer(b)?b:new Buffer(b),offset=0;while(offset<bytes.length){var n=fs.writeSync(fd,bytes,offset,bytes.length-offset,null);check(n>0,'Incomplete durable write');offset+=n;}fs.fsyncSync(fd);}finally{fs.closeSync(fd);}}
function parents(p,root){var parts=p.slice(root.length+1).split('/'),cur=root;for(var i=0;i<parts.length-1;i++){cur+='/'+parts[i];if(!fs.existsSync(cur))fs.mkdirSync(cur,448);directory(cur);}}
function main(){
 check(process.argv.length===5&&process.argv[2]==='--install-approved','Consolidated user approval required; use --install-approved STAGEDIR RELEASE_SHA');
 check(typeof process.getuid==='function'&&process.getuid()===0,'Root required');
 var stage=process.argv[3],expected=process.argv[4];
 check(/^\/tmp\/personalhome-release\.[a-f0-9]{32}$/.test(stage)&&/^[a-f0-9]{64}$/.test(expected),'Invalid staging identity');
 directory(stage);directory('/var/lib/webosbrew/init.d');
 check(!fs.existsSync(base)&&!fs.existsSync(hook)&&!fs.existsSync('/tmp/YSM'),'Existing installation/module preserved; refusing overwrite');
 var raw=file(stage+'/release.json');check(sha(raw)===expected,'Release manifest hash mismatch');var m=JSON.parse(raw);
 check(m.schema===1&&m.healthSchema===3&&m.files['policy.js']&&m.originalSha==='5d2c9872f8b2c918c605cd05a7c49844645a8b683d8c1f8ee55f7bb1be6738e9'&&/^[a-f0-9]{32}$/.test(m.nonce)&&m.runtimeDirectory==='/tmp/lg-native-production.'+m.nonce,'Invalid release');
 var names=Object.keys(m.files),bytes={};check(names.length>=250&&names.length<=400,'Unexpected release size');
 names.forEach(function(n){check(/^(?:original|candidate|guard.js|bootstrap.js|rollback.js|policy.js|module\/YSM\/[A-Za-z0-9_.\/-]+)$/.test(n)&&n.indexOf('..')<0&&/^[a-f0-9]{64}$/.test(m.files[n]),'Unsafe release path');bytes[n]=file(stage+'/'+n);check(sha(bytes[n])===m.files[n],'Release file changed:'+n);});
 check(sha(bytes.original)===m.originalSha&&sha(bytes.candidate)===m.candidateSha,'Executable identities differ');
 check(sha(file('/usr/bin/surface-manager-starfish'))===m.originalSha,'Original target required before installation');
 check(fs.readlinkSync('/proc/self/ns/mnt')===fs.readlinkSync('/proc/1/ns/mnt'),'Wrong mount namespace');
 var running=cp.spawnSync('/usr/bin/timeout',['-t','12','/bin/pidof','surface-manager-starfish'],{encoding:'utf8'});check(!running.error&&running.status===0&&/^\d+$/.test(running.stdout.trim()),'One original compositor required');
 var proc='/proc/'+running.stdout.trim()+'/exe';check(fs.readlinkSync(proc)==='/usr/bin/surface-manager-starfish'&&sha(fs.readFileSync(proc))===m.originalSha,'Running original process required');
 // Every package byte is validated before creating persistent state or the boot hook.
 fs.mkdirSync(base,448);createdBase=true;fs.mkdirSync(base+'/release',448);
 names.forEach(function(n){var dest=base+'/release/'+n;parents(dest,base+'/release');write(dest,bytes[n],384);});
 write(base+'/release/release.json',raw,384);
 write(base+'/installed.json',JSON.stringify({schema:1,nonce:m.nonce,releaseSha256:expected,bootHookSha256:sha(hookText),originalSha:m.originalSha,candidateSha:m.candidateSha})+'\n',384);
 write(base+'/enabled','enabled\n',384);
 createdHook=true;write(hook,hookText,448);
 var log=fs.openSync(base+'/boot.log','a',384),child=cp.spawn('/usr/bin/node',[base+'/release/bootstrap.js','--start'],{detached:true,stdio:['ignore',log,log]});fs.closeSync(log);child.unref();
 console.log(JSON.stringify({status:'installed-activation-requested',physicalAcceptanceRequired:true,rollback:base+'/release/rollback.js',originalExecutableOverwritten:false}));
}
try{main();}catch(e){
 if(createdBase){
  try{if(!fs.existsSync(base+'/disabled'))write(base+'/disabled',JSON.stringify({reason:'installation-failed'})+'\n',384);}catch(disableError){console.error('Disable latch failed: '+String(disableError));}
  try{if(createdHook&&fs.existsSync(hook)&&sha(file(hook))===sha(hookText))fs.renameSync(hook,base+'/setup-failed-hook');}catch(hookError){console.error('Hook preserved for recovery: '+String(hookError));}
 }
 console.error(String(e));process.exitCode=1;
}
