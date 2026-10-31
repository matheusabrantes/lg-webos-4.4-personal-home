'use strict';
var fs=require('fs'),vm=require('vm'),crypto=require('crypto'),assert=require('assert'),policy=require('./runtime/policy'),tests=0;
var source=fs.readFileSync(__dirname+'/runtime/rollback.js','utf8'),policyBytes=fs.readFileSync(__dirname+'/runtime/policy.js');
var original=fs.readFileSync(process.argv[2]+'/original'),nonce=Array(33).join('a'),base='/var/lib/personalhome',runtime='/tmp/lg-native-production.'+nonce,hook='/var/lib/webosbrew/init.d/90-personalhome',target='/var/luna/preferences/bootd.json';
function sha(v){return crypto.createHash('sha256').update(v).digest('hex');}
function run(scenario){
 var files={},current=scenario==='foreign'?'com.webos.app.hdmi2':policy.startupBridge,messages=[],errors=[];
 var spec={nonce:nonce,files:{'policy.js':sha(policyBytes)}},raw=JSON.stringify(spec),originalSha=sha(original);
 files[base+'/installed.json']=JSON.stringify({schema:1,nonce:nonce,originalSha:originalSha,candidateSha:sha('candidate'),releaseSha256:sha(raw),bootHookSha256:sha('owned hook')});
 files[base+'/release/release.json']=raw;files[base+'/release/policy.js']=policyBytes;files[hook]='owned hook';
 files[base+'/startup-input.json']=JSON.stringify({schema:1,nonce:nonce,originalAppId:'com.webos.app.livetv',candidateAppId:policy.startupBridge,phase:'prepared'});
 files[base+'/startup-config.json']=JSON.stringify({schema:1,path:target,originalSha256:sha('before bootd'),candidateSha256:sha('candidate bootd')});files[base+'/bootd-before.json']='before bootd';files[target]='candidate bootd';
 files[runtime+'/manifest.json']=JSON.stringify({directory:runtime,stateDirectory:base,nonce:nonce,original:runtime+'/original',candidate:runtime+'/candidate',target:'/usr/bin/surface-manager-starfish',originalSha:originalSha,candidateSha:sha('candidate')});files[runtime+'/original']=original;
 var dirs=[base,runtime,'/var/luna/preferences'];
 function stat(p){assert(dirs.indexOf(p)>=0||p in files,p);var d=dirs.indexOf(p)>=0;return {uid:0,nlink:1,mode:d?448:384,isSymbolicLink:function(){return false;},isDirectory:function(){return d;},isFile:function(){return !d;}};}
 var fakefs={lstatSync:stat,existsSync:function(p){return dirs.indexOf(p)>=0||p in files;},readFileSync:function(p){assert(p in files,p);return files[p];},writeFileSync:function(p,v,o){assert.equal(o.flag,'wx');assert(!(p in files));files[p]=v;},openSync:function(p,mode){if(mode==='wx'){assert(!(p in files));files[p]='';}return p;},writeSync:function(p,b,offset,length){files[p]+=b.slice(offset,offset+length).toString();return length;},closeSync:function(){},fsyncSync:function(){},renameSync:function(a,b){assert(a in files);files[b]=files[a];delete files[a];}};
 var cp={spawnSync:function(command,args){assert.equal(command,'/usr/bin/timeout');assert.equal(args[1],'2');var method=args[args.length-2],params=JSON.parse(args[args.length-1]),reply={returnValue:true};if(method==='luna://com.webos.settingsservice/getSystemSettings')reply.settings={lastInputApp:current};else{assert.equal(method,'luna://com.webos.settingsservice/setSystemSettings');assert.deepEqual(Object.keys(params.settings),['lastInputApp']);current=params.settings.lastInputApp;if(scenario==='timeout')return {status:1,stdout:'',stderr:'timeout'};}return {status:0,stdout:JSON.stringify(reply)};}};
 var context={require:function(n){if(n==='fs')return fakefs;if(n==='crypto')return crypto;if(n==='child_process')return cp;if(n===base+'/release/policy.js')return policy;throw Error(n);},Buffer:Buffer,process:{argv:['node','rollback.js','--rollback-approved'],getuid:function(){return 0;}},console:{log:function(v){messages.push(v);},error:function(v){errors.push(v);}}};
 vm.runInNewContext(source,context);
 return {files:files,current:current,context:context,messages:messages,errors:errors};
}
function test(name,fn){fn();tests++;console.log('PASS '+name);}
test('manual rollback restores input and bootd before disabling its hook and requesting runtime recovery',function(){var f=run('normal');assert.equal(f.context.process.exitCode,undefined,JSON.stringify(f.errors));assert.equal(f.current,'com.webos.app.livetv');assert.equal(f.files[target],'before bootd');assert(f.files[runtime+'/abort.json']);assert(f.files[base+'/boot-hook.disabled']);assert.equal(f.files[hook],undefined);});
test('manual rollback preserves a user input preference while still recovering the original UI',function(){var f=run('foreign');assert.equal(f.context.process.exitCode,undefined);assert.equal(f.current,'com.webos.app.hdmi2');assert.equal(JSON.parse(f.files[base+'/startup-input.json']).phase,'preserved');assert(f.files[runtime+'/abort.json']);});
test('an ambiguous input restore timeout cannot prevent bootd restoration or the guard abort request',function(){var f=run('timeout');assert.equal(f.context.process.exitCode,1);assert.equal(f.files[target],'before bootd');assert(f.files[runtime+'/abort.json']);assert.equal(f.files[hook],undefined);assert.equal(JSON.parse(f.messages[0]).startupRecoveryErrors.length,1);});
console.log(JSON.stringify({passed:true,tests:tests,physicalActions:0,scope:'actual manual rollback with native input calls mocked'}));
