'use strict';
var fs=require('fs'),os=require('os'),path=require('path'),vm=require('vm'),crypto=require('crypto'),assert=require('assert');
var originalRelease=process.argv[2],runtime=path.join(__dirname,'runtime'),source=fs.readFileSync(runtime+'/bootstrap.js','utf8'),tests=0;
function sha(data){return crypto.createHash('sha256').update(data).digest('hex');}
function test(name,profile,check){
 var sandbox='',base='/var/lib/personalhome',dir='/tmp/lg-native-production.'+Array(33).join('b');
 var validation=profile.indexOf('validation-')===0;if(validation)base='/var/lib/personalhome-validation.'+Array(33).join('b');
 var files={},dirs={},now=0,observations=0,commands=[],spawns=[],messages=[],errors=[];
 dirs[base]=true;dirs[base+'/release']=true;files[base+'/enabled']='enabled\n';
 var content={original:fs.readFileSync(originalRelease+'/original'),candidate:fs.readFileSync(originalRelease+'/candidate')};
 ['bootstrap.js','guard.js','rollback.js','policy.js'].forEach(function(n){content[n]=fs.readFileSync(runtime+'/'+n);});
 for(var i=0;i<246;i++)content['module/YSM/fixture-'+i+'.qml']='import QtQuick 2.4\nItem {}\n';
 var spec={schema:1,originalSha:sha(content.original),candidateSha:sha(content.candidate),nonce:Array(33).join('b'),runtimeDirectory:dir,files:{}};
 Object.keys(content).forEach(function(n){spec.files[n]=sha(content[n]);files[base+'/release/'+n]=content[n];});files[base+'/release/release.json']=JSON.stringify(spec);files[base+'/installed.json']=JSON.stringify({nonce:spec.nonce,releaseSha256:sha(files[base+'/release/release.json'])});files['/usr/bin/surface-manager-starfish']=content.original;
 if(validation)files[base+'/authorization.json']=JSON.stringify({nonce:spec.nonce,releaseSha256:sha(files[base+'/release/release.json']),issuedAt:0,expiresAt:profile==='validation-expired'?-1:14400000,maxBoots:profile==='validation-exhausted'?1:4});
 if(profile==='validation-exhausted')files[base+'/boot-counter.json']=JSON.stringify({bootId:'different',count:1});
 if(profile==='previous-incomplete')files[base+'/boot-activation.json']=JSON.stringify({nonce:spec.nonce,bootId:'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',phase:'prepared'});
 if(profile==='invalid-flag')files[base+'/enabled']='corrupted';
 if(profile==='invalid-qml')files[base+'/release/module/YSM/fixture-0.qml']='tampered';
 function stat(p){if(!dirs[p]&&!(p in files))throw Error('Unexpected path '+p);return {uid:0,nlink:1,mode:dirs[p]?448:384,dev:1,ino:2,isFile:function(){return !dirs[p];},isDirectory:function(){return !!dirs[p];},isSymbolicLink:function(){return false;}};}
 function proc(){var a=['S'];for(var i=1;i<22;i++)a.push('0');a[19]='99';return '77 (surface-manager) '+a.join(' ');}
 var fakefs={lstatSync:stat,statSync:stat,readlinkSync:function(p){if(p==='/proc/1/ns/mnt'||p==='/proc/self/ns/mnt')return 'ns';if(p==='/proc/77/exe')return '/usr/bin/surface-manager-starfish';throw Error(p);},existsSync:function(p){return !!dirs[p]||p in files||p==='/proc/555';},readFileSync:function(p){if(p==='/proc/sys/kernel/random/boot_id')return 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';if(p==='/proc/uptime')return String(now/1000)+' 0';if(p==='/proc/77/stat'||p==='/proc/555/stat')return proc();if(p==='/usr/bin/surface-manager-starfish'||p==='/proc/77/exe')return content.original;if(!(p in files))throw Error('Missing '+p);return files[p];},mkdirSync:function(p){if(dirs[p]){var e=Error('exists');e.code='EEXIST';throw e;}dirs[p]=true;},writeFileSync:function(p,data){files[p]=data;},renameSync:function(a,b){if(a in files){files[b]=files[a];delete files[a];return;}assert(dirs[a]);dirs[b]=true;delete dirs[a];Object.keys(files).filter(function(p){return p.indexOf(a+'/')===0;}).forEach(function(p){files[b+p.slice(a.length)]=files[p];delete files[p];});},openSync:function(p,mode){if(mode!=='r')files[p]='';return p;},fsyncSync:function(){},closeSync:function(){}};
 var fakecp={spawnSync:function(cmd,args){commands.push([cmd,args]);assert.equal(cmd,'/usr/bin/timeout');var tool=args[2];if(tool==='/bin/sleep'){now+=1000;return {status:0,stdout:''};}if(tool==='/bin/pidof')return {status:0,stdout:'77\n'};assert.equal(tool,'/usr/bin/luna-send');var uri=args[args.length-2],reply={returnValue:true};
  if(uri.indexOf('getPowerState')>=0){observations++;reply.state='Active';}
  else if(uri.indexOf('getBootStatus')>=0)reply.signals={'boot-done':true};
  else if(uri.indexOf('getStatus')>=0)reply.isRunning=profile==='never-ready'||observations<3;
  else if(uri.indexOf('getForegroundAppInfo')>=0)reply.foregroundAppInfo=observations<3?[]:[{appId:observations===3&&profile==='changed-intent'?'netflix':'com.abrantesflix.app',windowType:'_WEBOS_WINDOW_TYPE_CARD'}];
  else if(uri.indexOf('getCurrentState')>=0)reply.currentState='none';else throw Error('Unexpected method '+uri);
  return {status:0,stdout:JSON.stringify(reply)};
 },spawn:function(cmd,args){assert.equal(cmd,'/usr/bin/node');assert(args[2]==='primary'||args[2]==='lifeline');assert(observations>=4,'Guard spawned before native first-app readiness');files[dir+'/'+args[2]+'-pid.json']=JSON.stringify({pid:66,start:'99'});spawns.push(args);return {unref:function(){}};}};
 var context={require:function(n){if(n==='fs')return fakefs;if(n==='child_process')return fakecp;if(n==='crypto')return crypto;if(n===base+'/release/policy.js')return require('./runtime/policy');throw Error(n);},Date:{now:function(){return now;}},Buffer:Buffer,console:{log:function(s){messages.push(s);},error:function(s){errors.push(s);}},process:{argv:validation?['node','bootstrap.js','--validate',base]:['node','bootstrap.js','--start'],pid:555,getuid:function(){return 0;}}};
 function execute(){vm.runInNewContext(source,context,{timeout:10000});}
 execute();check({context:context,files:files,dir:dir,base:base,observations:function(){return observations;},spawns:spawns,commands:commands,execute:execute,messages:messages,errors:errors});
 tests++;console.log('PASS '+name);
}
test('actual bootstrap waits for cover completion and two stable foreground observations','normal',function(f){assert.equal(f.context.process.exitCode,undefined,JSON.stringify(f.errors));assert(f.files[f.dir+'/apply-request']);var m=JSON.parse(f.files[f.dir+'/manifest.json']);assert.equal(m.restoreAppId,'com.abrantesflix.app');assert.equal(m.healthSchema,3);assert.equal(f.spawns.length,2);assert(f.observations()>=4);assert(!f.commands.some(function(c){return c[1][2]==='/sbin/restart';}));});
test('duplicate startup cannot spawn guards or activate twice','normal',function(f){f.execute();assert.equal(f.spawns.length,2);assert(f.messages.some(function(s){return JSON.parse(s).stage==='activation-already-owned';}));});
test('a changed launch intent resets foreground readiness','changed-intent',function(f){assert(f.observations()>=5);assert.equal(JSON.parse(f.files[f.dir+'/manifest.json']).restoreAppId,'com.abrantesflix.app');});
test('a never-ending native cover is preserved; no compositor restart','never-ready',function(f){assert.equal(f.context.process.exitCode,1);assert.equal(f.spawns.length,0);assert(f.files[f.base+'/disabled']);assert(!f.files[f.dir+'/apply-request']);});
test('corrupted activation configuration fails before native actions','invalid-flag',function(f){assert.equal(f.context.process.exitCode,1);assert.equal(f.spawns.length,0);assert.equal(f.commands.length,0);});
test('invalid QML resource hash fails before native actions','invalid-qml',function(f){assert.equal(f.context.process.exitCode,1);assert.equal(f.spawns.length,0);assert.equal(f.commands.length,0);});
test('authorized temporary validation has separate state and bounded boot allowance','validation-valid',function(f){assert.equal(f.context.process.exitCode,undefined,JSON.stringify(f.errors));assert(f.files[f.dir+'/apply-request']);assert.equal(JSON.parse(f.files[f.dir+'/manifest.json']).stateDirectory,f.base);assert.equal(JSON.parse(f.files[f.base+'/boot-counter.json']).count,1);});
test('expired validation authorization cannot activate','validation-expired',function(f){assert.equal(f.context.process.exitCode,1);assert.equal(f.spawns.length,0);assert.equal(f.commands.length,0);});
test('exhausted validation boot allowance cannot activate','validation-exhausted',function(f){assert.equal(f.context.process.exitCode,1);assert.equal(f.spawns.length,0);assert.equal(f.commands.length,0);});
test('an incomplete previous OS boot cannot create an activation loop','previous-incomplete',function(f){assert.equal(f.context.process.exitCode,1);assert.equal(f.spawns.length,0);assert.equal(f.commands.length,0);assert(f.files[f.base+'/disabled']);});
console.log(JSON.stringify({passed:true,tests:tests,scope:'actual bootstrap in a filesystem/process sandbox',physicalActions:0}));
