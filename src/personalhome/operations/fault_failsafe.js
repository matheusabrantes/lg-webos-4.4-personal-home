/* One-shot safety net for specifically approved physical fault tests; never a production hook. */
'use strict';
var fs=require('fs'),crypto=require('crypto'),cp=require('child_process');
function check(v,message){if(!v)throw Error(message);}
function sha(p){return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');}
var runtime=process.argv[2],legacy=process.argv[3],legacySha=process.argv[4];
check(process.argv.length===5&&/^\/tmp\/lg-native-production\.[a-f0-9]{32}$/.test(runtime),'Invalid fault-test runtime');
check(/^\/tmp\/personalhome-release\.[a-f0-9]{32}\/legacy-guard.js$/.test(legacy)&&/^[a-f0-9]{64}$/.test(legacySha)&&sha(legacy)===legacySha,'Unknown backup actuator');
var stat=fs.lstatSync(runtime);check(stat.isDirectory()&&!stat.isSymbolicLink()&&stat.uid===0&&(stat.mode&511)===448,'Unsafe runtime');
var m=JSON.parse(fs.readFileSync(runtime+'/manifest.json','utf8'));
check(runtime==='/tmp/lg-native-production.'+m.nonce&&m.stateDirectory==='/var/lib/personalhome-validation.'+m.nonce&&m.original===runtime+'/original'&&m.candidate===runtime+'/candidate'&&m.target==='/usr/bin/surface-manager-starfish'&&m.originalSha==='5d2c9872f8b2c918c605cd05a7c49844645a8b683d8c1f8ee55f7bb1be6738e9'&&sha(m.original)===m.originalSha,'Fault-test identity differs');
check(fs.readlinkSync('/proc/self/ns/mnt')===m.namespace&&fs.readlinkSync('/proc/1/ns/mnt')===m.namespace,'Unexpected mount namespace');
function ownedTarget(){
 var entries=fs.readFileSync('/proc/self/mountinfo','utf8').trim().split('\n').map(function(s){return s.split(' ');}).filter(function(row){return row[4]===m.target;});
 if(!entries.length)return sha(m.target)===m.originalSha;
 var s=fs.statSync(m.target);
 return entries.length===1&&entries[0][3]===runtime.slice(4)+'/candidate'&&String(s.dev)+':'+String(s.ino)===m.candidateIdentity&&fs.readFileSync(runtime+'/mount-id','utf8').trim()===entries[0][0];
}
check(ownedTarget(),'Unknown target mount; fault test refused');
function write(name,value){fs.writeFileSync(runtime+'/'+name,JSON.stringify(value)+'\n',{mode:384});}
function run(command,args,seconds){var r=cp.spawnSync('/usr/bin/timeout',['-t',String(seconds),command].concat(args),{encoding:'utf8'});check(!r.error&&r.status===0,'Backup command failed');return r.stdout;}
function luna(method,args){var raw=run('/usr/bin/luna-send',['-n','1','-w','1000','luna://'+method,JSON.stringify(args||{})],2);return JSON.parse(raw.slice(raw.indexOf('{')));}
function ownedActor(actor){
 var p=JSON.parse(fs.readFileSync(runtime+'/'+actor+'-pid.json','utf8'));check(p.pid>1,'Invalid actor PID');
 try{var raw=fs.readFileSync('/proc/'+p.pid+'/stat','utf8');return raw.slice(raw.lastIndexOf(')')+2).split(' ')[19]===p.start?p.pid:null;}catch(error){return null;}
}
write('fault-failsafe-armed.json',{seconds:90,hostIndependent:true,legacySha256:legacySha});
setTimeout(function(){
 try{
  if(sha(m.target)===m.originalSha){
   var receipt=null;try{receipt=JSON.parse(fs.readFileSync(runtime+'/restored.json','utf8'));}catch(error){}
   if(receipt&&receipt.usableInterface===true){write('fault-failsafe-result.json',{used:false,reason:'new-guard-recovered'});return;}
  }
  write('fault-failsafe-result.json',{used:true,reason:'new-recovery-not-confirmed',newGuardTestPassed:false});
  check(ownedTarget()&&sha(legacy)===legacySha,'Recovery ownership or backup source changed');
  try{if(!fs.existsSync(m.disableFile))fs.writeFileSync(m.disableFile,JSON.stringify({reason:'fault-test-safety-net'})+'\n',{mode:384,flag:'wx'});}catch(disableError){write('fault-failsafe-latch-error.json',{error:String(disableError)});}
  ['primary','lifeline'].forEach(function(actor){try{var pid=ownedActor(actor);if(pid)process.kill(pid,'SIGKILL');}catch(error){}});
  var saved=JSON.parse(JSON.stringify(m));saved.disableFile='/var/lib/personalhome/disabled';
  fs.writeFileSync(runtime+'/manifest-before-failsafe.json',JSON.stringify(m)+'\n',{mode:384});
  fs.writeFileSync(runtime+'/manifest.json',JSON.stringify(saved)+'\n',{mode:384});
  // The independently preserved, previously exercised actuator verifies the exact owned bind before unmounting.
  run('/usr/bin/node',[legacy,runtime+'/manifest.json','restore'],60);
  check(sha(m.target)===m.originalSha,'Original compositor not restored');
  var app=/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(m.restoreAppId)?m.restoreAppId:'com.webos.app.livetv';
  var reply=luna('com.webos.applicationManager/launch',{id:app});
  if(!reply.returnValue)luna('com.webos.service.networkinput/sendSpecialKey',{key:'HOME'});
  write('fault-failsafe-finished.json',{originalRestored:true,foregroundLaunchAcknowledged:reply.returnValue===true,newGuardTestPassed:false});
 }catch(error){write('fault-failsafe-error.json',{error:String(error),requiresManualRecovery:true});}
},90000);
