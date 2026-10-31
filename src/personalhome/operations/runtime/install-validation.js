'use strict';
var fs=require('fs'),crypto=require('crypto'),cp=require('child_process');
var originalSha='5d2c9872f8b2c918c605cd05a7c49844645a8b683d8c1f8ee55f7bb1be6738e9';
var createdBase=null,createdHook=null,createdHookSha=null;
function check(v,m){if(!v)throw Error(m);}
function sha(data){return crypto.createHash('sha256').update(data).digest('hex');}
function directory(p){var s=fs.lstatSync(p);check(s.isDirectory()&&!s.isSymbolicLink()&&s.uid===0&&(s.mode&18)===0,'Unsafe directory '+p);}
function file(p){var s=fs.lstatSync(p);check(s.isFile()&&!s.isSymbolicLink()&&s.uid===0&&s.nlink===1&&(s.mode&18)===0,'Unsafe file '+p);return fs.readFileSync(p);}
function write(p,data,mode){var fd=fs.openSync(p,'wx',mode),bytes=Buffer.isBuffer(data)?data:new Buffer(data),offset=0;try{while(offset<bytes.length){var n=fs.writeSync(fd,bytes,offset,bytes.length-offset,null);check(n>0,'Incomplete write');offset+=n;}fs.fsyncSync(fd);}finally{fs.closeSync(fd);}}
function parents(p,base){var parts=p.slice(base.length+1).split('/'),cur=base;for(var i=0;i<parts.length-1;i++){cur+='/'+parts[i];if(!fs.existsSync(cur))fs.mkdirSync(cur,448);directory(cur);}}
function command(cmd,args){var p=cp.spawnSync('/usr/bin/timeout',['-t','12',cmd].concat(args),{encoding:'utf8'});check(!p.error&&p.status===0,'Preflight command failed');return p.stdout;}
function main(){
 check((process.argv.length===6||process.argv.length===7)&&process.argv[2]==='--install-validation-approved','Explicit physical-session approval required');
 var stage=process.argv[3],expected=process.argv[4],mode=process.argv[5];
 var sessionDeadline=process.argv.length===7?Number(process.argv[6]):null;
 check(sessionDeadline===null||isFinite(sessionDeadline)&&Math.floor(sessionDeadline)===sessionDeadline&&sessionDeadline>Date.now()&&sessionDeadline<=Date.now()+1500000,'Invalid remaining session deadline');
 check(/^\/tmp\/personalhome-release\.[a-f0-9]{32}$/.test(stage)&&/^[a-f0-9]{64}$/.test(expected)&&['manual','boot-session'].indexOf(mode)>=0,'Invalid validation arguments');
 check(typeof process.getuid==='function'&&process.getuid()===0,'Root required');directory(stage);directory('/var/lib/webosbrew/init.d');
 var raw=file(stage+'/release.json');check(sha(raw)===expected,'Staging manifest differs');var m=JSON.parse(raw);
 check(m.schema===1&&m.healthSchema===3&&m.originalSha===originalSha&&/^[a-f0-9]{32}$/.test(m.nonce)&&stage==='/tmp/personalhome-release.'+m.nonce&&m.runtimeDirectory==='/tmp/lg-native-production.'+m.nonce,'Invalid validation release');
 var base='/var/lib/personalhome-validation.'+m.nonce,hook='/var/lib/webosbrew/init.d/89-personalhome-validation';
 check(!fs.existsSync(base)&&!fs.existsSync(hook)&&!fs.existsSync(m.runtimeDirectory),'Existing validation state preserved');
 directory('/var/lib/personalhome');file('/var/lib/personalhome/disabled');check(!fs.existsSync('/var/lib/webosbrew/init.d/90-personalhome'),'Production Home must remain disabled');
 check(sha(file('/usr/bin/surface-manager-starfish'))===originalSha,'Original compositor target required');
 check(fs.readlinkSync('/proc/self/ns/mnt')===fs.readlinkSync('/proc/1/ns/mnt'),'Mount namespace differs');
 var pid=command('/bin/pidof',['surface-manager-starfish']).trim();check(/^\d+$/.test(pid)&&fs.readlinkSync('/proc/'+pid+'/exe')==='/usr/bin/surface-manager-starfish'&&sha(fs.readFileSync('/proc/'+pid+'/exe'))===originalSha,'One original compositor process required');
 var names=Object.keys(m.files),bytes={};check(names.length>=250&&names.length<=400,'Unexpected payload size');
 names.forEach(function(n){check(/^(?:original|candidate|guard.js|bootstrap.js|rollback.js|policy.js|module\/YSM\/[A-Za-z0-9_.\/-]+)$/.test(n)&&n.indexOf('..')<0&&/^[a-f0-9]{64}$/.test(m.files[n]),'Invalid source path');bytes[n]=file(stage+'/'+n);check(sha(bytes[n])===m.files[n],'Source changed '+n);});
 check(sha(bytes.original)===originalSha&&sha(bytes.candidate)===m.candidateSha&&bytes['policy.js'],'Missing verified recovery components');
 var preserved=null;
 if(fs.existsSync('/tmp/YSM')){
  directory('/tmp/YSM');var owner=file('/tmp/YSM/.trial-owner').toString(),priorBase='/var/lib/personalhome';
  check(/^[a-f0-9]{32}$/.test(owner),'Unknown existing module');
  var productionReceipt=JSON.parse(file(priorBase+'/installed.json'));
  if(owner!==productionReceipt.nonce){
   priorBase='/var/lib/personalhome-validation.'+owner;directory(priorBase);file(priorBase+'/disabled');
   var restored=JSON.parse(file('/tmp/lg-native-production.'+owner+'/restored.json'));
   check(restored.originalSha===originalSha&&restored.mountAbsent===true&&restored.usableInterface===true,'Previous validation restoration is unverified');
  }
  var installed=JSON.parse(file(priorBase+'/installed.json')),priorRaw=file(priorBase+'/release/release.json'),prior=JSON.parse(priorRaw);
  check(sha(priorRaw)===installed.releaseSha256&&prior.nonce===installed.nonce&&owner===prior.nonce,'Unknown existing module');
  Object.keys(prior.files).filter(function(n){return n.indexOf('module/YSM/')===0;}).forEach(function(n){check(sha(file('/tmp/'+n.slice(7)))===prior.files[n],'Existing module differs '+n);});
  preserved='/tmp/personalhome-module-before-validation.'+m.nonce;check(!fs.existsSync(preserved),'Module backup exists');
 }
 // All sources and prior module identities are checked before writing validation state.
 fs.mkdirSync(base,448);createdBase=base;fs.mkdirSync(base+'/release',448);
 names.forEach(function(n){var p=base+'/release/'+n;parents(p,base+'/release');write(p,bytes[n],384);});write(base+'/release/release.json',raw,384);
 var hookText='#!/bin/sh\numask 077\n/usr/bin/node '+base+'/release/bootstrap.js --validate '+base+' < /dev/null >> '+base+'/boot.log 2>&1 &\n';
 write(base+'/installed.json',JSON.stringify({schema:1,nonce:m.nonce,releaseSha256:expected,bootHookSha256:sha(hookText),originalSha:originalSha,candidateSha:m.candidateSha,temporary:true,preservedModule:preserved})+'\n',384);
 var now=Date.now(),expiresAt=sessionDeadline===null?now+1500000:sessionDeadline,maxBoots=3;write(base+'/authorization.json',JSON.stringify({nonce:m.nonce,releaseSha256:expected,issuedAt:now,expiresAt:expiresAt,maxBoots:maxBoots})+'\n',384);write(base+'/enabled','enabled\n',384);
 if(preserved)fs.renameSync('/tmp/YSM',preserved);
 if(mode==='boot-session'){createdHook=hook;createdHookSha=sha(hookText);write(hook,hookText,448);}
 var log=fs.openSync(base+'/boot.log','a',384),child=cp.spawn('/usr/bin/node',[base+'/release/bootstrap.js','--validate',base],{detached:true,stdio:['ignore',log,log]});fs.closeSync(log);child.unref();
 console.log(JSON.stringify({temporary:true,activationRequested:true,physicalAcceptanceRequired:true,productionHomeStillDisabled:true,base:base,expiresAt:expiresAt,maxBoots:maxBoots,recoveryReserveSeconds:300,bootHook:mode==='boot-session'?hook:null,preservedModule:preserved}));
}
try{main();}catch(error){
 if(createdBase){
  try{if(!fs.existsSync(createdBase+'/disabled'))write(createdBase+'/disabled',JSON.stringify({reason:'validation-setup-failed'})+'\n',384);}catch(disableError){console.error('Disable latch failed: '+String(disableError));}
  try{if(createdHook&&fs.existsSync(createdHook)&&sha(file(createdHook))===createdHookSha)fs.renameSync(createdHook,createdBase+'/setup-failed-hook');}catch(hookError){console.error('Hook preserved for recovery: '+String(hookError));}
 }
 console.error(String(error));process.exitCode=1;
}
