'use strict';
var fs=require('fs'),vm=require('vm'),assert=require('assert');
var files=JSON.parse(fs.readFileSync(0,'utf8'));
function fn(text,name){
 var start=text.indexOf('function '+name+'(');assert(start>=0,name);
 var open=text.indexOf('{',start),depth=1,end=open+1;
 while(depth&&end<text.length){if(text[end]==='{')depth++;else if(text[end]==='}')depth--;end++;}
 return text.slice(start,end);
}
function handler(text,name){
 var start=text.indexOf(name+': {');assert(start>=0,name);
 var open=text.indexOf('{',start),depth=1,end=open+1;
 while(depth&&end<text.length){if(text[end]==='{')depth++;else if(text[end]==='}')depth--;end++;}
 return text.slice(open+1,end-1);
}
function nativeInput(){
 var pauses=[],starts=0;
 var service={globalVars:{appId:'com.webos.app.livetv'},pauseACB:{callService:function(params){pauses.push(params);}}};
 vm.createContext(service);vm.runInContext(fn(files['native/AcbService.qml'],'setPause'),service);
 var acb={context:'input-owned-pipeline',acbService:{appStateSet:{Background:'background'},playStateSet:{Paused:'paused'},setPause:service.setPause},getCurrentVideoCancel:function(){},getDolbyConflictStatusCancel:function(){}};
 vm.createContext(acb);vm.runInContext(fn(files['native/AcbController.qml'],'pauseACB'),acb);
 var display={acbController:acb,_isFirstLaunch:false,_playerPipelineId:'',globalVars:{inputType:'TV',appStatus:{},interactiveAppModel:{channelPlus:false}},
  console:{log:function(){}},channelService:{getSignalLevelCancel:function(){}},signalLevelUpdated:function(){},isRecordingAbortChanged:function(){},
  tvPowerService:{registerScreenSaverRequest:function(){},registerScreenSaverRequestCancel:function(){}},startVideo:function(){starts++;}};
 vm.createContext(display);['appActivated','appDeactivated','stopVideo','pause','playerDisconnect'].forEach(function(name){vm.runInContext(fn(files['native/DisplayVideoModel.qml'],name),display);});
 var main={isActivate:true,mainView:{activate:display.appActivated,deactivate:display.appDeactivated}};
 vm.createContext(main);['windowMinimized','windowMaximized'].forEach(function(name){vm.runInContext(fn(files['native/main.qml'],name),main);});
 return {minimize:main.windowMinimized,maximize:main.windowMaximized,pauses:pauses,starts:function(){return starts;}};
}
function fixture(initialPower){
 var calls=0,nextToken=0,minimized=0,resumed=0,serviceCalls=[],launched=[];
 var c={generation:0,requestGeneration:-1,requestToken:-1,sleeping:false,observedActive:false,nativeOffCount:0,nativeOnCount:0,lastReason:'',queried:false,interrupted:false,armed:false,requested:false,mappingHeld:false,pausedSurface:null,bridgeSurface:null,bridgeGeneration:-1,bridgeAcknowledged:false,
  bridgeReadyOwned:false,bridgeReadyToken:-1,bridgeReadyGeneration:-1,bridgeReadySurface:null,bridgeReadyUntil:-1,bridgeReadyNext:0,bridgeReadySent:0,bridgeReadyAttempts:0,
  personalHomeStartupReleased:false,personalHomeStartupSurface:null,nativeIntent:null,now:100,foregroundRows:[],
  personalHomeStartupIntentFile:{read:function(){if(!c.nativeIntent)throw Error('no startup intent');return JSON.stringify(c.nativeIntent);}},personalHomeStartupUptimeFile:{read:function(){return String(c.now)+' 0';}},
  foregroundAppInfoMgr:{getForegroundAppInfo:function(){return c.foregroundRows;}},
  systemSettings:{powerState:initialPower===undefined?'Active':initialPower,powerProcessing:'',disableHome:false,bootFirstUse:false},
  uiScope:{personalHomeOwnsRibbon:true,focusPersonalHome:function(){}},personalHomeLoader:{item:{activeFocus:true}},
  overlayView:{accessRibbon:true,state:'closed'},notificationView:{modalAlertActive:false,closePincodePrompt:function(){}},
  globalActions:{popupOpen:false,closePopups:function(){}},fullscreenView:{delegating:false},
  reasonService:{call:function(service,method,payload){serviceCalls.push({service:service,method:method,payload:JSON.parse(payload)});return ++nextToken;}},
  ysm:{state:'hidden',smartTvReady:true,coverUIOpen:false,access:{ribbon:true},foregroundSufaceWasHidden:false,
   goHome:function(){calls++;this.state=this.state==='visible'?'hidden':'visible';},
   gotoState:function(state,callback){this.state=state;if(callback)callback();},recentsWindowModel:{},
   appList:{getAppInfoAbsPath:function(){return '';},getAppInfoValue:function(){return '';}},
   magnifier:{isRun:function(){return false;}},isRibbonHolderApp:function(){return false;},
   launchPointsModel:{getLaunchPointByAppId:function(id){return {id:id};}},launchPointActivated:function(point){launched.push(point.id);}},
  compositor:{fullscreen:{appId:'com.webos.app.livetv',customImageFilePath:'none',state:2,requestFullscreen:function(){resumed++;this.state=2;}},prepareSnapShot:function(){minimized++;}},
  root:{state:'hidden'},superRibbon:{state:'home'},today:{hide:function(){},isVisible:function(){return false;}},overlaySurfaceGroupView:{state:'closed'},
  Qt:{Key_Left:40,Key_Right:42,Key_Up:41,Key_Down:43,Key_Return:44,Key_Enter:45,Key_PowerOff:999,WindowMinimized:1,WindowFullScreen:2,binding:function(f){return f();}},access:{assignPoliciesFromItem:function(){}},
  console:{log:function(){},warn:function(){}},speakKeyEvents:function(){},KeyPolicy:{NextPolicy:3},
  launcherOnBootTimer:{start:function(){}}
 };
 c.ysm.personalHomePowerWake=c;
 Object.defineProperty(c.uiScope,'personalHomeShown',{get:function(){return c.uiScope.personalHomeOwnsRibbon&&c.ysm.state==='visible';}});
 Object.defineProperty(c,'state',{get:function(){return c.ysm.state;},set:function(value){c.ysm.state=value;}});
 c.access.ribbon=true;c.closeOverlaidItems=function(){};c.FocusHandler={requestFocus:function(){}};
 c.gotoState=function(state,callback){c.ysm.gotoState(state,callback);};
 c.item={completeAction:function(){}};c.forgetLaunch=function(){};
 vm.createContext(c);
 ['personalHomeStartupClock','personalHomeStartupPending','personalHomeStartupEmptyHold','personalHomeStartupBridgeMapped','personalHomeStartupComposed'].forEach(function(name){vm.runInContext(fn(files['YSM/YSM.qml'],name),c);c.ysm[name]=c[name];});
 var foregroundSource=process.argv.indexOf('--before-startup-hold')>=0?files['baseline/YSM.qml']:files['YSM/YSM.qml'];
 vm.runInContext(fn(foregroundSource,'getForegroundAppInfo'),c);
 var controller=files['YSM/YSM.qml'].slice(files['YSM/YSM.qml'].indexOf('id: personalHomePowerWakeController'));
 ['cancel','powerChanged','receive','tryShow','keepHomeForSurface','bridgeReadyContext','acknowledgeBridgeFrame','resumePausedInput','nativeShowHome'].forEach(function(name){vm.runInContext(fn(controller,name),c);});
 ['nativePowerOff','nativePowerOn','nativeResume'].forEach(function(name){if(controller.indexOf('function '+name+'(')>=0)vm.runInContext(fn(controller,name),c);});
 vm.runInContext(fn(files['YSM/YSM.qml'],'handleAction'),c);
 vm.runInContext(fn(files['YSM/YSM.qml'],'goHome'),c);
 vm.runInContext(fn(files['YSM/YSM.qml'],'showHome'),c);
 vm.runInContext(fn(files['YSM/compositor.js'],'fullscreenSurfaceChanged'),c);
 vm.runInContext(fn(files['YSM/compositor.js'],'minimizeByAppId'),c);
 c.CompositorLogic={minimizeByAppId:c.minimizeByAppId};
 c.powerEvents=[];c.recentsDb={storeRecents:function(){c.powerEvents.push('store-recents');}};
 c.magnifier={storeProperty:function(){}};c.pmLog={info:function(){}};
 c.tvPowerResponse={acceptPowerOff:function(value){assert.equal(value,true);assert.equal(c.sleeping,true,'wake intent precedes native off acknowledgement');c.powerEvents.push('ack-off');},acceptPowerOn:function(value){assert.equal(value,true);c.powerEvents.push('ack-on');}};
 c.ysm.prepareSystemSuspended=function(){assert.equal(c.sleeping,true,'wake intent precedes native suspend preparation');c.powerEvents.push('prepare-suspend');c.ysm.state='hidden';};
 c.CompositorLogic.clearFullscreen=function(){c.compositor.fullscreen=null;};c.compositor.setMouseFocus=function(){};
 c.safePreparingPowerOnTimer={restart:function(){c.powerEvents.push('native-on-timer');}};
 c.nativePowerEvent=function(type){
  var map={suspend:['tvPowerPrepareSuspend','registerPrepareSuspend','systemSuspended','onSystemSuspended'],off:['tvPowerPreparePowerOff','registerPreparePowerOff','systemPowerOff','onSystemPowerOff'],on:['tvPowerPreparePowerOn','registerPreparePowerOn','systemPowerOn','onSystemPowerOn']},entry=map[type];
  c.systemSettings[entry[2]]=function(){vm.runInContext('(function(){'+handler(files['YSM/YSM.qml'],entry[3])+'})()',c);};
  var s={root:c.systemSettings,console:c.console,method:entry[1],payload:'{"timestamp":"native-event"}'};s[entry[1]]=entry[1];
  vm.runInNewContext('(function(){'+handler(files['YSM/SystemSettings.qml'].slice(files['YSM/SystemSettings.qml'].indexOf('id: '+entry[0])),'onResponse')+'})()',s);
 };
 vm.runInContext(fn(files['YSM/StarfishKeyFilter.qml'],'preProcess'),c);
 c.sleep=function(){c.nativePowerEvent('suspend');c.systemSettings.powerState='Suspend';c.systemSettings.powerProcessing='';c.uiScope.personalHomeOwnsRibbon=false;c.powerChanged();};
 c.resume=function(reason){c.systemSettings.powerProcessing='Prepare Resume';c.powerChanged(true);assert.equal(c.requestToken,-1);c.systemSettings.powerProcessing='LastInput Ready';c.powerChanged(true);var token=c.requestToken;c.receive(token,'/power/getPowerOnReason',JSON.stringify({returnValue:true,reason:reason}));c.systemSettings.powerState='Active';c.systemSettings.powerProcessing='';c.uiScope.personalHomeOwnsRibbon=true;c.powerChanged();return token;};
 c.calls=function(){return calls;};c.minimizes=function(){return minimized;};c.resumes=function(){return resumed;};c.serviceCalls=serviceCalls;c.launched=launched;c.powerChanged();return c;
}
var completionWake=fixture();completionWake.sleep();completionWake.systemSettings.powerProcessing='Prepare Resume';completionWake.powerChanged(true);
assert.equal(completionWake.requestToken,-1,'Prepare Resume may still report old AC reason and must not consume native off intent');assert.equal(completionWake.sleeping,true);
completionWake.systemSettings.powerState='Active';completionWake.uiScope.personalHomeOwnsRibbon=true;completionWake.powerChanged();assert.equal(completionWake.requestToken,-1,'Active alone is not native reason completion');
completionWake.systemSettings.powerProcessing='LastInput Ready';completionWake.powerChanged(true);assert(completionWake.requestToken>0);completionWake.receive(completionWake.requestToken,'/power/getPowerOnReason','{"returnValue":true,"reason":"remoteKey"}');assert.equal(completionWake.calls(),1);assert.equal(completionWake.nativeOnCount,0,'Suspend resume does not require SystemPowerOn callback');
completionWake.systemSettings.powerProcessing='Screen On';completionWake.powerChanged(true);assert.equal(completionWake.serviceCalls.filter(function(call){return call.method==='/power/getPowerOnReason';}).length,1,'later completion is idempotent');
var nativeWake=fixture();nativeWake.systemSettings.powerProcessing='LastInput Ready';nativeWake.nativePowerEvent('off');
assert.equal(nativeWake.sleeping,true,'native prepare-off must record wake intent even when getPowerState stays Active');assert.deepEqual(nativeWake.powerEvents,['store-recents','ack-off']);
nativeWake.powerChanged();assert.equal(nativeWake.requestToken,-1,'stale Active and old LastInput Ready cannot query an off-cycle reason');
nativeWake.compositor.fullscreen=null;nativeWake.nativePowerEvent('on');assert.equal(nativeWake.requestToken,-1,'native prepare-PowerOn is not reason completion');nativeWake.systemSettings.powerProcessing='Prepare Power On';nativeWake.powerChanged(true);nativeWake.systemSettings.powerProcessing='LastInput Ready';nativeWake.powerChanged(true);assert(nativeWake.requestToken>0,'native completion queries the new reason without a Suspend state sample');
nativeWake.receive(nativeWake.requestToken,'/power/getPowerOnReason','{"returnValue":true,"reason":"remoteKey"}');assert.equal(nativeWake.ysm.state,'visible');assert.equal(nativeWake.powerEvents[nativeWake.powerEvents.length-1],'ack-on');
nativeWake.preProcess(0x01200201,true,false);nativeWake.preProcess(0x01200202,true,false);assert.equal(nativeWake.armed,true,'cursor show/hide are not a new user intent');
var callbackOnly=fixture();callbackOnly.compositor.fullscreen=null;callbackOnly.nativePowerEvent('on');assert.equal(callbackOnly.requestToken,-1,'initial native on without an off callback cannot arm cold Home');assert.deepEqual(callbackOnly.powerEvents,['ack-on']);
callbackOnly=fixture();callbackOnly.nativePowerEvent('off');var offGeneration=callbackOnly.generation;callbackOnly.nativePowerEvent('suspend');assert.equal(callbackOnly.generation,offGeneration,'off and suspend callbacks belong to one generation');assert.equal(callbackOnly.nativeOffCount,2);
callbackOnly.systemSettings.powerState='Screen Off';callbackOnly.uiScope.personalHomeOwnsRibbon=false;callbackOnly.powerChanged();assert.equal(callbackOnly.requestToken,-1);
callbackOnly.nativePowerEvent('on');assert.equal(callbackOnly.requestToken,-1);assert.equal(callbackOnly.powerEvents[callbackOnly.powerEvents.length-1],'native-on-timer','native deferred acknowledgement branch remains intact');
callbackOnly.systemSettings.powerProcessing='Prepare Power On';callbackOnly.powerChanged(true);assert.equal(callbackOnly.requestToken,-1);callbackOnly.systemSettings.powerProcessing='LastInput Ready';callbackOnly.powerChanged(true);old=callbackOnly.requestToken;assert(old>0,'completion is accepted even before the Active state sample');
callbackOnly.receive(old,'/power/getPowerOnReason','{"returnValue":true,"reason":"remoteKey"}');assert.equal(callbackOnly.calls(),0,'resume reason alone cannot show Home before readiness');
callbackOnly.systemSettings.powerState='Active';callbackOnly.uiScope.personalHomeOwnsRibbon=true;callbackOnly.powerChanged();assert.equal(callbackOnly.calls(),1);
callbackOnly.nativePowerEvent('on');assert.equal(callbackOnly.serviceCalls.filter(function(call){return call.method==='/power/getPowerOnReason';}).length,1,'duplicate native on cannot query twice');
callbackOnly=fixture();callbackOnly.nativePowerEvent('off');callbackOnly.compositor.fullscreen=null;callbackOnly.nativePowerEvent('on');callbackOnly.systemSettings.powerProcessing='LastInput Ready';callbackOnly.powerChanged(true);callbackOnly.receive(callbackOnly.requestToken,'/power/getPowerOnReason','{"returnValue":true,"reason":"amazon"}');assert.equal(callbackOnly.calls(),0);assert.equal(callbackOnly.lastReason,'amazon');assert.equal(callbackOnly.armed,false,'app-button reason preserves native app launch');
callbackOnly=fixture();callbackOnly.sleep();callbackOnly.systemSettings.powerProcessing='LastInput Ready';callbackOnly.powerChanged(true);old=callbackOnly.requestToken;callbackOnly.preProcess(0x01200201,true,false);callbackOnly.preProcess(0x01200202,true,false);assert.equal(callbackOnly.requestToken,old,'cursor events preserve pending reason generation');callbackOnly.preProcess(12345,true,false);callbackOnly.receive(old,'/power/getPowerOnReason','{"returnValue":true,"reason":"remoteKey"}');assert.equal(callbackOnly.armed,false,'real new key still cancels pending native wake');
var cold=fixture('');cold.systemSettings.powerState='Active';cold.powerChanged();assert.equal(cold.requestToken,-1,'initial unknown to Active is not a warm wake');
cold=fixture('Suspend');cold.resume('remoteKey');assert.equal(cold.requestToken,-1);assert.equal(cold.calls(),0,'initial Suspend without an observed Active must not arm');
var f=fixture();f.powerChanged();assert.equal(f.calls(),0,'cold activation does not invent a warm wake');
f.systemSettings.powerState='Screen Off';f.powerChanged();f.systemSettings.powerState='Active';f.powerChanged();assert.equal(f.requestToken,-1,'screen blanking is not a Power wake');
f.sleep();f.resume('remoteKey');assert.equal(f.calls(),1);assert.equal(f.ysm.state,'visible');
f.showHome({});f.showHome({});assert.equal(f.calls(),1,'delayed native showHome cannot toggle fulfilled wake');
f.fullscreenSurfaceChanged();assert.equal(f.ysm.state,'visible','first automatic last-input mapping preserves Home');
assert.equal(f.minimizes(),1,'automatic LiveTV must enter its native minimized media lifecycle');
f.fullscreenSurfaceChanged();assert.equal(f.ysm.state,'visible','same minimized surface callback is reentrant');assert.equal(f.minimizes(),1);
f.compositor.fullscreen.state=2;f.fullscreenSurfaceChanged();assert.equal(f.ysm.state,'hidden','later fullscreen request is not suppressed');assert.equal(f.armed,false);
['amazon','netflix','unknown'].forEach(function(reason){var x=fixture();x.sleep();x.resume(reason);assert.equal(x.calls(),0);assert.equal(x.armed,false);});
f=fixture();f.sleep();f.systemSettings.powerProcessing='LastInput Ready';f.powerChanged(true);var old=f.requestToken;
f.preProcess(42,true,false);f.receive(old,'/power/getPowerOnReason','{"returnValue":true,"reason":"remoteKey"}');assert.equal(f.armed,false,'app key cancels stale reason reply');
f=fixture();f.sleep();f.resume('remoteKey');f.preProcess(42,true,false);f.fullscreenSurfaceChanged();assert.equal(f.ysm.state,'hidden');assert.equal(f.armed,false);
f=fixture();f.sleep();f.resume('remoteKey');f.fullscreenSurfaceChanged();f.preProcess(42,true,false);assert.equal(f.resumes(),0,'arrows must not resume TV audio');f.showHome({});assert.equal(f.ysm.state,'visible','native showHome stays idempotent after arrows cancel wake intent');f.handleAction('back');assert.equal(f.resumes(),1,'explicit UI Back resumes paused TV');assert.equal(f.ysm.state,'hidden');
f=fixture();f.sleep();f.resume('remoteKey');f.fullscreenSurfaceChanged();f.preProcess(42,true,false);f.goHome();assert.equal(f.resumes(),1,'native Home/Back dismissal resumes paused input');assert.equal(f.ysm.state,'hidden');
f=fixture();f.sleep();f.resume('remoteKey');f.fullscreenSurfaceChanged();f.preProcess(42,true,false);f.compositor.fullscreen={appId:'com.abrantesflix.app',state:2};f.fullscreenSurfaceChanged();assert.equal(f.resumes(),0,'app launch cannot resume paused LiveTV');
f=fixture();f.sleep();f.ysm.coverUIOpen=true;f.resume('remoteKey');assert.equal(f.calls(),0);f.ysm.coverUIOpen=false;f.tryShow();assert.equal(f.calls(),1);
f=fixture();f.sleep();f.ysm.access.ribbon=false;f.resume('remoteKey');assert.equal(f.calls(),0);f.ysm.access.ribbon=true;f.tryShow();assert.equal(f.calls(),1);
f=fixture();f.sleep();f.resume('remoteKey');f.preProcess(999,true,false);assert.equal(f.armed,true,'initiating Power key is not a new app intent');
f=fixture();f.sleep();f.resume('remoteKey');f.compositor.fullscreen.appId='com.abrantesflix.app';f.fullscreenSurfaceChanged();assert.equal(f.armed,false);assert.equal(f.ysm.state,'hidden');
f=fixture();f.sleep();f.resume('remoteKey');f.compositor.fullscreen.appId='com.personalhome.startup';f.fullscreenSurfaceChanged();assert.equal(f.ysm.state,'visible','automatic silent bridge must preserve Home');assert.equal(f.minimizes(),0,'bridge is not paused as LiveTV');
function acks(context){return context.serviceCalls.filter(function(call){return call.method==='/ready';});}
assert.equal(acks(f).length,0,'mapping without a Home frame cannot acknowledge bridge');
f.personalHomeLoader.item.activeFocus=false;f.acknowledgeBridgeFrame();assert.equal(acks(f).length,0,'unfocused Home frame cannot acknowledge');
f.personalHomeLoader.item.activeFocus=true;f.acknowledgeBridgeFrame();f.acknowledgeBridgeFrame();assert.equal(acks(f).length,1,'one frame ACK per wake');
assert.deepEqual(acks(f)[0],{service:'luna://com.personalhome.startup.service',method:'/ready',payload:{nonce:'__NONCE__'}});
assert.equal(f.bridgeAcknowledged,false,'attempted readiness call is not an accepted ACK');
f.preProcess(42,true,false);assert.equal(f.armed,false);assert.equal(f.bridgeReadyOwned,true,'Home arrows preserve independent frame-proven readiness');
f.receive(f.bridgeReadyToken,'/ready','{"returnValue":false,"errorCode":2}');f.now=101;f.acknowledgeBridgeFrame();assert.equal(acks(f).length,2,'late bridge subscriber is retried after Home navigation');
f.receive(f.bridgeReadyToken,'/ready','{"returnValue":true,"nonce":"wrong","ready":true}');assert.equal(f.bridgeAcknowledged,false);
f.now=102;f.acknowledgeBridgeFrame();f.receive(f.bridgeReadyToken,'/ready','{"returnValue":true,"nonce":"__NONCE__","ready":true}');assert.equal(f.bridgeAcknowledged,true);f.acknowledgeBridgeFrame();assert.equal(acks(f).length,3);
f.handleAction('back');assert.deepEqual(f.launched,['com.webos.app.livetv'],'Back launches real input, not the bridge');assert.equal(f.resumes(),0);assert.equal(f.ysm.state,'hidden');
f=fixture();f.sleep();f.resume('remoteKey');f.compositor.fullscreen.appId='com.personalhome.startup';f.fullscreenSurfaceChanged();f.ysm.launchPointsModel.getLaunchPointByAppId=function(){return null;};f.handleAction('back');assert.equal(f.ysm.state,'visible','missing input launchpoint cannot expose silent black bridge');
f=fixture();f.sleep();f.resume('remoteKey');f.compositor.fullscreen.appId='com.personalhome.startup';f.fullscreenSurfaceChanged();f.systemSettings.lastInputApp='com.webos.app.hdmi2';f.goHome();assert.deepEqual(f.launched,['com.webos.app.hdmi2']);assert.equal(f.ysm.state,'hidden');
f=fixture();f.sleep();f.systemSettings.powerProcessing='LastInput Ready';f.powerChanged(true);var bridgeToken=f.requestToken;f.compositor.fullscreen.appId='com.personalhome.startup';f.fullscreenSurfaceChanged();f.acknowledgeBridgeFrame();assert.equal(acks(f).length,0,'bridge mapped before reason/visible Home cannot ACK');
f.receive(bridgeToken,'/power/getPowerOnReason','{"returnValue":true,"reason":"remoteKey"}');f.systemSettings.powerState='Active';f.systemSettings.powerProcessing='';f.uiScope.personalHomeOwnsRibbon=true;f.powerChanged();f.acknowledgeBridgeFrame();assert.equal(acks(f).length,1,'post-wake bridge mapping recorded before Home is acknowledged after its frame');
f.sleep();f.resume('remoteKey');f.acknowledgeBridgeFrame();assert.equal(acks(f).length,1,'next wake cannot ACK an old bridge before a new native mapping');
f=fixture();f.sleep();f.resume('amazon');f.compositor.fullscreen.appId='com.personalhome.startup';f.fullscreenSurfaceChanged();f.acknowledgeBridgeFrame();assert.equal(acks(f).length,0,'app-button wake cannot acknowledge automatic bridge');
f=fixture();f.sleep();f.resume('remoteKey');f.compositor.fullscreen.appId='com.personalhome.startup';f.fullscreenSurfaceChanged();f.acknowledgeBridgeFrame();var inflight=f.bridgeReadyToken;f.now=101;f.acknowledgeBridgeFrame();assert.equal(acks(f).length,1,'one readiness request stays in flight');f.now=102;f.acknowledgeBridgeFrame();assert.equal(acks(f).length,2,'unanswered readiness call has bounded retry');f.receive(inflight,'/ready','{"returnValue":true,"nonce":"__NONCE__","ready":true}');assert.equal(f.bridgeAcknowledged,false,'stale token cannot accept readiness');
for(var second=103;second<=108;second++){f.now=second;f.receive(f.bridgeReadyToken,'/ready','{"returnValue":false}');f.acknowledgeBridgeFrame();}assert(acks(f).length<=6);assert.equal(f.bridgeAcknowledged,false,'retry deadline never declares success');
f=fixture();f.sleep();f.resume('remoteKey');f.compositor.fullscreen.appId='com.personalhome.startup';f.fullscreenSurfaceChanged();f.acknowledgeBridgeFrame();inflight=f.bridgeReadyToken;f.compositor.fullscreen={appId:'com.abrantesflix.app',state:2};f.fullscreenSurfaceChanged();assert.equal(f.bridgeReadyOwned,false);f.receive(inflight,'/ready','{"returnValue":true,"nonce":"__NONCE__","ready":true}');assert.equal(f.bridgeAcknowledged,false,'new app card cancels old Home readiness');
var early=fixture();early.nativeIntent={nonce:'__NONCE__',bridge:true,pending:true,until:147};delete early.uiScope;delete early.personalHomeLoader;
assert.equal(JSON.parse(early.getForegroundAppInfo({})).reason,'forceMinimize','earliest native NULL callback before child UI objects must hold SAM last-input fallback');
early.foregroundRows=[{appId:'com.abrantesflix.app'}];assert.equal(JSON.parse(early.getForegroundAppInfo({})).reason,undefined,'real user app foreground is unchanged');
early.foregroundRows=[];early.nativeIntent.nonce='stale';assert.equal(JSON.parse(early.getForegroundAppInfo({})).reason,undefined);
early.nativeIntent.nonce='__NONCE__';early.nativeIntent.until=148;assert.equal(JSON.parse(early.getForegroundAppInfo({})).reason,undefined,'an overlong startup hold is rejected');
early.nativeIntent.until=147;early.now=147;assert.equal(JSON.parse(early.getForegroundAppInfo({})).reason,undefined,'deadline releases hold without declaring success');
early.now=100;early.nativeIntent.pending=false;assert.equal(JSON.parse(early.getForegroundAppInfo({})).reason,undefined,'guard fallback releases hold');
var coldHold=fixture();coldHold.nativeIntent={nonce:'__NONCE__',bridge:true,pending:true,until:147};coldHold.compositor.fullscreen.appId='com.personalhome.startup';coldHold.ysm.state='visible';coldHold.fullscreenSurfaceChanged();assert.equal(coldHold.ysm.state,'visible','cold bridge mapping cannot hide Home');
coldHold.personalHomeLoader.item.activeFocus=false;coldHold.acknowledgeBridgeFrame();assert.equal(coldHold.personalHomeStartupReleased,false,'mapping plus unfocused frame is not success');
coldHold.personalHomeLoader.item.activeFocus=true;coldHold.acknowledgeBridgeFrame();assert.equal(coldHold.personalHomeStartupReleased,true,'real bridge mapping and focused Home frame release native hold');assert.equal(acks(coldHold).length,0,'cold readiness ACK belongs to guard only');
assert.equal(JSON.parse(coldHold.getForegroundAppInfo({})).reason,undefined);
coldHold.nativeIntent.pending=false;coldHold.fullscreenSurfaceChanged();assert.equal(coldHold.ysm.state,'visible','late same bridge mapping keeps composed Home after guard acceptance');
coldHold.cancel();coldHold.compositor.fullscreen={appId:'com.personalhome.startup',state:2};coldHold.fullscreenSurfaceChanged();assert.equal(coldHold.ysm.state,'visible','late replacement bridge card also preserves already shown Home');
coldHold.compositor.fullscreen={appId:'com.abrantesflix.app',state:2};coldHold.fullscreenSurfaceChanged();assert.equal(coldHold.ysm.state,'hidden','bridge preservation never applies to a real app');
coldHold.compositor.fullscreen={appId:'com.personalhome.startup',state:2};coldHold.fullscreenSurfaceChanged();assert.equal(coldHold.ysm.state,'hidden','late bridge card cannot reopen dismissed Home');
f=fixture();f.sleep();f.systemSettings.powerProcessing='LastInput Ready';f.powerChanged(true);old=f.requestToken;f.systemSettings.powerState='Active';f.powerChanged();f.sleep();f.systemSettings.powerProcessing='LastInput Ready';f.powerChanged(true);f.receive(old,'/power/getPowerOnReason','{"returnValue":true,"reason":"remoteKey"}');assert.equal(f.armed,false,'previous wake token cannot arm new generation');
console.log('PASS native Power wake chain: intent, readiness, one mapping, delayed showHome, cancellation and stale replies');
if(files['native/ScreenSaverView.qml']){
 function expireIdle(source,ownsHome){
  var c=fixture(),cleanup=[];c.ysm.state='visible';c.uiScope.personalHomeOwnsRibbon=ownsHome;
  c.compositor.fullscreen.appId='com.personalhome.startup';c.superRibbon.shows={videoCompositing:false};
  c.today.hide=function(){cleanup.push('today');};c.globalActions.closePopups=function(){cleanup.push('popups');};
  ['closeAlert','closeModalAlert','closeAdvancedAlert','closePincodePrompt'].forEach(function(name){c.notificationView[name]=function(){cleanup.push(name);};});
  c.compositor.xInput={sendDeactivationAll:function(){cleanup.push('xInput');}};c.appSpinner={visible:false};
  vm.runInContext('function expire(userActivityTimer){'+handler(source,'onUserActivityExpired')+'}',c);
  c.cursorHidden=true;c.root={userActivityExpired:function(timer){c.expire(timer);}};
  vm.runInContext('(function(){'+handler(files['native/ScreenSaverView.qml'],'onTriggered')+'})()',c);
  c.idleCleanup=cleanup;return c;
 }
 var policy=require('../operations/runtime/policy.js');
 function idleHealth(c){return {schema:3,nonce:'a'.repeat(32),frameSequence:10,renderProbe:2,powerActive:true,focusRequired:false,coverOpen:false,overlayOpen:false,foregroundAppId:c.compositor.fullscreen.appId,ready:true,nativeContextAttached:true,windowAttached:true,shown:c.uiScope.personalHomeShown,visible:c.uiScope.personalHomeShown,activeFocus:true};}
 var beforeIdle=expireIdle(files['baseline/YSM.qml'],true),unhealthy={};assert.equal(beforeIdle.ysm.state,'hidden');
 assert.equal(policy.failure(unhealthy,idleHealth(beforeIdle),'a'.repeat(32),120),null);assert.equal(policy.failure(unhealthy,idleHealth(beforeIdle),'a'.repeat(32),128),'no-usable-foreground');
 var afterIdle=expireIdle(files['YSM/YSM.qml'],true),healthy={};assert.equal(afterIdle.ysm.state,'visible','native idle timeout must retain shown PersonalHome');
 assert.equal(policy.failure(healthy,idleHealth(afterIdle),'a'.repeat(32),120),null);assert.equal(policy.failure(healthy,idleHealth(afterIdle),'a'.repeat(32),128),null);
 assert.deepEqual(afterIdle.idleCleanup,beforeIdle.idleCleanup,'native idle cleanup must be preserved');
 assert.equal(expireIdle(files['YSM/YSM.qml'],false).ysm.state,'hidden','native original/fallback Home still expires');
 console.log('PASS native idle callback and watchdog policy');
}
if(files['native/main.qml']){
 var input=nativeInput(),audio=fixture(),surface=audio.compositor.fullscreen,current=2;
 Object.defineProperty(surface,'state',{get:function(){return current;},set:function(value){current=value;if(value===1)input.minimize();else if(value===2)input.maximize();}});
 audio.sleep();audio.resume('remoteKey');audio.fullscreenSurfaceChanged();
 assert.equal(audio.compositor.fullscreen,surface,'native minimize retains the exact surface pointer');
 assert.equal(input.pauses.length,1);assert.deepEqual(input.pauses[0],{appId:'com.webos.app.livetv',pipelineId:'input-owned-pipeline',appState:'background',playState:'paused'});
 audio.fullscreenSurfaceChanged();assert.equal(input.pauses.length,1,'reentrant minimized state must not issue another media pause');
 surface.requestFullscreen();assert.equal(input.starts(),1,'TV shortcut resumes via native windowMaximized and appActivated');
 console.log('PASS captured inputcommon media lifecycle: native minimize, owned ACB pause, TV shortcut resume');
}
