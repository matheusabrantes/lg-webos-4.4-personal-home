'use strict';
var fs=require('fs'),os=require('os'),path=require('path'),crypto=require('crypto'),vm=require('vm'),assert=require('assert');
var release=process.argv[2],meta=JSON.parse(fs.readFileSync(release+'/release.json')),source=fs.readFileSync(__dirname+'/runtime/install-validation.js','utf8'),tests=0;
function sha(b){return crypto.createHash('sha256').update(b).digest('hex');}
function test(name,scenario){
 var dir=fs.mkdtempSync(path.join(os.tmpdir(),'ph-validation-install-')),local=dir+'/stage',stage='/tmp/personalhome-release.'+meta.nonce,base='/var/lib/personalhome-validation.'+meta.nonce,hook='/var/lib/webosbrew/init.d/89-personalhome-validation',spawned=[];
 fs.cpSync(release,local,{recursive:true});
 function mapped(p){if(p===stage||p.indexOf(stage+'/')===0)return local+p.slice(stage.length);if(p==='/usr/bin/surface-manager-starfish'||p==='/proc/77/exe')return release+'/original';if(p.indexOf('/var/lib/personalhome')===0||p.indexOf('/var/lib/webosbrew/init.d')===0||p.indexOf('/tmp/YSM')===0||p.indexOf('/tmp/personalhome-module-before-validation.')===0||p.indexOf('/tmp/lg-native-production.')===0)return dir+p;throw Error('Sandbox refused path '+p);}
 function make(p){fs.mkdirSync(mapped(p),{recursive:true,mode:448});}
 make('/var/lib/personalhome');make('/var/lib/webosbrew/init.d');
 fs.writeFileSync(mapped('/var/lib/personalhome/disabled'),'original-mode',{mode:384});
 if(scenario==='production-active')fs.writeFileSync(mapped('/var/lib/webosbrew/init.d/90-personalhome'),'foreign',{mode:448});
 if(scenario==='existing'){make(base);fs.writeFileSync(mapped(base+'/keep'),'preserve');}
 if(scenario==='tampered')fs.appendFileSync(local+'/module/YSM/PersonalHome/PersonalHome.qml','tampered');
 if(scenario==='foreign-module'||scenario==='owned-module'){
  make('/var/lib/personalhome/release');fs.writeFileSync(mapped('/var/lib/personalhome/release/release.json'),fs.readFileSync(local+'/release.json'),{mode:384});fs.writeFileSync(mapped('/var/lib/personalhome/installed.json'),JSON.stringify({nonce:meta.nonce,releaseSha256:sha(fs.readFileSync(local+'/release.json'))}),{mode:384});
  fs.mkdirSync(path.dirname(mapped('/tmp/YSM')),{recursive:true});fs.cpSync(local+'/module/YSM',mapped('/tmp/YSM'),{recursive:true});if(scenario==='foreign-module')fs.writeFileSync(mapped('/tmp/YSM/.trial-owner'),'unknown',{mode:384});
 }
 if(scenario==='previous-validation'||scenario==='unverified-previous-validation'){
  var owner=Array(33).join('a'),previous='/var/lib/personalhome-validation.'+owner,prior=JSON.parse(JSON.stringify(meta));
  make('/var/lib/personalhome/release');fs.writeFileSync(mapped('/var/lib/personalhome/installed.json'),JSON.stringify({nonce:Array(33).join('b')}),{mode:384});
  make(previous+'/release');make('/tmp/lg-native-production.'+owner);
  fs.mkdirSync(path.dirname(mapped('/tmp/YSM')),{recursive:true});fs.cpSync(local+'/module/YSM',mapped('/tmp/YSM'),{recursive:true});fs.writeFileSync(mapped('/tmp/YSM/.trial-owner'),owner,{mode:384});
  prior.nonce=owner;prior.files['module/YSM/.trial-owner']=sha(owner);var raw=JSON.stringify(prior);
  fs.writeFileSync(mapped(previous+'/release/release.json'),raw,{mode:384});fs.writeFileSync(mapped(previous+'/installed.json'),JSON.stringify({nonce:owner,releaseSha256:sha(raw)}),{mode:384});fs.writeFileSync(mapped(previous+'/disabled'),'restored',{mode:384});
  fs.writeFileSync(mapped('/tmp/lg-native-production.'+owner+'/restored.json'),JSON.stringify({originalSha:meta.originalSha,mountAbsent:true,usableInterface:scenario==='previous-validation'}),{mode:384});
 }
 var adapter={};['existsSync','readFileSync','writeFileSync','mkdirSync','openSync'].forEach(function(n){adapter[n]=function(p){var args=Array.prototype.slice.call(arguments);args[0]=mapped(p);return fs[n].apply(fs,args);};});
 adapter.lstatSync=function(p){var s=fs.lstatSync(mapped(p));s.uid=0;return s;};
 adapter.readlinkSync=function(p){if(p==='/proc/self/ns/mnt'||p==='/proc/1/ns/mnt')return 'namespace';if(p==='/proc/77/exe')return '/usr/bin/surface-manager-starfish';throw Error('Unexpected link');};
 adapter.renameSync=function(a,b){return fs.renameSync(mapped(a),mapped(b));};['writeSync','fsyncSync','closeSync'].forEach(function(n){adapter[n]=function(){return fs[n].apply(fs,arguments);};});
 var errors=[],messages=[],context={require:function(n){if(n==='fs')return adapter;if(n==='crypto')return crypto;if(n==='child_process')return {spawnSync:function(cmd,args){assert.equal(cmd,'/usr/bin/timeout');assert.deepEqual(Array.prototype.slice.call(args),['-t','12','/bin/pidof','surface-manager-starfish']);return {status:0,stdout:'77\n'};},spawn:function(cmd,args){assert.equal(cmd,'/usr/bin/node');assert.equal(args[0],base+'/release/bootstrap.js');assert.equal(args[1],'--validate');assert.equal(args[2],base);if(scenario==='spawn-fails')throw Error('Simulated spawn failure');spawned.push(args);return {unref:function(){}};}};throw Error(n);},Date:Date,Buffer:Buffer,process:{argv:['node','install-validation.js','--install-validation-approved',stage,scenario==='bad-hash'?Array(65).join('0'):sha(fs.readFileSync(local+'/release.json')),scenario==='manual'?'manual':'boot-session'],getuid:function(){return 0;}},console:{log:function(s){messages.push(s);},error:function(s){errors.push(s);}}};
 if(scenario==='bounded-retry')context.process.argv.push(String(Date.now()+600000));
 if(scenario==='expired-retry')context.process.argv.push(String(Date.now()-1));
 vm.runInNewContext(source,context,{timeout:10000});
 if(['bad-hash','existing','production-active','tampered','foreign-module','unverified-previous-validation','expired-retry'].indexOf(scenario)>=0){assert.equal(context.process.exitCode,1);assert.equal(spawned.length,0);assert(!fs.existsSync(mapped(hook)));if(scenario==='existing')assert.equal(fs.readFileSync(mapped(base+'/keep'),'utf8'),'preserve');else assert(!fs.existsSync(mapped(base)));}
 else if(scenario==='spawn-fails'){assert.equal(context.process.exitCode,1);assert(fs.existsSync(mapped(base+'/disabled')));assert(!fs.existsSync(mapped(hook)));assert(fs.existsSync(mapped(base+'/setup-failed-hook')));}
 else{assert.equal(context.process.exitCode,undefined,JSON.stringify(errors));assert.equal(spawned.length,1);assert.equal(fs.existsSync(mapped(hook)),scenario!=='manual');var receipt=JSON.parse(fs.readFileSync(mapped(base+'/installed.json'))),auth=JSON.parse(fs.readFileSync(mapped(base+'/authorization.json')));assert.equal(receipt.releaseSha256,sha(fs.readFileSync(local+'/release.json')));assert(auth.expiresAt-auth.issuedAt>0&&auth.maxBoots===3);if(scenario==='bounded-retry')assert(auth.expiresAt-auth.issuedAt<=600000);else assert.equal(auth.expiresAt-auth.issuedAt,1500000);assert.equal(JSON.parse(messages[0]).recoveryReserveSeconds,300);assert(receipt.temporary);assert(JSON.parse(messages[0]).physicalAcceptanceRequired);if(scenario==='rollback-runtime'){var runtime='/tmp/lg-native-production.'+meta.nonce;make(runtime);fs.copyFileSync(release+'/original',mapped(runtime+'/original'));fs.writeFileSync(mapped(runtime+'/manifest.json'),JSON.stringify({directory:runtime,stateDirectory:base,nonce:meta.nonce,original:runtime+'/original',candidate:runtime+'/candidate',target:'/usr/bin/surface-manager-starfish',originalSha:meta.originalSha,candidateSha:meta.candidateSha}),{mode:384});context.process.argv=['node','rollback.js','--rollback-validation-approved',base];vm.runInNewContext(fs.readFileSync(__dirname+'/runtime/rollback.js','utf8'),context,{timeout:10000});assert.equal(context.process.exitCode,undefined,JSON.stringify(errors));assert(fs.existsSync(mapped(base+'/disabled')));assert(!fs.existsSync(mapped(hook)));assert(fs.existsSync(mapped(runtime+'/abort.json')));assert.equal(JSON.parse(messages[messages.length-1]).verifiedOriginalRestored,false);}if(scenario==='owned-module'||scenario==='previous-validation'){var preserved=JSON.parse(messages[0]).preservedModule;assert.equal(fs.readFileSync(mapped(preserved+'/.trial-owner'),'utf8'),scenario==='previous-validation'?Array(33).join('a'):meta.nonce);assert(!fs.existsSync(mapped('/tmp/YSM')));}}
 assert.equal(fs.readFileSync(mapped('/var/lib/personalhome/disabled'),'utf8'),'original-mode');assert.equal(sha(fs.readFileSync(release+'/original')),meta.originalSha);
 fs.rmSync(dir,{recursive:true,force:true});tests++;console.log('PASS '+name);
}
test('manual validation preserves permanent LG mode and does not install a startup hook','manual');
test('boot validation creates only a bounded temporary hook and separate state','boot-session');
test('unapproved manifest hash cannot write state','bad-hash');
test('existing validation state is not overwritten','existing');
test('production activation must remain disabled before validation','production-active');
test('tampered source cannot reach activation','tampered');
test('an unknown old UI module is preserved','foreign-module');
test('the verified prior UI module is archived before validation, with all hashes checked','owned-module');
test('a failed activation spawn revokes the hook and leaves LG original intact','spawn-fails');
test('actual validation rollback disables only its own hook and requests guarded restoration','rollback-runtime');
test('a previously restored owned validation module can be safely preserved for the next test','previous-validation');
test('unverified previous validation cannot be replaced by a new test','unverified-previous-validation');
test('a relevant retry cannot reset the original physical-session deadline','bounded-retry');
test('an expired retry cannot create activation state','expired-retry');
console.log(JSON.stringify({passed:true,tests:tests,scope:'actual validation installer; protected paths mapped to a local sandbox',physicalActions:0}));
