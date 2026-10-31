'use strict';
var fs=require('fs'),vm=require('vm'),assert=require('assert');
var qml=fs.readFileSync(process.argv[2],'utf8');
var timer=/id: launcherOnBootTimer\s+interval: ysm.launcherOnBootTimeout\s+onTriggered: ([^\n]+)/.exec(qml);
assert(timer,'Native startup timer anchor is missing');
[true,false].forEach(function(shown){
 var hidden=0;
 vm.runInNewContext(timer[1],{uiScope:{personalHomeShown:shown},ysm:{gotoState:function(state){assert.equal(state,'hidden');hidden++;}}});
 assert.equal(hidden,shown?0:1,shown?'Native timeout must not dismiss a ready PersonalHome':'Original LG timeout must remain available');
});
console.log(JSON.stringify({passed:true,tests:2,scope:'actual native startup timeout handler; no device actions'}));
