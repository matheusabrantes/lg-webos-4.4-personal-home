/* Disable our boot hook and request guarded rollback; never unmount an unknown overlay. */
'use strict';
var fs=require('fs'),crypto=require('crypto'),cp=require('child_process');
var base='/var/lib/personalhome',hook='/var/lib/webosbrew/init.d/90-personalhome';
function check(v,m){if(!v)throw Error(m);}
function safe(p,directory){var s=fs.lstatSync(p);check(!s.isSymbolicLink()&&s.uid===0&&(s.mode&18)===0&&(directory?s.isDirectory():s.isFile()&&s.nlink===1),'Unsafe owned path:'+p);}
function read(p){safe(p,false);return fs.readFileSync(p);}
function hash(p){return crypto.createHash('sha256').update(read(p)).digest('hex');}
function luna(method,args){var result=cp.spawnSync('/usr/bin/timeout',['-t','2','/usr/bin/luna-send','-n','1','-w','1000','luna://'+method,JSON.stringify(args||{})],{encoding:'utf8'});check(!result.error&&result.status===0,'Bounded native recovery command failed');var reply=JSON.parse(result.stdout.slice(result.stdout.indexOf('{')));check(reply.returnValue===true,'Native startup input recovery rejected');return reply;}
function saveNew(p,b){var fd=fs.openSync(p,'wx',384);try{var bytes=Buffer.isBuffer(b)?b:new Buffer(b),offset=0;while(offset<bytes.length){var n=fs.writeSync(fd,bytes,offset,bytes.length-offset,null);check(n>0,'Incomplete durable write');offset+=n;}fs.fsyncSync(fd);}finally{fs.closeSync(fd);}}
function main(){
 var validation=process.argv.length===4&&process.argv[2]==='--rollback-validation-approved'&&/^\/var\/lib\/personalhome-validation\.[a-f0-9]{32}$/.test(process.argv[3]);
 check(validation||process.argv.length===3&&process.argv[2]==='--rollback-approved','Use the approved production or validation rollback');
 if(validation){base=process.argv[3];hook='/var/lib/webosbrew/init.d/89-personalhome-validation';}
 check(typeof process.getuid==='function'&&process.getuid()===0,'Root required');safe(base,true);
 var installed=JSON.parse(read(base+'/installed.json'));
 check(installed.schema===1&&/^[a-f0-9]{32}$/.test(installed.nonce)&&installed.originalSha==='5d2c9872f8b2c918c605cd05a7c49844645a8b683d8c1f8ee55f7bb1be6738e9','Invalid installation receipt');
 check(!validation||base==='/var/lib/personalhome-validation.'+installed.nonce,'Validation receipt identity differs');
 if(!fs.existsSync(base+'/disabled'))saveNew(base+'/disabled',JSON.stringify({reason:'manual-rollback',nonce:installed.nonce})+'\n');
 var recoveryErrors=[];
 if(fs.existsSync(base+'/startup-config.json')||fs.existsSync(base+'/startup-input.json')){
  var release=base+'/release',raw=read(release+'/release.json'),spec=JSON.parse(raw);
  check(crypto.createHash('sha256').update(raw).digest('hex')===installed.releaseSha256&&spec.nonce===installed.nonce,'Release receipt differs before startup restoration');
  check(spec.files&&hash(release+'/policy.js')===spec.files['policy.js'],'Untrusted startup recovery policy');
  var policy=require(release+'/policy.js');
  try{policy.restoreStartupInput(fs,crypto,base,installed.nonce,luna);}catch(inputError){recoveryErrors.push(String(inputError));}
  try{policy.restoreStartupConfig(fs,crypto,base);}catch(configError){recoveryErrors.push(String(configError));}
 }
 if(fs.existsSync(hook)){check(hash(hook)===installed.bootHookSha256,'Foreign hook preserved; disabled latch already set');check(!fs.existsSync(base+'/boot-hook.disabled'),'Preserving existing hook backup');fs.renameSync(hook,base+'/boot-hook.disabled');}
 var runtime='/tmp/lg-native-production.'+installed.nonce,requested=false;
 if(fs.existsSync(runtime)){
  safe(runtime,true);var m=JSON.parse(read(runtime+'/manifest.json'));
  check(m.directory===runtime&&m.nonce===installed.nonce&&m.stateDirectory===base&&m.original===runtime+'/original'&&m.candidate===runtime+'/candidate'&&m.target==='/usr/bin/surface-manager-starfish'&&m.originalSha===installed.originalSha&&m.candidateSha===installed.candidateSha,'Runtime identity differs');
  check(hash(m.original)===installed.originalSha,'Original runtime backup changed');
  if(!fs.existsSync(runtime+'/abort.json'))saveNew(runtime+'/abort.json',JSON.stringify({reason:'manual-rollback'})+'\n');requested=true;
 }
 console.log(JSON.stringify({status:'boot-disabled-rollback-requested',runtimeRequest:requested,verifiedOriginalRestored:false,requiresReadback:true,coldPowerCycleSkipsOurHook:true,startupRecoveryErrors:recoveryErrors}));
 if(recoveryErrors.length){console.error(recoveryErrors.join('\n'));process.exitCode=1;}
}
try{main();}catch(e){console.error(String(e));process.exitCode=1;}
