/* Trial-only guard for the TV's Node 0.12 runtime. Never installed at boot. */
'use strict';
var fs=require('fs'), crypto=require('crypto'), cp=require('child_process');
var path=process.argv[2], role=process.argv[3], dir=path.slice(0,path.lastIndexOf('/'));
function fail(message){throw Error(message);}
if(!/^\/tmp\/lg-native-trial\.[A-Za-z0-9]+\/manifest.json$/.test(path))fail('Unsafe manifest path');
if(['primary','lifeline','restore'].indexOf(role)<0)fail('Unknown guard role');
var ds=fs.lstatSync(dir), ms=fs.lstatSync(path);
if(!ds.isDirectory()||ds.isSymbolicLink()||ds.uid!==0||(ds.mode&63)!==0||!ms.isFile()||ms.isSymbolicLink()||ms.uid!==0||(ms.mode&63)!==0)fail('Unsafe trial ownership/mode');
var m=JSON.parse(fs.readFileSync(path,'utf8'));
if(['canary','freeze','native'].indexOf(m.kind)<0||m.directory!==dir||typeof m.deadline!=='number'||!isFinite(m.deadline)||(role!=='restore'&&m.deadline<=uptime())||m.deadline>uptime()+120)fail('Invalid trial manifest/deadline');
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
function write(name,value){fs.writeFileSync(dir+'/'+name,JSON.stringify(value)+'\n',{mode:384});}
function log(event,extra){fs.appendFileSync(dir+'/guard-events.jsonl',JSON.stringify({role:role,event:event,uptime:uptime(),extra:extra||null})+'\n',{mode:384});}
function run(command,args){var r=cp.spawnSync(command,args,{encoding:'utf8'});if(r.error||r.status!==0)fail('Command failed: '+command+' '+JSON.stringify(args)+' '+r.stderr);return r.stdout;}
function apply(){
 if(uptime()+2>=m.deadline||exists(dir+'/abort.json')||exists(dir+'/restored.json'))fail('Trial expired before apply');
 if(mounts().length||hash(m.target)!==m.originalSha)fail('Target changed before apply');
 if(m.kind==='freeze'){
  if(procIdentity(m.pid)!==m.processStart||fs.readlinkSync('/proc/'+m.pid+'/exe')!==m.target)fail('Original process identity changed');
  process.kill(m.pid,'SIGSTOP');
 }else{
  run('/bin/mount',['-n','--bind',m.candidate,m.target]);
  var entry=mounts();
  if(entry.length!==1||identity(m.target)!==m.candidateIdentity)fail('Mount was not applied as expected');
  fs.writeFileSync(dir+'/mount-id',entry[0][0]+'\n',{mode:384});
  if(m.kind==='native'){
   if(uptime()+14>=m.deadline)fail('Insufficient restart/recovery margin');
   fs.writeFileSync(dir+'/restart-needed','restart\n',{mode:384});
   run('/usr/bin/timeout',['-t','12','/sbin/restart','surface-manager']);
  }
 }
 write('applied.json',{uptime:uptime(),kind:m.kind});log('applied');
}
function restore(reason){
 if(exists(dir+'/restored.json'))return;
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
 write('restored.json',{reason:reason,uptime:uptime(),originalSha:hash(m.target),mountAbsent:mounts().length===0});log('restored',reason);
}
function abort(reason){if(!exists(dir+'/abort.json'))write('abort.json',{reason:reason});}
function validViewHealth(h,initializing){
 var pendingLoader=initializing===true&&h&&h.focusIndex===-1&&h.moduleResolved===true
  &&h.componentInstantiated===false&&h.initialized===false&&h.windowAttached===false
  &&h.nativeContextAttached===false&&h.ready===false&&h.shown===false&&h.visible===false
  &&h.activeFocus===false&&h.originalFallback===false&&h.keyEvents===0&&h.lastKey===0;
 if(!(h&&h.schema===2&&h.nonce===m.nonce&&h.rootSource==='file:///tmp/YSM/YSM.qml'
  &&typeof h.sequence==='number'&&isFinite(h.sequence)&&h.sequence>=1&&Math.floor(h.sequence)===h.sequence
  &&typeof h.keyEvents==='number'&&isFinite(h.keyEvents)&&h.keyEvents>=0&&Math.floor(h.keyEvents)===h.keyEvents
  &&typeof h.lastKey==='number'&&isFinite(h.lastKey)&&h.lastKey>=0&&Math.floor(h.lastKey)===h.lastKey
  &&typeof h.focusIndex==='number'&&isFinite(h.focusIndex)&&(h.focusIndex>=0||pendingLoader)&&h.focusIndex<=10&&Math.floor(h.focusIndex)===h.focusIndex))return false;
 var flags=['moduleResolved','componentInstantiated','initialized','windowAttached','nativeContextAttached','ready','shown','visible','activeFocus','originalFallback'];
 for(var i=0;i<flags.length;i++)if(typeof h[flags[i]]!=='boolean')return false;
 return !h.ready||(h.moduleResolved&&h.componentInstantiated&&h.initialized&&h.windowAttached&&h.nativeContextAttached);
}

