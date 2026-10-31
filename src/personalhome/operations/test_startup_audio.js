'use strict';
var assert=require('assert'),policy=require('./runtime/policy'),tests=0;
var boot='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
function fixture(options){
 options=options||{};var calls=[],closed=!!options.closed,reads=0;
 function luna(method,args){calls.push({method:method,args:args});if(method.indexOf('getPipeline4BootUp')>=0)return {returnValue:true,broadcastId:options.noTV?'':'fresh-pipeline'};
 if(method.indexOf('getBroadcastState')>=0){if(options.networkError)throw Error('Service timeout');if(closed){var reply={returnValue:false,broadcastId:options.foreignRejectedId?'foreign':'fresh-pipeline',subscribed:false,errorCode:options.wrongError?'BROADCAST_ERROR_9999':'BROADCAST_ERROR_0001',errorText:'Invalid broadcastID error'};var error=Error('Native rejected getter');error.nativeReply=reply;throw error;}return {returnValue:true,broadcastId:options.foreignId?'foreign':'fresh-pipeline',conflictResult:options.conflict?'CONFLICT':'NO_CONFLICT',state:'BROADCAST_STATE_RENDERING'};}
 assert.equal(method,'com.webos.service.utp.broadcast/close');assert.deepEqual(args,{broadcastId:'fresh-pipeline'});if(!options.stillAllocated)closed=true;return {returnValue:!options.failedClose,broadcastId:options.foreignCloseId?'foreign':'fresh-pipeline'};}
 return {calls:calls,run:function(){return policy.quietStartupAudio(luna,boot,function(){return options.changedBoot&&++reads>1?'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb':boot;},!!options.inputRunning);}};
}
function test(name,fn){fn();tests++;console.log('PASS '+name);}
test('cold preload closes its freshly verified broadcast and confirms native invalid-ID readback',function(){var f=fixture();assert.equal(f.run().changed,true);assert.equal(f.calls.length,4);assert.equal(f.calls[0].method,'com.webos.service.tv.broadcast/getPipeline4BootUp');assert.equal(f.calls[1].args.subscribe,false);});
test('an already closed broadcast needs no close mutation',function(){var f=fixture({closed:true});assert.equal(f.run().reason,'broadcast-already-closed');assert.equal(f.calls.length,2);});
test('no broadcast pipeline needs no guessed ID or close',function(){var f=fixture({noTV:true});assert.equal(f.run().reason,'no-broadcast-pipeline');assert.equal(f.calls.length,1);});
test('a real running input app retains its normal lifecycle',function(){var f=fixture({inputRunning:true});assert.equal(f.run().reason,'native-input-app-running');assert.equal(f.calls.length,0);});
test('foreign broadcast IDs and conflicted sources are never mutated',function(){[{foreignId:true},{conflict:true}].forEach(function(options){var f=fixture(options);assert.throws(f.run,/ownership or state differs/);assert.equal(f.calls.length,2);});});
test('boot identity is rechecked before close',function(){var f=fixture({changedBoot:true});assert.throws(f.run,/boot changed/);assert.equal(f.calls.length,2);});
test('failed or foreign close acknowledgments cannot claim teardown',function(){[{failedClose:true},{foreignCloseId:true}].forEach(function(options){assert.throws(fixture(options).run,/close was not acknowledged/);});});
test('a successful close reply with an allocated readback cannot claim teardown',function(){assert.throws(fixture({stillAllocated:true}).run,/remains allocated/);});
test('only the exact native invalid-ID reply confirms closure',function(){[{closed:true,wrongError:true},{closed:true,foreignRejectedId:true},{networkError:true}].forEach(function(options){assert.throws(fixture(options).run);});});
console.log(JSON.stringify({passed:true,tests:tests,physicalActions:0,scope:'cold preload broadcast close with exact native readback in memory'}));
