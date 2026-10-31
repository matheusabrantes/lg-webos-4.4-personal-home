/* Daily Home bootstrap candidate. Installed execution requires a separate explicit approval. */
'use strict';
var fs=require('fs'),cp=require('child_process'),crypto=require('crypto');
var base='/var/lib/personalhome',release=base+'/release',target='/usr/bin/surface-manager-starfish',policy;
var diagnosticsReady=false,lastStage='',previousActivation=null,releaseNonce=null;
function check(v,m){if(!v)throw Error(m);}
function safeDirectory(p){var s=fs.lstatSync(p);check(s.isDirectory()&&!s.isSymbolicLink()&&s.uid===0&&(s.mode&18)===0,'Unsafe directory:'+p);}
function safeFile(p){var s=fs.lstatSync(p);check(s.isFile()&&!s.isSymbolicLink()&&s.uid===0&&(s.mode&18)===0&&s.nlink===1,'Unsafe file:'+p);return s;}
function hash(p){safeFile(p);return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');}
function run(command,args){var r=cp.spawnSync('/usr/bin/timeout',['-t','12',command].concat(args),{encoding:'utf8'});check(!r.error&&r.status===0,'Bounded command failed:'+command);return r.stdout;}
function save(p,value){fs.writeFileSync(p,JSON.stringify(value)+'\n',{mode:384});}
function durable(p,value){
 var temporary=p+'.'+bootIdentity()+'.new';fs.writeFileSync(temporary,JSON.stringify(value)+'\n',{mode:384,flag:'wx'});
 var fd=fs.openSync(temporary,'r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}fs.renameSync(temporary,p);
 fd=fs.openSync(p.slice(0,p.lastIndexOf('/')),'r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
}
function bootIdentity(){var boot=fs.readFileSync('/proc/sys/kernel/random/boot_id','utf8').trim();check(/^[a-f0-9-]{36}$/.test(boot),'Invalid kernel boot identity');return boot;}
function copyFile(a,b,mode){check(!fs.existsSync(b),'Destination exists:'+b);fs.writeFileSync(b,fs.readFileSync(a),{mode:mode});}
function mkdirParents(p,root){var tail=p.slice(root.length+1).split('/');var cur=root;for(var i=0;i<tail.length-1;i++){cur+='/'+tail[i];if(!fs.existsSync(cur))fs.mkdirSync(cur,448);safeDirectory(cur);}}
function stage(name,detail){
 var event={stage:name,bootId:null,nonce:releaseNonce,uptime:null,wallTimeMs:Date.now(),detail:detail||null};
 try{event.bootId=bootIdentity();event.uptime=parseFloat(fs.readFileSync('/proc/uptime','utf8'));}catch(identityError){}
 console.log(JSON.stringify(event));
 if(!diagnosticsReady||name===lastStage)return;lastStage=name;
 try{
  var p=base+'/bootstrap-events.jsonl';
  if(fs.existsSync(p)&&safeFile(p).size>=16384){if(fs.existsSync(p+'.1'))safeFile(p+'.1');fs.renameSync(p,p+'.1');}
  fs.appendFileSync(p,JSON.stringify(event)+'\n',{mode:384});
 }catch(error){console.error('Diagnostic write skipped: '+String(error));}
}
function luna(method,args){
 var raw=run('/usr/bin/luna-send',['-n','1','-w','1000','luna://'+method,JSON.stringify(args||{})]);
 var result=JSON.parse(raw.slice(raw.indexOf('{')));check(result.returnValue===true,'Native service rejected:'+method);return result;
}
function processStart(pid){var raw=fs.readFileSync('/proc/'+pid+'/stat','utf8');return raw.slice(raw.lastIndexOf(')')+2).split(' ')[19];}
function claim(spec){
 var lock=spec.runtimeDirectory+'.startup-lock';
 try{fs.mkdirSync(lock,448);}catch(error){
  if(error.code!=='EEXIST')throw error;
  safeDirectory(lock);safeFile(lock+'/owner.json');var owner=JSON.parse(fs.readFileSync(lock+'/owner.json','utf8'));
  check(owner.nonce===spec.nonce&&owner.pid>1,'Unknown startup owner');
  if(fs.existsSync(spec.runtimeDirectory)||fs.existsSync('/proc/'+owner.pid)&&processStart(owner.pid)===owner.start){stage('activation-already-owned');return false;}
  check(!fs.existsSync(lock+'.stale'),'Stale startup already preserved');fs.renameSync(lock,lock+'.stale');fs.mkdirSync(lock,448);
 }
 save(lock+'/owner.json',{nonce:spec.nonce,pid:process.pid,start:processStart(process.pid)});return true;
}
function validateSession(spec){
 safeFile(base+'/authorization.json');
 var auth=JSON.parse(fs.readFileSync(base+'/authorization.json','utf8')),now=Date.now();
 check(auth.nonce===spec.nonce&&auth.releaseSha256===hash(release+'/release.json'),'Validation authorization differs from release');
 check(typeof auth.issuedAt==='number'&&typeof auth.expiresAt==='number'&&now>=auth.issuedAt&&now<auth.expiresAt&&auth.expiresAt-auth.issuedAt<=14400000,'Validation session is not current');
 check(typeof auth.maxBoots==='number'&&auth.maxBoots>=1&&auth.maxBoots<=24&&Math.floor(auth.maxBoots)===auth.maxBoots,'Invalid boot allowance');
 var boot=bootIdentity();
 var count={bootId:'',count:0};
 if(fs.existsSync(base+'/boot-counter.json')){safeFile(base+'/boot-counter.json');count=JSON.parse(fs.readFileSync(base+'/boot-counter.json','utf8'));}
 check(typeof count.count==='number'&&count.count>=0&&Math.floor(count.count)===count.count,'Invalid boot counter');
 if(count.bootId!==boot){check(count.count<auth.maxBoots,'Validation boot allowance exhausted');count={bootId:boot,count:count.count+1};durable(base+'/boot-counter.json',count);}
 return auth.expiresAt;
}
function waitForBoot(){
 var gate={},until=Date.now()+75000,snapshot,identity;
 stage('waiting-native-boot');
 while(Date.now()<until){
  check(!fs.existsSync(base+'/disabled'),'Disabled while waiting for boot');
  try{snapshot={power:luna('com.webos.service.tvpower/power/getPowerState'),boot:luna('com.webos.bootManager/getBootStatus'),cover:luna('com.webos.coverUI/getStatus'),surface:luna('com.webos.surfacemanager/getForegroundAppInfo'),ui:luna('com.webos.surfacemanager/getCurrentState')};}
  catch(error){gate={};stage('waiting-native-services');run('/bin/sleep',['1']);continue;}
  var pid=run('/bin/pidof',['surface-manager-starfish']).trim();identity=/^\d+$/.test(pid)?pid+':'+processStart(pid):'';
  if(policy.bootGate(gate,snapshot,identity)){stage('native-first-app-ready');var intent=policy.bootIntent(snapshot);intent.identity=identity;return intent;}
  run('/bin/sleep',['1']);
 }
 throw Error('Native first app/cover did not settle; original compositor preserved');
}
function main(){
 var validation=process.argv.length===4&&process.argv[2]==='--validate'&&/^\/var\/lib\/personalhome-validation\.[a-f0-9]{32}$/.test(process.argv[3]);
 check(validation||process.argv.length===3&&process.argv[2]==='--start','Use --start or an approved validation directory');
 if(validation){base=process.argv[3];release=base+'/release';}
 stage('bootstrap-start');
 safeDirectory(base);safeDirectory(release);
 check((fs.lstatSync(base).mode&511)===448,'State directory must be0700');
 diagnosticsReady=true;
 var disabled=fs.existsSync(base+'/disabled');if(disabled)safeFile(base+'/disabled');
 safeFile(release+'/release.json');
 var spec=JSON.parse(fs.readFileSync(release+'/release.json','utf8'));
 releaseNonce=spec.nonce;
 check(!validation||base==='/var/lib/personalhome-validation.'+spec.nonce,'Validation identity mismatch');
 safeFile(base+'/installed.json');var installed=JSON.parse(fs.readFileSync(base+'/installed.json','utf8'));
 check(installed.nonce===spec.nonce&&installed.releaseSha256===hash(release+'/release.json'),'Installation receipt differs from release');
 check(spec.schema===1&&spec.originalSha==='5d2c9872f8b2c918c605cd05a7c49844645a8b683d8c1f8ee55f7bb1be6738e9'&&/^[a-f0-9]{32}$/.test(spec.nonce)&&spec.runtimeDirectory==='/tmp/lg-native-production.'+spec.nonce,'Invalid release identity');
 check(spec.files&&typeof spec.files==='object'&&!Array.isArray(spec.files),'Missing file map');
 var names=Object.keys(spec.files);check(names.length>=250&&names.length<=400,'Unexpected release size');
 names.forEach(function(n){check(/^(?:original|candidate|guard.js|bootstrap.js|rollback.js|policy.js|module\/YSM\/[A-Za-z0-9_.\/-]+)$/.test(n)&&n.indexOf('..')<0&&/^[a-f0-9]{64}$/.test(spec.files[n]),'Unsafe release file');check(hash(release+'/'+n)===spec.files[n],'Release hash mismatch:'+n);});
 check(spec.files['policy.js'],'Missing lifecycle policy');policy=require(release+'/policy.js');
 if(disabled){policy.restoreStartupInput(fs,crypto,base,spec.nonce,luna);policy.restoreStartupConfig(fs,crypto,base);stage('disabled-original-preserved',JSON.parse(fs.readFileSync(base+'/disabled','utf8')));return;}
 safeFile(base+'/enabled');check(fs.readFileSync(base+'/enabled','utf8')==='enabled\n','Invalid activation flag');
 var sessionExpiresAt=validation?validateSession(spec):null;
 check(hash(release+'/original')===spec.originalSha&&hash(release+'/candidate')===spec.candidateSha,'Executable changed');
 stage('release-verified');
 var bootId=bootIdentity();
 if(fs.existsSync(base+'/boot-activation.json')){
  safeFile(base+'/boot-activation.json');previousActivation=JSON.parse(fs.readFileSync(base+'/boot-activation.json','utf8'));
  check(previousActivation.nonce===spec.nonce&&/^[a-f0-9-]{36}$/.test(previousActivation.bootId)&&['prepared','applying','verified'].indexOf(previousActivation.phase)>=0,'Invalid previous boot activation');
  var interruptedBeforeApply=previousActivation.schema===2&&previousActivation.phase==='prepared';
  check(previousActivation.bootId===bootId||previousActivation.phase==='verified'||interruptedBeforeApply,'Previous boot never reached a usable interface');
  if(interruptedBeforeApply&&previousActivation.bootId!==bootId)stage('previous-boot-interrupted-before-apply',previousActivation);
 }
 if(!claim(spec))return;
 var intent=waitForBoot();
 durable(base+'/boot-activation.json',{schema:2,nonce:spec.nonce,bootId:bootId,phase:'prepared'});
 check(fs.readlinkSync('/proc/self/ns/mnt')===fs.readlinkSync('/proc/1/ns/mnt'),'Wrong mount namespace');
 check(hash(target)===spec.originalSha,'Original compositor target required');
 check(!fs.existsSync('/tmp/YSM')&&!fs.existsSync(spec.runtimeDirectory),'Another module/runtime exists');
 var p=run('/bin/pidof',['surface-manager-starfish']).trim();check(/^\d+$/.test(p),'One running original compositor required');
 check(fs.readlinkSync('/proc/'+p+'/exe')===target&&crypto.createHash('sha256').update(fs.readFileSync('/proc/'+p+'/exe')).digest('hex')===spec.originalSha,'Running original identity required');
 var raw=fs.readFileSync('/proc/'+p+'/stat','utf8'),start=raw.slice(raw.lastIndexOf(')')+2).split(' ')[19];
 check(intent.identity===p+':'+start,'Compositor changed after readiness; activation cancelled');
 fs.mkdirSync(spec.runtimeDirectory,448);fs.mkdirSync('/tmp/YSM',448);
 copyFile(release+'/original',spec.runtimeDirectory+'/original',448);copyFile(release+'/candidate',spec.runtimeDirectory+'/candidate',448);copyFile(release+'/guard.js',spec.runtimeDirectory+'/guard.js',384);copyFile(release+'/policy.js',spec.runtimeDirectory+'/policy.js',384);
 names.filter(function(n){return n.indexOf('module/YSM/')===0;}).forEach(function(n){var dest='/tmp/'+n.slice('module/'.length);mkdirParents(dest,'/tmp/YSM');copyFile(release+'/'+n,dest,384);});
 stage('module-copied');
 var s=fs.statSync(spec.runtimeDirectory+'/candidate');
 var m={kind:'native',stateDirectory:base,sessionExpiresAt:sessionExpiresAt,bootId:bootId,directory:spec.runtimeDirectory,target:target,original:spec.runtimeDirectory+'/original',candidate:spec.runtimeDirectory+'/candidate',originalSha:spec.originalSha,candidateSha:spec.candidateSha,candidateIdentity:s.dev+':'+s.ino,namespace:fs.readlinkSync('/proc/self/ns/mnt'),pid:Number(p),processStart:start,requireViewHealth:true,healthSchema:3,guardSha:spec.files['guard.js'],policySha:spec.files['policy.js'],restoreAppId:intent.appId,restoreHome:intent.home,startupBridge:intent.bridge,nonce:spec.nonce,failureRecoverySeconds:120,disableFile:base+'/disabled'};
 save(spec.runtimeDirectory+'/manifest.json',m);
 ['lifeline','primary'].forEach(function(role){var fd=fs.openSync(spec.runtimeDirectory+'/'+role+'.log','a',384);var child=cp.spawn('/usr/bin/node',[spec.runtimeDirectory+'/guard.js',spec.runtimeDirectory+'/manifest.json',role],{detached:true,stdio:['ignore',fd,fd]});fs.closeSync(fd);child.unref();});
 var until=Date.now()+5000;
 while(!(fs.existsSync(spec.runtimeDirectory+'/primary-pid.json')&&fs.existsSync(spec.runtimeDirectory+'/lifeline-pid.json'))){check(Date.now()<until,'Guard startup did not complete');run('/bin/sleep',['1']);}
 fs.writeFileSync(spec.runtimeDirectory+'/apply-request','apply\n',{mode:384});
 stage('activation-requested');
 save(base+'/last-session.json',{directory:spec.runtimeDirectory,nonce:spec.nonce});
 console.log(JSON.stringify({status:'activation-requested',directory:spec.runtimeDirectory,guarded:true,physicalAcceptanceRequired:true}));
}
try{main();}catch(e){
 try{if(policy)policy.restoreStartupInput(fs,crypto,base,releaseNonce,luna);}catch(inputError){console.error('Startup input restore failed: '+String(inputError));}
 try{if(policy)policy.restoreStartupConfig(fs,crypto,base);}catch(configError){console.error('Startup config restore failed: '+String(configError));}
 var failure={reason:'bootstrap-failed',error:String(e),bootId:null,nonce:releaseNonce,previousActivation:previousActivation};
 try{failure.bootId=bootIdentity();}catch(identityError){}
 try{safeDirectory(base);if(!fs.existsSync(base+'/disabled'))fs.writeFileSync(base+'/disabled',JSON.stringify(failure)+'\n',{mode:384,flag:'wx'});}catch(latchError){console.error('Disable latch failed: '+String(latchError));}
 stage('bootstrap-failed',failure);
 console.error(String(e));process.exitCode=1;
}
