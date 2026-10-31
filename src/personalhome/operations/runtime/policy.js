'use strict';
var transient = ['com.webos.app.cpcover','com.webos.app.coverui'];
var startupBridge = 'com.personalhome.startup';
function appId(value) {
 return typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value) && transient.indexOf(value) < 0;
}
function foreground(reply) {
 if (!reply || reply.returnValue !== true || !Array.isArray(reply.foregroundAppInfo)) return '';
 var cards = reply.foregroundAppInfo.filter(function(row) { return row && row.windowType === '_WEBOS_WINDOW_TYPE_CARD' && appId(row.appId); });
 return cards.length === 1 ? cards[0].appId : '';
}
function recoveryAppId(value) { return appId(value) && value !== startupBridge; }
function bootIntent(snapshot) {
 var app = foreground(snapshot && snapshot.surface), bridge = app === startupBridge;
 return {appId:bridge?'com.webos.app.livetv':app,home:bridge||snapshot.ui.currentState!=='none',bridge:bridge};
}
function quietStartupAudio(luna,bootId,readBootId,inputRunning) {
 if(!/^[a-f0-9-]{36}$/.test(bootId)||readBootId()!==bootId)throw Error('Startup audio boot identity differs');
 if(inputRunning===true)return {changed:false,reason:'native-input-app-running'};
 if(inputRunning!==false)throw Error('Unknown native input process state');
 var boot=luna('com.webos.service.tv.broadcast/getPipeline4BootUp',{});
 if(!boot||boot.returnValue!==true)throw Error('Startup broadcast pipeline unavailable');
 if(boot.broadcastId===undefined||boot.broadcastId===null||boot.broadcastId==='')return {changed:false,reason:'no-broadcast-pipeline'};
 var id=boot.broadcastId;
 if(typeof id!=='string'||!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(id))throw Error('Invalid startup broadcast pipeline');
 function closed(reply){return !!(reply&&reply.returnValue===false&&reply.broadcastId===id&&reply.errorCode==='BROADCAST_ERROR_0001'&&reply.errorText==='Invalid broadcastID error'&&reply.subscribed===false);}
 function state(){
  var reply;try{reply=luna('com.webos.service.utp.broadcast/getBroadcastState',{broadcastId:id,subscribe:false});}
  catch(error){if(closed(error.nativeReply))return null;throw error;}
  if(closed(reply))return null;
  if(!reply||reply.returnValue!==true||reply.broadcastId!==id||reply.conflictResult!=='NO_CONFLICT'||typeof reply.state!=='string'||!/^BROADCAST_STATE_[A-Z_]{1,48}$/.test(reply.state))throw Error('Startup broadcast ownership or state differs');
  return reply;
 }
 if(state()===null)return {changed:false,pipelineId:id,reason:'broadcast-already-closed'};
 if(readBootId()!==bootId)throw Error('Startup audio boot changed before close');
 var reply=luna('com.webos.service.utp.broadcast/close',{broadcastId:id});
 if(!reply||reply.returnValue!==true||reply.broadcastId!==undefined&&reply.broadcastId!==id)throw Error('Startup broadcast close was not acknowledged');
 if(state()!==null)throw Error('Startup broadcast remains allocated after close');
 return {changed:true,pipelineId:id,reason:'preloaded-broadcast-closed'};
}
function startupInput(fs,crypto,base,nonce,luna) {
 if(!/^\/var\/lib\/personalhome(?:-validation\.[a-f0-9]{32})?$/.test(base)||!/^[a-f0-9]{32}$/.test(nonce))throw Error('Invalid startup input identity');
 function safe(p,directory){var s=fs.lstatSync(p);if(s.isSymbolicLink()||s.uid!==0||(s.mode&18)!==0||(directory?!s.isDirectory()||(s.mode&511)!==448:!s.isFile()||s.nlink!==1))throw Error('Unsafe startup input path:'+p);}
 var path=base+'/startup-input.json';safe(base,true);
 var journal=null;
 if(fs.existsSync(path)){
  safe(path,false);journal=JSON.parse(fs.readFileSync(path,'utf8'));
  if(journal.schema!==1||journal.nonce!==nonce||journal.candidateAppId!==startupBridge||!recoveryAppId(journal.originalAppId)||['prepared','restored','preserved'].indexOf(journal.phase)<0)throw Error('Invalid startup input journal');
 }
 function current(){var reply=luna('com.webos.settingsservice/getSystemSettings',{category:'general',keys:['lastInputApp']});if(!reply||reply.returnValue!==true||!reply.settings||!appId(reply.settings.lastInputApp))throw Error('Invalid native startup input');return reply.settings.lastInputApp;}
 function save(value){var temporary=path+'.'+crypto.randomBytes(8).toString('hex');fs.writeFileSync(temporary,JSON.stringify(value)+'\n',{mode:384,flag:'wx'});var fd=fs.openSync(temporary,'r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}fs.renameSync(temporary,path);fd=fs.openSync(base,'r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}}
 function set(value,expected){if(current()!==expected)return false;var reply=luna('com.webos.settingsservice/setSystemSettings',{category:'general',settings:{lastInputApp:value}});if(!reply||reply.returnValue!==true)throw Error('Native startup input rejected');if(current()!==value)throw Error('Native startup input readback differs');return true;}
 return {journal:journal,current:current,save:save,set:set};
}
function prepareStartupInput(fs,crypto,base,nonce,luna) {
 var state=startupInput(fs,crypto,base,nonce,luna),current=state.current(),original=current;
 if(current===startupBridge){if(!state.journal||state.journal.phase!=='prepared')throw Error('Startup input bridge has no owned backup');original=state.journal.originalAppId;}
 var journal={schema:1,nonce:nonce,originalAppId:original,candidateAppId:startupBridge,phase:'prepared'};
 state.save(journal);if(!state.set(startupBridge,current))throw Error('Native startup input changed before mutation');return journal;
}
function restoreStartupInput(fs,crypto,base,nonce,luna) {
 if(!fs.existsSync(base+'/startup-input.json'))return false;
 var state=startupInput(fs,crypto,base,nonce,luna),journal=state.journal;
 if(journal.phase!=='prepared')return false;
 var current=state.current(),owned=current===startupBridge;
 if(owned&&!state.set(journal.originalAppId,startupBridge)){journal.phase='preserved';state.save(journal);return false;}
 journal.phase=owned||current===journal.originalAppId?'restored':'preserved';state.save(journal);return owned;
}
function restoreStartupConfig(fs, crypto, base) {
 if(!/^\/var\/lib\/personalhome(?:-validation\.[a-f0-9]{32})?$/.test(base))throw Error('Invalid startup state directory');
 var contractPath=base+'/startup-config.json';
 if(!fs.existsSync(contractPath))return false;
 function safe(p,directory){var s=fs.lstatSync(p);if(s.isSymbolicLink()||s.uid!==0||(s.mode&18)!==0||(directory?!s.isDirectory():!s.isFile()||s.nlink!==1))throw Error('Unsafe startup config path:'+p);return s;}
 function bytes(p){safe(p,false);return fs.readFileSync(p);}
 function sha(data){return crypto.createHash('sha256').update(data).digest('hex');}
 if((safe(base,true).mode&511)!==448)throw Error('Startup state directory must be0700');safe('/var/luna/preferences',true);
 var contract=JSON.parse(bytes(contractPath).toString());
 if(contract.schema!==1||contract.path!=='/var/luna/preferences/bootd.json'||!/^[a-f0-9]{64}$/.test(contract.originalSha256)||!/^[a-f0-9]{64}$/.test(contract.candidateSha256))throw Error('Invalid startup config contract');
 var original=bytes(base+'/bootd-before.json');
 if(sha(original)!==contract.originalSha256)throw Error('Startup config backup changed');
 var current=sha(bytes(contract.path));
 if(current===contract.originalSha256)return false;
 if(current!==contract.candidateSha256)throw Error('Foreign startup config preserved');
 var temporary=contract.path+'.personalhome-restore.'+crypto.randomBytes(8).toString('hex');
 fs.writeFileSync(temporary,original,{mode:384,flag:'wx'});
 var fd=fs.openSync(temporary,'r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
 current=sha(bytes(contract.path));
 if(current!==contract.originalSha256&&current!==contract.candidateSha256)throw Error('Startup config changed during restoration');
 fs.renameSync(temporary,contract.path);
 fd=fs.openSync('/var/luna/preferences','r');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
 return true;
}
function bootReady(snapshot) {
 return !!(snapshot && snapshot.power && snapshot.power.returnValue === true && snapshot.power.state === 'Active'
  && snapshot.boot && snapshot.boot.returnValue === true && snapshot.boot.signals && snapshot.boot.signals['boot-done'] === true
  && snapshot.cover && snapshot.cover.returnValue === true && snapshot.cover.isRunning === false
  && snapshot.ui && snapshot.ui.returnValue === true && ['none','home','launcher','smartHome'].indexOf(snapshot.ui.currentState) >= 0
  && foreground(snapshot.surface));
}
function bootGate(state, snapshot, identity) {
 var app = foreground(snapshot && snapshot.surface);
 if (!bootReady(snapshot) || !identity) { state.app = ''; state.identity = ''; state.samples = 0; return false; }
 if (state.app !== app || state.identity !== identity) { state.app = app; state.identity = identity; state.samples = 1; return false; }
 return ++state.samples >= 2;
}
function number(value) { return typeof value === 'number' && isFinite(value) && Math.floor(value) === value && value >= 0; }
function healthShape(h, nonce) {
 return !!(h && h.schema === 3 && h.nonce === nonce && number(h.frameSequence) && number(h.renderProbe)
  && typeof h.powerActive === 'boolean' && typeof h.focusRequired === 'boolean' && typeof h.coverOpen === 'boolean'
  && typeof h.overlayOpen === 'boolean' && typeof h.foregroundAppId === 'string'
  && (!h.foregroundAppId || appId(h.foregroundAppId) || h.coverOpen && transient.indexOf(h.foregroundAppId)>=0));
}
function failure(state, h, nonce, now) {
 if (!healthShape(h, nonce)) return 'invalid-runtime-health';
 if (!h.powerActive) { state.unusableSince = null; state.reason = ''; return null; }
 var reason = !h.ready || !h.nativeContextAttached || !h.windowAttached ? 'native-view-not-ready'
  : h.shown && !h.visible ? 'home-not-visible'
  : h.shown && h.focusRequired && !h.activeFocus ? 'home-focus-unavailable'
  : !h.shown && !h.overlayOpen && !h.coverOpen && !recoveryAppId(h.foregroundAppId) ? 'no-usable-foreground'
  : h.coverOpen ? 'startup-cover-did-not-finish' : '';
 if (!reason) { state.unusableSince = null; state.reason = ''; return null; }
 if (state.reason !== reason) { state.reason = reason; state.unusableSince = now; }
 var limit = reason === 'native-view-not-ready' ? 35 : reason === 'startup-cover-did-not-finish' ? 30 : 8;
 return now - state.unusableSince >= limit ? reason : null;
}
module.exports = {startupBridge:startupBridge,appId:appId,recoveryAppId:recoveryAppId,foreground:foreground,bootIntent:bootIntent,quietStartupAudio:quietStartupAudio,prepareStartupInput:prepareStartupInput,restoreStartupInput:restoreStartupInput,restoreStartupConfig:restoreStartupConfig,bootReady:bootReady,bootGate:bootGate,healthShape:healthShape,failure:failure};