if(hash(m.original)!==m.originalSha||(role!=='restore'&&(hash(m.candidate)!==m.candidateSha||identity(m.candidate)!==m.candidateIdentity)))fail('Sources changed');
write(role+'-pid.json',{pid:process.pid,start:procIdentity(process.pid)});log('started');
if(role==='restore'){restore('host-request');process.exit(0);}
var started=uptime(),lastSequence=-1,lastKeyEvents=-1,lastHealth=started,viewAccepted=false;
var timer=setInterval(function(){
 try{
  if(exists(dir+'/restored.json')){clearInterval(timer);return;}
  if(role==='lifeline'){
   var reason=null;
   if(uptime()>=m.deadline)reason='fixed-deadline';
   if(exists(dir+'/abort.json'))reason=JSON.parse(fs.readFileSync(dir+'/abort.json','utf8')).reason;
   if(exists(dir+'/primary-pid.json')){var primary=JSON.parse(fs.readFileSync(dir+'/primary-pid.json','utf8'));if(procIdentity(primary.pid)!==primary.start)reason='primary-monitor-died';}
   if(reason){restore(reason);clearInterval(timer);}
   else if(exists(dir+'/apply-request')&&!exists(dir+'/applied.json'))apply();
  }else{
   if(exists(dir+'/lifeline-pid.json')){
    var lifeline=JSON.parse(fs.readFileSync(dir+'/lifeline-pid.json','utf8'));
    if(procIdentity(lifeline.pid)!==lifeline.start){
     log('lifeline-died-rescue');
     var rescue=cp.spawn('/usr/bin/node',[dir+'/guard.js',path,'restore'],{detached:true,stdio:'ignore'});rescue.unref();clearInterval(timer);return;
    }
   }
   if(hash(m.original)!==m.originalSha||hash(m.candidate)!==m.candidateSha)abort('source-changed');
   if(m.requireViewHealth&&exists(dir+'/restart-needed')){
    if(exists(dir+'/health.json')){
     var h=null;try{h=JSON.parse(fs.readFileSync(dir+'/health.json','utf8'));}catch(incompleteWrite){}
     if(h&&(!validViewHealth(h,!viewAccepted&&uptime()-started<=35)||h.sequence<lastSequence||h.keyEvents<lastKeyEvents))abort('invalid-view-health');
     else if(h&&h.originalFallback)abort('view-fell-back');
     else if(h&&!h.ready&&(viewAccepted||uptime()-started>35))abort('view-not-ready');
     else if(h&&h.sequence>lastSequence){lastSequence=h.sequence;lastKeyEvents=h.keyEvents;lastHealth=uptime();if(h.ready)viewAccepted=true;write('health-received.json',{nonce:h.nonce,sequence:h.sequence,uptime:lastHealth,ready:h.ready,nativeContextAttached:h.nativeContextAttached,keyEvents:h.keyEvents});}
    }
    if((viewAccepted||uptime()-started>35)&&uptime()-lastHealth>3)abort('view-heartbeat-expired');
   }
  }
 }catch(e){log('failure',String(e));if(role==='primary')abort('primary-error');else{try{restore('lifeline-error');}catch(error){log('restore-failed',String(error));process.exitCode=1;}clearInterval(timer);}}
},200);
