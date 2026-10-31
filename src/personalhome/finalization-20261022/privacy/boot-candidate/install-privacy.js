'use strict';
var fs = require('fs'), crypto = require('crypto');
var HASH = {
  helper: '8b23442880e11a436cb2b962016e2ff6757911a11969e6da270371b69cf82edd',
  hook: 'ef8665cc9a58fb86247f62cdbf14880805f85731a4e8fc6f5d072655540b6086'
};
function run(mode, options) {
  options = options || {};
  var io = options.fs || fs, uid = options.uid === undefined ? 0 : options.uid;
  var base = options.base || '/var/lib/personalhome-privacy';
  var hook = options.hook || '/var/lib/webosbrew/init.d/62-personalhome-privacy';
  var stage = hook + '.stage', receipt = base + '/receipt.json';
  var helper = base + '/boot-flags.js', log = base + '/boot-status.log';
  var parent = hook.slice(0, hook.lastIndexOf('/'));
  var expected = JSON.stringify({schema: 1, owner: 'personalhome-privacy', base: base,
    hook: hook, helperSha256: HASH.helper, hookSha256: HASH.hook}) + '\n';
  function exists(path) { try { io.lstatSync(path); return true; } catch (e) { if (e.code === 'ENOENT') return false; throw e; } }
  function directory(path, own) {
    var s = io.lstatSync(path);
    if (!s.isDirectory() || s.isSymbolicLink() || s.uid !== uid || (s.mode & 18) || (own && (s.mode & 511) !== 448)) throw Error('Unsafe directory: ' + path);
  }
  function parents(path) {
    var parts = path.split('/'), next = '';
    for (var i = 1; i < parts.length; i += 1) { next += '/' + parts[i]; directory(next, false); }
  }
  function regular(path, modeBits, links) {
    var s = io.lstatSync(path);
    if (!s.isFile() || s.isSymbolicLink() || s.uid !== uid || (s.mode & 511) !== modeBits || s.nlink > links || s.nlink < 1 || s.size > 1048576) throw Error('Unsafe file: ' + path);
  }
  function digest(path) { return crypto.createHash('sha256').update(io.readFileSync(path)).digest('hex'); }
  function checked(path, hash, modeBits) { regular(path, modeBits, 2); if (digest(path) !== hash) throw Error('Hash differs: ' + path); }
  function create(path, value, modeBits) {
    var fd = io.openSync(path, 'wx', modeBits);
    try {
      var bytes = Buffer.isBuffer(value) ? value : new Buffer(value, 'utf8');
      var offset = 0;
      while (offset < bytes.length) {
        var written = io.writeSync(fd, bytes, offset, bytes.length - offset, null);
        if (typeof written !== 'number' || written <= 0 || written > bytes.length - offset) throw Error('Incomplete write: ' + path);
        offset += written;
      }
      io.fchmodSync(fd, modeBits); io.fsyncSync(fd);
    } finally { io.closeSync(fd); }
  }
  function rollback() {
    directory(base, true); parents(parent);
    regular(receipt, 384, 1);
    if (io.readFileSync(receipt, 'utf8') !== expected) throw Error('Foreign receipt');
    var allowed = ['receipt.json', 'boot-flags.js', 'boot-status.log'];
    io.readdirSync(base).forEach(function (name) { if (allowed.indexOf(name) < 0) throw Error('Unknown owned-directory content'); });
    if (exists(helper)) checked(helper, HASH.helper, 384);
    if (exists(hook)) checked(hook, HASH.hook, 448);
    if (exists(stage)) checked(stage, HASH.hook, 448);
    if (exists(log)) regular(log, 384, 1);
    if (options.helperActive && options.helperActive(helper)) throw Error('Finite helper still active; retry after it exits');
    // Validate everything before removing the hook or any owned file.
    [hook, stage, helper, log].forEach(function (path) { if (exists(path)) io.unlinkSync(path); });
    io.unlinkSync(receipt); io.rmdirSync(base);
    return {status: 'rolled-back', profileRestored: false};
  }
  if (mode === '--rollback-approved') return rollback();
  if (mode !== '--install-approved') throw Error('Explicit approved operation required');
  parents(base.slice(0, base.lastIndexOf('/'))); parents(parent);
  if (exists(base) || exists(hook) || exists(stage)) throw Error('Destination already exists; refusing overwrite');
  var source = options.source || __dirname;
  var helperSource = io.readFileSync(source + '/boot-flags.js'), hookSource = io.readFileSync(source + '/62-personalhome-privacy');
  if (crypto.createHash('sha256').update(helperSource).digest('hex') !== HASH.helper || crypto.createHash('sha256').update(hookSource).digest('hex') !== HASH.hook) throw Error('Source hash differs');
  io.mkdirSync(base, 448); io.chmodSync(base, 448);
  try {
    create(receipt, expected, 384);
    create(helper, helperSource, 384);
    create(log, '', 384);
    create(stage, hookSource, 448);
    checked(helper, HASH.helper, 384); checked(stage, HASH.hook, 448);
    io.linkSync(stage, hook); io.unlinkSync(stage);
    checked(hook, HASH.hook, 448); directory(base, true);
    return {status: 'installed', helperExecuted: false, base: base, hook: hook};
  } catch (e) {
    try { rollback(); } catch (recovery) { throw Error(e.message + '; partial state retained: ' + recovery.message); }
    throw e;
  }
}
function helperActive(helper) {
  return fs.readdirSync('/proc').some(function (pid) {
    if (!/^\d+$/.test(pid)) return false;
    try { return fs.readFileSync('/proc/' + pid + '/cmdline', 'utf8').split('\0').indexOf(helper) >= 0; }
    catch (e) { if (e.code === 'ENOENT' || e.code === 'ESRCH') return false; throw e; }
  });
}
module.exports = {run: run};
if (require.main === module) {
  try {
    if (process.getuid() !== 0 || process.argv.length !== 3) throw Error('Root and exactly one approved operation required');
    process.stdout.write(JSON.stringify(run(process.argv[2], {helperActive: helperActive})) + '\n');
  } catch (e) { process.stderr.write(e.message + '\n'); process.exitCode = 1; }
}
