'use strict';
var fs = require('fs'), assert = require('assert'), os = require('os');
var installer = require('../boot-candidate/install-privacy');
var source = __dirname + '/../boot-candidate';
var tmp = fs.realpathSync(os.tmpdir()) + '/ph-privacy-test-' + process.pid;
fs.mkdirSync(tmp, 448);
var count = 0, serial = 0;
function sandbox(fn) {
  var home = tmp + '/case-' + serial++;
  fs.mkdirSync(home, 448); fs.mkdirSync(home + '/init', 448);
  var io = Object.create(fs), realStat = fs.lstatSync;
  io.lstatSync = function (path) {
    // Only trusted ancestors are mocked; all installation targets use real disk operations.
    if (path === home || path.indexOf(home + '/') === 0) return realStat(path);
    if (home.indexOf(path + '/') === 0 || path === '') return {isDirectory: function () { return true; }, isSymbolicLink: function () { return false; }, uid: process.getuid(), mode: 493};
    return realStat(path);
  };
  var opts = {fs: io, uid: process.getuid(), base: home + '/owned', hook: home + '/init/62-personalhome-privacy', source: source};
  fn(opts);
}
function test(name, fn) { sandbox(fn); count++; console.log('PASS ' + name); }
test('exclusive install and exact owned rollback on actual sandbox files', function (o) {
  assert.strictEqual(installer.run('--install-approved',o).status,'installed');
  assert.strictEqual(fs.statSync(o.base).mode & 511,448);
  assert.strictEqual(fs.statSync(o.base+'/boot-flags.js').mode & 511,384);
  assert.strictEqual(fs.statSync(o.base+'/boot-status.log').mode & 511,384);
  assert.strictEqual(fs.statSync(o.hook).mode & 511,448);
  assert.strictEqual(fs.statSync(o.hook).nlink,1);
  assert.strictEqual(installer.run('--rollback-approved',o).profileRestored,false);
  assert(!fs.existsSync(o.base)); assert(!fs.existsSync(o.hook));
});
test('preexisting base or hook is never overwritten',function(o){
  fs.writeFileSync(o.hook,'foreign');
  assert.throws(function(){installer.run('--install-approved',o);});
  assert.strictEqual(fs.readFileSync(o.hook,'utf8'),'foreign'); assert(!fs.existsSync(o.base));
});
test('symlink destination is refused before writes',function(o){
  fs.symlinkSync(o.hook,o.base);
  assert.throws(function(){installer.run('--install-approved',o);});
  assert(fs.lstatSync(o.base).isSymbolicLink()); assert(!fs.existsSync(o.hook));
});
test('changed helper blocks rollback without deleting hook',function(o){
  installer.run('--install-approved',o); fs.writeFileSync(o.base+'/boot-flags.js','changed');
  assert.throws(function(){installer.run('--rollback-approved',o);}); assert(fs.existsSync(o.hook));
});
test('unknown owned content and foreign receipt block rollback',function(o){
  installer.run('--install-approved',o); fs.writeFileSync(o.base+'/unknown','x');
  assert.throws(function(){installer.run('--rollback-approved',o);}); assert(fs.existsSync(o.hook));
  fs.unlinkSync(o.base+'/unknown'); fs.writeFileSync(o.base+'/receipt.json','{}\n');
  assert.throws(function(){installer.run('--rollback-approved',o);}); assert(fs.existsSync(o.hook));
});
test('partial installation cleans only its validated owned files',function(o){
  o.fs.linkSync=function(){throw Error('simulated publish failure');};
  assert.throws(function(){installer.run('--install-approved',o);});
  assert(!fs.existsSync(o.base));assert(!fs.existsSync(o.hook));assert(!fs.existsSync(o.hook+'.stage'));
});
test('concurrent final hook publication is not overwritten or deleted',function(o){
  o.fs.linkSync=function(stage,hook){fs.writeFileSync(hook,'foreign concurrent');throw Error('EEXIST');};
  assert.throws(function(){installer.run('--install-approved',o);});
  assert.strictEqual(fs.readFileSync(o.hook,'utf8'),'foreign concurrent');assert(fs.existsSync(o.base+'/receipt.json'));
});
test('active helper refuses rollback until finite process exits',function(o){
  installer.run('--install-approved',o);o.helperActive=function(){return true;};
  assert.throws(function(){installer.run('--rollback-approved',o);});assert(fs.existsSync(o.hook));
  o.helperActive=function(){return false;};installer.run('--rollback-approved',o);
});
test('log symlink and unexpected command are refused',function(o){
  assert.throws(function(){installer.run('install',o);});assert(!fs.existsSync(o.base));
  installer.run('--install-approved',o);fs.unlinkSync(o.base+'/boot-status.log');fs.symlinkSync(o.hook,o.base+'/boot-status.log');
  assert.throws(function(){installer.run('--rollback-approved',o);});assert(fs.existsSync(o.hook));
});
test('symlink parent and writable private directory are refused',function(o){
  fs.symlinkSync(o.hook.slice(0,o.hook.lastIndexOf('/')),o.base+'-link');
  var original=o.hook;o.hook=o.base+'-link/62-personalhome-privacy';
  assert.throws(function(){installer.run('--install-approved',o);});assert(!fs.existsSync(o.base));
  o.hook=original;installer.run('--install-approved',o);fs.chmodSync(o.base,493);
  assert.throws(function(){installer.run('--rollback-approved',o);});assert(fs.existsSync(o.hook));
});
test('Node0.12 fd writes reject writeFileSync and support partial writeSync',function(o){
  var fileWrite=fs.writeFileSync, calls=0;
  o.fs.writeFileSync=function(path,value){if(typeof path==='number')throw TypeError('path must be a string');return fileWrite(path,value);};
  o.fs.writeSync=function(fd,value,offset,length,position){calls++;return fs.writeSync(fd,value,offset,Math.min(length,7),position);};
  assert.strictEqual(installer.run('--install-approved',o).status,'installed');
  assert(calls>3);installer.run('--rollback-approved',o);
});
function removeTree(path) {
  var stat=fs.lstatSync(path);
  if(stat.isDirectory()&&!stat.isSymbolicLink()) {fs.readdirSync(path).forEach(function(name){removeTree(path+'/'+name);});fs.rmdirSync(path);}
  else fs.unlinkSync(path);
}
removeTree(tmp);
console.log(JSON.stringify({passed:count,failed:0,node:process.version,nativeNodeExecuted:false,sandboxOnly:true}));
