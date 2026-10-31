'use strict';
var fs=require('fs'),vm=require('vm'),assert=require('assert');
var text=fs.readFileSync(process.argv[2]+'/module/YSM/YSM.qml','utf8'),start=text.indexOf('    function launchPointActivated('),end=text.indexOf('\n    CoverViewContainer {',start),source=text.slice(start,end),tests=0;
assert(source.indexOf('restoreHidden !== true')>=0);
function check(name,hidden,restore,hasSurface){
 var surfaced=0,launched=0,accepted=0;
 var surface={isSurfaced:function(){return true;},itemState:1,launchRequired:false,type:'_WEBOS_WINDOW_TYPE_CARD',requestFullscreen:function(){surfaced++;}};
 var ysm={state:hidden?'hidden':'visible',style:{baseWidth:1920,baseHeight:1080},gotoState:function(state,callback){assert.equal(state,'hidden');callback();},launchUnsurfacedItem:function(id,params,origin,callback){assert.equal(id,'com.abrantesflix.app');launched++;if(callback)callback(1);}};
 var context={ysm:ysm,compositor:{surfaceForApplication:function(id){assert.equal(id,'com.abrantesflix.app');return hasSurface?surface:null;}},SurfaceItem:{ItemStateProxy:99},systemSettings:{unifiedAppLifeCycleSupport:{relaunch:false}},rootSettings:{settings:{recents:{resizeOnMinimized:false}}},Qt:{size:function(w,h){return {width:w,height:h};}},pmTrace:{traceLogEventTypeContextData:function(){}},console:{warn:function(){},log:function(){}}};
 vm.runInNewContext(source,context);context.launchPointActivated({id:'com.abrantesflix.app'},function(){accepted++;},restore);
 if(hidden&&!restore){assert.equal(surfaced,0);assert.equal(launched,0);assert.equal(accepted,0);}else{assert.equal(surfaced,hasSurface?1:0);assert.equal(launched,hasSurface?0:1);assert.equal(accepted,1);}
 tests++;console.log('PASS '+name);
}
check('ordinary hidden-Home callers remain ignored',true,false,true);
check('explicit recovery resurfaces the existing app through the shipped native path',true,true,true);
check('explicit recovery launches an unavailable surface once through the shipped native path',true,true,false);
console.log(JSON.stringify({passed:true,tests:tests,scope:'actual shipped launchPointActivated function with isolated native objects',physicalActions:0}));
