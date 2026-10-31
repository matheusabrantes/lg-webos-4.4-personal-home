'use strict';
var fs=require('fs'),vm=require('vm'),crypto=require('crypto'),assert=require('assert');
var source=fs.readFileSync(__dirname+'/fault_failsafe.js','utf8'),original=fs.readFileSync(process.argv[2]+'/original'),tests=0;
function hash(b){return crypto.createHash('sha256').update(b).digest('hex');}
function test(name,scenario){
 var nonce=Array(33).join('a'),dir='/tmp/lg-native-production.'+nonce,legacy='/tmp/personalhome-release.'+nonce+'/legacy-guard.js',files={},candidate=new Buffer('candidate'),knownLegacy=new Buffer('preserved-legacy-actor'),commands=[],kills=[],timer;
 var m={nonce:nonce,stateDirectory:'/var/lib/personalhome-validation.'+nonce,disableFile:'/var/lib/personalhome-validation.'+nonce+'/disabled',target:'/usr/bin/surface-manager-starfish',original:dir+'/original',candidate:dir+'/candidate',originalSha:hash(original),candidateSha:hash(candidate),candidateIdentity:'1:2',namespace:'ns',restoreAppId:'com.abrantesflix.app'};
 files[dir+'/manifest.json']=JSON.stringify(m);files[m.original]=original;files[m.candidate]=candidate;files[m.target]=scenario==='recovered'?original:candidate;files[legacy]=knownLegacy;files['/proc/self/mountinfo']=scenario==='recovered'?'':'76 22 0:17 '+dir.slice(4)+'/candidate '+m.target+' rw - overlay overlay rw';files[dir+'/mount-id']='76';files[dir+'/primary-pid.json']=JSON.stringify({pid:77,start:'99'});files[dir+'/lifeline-pid.json']=JSON.stringify({pid:88,start:'100'});
 if(scenario==='recovered')files[dir+'/restored.json']=JSON.stringify({usableInterface:true});
 if(scenario==='foreign')files['/proc/self/mountinfo']='76 22 0:17 /foreign '+m.target+' rw - overlay overlay rw';
 function stat(p){return {uid:0,mode:448,dev:1,ino:2,isDirectory:function(){return p===dir;},isSymbolicLink:function(){return false;}};}
 var fakefs={lstatSync:stat,statSync:stat,existsSync:function(p){return p in files;},readlinkSync:function(){return 'ns';},readFileSync:function(p){if(p==='/proc/77/stat'||p==='/proc/88/stat'){var a=['R'];for(var i=1;i<22;i++)a.push('0');a[19]=p.indexOf('/77/')>=0?'99':'100';return '77 (guard) '+a.join(' ');}assert(p in files,'Unexpected read '+p);return files[p];},writeFileSync:function(p,v){files[p]=v;}};
 var fakecp={spawnSync:function(command,args){commands.push([command,args]);assert.equal(command,'/usr/bin/timeout');var tool=args[2];if(tool==='/usr/bin/node'){assert.equal(args[3],legacy);assert.equal(args[4],dir+'/manifest.json');assert.equal(args[5],'restore');files[m.target]=original;files['/proc/self/mountinfo']='';return {status:0,stdout:''};}assert.equal(tool,'/usr/bin/luna-send');assert(args.some(function(v){return typeof v==='string'&&v.indexOf('com.webos.applicationManager/launch')>=0;}));return {status:0,stdout:'{"returnValue":true}'};}};
 var context={require:function(n){if(n==='fs')return fakefs;if(n==='crypto')return crypto;if(n==='child_process')return fakecp;throw Error(n);},process:{argv:['node','failsafe.js',dir,legacy,hash(knownLegacy)],kill:function(pid,signal){assert([77,88].indexOf(pid)>=0&&signal==='SIGKILL');kills.push(pid);}},setTimeout:function(fn,ms){assert.equal(ms,90000);timer=fn;}};
 if(scenario==='foreign'){assert.throws(function(){vm.runInNewContext(source,context);});assert.equal(commands.length,0);assert.equal(kills.length,0);}
 else{vm.runInNewContext(source,context);assert(timer);if(scenario==='changed-source')files[legacy]=new Buffer('tampered');timer();
  if(scenario==='recovered'){assert.equal(JSON.parse(files[dir+'/fault-failsafe-result.json']).used,false);assert.equal(commands.length,0);assert.equal(kills.length,0);}
  else if(scenario==='changed-source'){assert(files[dir+'/fault-failsafe-error.json']);assert.equal(commands.length,0);assert.equal(kills.length,0);}
  else{assert.equal(kills.length,2);assert.equal(commands.length,2);assert.equal(JSON.parse(files[dir+'/fault-failsafe-finished.json']).originalRestored,true);assert.equal(JSON.parse(files[dir+'/fault-failsafe-result.json']).newGuardTestPassed,false);assert(files[m.disableFile]);}
 }
 tests++;console.log('PASS '+name);
}
test('successful new-guard recovery cancels backup actuation','recovered');
test('a changed backup source cannot execute or terminate actors','changed-source');
test('a foreign compositor bind refuses the fault test before arming','foreign');
test('the one-shot backup remains independent and cannot count as a new-guard PASS','fallback');
console.log(JSON.stringify({passed:true,tests:tests,scope:'one-shot physical-test safety wrapper in VM; native operations mocked',physicalActions:0}));
