/* Production candidate: healthy lifetime is unbounded; failures restore the original locally. Not installed. */
'use strict';
var fs=require('fs'), crypto=require('crypto'), cp=require('child_process');
var path=process.argv[2], role=process.argv[3], dir=path.slice(0,path.lastIndexOf('/'));
function fail(message){throw Error(message);}
if(!/^\/tmp\/lg-native-production\.[A-Za-z0-9]+\/manifest.json$/.test(path))fail('Unsafe manifest path');
if(['primary','lifeline','restore'].indexOf(role)<0)fail('Unknown guard role');
var ds=fs.lstatSync(dir), ms=fs.lstatSync(path);
if(!ds.isDirectory()||ds.isSymbolicLink()||ds.uid!==0||(ds.mode&63)!==0||!ms.isFile()||ms.isSymbolicLink()||ms.uid!==0||(ms.mode&63)!==0)fail('Unsafe trial ownership/mode');
var manifestBytes=fs.readFileSync(path),manifestHash=crypto.createHash('sha256').update(manifestBytes).digest('hex'),m=JSON.parse(manifestBytes.toString());
if(m.startupBridge!==undefined&&typeof m.startupBridge!=='boolean')fail('Invalid startup bridge intent');
if(m.healthSchema!==3||!/^[a-f0-9]{64}$/.test(m.guardSha)||!/^[a-f0-9]{64}$/.test(m.policySha)||typeof m.restoreHome!=='boolean'||!/^[a-f0-9-]{36}$/.test(m.bootId))fail('Missing runtime recovery contract');
if(m.kind!=='native'||m.directory!==dir||m.failureRecoverySeconds!==120||typeof m.nonce!=='string'||!/^([a-f0-9]{32})$/.test(m.nonce)||m.deadline!==undefined)fail('Invalid production manifest');
if(dir!=='/tmp/lg-native-production.'+m.nonce)fail('Runtime directory does not match nonce');
if((m.stateDirectory!=='/var/lib/personalhome'&&m.stateDirectory!=='/var/lib/personalhome-validation.'+m.nonce)||m.disableFile!==m.stateDirectory+'/disabled')fail('Invalid recovery state directory');
if(m.stateDirectory==='/var/lib/personalhome'?m.sessionExpiresAt!==null:typeof m.sessionExpiresAt!=='number'||!isFinite(m.sessionExpiresAt)||m.sessionExpiresAt>Date.now()+14400000)fail('Invalid validation lifetime');
var persistent=fs.lstatSync(m.stateDirectory);
if(!persistent.isDirectory()||persistent.isSymbolicLink()||persistent.uid!==0||(persistent.mode&511)!==448)fail('Unsafe persistent state directory');
if(m.kind!=='canary'&&(typeof m.pid!=='number'||m.pid<=1||Math.floor(m.pid)!==m.pid||!/^\d+$/.test(m.processStart)))fail('Invalid native process identity');
if(m.target!==(m.kind==='canary'?dir+'/target':'/usr/bin/surface-manager-starfish'))fail('Unexpected target');
if(m.original!==dir+'/original'||m.candidate!==dir+'/candidate'||!/^[a-f0-9]{64}$/.test(m.originalSha)||!/^[a-f0-9]{64}$/.test(m.candidateSha))fail('Invalid source identities');
if(fs.readlinkSync('/proc/self/ns/mnt')!==m.namespace||fs.readlinkSync('/proc/1/ns/mnt')!==m.namespace)fail('Wrong mount namespace');
function uptime(){return parseFloat(fs.readFileSync('/proc/uptime','utf8').split(' ')[0]);}
function exists(p){return fs.existsSync(p);}
var hashBuffer=new Buffer(65536);
function hash(p){
 var s=fs.lstatSync(p);if(!s.isFile()||s.isSymbolicLink())fail('Not a regular file');
 var fd=fs.openSync(p,'r'),position=0,n,t;
 try{
  t=fs.fstatSync(fd);if(!t.isFile()||t.dev!==s.dev||t.ino!==s.ino||t.size!==s.size)fail('Source changed while opening');
  var h=crypto.createHash('sha256');
  while(position<s.size){n=fs.readSync(fd,hashBuffer,0,Math.min(hashBuffer.length,s.size-position),position);if(n<=0)fail('Source ended while hashing');h.update(hashBuffer.slice(0,n));position+=n;}
  t=fs.fstatSync(fd);if(!t.isFile()||t.dev!==s.dev||t.ino!==s.ino||t.size!==s.size)fail('Source changed while hashing');
  return h.digest('hex');
 }finally{fs.closeSync(fd);}
}
function identity(p){var s=fs.statSync(p);return String(s.dev)+':'+String(s.ino);}
function procIdentity(pid){try{var raw=fs.readFileSync('/proc/'+pid+'/stat','utf8'),s=raw.slice(raw.lastIndexOf(')')+2).split(' ');return s[0]==='Z'?null:s[19];}catch(e){return null;}}
function mounts(){return fs.readFileSync('/proc/self/mountinfo','utf8').trim().split('\n').map(function(s){return s.split(' ');}).filter(function(a){return a[4]===m.target;});}
function write(name,value){
 var temporary=dir+'/'+name+'.'+role+'.'+process.pid+'.new';
 fs.writeFileSync(temporary,JSON.stringify(value)+'\n',{mode:384,flag:'wx'});
 fs.renameSync(temporary,dir+'/'+name);
}
function appendEvent(p,line){
 if(exists(p)){
  var s=fs.lstatSync(p);if(!s.isFile()||s.isSymbolicLink()||s.uid!==0||(s.mode&63)!==0||s.nlink!==1)fail('Unsafe diagnostic file');
  if(s.size>=16384){if(exists(p+'.1')){var old=fs.lstatSync(p+'.1');if(!old.isFile()||old.isSymbolicLink()||old.uid!==0||old.nlink!==1)fail('Unsafe diagnostic backup');}fs.renameSync(p,p+'.1');}
 }
 fs.appendFileSync(p,line,{mode:384});
}
function log(event,extra){
 var line=JSON.stringify({role:role,event:event,bootId:m.bootId,nonce:m.nonce,uptime:uptime(),wallTimeMs:Date.now(),extra:extra||null})+'\n';
 try{appendEvent(dir+'/guard-events.jsonl',line);}catch(error){}
 if(['started','activation-switch-starting','activation-verified','foreground-restored','kernel-resume-observed','power-state-changed','failure','recovery-requested','startup-audio-quiet','disable-latch-failed','startup-hook-disabled','restored','restore-failed'].indexOf(event)>=0){
  try{appendEvent(m.stateDirectory+'/guard-'+role+'-events.jsonl',line);}catch(error){}
 }
}
function activationState(phase){
 var p=m.stateDirectory+'/boot-activation.json',temporary=p+'.'+m.bootId+'.'+role+'.new';
 fs.writeFileSync(temporary,JSON.stringify({schema:2,nonce:m.nonce,bootId:m.bootId,phase:phase})+'\n',{mode:384,flag:'wx'});
 var fd=fs.openSync(temporary,'r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}fs.renameSync(temporary,p);
 fd=fs.openSync(m.stateDirectory,'r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
}
function run(command,args){pulse();if(command!=='/usr/bin/timeout'){args=['-t','12',command].concat(args);command='/usr/bin/timeout';}var r=cp.spawnSync(command,args,{encoding:'utf8'});pulse();if(r.error||r.status!==0)fail('Command failed: '+command+' '+JSON.stringify(args)+' '+r.stderr);return r.stdout;}
function luna(method,args){
 var raw=run('/usr/bin/timeout',['-t','2','/usr/bin/luna-send','-n','1','-w','1000','luna://'+method,JSON.stringify(args||{})]);
 var result=JSON.parse(raw.slice(raw.indexOf('{')));if(result.returnValue!==true){var error=Error('Native service rejected:'+method);error.nativeReply=result;throw error;}return result;
}
function readHealth(){try{return JSON.parse(fs.readFileSync(dir+'/health.json','utf8'));}catch(error){return null;}}
function ensureForeground(app,custom,wantHome,recoveryUntil){
 var until=custom?JSON.parse(fs.readFileSync(dir+'/context-restore-needed.json','utf8')).until:recoveryUntil,launched=false,lastLaunch=-1,lastHome=-1,homeRequested=false,seenApp='',seenProbe=-1,homeProbe=-1,visibleHomeProbe=-1,overlayProbe=-1;
 while(uptime()<until){
  if(custom&&(exists(dir+'/abort.json')||exists(m.disableFile)))fail('Activation cancelled during foreground recovery');
  var h=custom?readHealth():null;
  if(!custom||h&&policy.healthShape(h,m.nonce)&&h.ready&&h.nativeContextAttached&&h.windowAttached&&h.renderProbe>0&&!h.coverOpen){
   if(custom&&h.overlayOpen){
    if(overlayProbe<0)overlayProbe=h.renderProbe;
    else if(h.renderProbe>overlayProbe)return {nativeOverlay:true,verified:true,custom:true,renderProbe:h.renderProbe};
    run('/bin/sleep',['1']);continue;
   }
   if(custom&&h.shown&&h.visible&&h.activeFocus&&!homeRequested&&(wantHome||h.keyEvents>0)){
    if(visibleHomeProbe<0)visibleHomeProbe=h.renderProbe;
    else if(h.renderProbe>visibleHomeProbe)return {home:true,userOrNativeHomeIntent:true,verified:true,custom:true,renderProbe:h.renderProbe};
   }
   var foreground;
   try{foreground=policy.foreground(luna('com.webos.surfacemanager/getForegroundAppInfo'));}
   catch(serviceError){log('foreground-service-not-ready',String(serviceError));run('/bin/sleep',['1']);continue;}
   var appUncovered=true;
   if(custom&&foreground){
    try{appUncovered=luna('com.webos.surfacemanager/getCurrentState').currentState==='none';}
    catch(nativeStateError){log('foreground-state-not-ready',String(nativeStateError));run('/bin/sleep',['1']);continue;}
   }
   if(policy.recoveryAppId(foreground)&&appUncovered&&(foreground===app||custom&&h.keyEvents>0)&&!wantHome){
    if(!custom)return {appId:foreground,verified:true,custom:false};
    if(seenApp!==foreground){seenApp=foreground;seenProbe=uptime();}
    else if(uptime()-seenProbe>=1)return {appId:foreground,verified:true,custom:true,nativeSurfaceVerified:true,preLaunchRenderProbe:h.renderProbe};
   }
   if(custom&&homeRequested&&h.shown&&h.visible&&h.activeFocus&&h.renderProbe>homeProbe)return {home:true,verified:true,custom:true,renderProbe:h.renderProbe};
   if(!custom&&(wantHome||homeRequested)){
    try{if(luna('com.webos.surfacemanager/getCurrentState').currentState==='home')return {home:true,verified:true,custom:false};}
    catch(stateError){log('home-service-not-ready',String(stateError));run('/bin/sleep',['1']);continue;}
   }
   if(wantHome&&(!homeRequested||!custom&&uptime()-lastHome>=3)&&(!custom||!h.shown)){homeProbe=custom?h.renderProbe:-1;homeRequested=true;lastHome=uptime();try{luna('com.webos.service.networkinput/sendSpecialKey',{key:'HOME'});}catch(homeError){log('home-request-reply-missing',String(homeError));}}
   else if((!launched||!custom&&uptime()-lastLaunch>=3)&&!wantHome&&foreground!==app&&(!custom||!h.shown||h.keyEvents===0)){
    launched=true;lastLaunch=uptime();
    if(custom)write('foreground-request.json',{nonce:m.nonce,appId:app});
    else try{luna('com.webos.applicationManager/launch',{id:app});}catch(error){log('foreground-launch-failed',String(error));}
   }else if(!custom&&!homeRequested&&uptime()>until-7){homeProbe=custom?h.renderProbe:-1;homeRequested=true;try{luna('com.webos.service.networkinput/sendSpecialKey',{key:'HOME'});}catch(homeError){log('home-request-reply-missing',String(homeError));}}
  }
  run('/bin/sleep',['1']);
 }
 fail('No usable foreground after compositor recovery');
}
function apply(){
 if(exists(m.disableFile)||exists(dir+'/abort.json')||exists(dir+'/restored.json'))fail('Production disabled before apply');
 if(mounts().length||hash(m.target)!==m.originalSha)fail('Target changed before apply');
 var activation=JSON.parse(fs.readFileSync(m.stateDirectory+'/boot-activation.json','utf8'));
 if(activation.schema!==2||activation.nonce!==m.nonce||activation.bootId!==m.bootId||activation.phase!=='prepared')fail('Startup transaction is not prepared');
 var gate={},until=uptime()+75,snapshot;
 while(true){
  if(procIdentity(m.pid)!==m.processStart)fail('Original compositor changed before apply');
  if(exists(m.disableFile)||exists(dir+'/abort.json'))fail('Activation cancelled while waiting');
  if(uptime()>=until)fail('Native launch is still unsettled; original preserved');
  try{snapshot={power:luna('com.webos.service.tvpower/power/getPowerState'),boot:luna('com.webos.bootManager/getBootStatus'),cover:luna('com.webos.coverUI/getStatus'),surface:luna('com.webos.surfacemanager/getForegroundAppInfo'),ui:luna('com.webos.surfacemanager/getCurrentState')};}
  catch(serviceError){gate={};log('waiting-native-services',String(serviceError));run('/bin/sleep',['1']);continue;}
  if(policy.bootGate(gate,snapshot,String(m.pid)+':'+m.processStart))break;
  run('/bin/sleep',['1']);
 }
 var intent=policy.bootIntent(snapshot);m.restoreAppId=intent.appId;m.restoreHome=intent.home;m.startupBridge=intent.bridge;
 write('foreground-intent.json',{nonce:m.nonce,appId:m.restoreAppId,home:m.restoreHome,bridge:m.startupBridge,pending:true,until:uptime()+47});
 if(m.startupBridge)policy.prepareStartupInput(fs,crypto,m.stateDirectory,m.nonce,luna);else policy.restoreStartupInput(fs,crypto,m.stateDirectory,m.nonce,luna);
 if(m.startupBridge){
  var input=cp.spawnSync('/usr/bin/timeout',['-t','2','/bin/pidof','com.webos.app.inputcommon'],{encoding:'utf8'}),inputRunning;
  if(!input.error&&input.status===1&&input.stdout.trim()==='')inputRunning=false;
  else if(!input.error&&input.status===0&&/^\d+(?:\s+\d+)*$/.test(input.stdout.trim()))inputRunning=true;
  else fail('Native input process identity unavailable');
  log('startup-audio-quiet',policy.quietStartupAudio(luna,m.bootId,function(){return fs.readFileSync('/proc/sys/kernel/random/boot_id','utf8').trim();},inputRunning));
 }
 if(m.kind==='freeze'){
  if(procIdentity(m.pid)!==m.processStart||fs.readlinkSync('/proc/'+m.pid+'/exe')!==m.target)fail('Original process identity changed');
  process.kill(m.pid,'SIGSTOP');
 }else{
  activationState('applying');log('activation-switch-starting');
  run('/bin/mount',['-n','--bind',m.candidate,m.target]);
  var entry=mounts();
  if(entry.length!==1||identity(m.target)!==m.candidateIdentity)fail('Mount was not applied as expected');
  fs.writeFileSync(dir+'/mount-id',entry[0][0]+'\n',{mode:384});
  if(m.kind==='native'){
   fs.writeFileSync(dir+'/restart-needed','restart\n',{mode:384});
   write('context-restore-needed.json',{until:uptime()+47,appId:m.restoreAppId});
   run('/usr/bin/timeout',['-t','12','/sbin/restart','surface-manager']);
   var candidatePid=run('/bin/pidof',['surface-manager-starfish']).trim();
   if(!/^\d+$/.test(candidatePid)||procIdentity(candidatePid)===null)fail('Candidate compositor is not running');
   write('candidate-process.json',{pid:Number(candidatePid),start:procIdentity(candidatePid)});
   if(m.startupBridge){try{luna('com.webos.applicationManager/launch',{id:policy.startupBridge,params:{boot:true}});}catch(launchError){log('startup-bridge-launch-reply-missing',String(launchError));}}
  }
 }
 write('applied.json',{uptime:uptime(),kind:m.kind});log('applied');
 write('context-restore-needed.json',{until:uptime()+35,appId:m.restoreAppId});
 var context=ensureForeground(m.restoreAppId,true,m.restoreHome);
 if(context.home&&!m.restoreHome&&!context.userOrNativeHomeIntent)fail('Requested app did not produce a usable foreground');
 if(m.startupBridge&&!context.home)fail('Startup bridge requires composed focused Home');
 if(!m.startupBridge)write('foreground-intent.json',{nonce:m.nonce,appId:m.restoreAppId,home:m.restoreHome,bridge:false,pending:false});
 if(m.startupBridge){
  var confirmationUntil=uptime()+16;write('context-restore-needed.json',{until:confirmationUntil,appId:m.restoreAppId});
  if(policy.foreground(luna('com.webos.surfacemanager/getForegroundAppInfo'))!==policy.startupBridge)fail('Startup bridge has no actual foreground card');
  write('foreground-intent.json',{nonce:m.nonce,appId:m.restoreAppId,home:m.restoreHome,bridge:true,pending:false});
  var ackUntil=Math.min(uptime()+6,confirmationUntil),acknowledged=false;
  while(uptime()<ackUntil){
   var accepted=readHealth();
   if(!policy.healthShape(accepted,m.nonce)||!accepted.ready||!accepted.powerActive||accepted.coverOpen||accepted.overlayOpen||!accepted.nativeContextAttached||!accepted.windowAttached||!accepted.shown||!accepted.visible||!accepted.activeFocus||accepted.renderProbe<context.renderProbe)fail('Home lost before startup readiness acknowledgment');
   var reply;try{reply=luna('com.personalhome.startup.service/ready',{nonce:m.nonce});}
   catch(serviceError){log('startup-readiness-service-not-ready',String(serviceError));run('/bin/sleep',['1']);continue;}
   if(reply.nonce!==m.nonce||reply.ready!==true)fail('Invalid startup readiness acknowledgment');
   acknowledged=true;break;
  }
  if(!acknowledged)fail('Startup readiness service did not accept current Home');
  policy.restoreStartupInput(fs,crypto,m.stateDirectory,m.nonce,luna);
 }
 write('context-restored.json',context);log('foreground-restored',context);
 activationState('verified');log('activation-verified',context);
}
function disableActivation(reason){
 var disabled=JSON.stringify({reason:reason,nonce:m.nonce,bootId:m.bootId,uptime:uptime(),wallTimeMs:Date.now()})+'\n';
 try{if(!exists(m.disableFile)){var fd=fs.openSync(m.disableFile,'wx',384);try{fs.writeSync(fd,disabled,0,'utf8');fs.fsyncSync(fd);}finally{fs.closeSync(fd);}}}catch(latchError){log('disable-latch-failed',String(latchError));}
 var hook=m.stateDirectory==='/var/lib/personalhome'?'/var/lib/webosbrew/init.d/90-personalhome':'/var/lib/webosbrew/init.d/89-personalhome-validation';
 try{if(exists(hook)){
  var receipt=JSON.parse(fs.readFileSync(m.stateDirectory+'/installed.json','utf8'));
  if(receipt.nonce!==m.nonce||hash(hook)!==receipt.bootHookSha256)fail('Foreign startup hook; refusing overwrite');
  var hookBackup=m.stateDirectory+'/failed-hook.'+m.nonce;
  if(exists(hookBackup))fail('Startup hook backup already exists');
  fs.renameSync(hook,hookBackup);log('startup-hook-disabled');
 }}catch(hookError){log('startup-hook-preserved',String(hookError));}
}
function restore(reason){
 if(exists(dir+'/restored.json'))return;
 var recoveryUntil=uptime()+m.failureRecoverySeconds;
 disableActivation(reason);
 try{if(policy.restoreStartupInput(fs,crypto,m.stateDirectory,m.nonce,luna))log('startup-input-restored');}catch(inputError){log('startup-input-preserved',String(inputError));}
 try{if(policy.restoreStartupConfig(fs,crypto,m.stateDirectory))log('startup-config-restored');}catch(configError){log('startup-config-preserved',String(configError));}
 var intent={appId:m.restoreAppId,home:m.restoreHome,bridge:m.startupBridge===true};
 if(exists(dir+'/foreground-intent.json')){var savedIntent=JSON.parse(fs.readFileSync(dir+'/foreground-intent.json','utf8'));if(savedIntent.nonce===m.nonce&&policy.recoveryAppId(savedIntent.appId)&&typeof savedIntent.home==='boolean'&& (savedIntent.bridge===undefined||typeof savedIntent.bridge==='boolean'))intent=savedIntent;}
 intent.nonce=m.nonce;intent.pending=false;write('foreground-intent.json',intent);
 var recent=readHealth(),restoreApp=exists(dir+'/context-restored.json')&&recent&&recent.nonce===m.nonce&&policy.recoveryAppId(recent.foregroundAppId)?recent.foregroundAppId:intent.appId;
 if(hash(m.original)!==m.originalSha)fail('Original backup changed');
 var entries=mounts();
 if(entries.length){
  if(entries.length!==1||entries[0][3]!==dir.slice(4)+'/candidate'||identity(m.target)!==m.candidateIdentity)fail('Foreign target mount; refusing unmount');
  if(exists(dir+'/mount-id')&&fs.readFileSync(dir+'/mount-id','utf8').trim()!==entries[0][0])fail('Mount ID changed');
  if(m.kind==='native'&&exists(dir+'/restart-needed')){
   var status=run('/sbin/initctl',['status','surface-manager']);
   if(status.indexOf('stop/waiting')<0){log('stop-before-unmount');run('/usr/bin/timeout',['-t','12','/sbin/stop','surface-manager']);}
   if(run('/sbin/initctl',['status','surface-manager']).indexOf('stop/waiting')<0)fail('Native job did not stop');
   entries=mounts();
   if(entries.length!==1||entries[0][3]!==dir.slice(4)+'/candidate'||identity(m.target)!==m.candidateIdentity||fs.readFileSync(dir+'/mount-id','utf8').trim()!==entries[0][0])fail('Mount changed while stopping');
  }
  log('unmount',entries[0][0]);run('/bin/umount',[m.target]);
 }
 if(mounts().length||hash(m.target)!==m.originalSha)fail('Original target not restored');
 if(m.kind==='freeze'&&procIdentity(m.pid)===m.processStart){process.kill(m.pid,'SIGCONT');log('continued-original',m.pid);}
 if(m.kind==='native'&&exists(dir+'/restart-needed')){
  log('start-original');
  var state=run('/sbin/initctl',['status','surface-manager']);
  if(state.indexOf('stop/waiting')>=0)run('/usr/bin/timeout',['-t','12','/sbin/start','surface-manager']);
  else run('/usr/bin/timeout',['-t','12','/sbin/restart','surface-manager']);
 }
 var foreground=null;
 try{if(intent.bridge)ensureForeground('com.webos.app.livetv',false,false,recoveryUntil);foreground=ensureForeground(intent.bridge?'com.webos.app.livetv':restoreApp,false,intent.bridge||intent.home,recoveryUntil);}catch(error){log('foreground-recovery-incomplete',String(error));}
 write('restored.json',{reason:reason,uptime:uptime(),originalSha:hash(m.target),mountAbsent:mounts().length===0,foreground:foreground,usableInterface:!!foreground});log('restored',reason);
 ['primary','lifeline'].forEach(function(actor){
  try{if(exists(dir+'/'+actor+'-pid.json')){var peer=JSON.parse(fs.readFileSync(dir+'/'+actor+'-pid.json','utf8'));if(peer.pid!==process.pid&&procIdentity(peer.pid)===peer.start){process.kill(peer.pid,'SIGKILL');log('retired-peer',actor);}}}catch(peerError){log('peer-retirement-failed',String(peerError));}
 });
}
function abort(reason){
 if(exists(dir+'/abort.json'))return;
 write('abort.json',{reason:reason});
 try{
  var h=readHealth()||{},health={};
  ['shown','visible','activeFocus','ready','powerWakeSleeping','powerWakeArmed','powerWakeRequested','powerWakeInterrupted','powerWakeMappingHeld'].forEach(function(key){health[key]=typeof h[key]==='boolean'?h[key]:null;});
  health.foregroundAppId=typeof h.foregroundAppId==='string'?h.foregroundAppId.slice(0,128):null;
  ['keyEvents','lastKey','sequence','frameSequence','renderProbe'].forEach(function(key){health[key]=typeof h[key]==='number'&&isFinite(h[key])?h[key]:null;});
  ['nativePowerOffCount','nativePowerOnCount','powerWakeGeneration'].forEach(function(key){health[key]=typeof h[key]==='number'&&isFinite(h[key])&&Math.floor(h[key])===h[key]&&h[key]>=0?h[key]:null;});
  health.powerWakeReason=['empty','pending','remoteKey','amazon','other','invalid'].indexOf(h.powerWakeReason)>=0?h.powerWakeReason:null;
  log('recovery-requested',{reason:typeof reason==='string'?reason.slice(0,128):'unknown',health:health,
   nativePresentation:{appId:typeof presentationApp==='string'?presentationApp.slice(0,128):null,state:typeof presentationState==='string'?presentationState.slice(0,128):null,lastValid:lastPresentationValid},
   power:{active:powerActive,lastValid:lastPowerValid}});
 }catch(diagnosticError){}
}
function validViewHealth(h,initializing){
 var pendingLoader=initializing===true&&h&&h.focusIndex===-1&&h.moduleResolved===true
  &&h.componentInstantiated===false&&h.initialized===false&&h.windowAttached===false
  &&h.nativeContextAttached===false&&h.ready===false&&h.shown===false&&h.visible===false
  &&h.activeFocus===false&&h.originalFallback===false&&h.keyEvents===0&&h.lastKey===0;
 if(!(policy.healthShape(h,m.nonce)&&h.rootSource==='file:///tmp/YSM/YSM.qml'
  &&typeof h.sequence==='number'&&isFinite(h.sequence)&&h.sequence>=1&&Math.floor(h.sequence)===h.sequence
  &&typeof h.keyEvents==='number'&&isFinite(h.keyEvents)&&h.keyEvents>=0&&Math.floor(h.keyEvents)===h.keyEvents
  &&typeof h.lastKey==='number'&&isFinite(h.lastKey)&&h.lastKey>=0&&Math.floor(h.lastKey)===h.lastKey
  &&typeof h.focusIndex==='number'&&isFinite(h.focusIndex)&&(h.focusIndex>=0||pendingLoader)&&h.focusIndex<=10&&Math.floor(h.focusIndex)===h.focusIndex))return false;
 var flags=['moduleResolved','componentInstantiated','initialized','windowAttached','nativeContextAttached','ready','shown','visible','activeFocus','originalFallback'];
 for(var i=0;i<flags.length;i++)if(typeof h[flags[i]]!=='boolean')return false;
 return !h.ready||(h.moduleResolved&&h.componentInstantiated&&h.initialized&&h.windowAttached&&h.nativeContextAttached);
}

if(hash(dir+'/policy.js')!==m.policySha||hash(dir+'/guard.js')!==m.guardSha)fail('Recovery sources changed');
var policy=require(dir+'/policy.js');if(!policy.recoveryAppId(m.restoreAppId))fail('Invalid recovery app');
if(hash(m.original)!==m.originalSha||(role!=='restore'&&(hash(m.candidate)!==m.candidateSha||identity(m.candidate)!==m.candidateIdentity)))fail('Sources changed');
write(role+'-pid.json',{pid:process.pid,start:procIdentity(process.pid)});log('started');
if(role==='restore'){restore('host-request');process.exit(0);}
var started=uptime(),lastSequence=-1,lastKeyEvents=-1,lastHealth=started,viewAccepted=false;
var runtimeHealth={},probeSequence=0,probePending=0,probeFrame=-1,probeSent=started,lastProbe=started,lastFrame=-1,lastRenderProbe=-1;
var powerActive=null,lastPower=0,resumeUntil=0,lastPowerValid=started,powerMismatchSince=null;
var presentationApp='',presentationState='',lastPresentation=0,lastPresentationValid=-100,wasExternal=false;
var sessionDeadline=m.sessionExpiresAt===null?null:started+Math.max(0,(m.sessionExpiresAt-Date.now())/1000),expiryPowerCheck=0;
function monotonic(){var value=process.hrtime();return value[0]+value[1]/1000000000;}
var observedBootTime=started,observedMonotonic=monotonic();
var peerRole=role==='primary'?'lifeline':'primary',peerSequence=-1,peerSeen=started,pulseSequence=0,lastPulse=-1,lastIntegrity=started;
function pulse(){if(uptime()-lastPulse>=1){lastPulse=uptime();write(role+'-pulse.json',{pid:process.pid,start:procIdentity(process.pid),nonce:m.nonce,sequence:++pulseSequence,uptime:lastPulse});}}
function peerHealthy(){
 var peerPath=dir+'/'+peerRole+'-pid.json',pulsePath=dir+'/'+peerRole+'-pulse.json';
 if(exists(peerPath)){var peer=JSON.parse(fs.readFileSync(peerPath,'utf8'));if(procIdentity(peer.pid)!==peer.start)return false;
  if(exists(pulsePath)){var p=JSON.parse(fs.readFileSync(pulsePath,'utf8'));
   if(p.nonce!==m.nonce||p.pid!==peer.pid||p.start!==peer.start||typeof p.sequence!=='number'||!isFinite(p.sequence)||p.sequence<1||Math.floor(p.sequence)!==p.sequence||p.sequence<peerSequence)return false;
   if(p.sequence>peerSequence){peerSequence=p.sequence;peerSeen=uptime();}
  }
 }
 return uptime()-peerSeen<=30;
}
pulse();
function handleFailure(e){log('failure',String(e));if(role==='primary')abort('primary-error');else{try{restore('lifeline-error');}catch(error){log('restore-failed',String(error));process.exitCode=1;}clearInterval(timer);}}
var activationQueued=false;
var timer=setInterval(function(){
 try{
  if(exists(dir+'/restored.json')){clearInterval(timer);return;}
  var bootNow=uptime(),monoNow=monotonic();
  if(bootNow-observedBootTime-(monoNow-observedMonotonic)>1){
   resumeUntil=bootNow+20;lastHealth=bootNow;peerSeen=bootNow;probePending=0;runtimeHealth={};lastPower=0;
   log('kernel-resume-observed',{suspendedSeconds:Math.round(bootNow-observedBootTime-(monoNow-observedMonotonic))});
  }
  observedBootTime=bootNow;observedMonotonic=monoNow;
  pulse();
  if(sessionDeadline!==null&&(uptime()>=sessionDeadline||Date.now()>=m.sessionExpiresAt))abort('validation-session-expired');
  if(role==='lifeline'){
   var reason=null;
   if(!peerHealthy())reason='primary-monitor-stalled';
   if(exists(dir+'/abort.json'))reason=JSON.parse(fs.readFileSync(dir+'/abort.json','utf8')).reason;
   if(exists(dir+'/primary-pid.json')){var primary=JSON.parse(fs.readFileSync(dir+'/primary-pid.json','utf8'));if(procIdentity(primary.pid)!==primary.start)reason='primary-monitor-died';}
   if(reason){
    if(reason==='validation-session-expired'){
     disableActivation(reason);
     if(uptime()<expiryPowerCheck)return;expiryPowerCheck=uptime()+2;
     try{if(luna('com.webos.service.tvpower/power/getPowerState').state!=='Active')return;}catch(powerError){return;}
    }
    restore(reason);clearInterval(timer);
   }
   else if(exists(dir+'/apply-request')&&!exists(dir+'/applied.json')&&!activationQueued){
    activationQueued=true;
    // Node0.12 repeats the blocking time after a long interval callback.
    setImmediate(function(){try{apply();}catch(error){handleFailure(error);}});
   }
  }else{
   if(exists(dir+'/lifeline-pid.json')){
    var lifeline=JSON.parse(fs.readFileSync(dir+'/lifeline-pid.json','utf8'));
    if(procIdentity(lifeline.pid)!==lifeline.start||!peerHealthy()){
     log('lifeline-died-rescue');
     if(procIdentity(lifeline.pid)===lifeline.start){process.kill(lifeline.pid,'SIGKILL');if(procIdentity(lifeline.pid)===lifeline.start)fail('Stalled lifeline did not terminate');}
     var rescue=cp.spawn('/usr/bin/node',[dir+'/guard.js',path,'restore'],{detached:true,stdio:'ignore'});rescue.unref();clearInterval(timer);return;
    }
   }
   if(uptime()-lastIntegrity>=5){
    lastIntegrity=uptime();if(hash(path)!==manifestHash)abort('runtime-manifest-changed');
    if(hash(m.original)!==m.originalSha||hash(m.candidate)!==m.candidateSha||hash(dir+'/guard.js')!==m.guardSha||hash(dir+'/policy.js')!==m.policySha)abort('source-changed');
    if(exists(dir+'/candidate-process.json')){
     var candidateProcess=JSON.parse(fs.readFileSync(dir+'/candidate-process.json','utf8'));
     if(procIdentity(candidateProcess.pid)!==candidateProcess.start)abort('compositor-process-changed');
     else if(fs.readlinkSync('/proc/'+candidateProcess.pid+'/exe')!==m.target||crypto.createHash('sha256').update(fs.readFileSync('/proc/'+candidateProcess.pid+'/exe')).digest('hex')!==m.candidateSha)abort('compositor-executable-changed');
    }
   }
   if(!exists(dir+'/lifeline-pid.json')&&!peerHealthy())abort('lifeline-not-started');
   if(m.requireViewHealth&&exists(dir+'/restart-needed')){
    var now=uptime();
    var startupPending=exists(dir+'/context-restore-needed.json')&&!exists(dir+'/context-restored.json');
    var startupUntil=startupPending?JSON.parse(fs.readFileSync(dir+'/context-restore-needed.json','utf8')).until:0;
    if(startupPending&&now>startupUntil)abort('startup-foreground-not-restored');
    if(now-lastPower>=2){
     lastPower=now;
     try{var power=luna('com.webos.service.tvpower/power/getPowerState');if(['Active','Suspend','Active Standby','Screen Off'].indexOf(power.state)<0)fail('Unknown power state');var active=power.state==='Active';
      if(active&&powerActive===false){resumeUntil=now+20;lastHealth=now;probePending=0;runtimeHealth={};}
      if(powerActive!==active)log('power-state-changed',{fromActive:powerActive,state:power.state});
      powerActive=active;lastPowerValid=now;
     }catch(error){if(now-lastPowerValid>20)abort('power-service-unavailable');}
    }
    if(powerActive===false){lastHealth=now;probePending=0;runtimeHealth={};return;}
    var external=false;
    if(viewAccepted&&exists(dir+'/context-restored.json')){
     if(now-lastPresentation>=2){
      lastPresentation=now;
      try{
       var card=policy.foreground(luna('com.webos.surfacemanager/getForegroundAppInfo'));
       var nativeState=luna('com.webos.surfacemanager/getCurrentState').currentState;
       presentationApp=card;presentationState=nativeState;lastPresentationValid=uptime();
       write('presentation-verified.json',{appId:card,uiState:nativeState,uptime:lastPresentationValid,nativeSurfaceVerified:policy.recoveryAppId(card)});
      }catch(presentationError){log('presentation-service-not-ready',String(presentationError));}
     }
     external=policy.recoveryAppId(presentationApp)&&presentationState==='none'&&now-lastPresentationValid<=6;
     if(wasExternal&&!external){lastHealth=now;resumeUntil=Math.max(resumeUntil,now+5);probePending=0;}
     wasExternal=external;
    }
    if(exists(dir+'/health.json')){
     var h=null;try{h=JSON.parse(fs.readFileSync(dir+'/health.json','utf8'));}catch(incompleteWrite){}
     if(h&&(!validViewHealth(h,!viewAccepted&&uptime()-started<=35)||h.sequence<lastSequence||h.keyEvents<lastKeyEvents||h.frameSequence<lastFrame||h.renderProbe<lastRenderProbe))abort('invalid-view-health');
     else if(h&&h.originalFallback)abort('view-fell-back');
     else if(h&&h.ready&&external&&viewAccepted){lastHealth=now;probePending=0;runtimeHealth={};return;}
     else if(h&&!h.ready&&(viewAccepted||uptime()-started>35))abort('view-not-ready');
     else if(h&&h.sequence>lastSequence){
      lastSequence=h.sequence;lastKeyEvents=h.keyEvents;lastFrame=h.frameSequence;lastRenderProbe=h.renderProbe;lastHealth=uptime();if(h.ready)viewAccepted=true;
      var restoring=exists(dir+'/context-restore-needed.json')&&!exists(dir+'/context-restored.json');
      var contextDeadline=restoring?JSON.parse(fs.readFileSync(dir+'/context-restore-needed.json','utf8')).until:0;
      if(restoring&&now>contextDeadline)abort('startup-foreground-not-restored');
      else if(!restoring&&now>=resumeUntil){var unhealthy=policy.failure(runtimeHealth,h,m.nonce,now);if(unhealthy)abort(unhealthy);}
      if(powerActive===true&&!h.powerActive&&now>=resumeUntil){if(powerMismatchSince===null)powerMismatchSince=now;else if(now-powerMismatchSince>=8)abort('power-health-mismatch');}else powerMismatchSince=null;
      if(h.renderProbe>probeSequence)abort('unrequested-render-confirmation');
      if(probePending&&h.renderProbe===probePending&&h.frameSequence>probeFrame){probePending=0;}
      if(h.ready&&h.powerActive&&!probePending&&now-lastProbe>=3){probePending=++probeSequence;probeFrame=h.frameSequence;probeSent=now;lastProbe=now;write('render-request.json',{nonce:m.nonce,sequence:probePending});}
      write('health-received.json',{nonce:h.nonce,sequence:h.sequence,uptime:lastHealth,ready:h.ready,nativeContextAttached:h.nativeContextAttached,keyEvents:h.keyEvents,renderProbe:h.renderProbe});
     }
    }
    if(!startupPending&&probePending&&now-probeSent>8&&now>=resumeUntil)abort('composition-not-progressing');
    if(!startupPending&&(viewAccepted||uptime()-started>35)&&uptime()-lastHealth>3&&now>=resumeUntil)abort('view-heartbeat-expired');
   }
  }
 }catch(e){handleFailure(e);}
},200);
