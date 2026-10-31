'use strict';
var fs = require('fs');
var vm = require('vm');
var assert = require('assert');
var code = fs.readFileSync(__dirname + '/../boot-candidate/boot-flags.js', 'utf8');
var hook = fs.readFileSync(__dirname + '/../boot-candidate/62-personalhome-privacy', 'utf8');
var count = 0;

function scenario(options) {
  options = options || {};
  var states = {
    'com.webos.rdxd': {analyticsLog: true, crashLog: true},
    'com.palm.uploadd': {analyticsLog: true, crashLog: false}
  };
  if (options.already) Object.keys(states).forEach(function (s) { states[s] = {analyticsLog: false, crashLog: false}; });
  var calls = [], attempts = {}, finished = 0, error = null, result = null;
  function execFile(file, args, settings, next) {
    assert.strictEqual(file, '/usr/bin/luna-send');
    assert.deepEqual(args.slice(0, 6), ['-n', '1', '-w', '5000', '-f', args[5]]);
    assert.strictEqual(settings.timeout, 5000);
    assert.strictEqual(settings.killSignal, 'SIGKILL');
    assert.strictEqual(settings.maxBuffer, 8192);
    assert.strictEqual(settings.encoding, 'utf8');
    var match = /^luna:\/\/(com\.webos\.rdxd|com\.palm\.uploadd)\/(getLogSettings|setLogSettings)$/.exec(args[5]);
    assert(match, 'unrelated service or method');
    var service = match[1], method = match[2], key = service + '/' + method;
    attempts[key] = (attempts[key] || 0) + 1;
    calls.push({service: service, method: method, payload: JSON.parse(args[6])});
    if (options.throwAll) throw Error('mock-exec-throw');
    if (options.fail && options.fail(service, method, attempts[key])) return next(Error('mock-timeout'), '');
    if (options.bad && options.bad(service, method, attempts[key])) return next(null, options.badValue || '{bad');
    if (method === 'setLogSettings') {
      assert.deepEqual(JSON.parse(args[6]), {analyticsLog: false, crashLog: false});
      if (options.denySet === service) return next(null, '{"returnValue":false}');
      if (options.ignoreSet !== service) states[service] = JSON.parse(args[6]);
      next(null, '{"returnValue":true}');
    } else {
      assert.deepEqual(JSON.parse(args[6]), {});
      next(null, JSON.stringify({returnValue: true, analyticsLog: states[service].analyticsLog, crashLog: states[service].crashLog}));
    }
    if (options.doubleReply) next(Error('late-callback'), '');
  }
  var sandbox = {module: {exports: {}}, Buffer: {byteLength: Buffer.byteLength}, require: function () { throw Error('unexpected-require'); }};
  sandbox.require.main = {};
  vm.runInNewContext(code, sandbox);
  sandbox.module.exports.run(execFile, function (e, r) { finished += 1; error = e; result = JSON.parse(JSON.stringify(r)); });
  assert.strictEqual(finished, 1);
  assert(calls.length <= 12, 'finite RPC ceiling exceeded');
  return {calls: calls, error: error, result: result, states: states};
}

function test(name, fn) { fn(); count += 1; process.stdout.write('PASS ' + name + '\n'); }

test('applies and reads back both consumers with the native Node0.12 API surface', function () {
  var r = scenario();
  assert.strictEqual(r.error, null);
  assert.strictEqual(r.result.status, 'disabled');
  assert.strictEqual(r.calls.length, 6);
  Object.keys(r.states).forEach(function (s) { assert.deepEqual(r.states[s], {analyticsLog: false, crashLog: false}); });
});
test('already disabled only reads, never writes', function () {
  var r = scenario({already: true});
  assert.strictEqual(r.calls.length, 2);
  assert.strictEqual(r.error, null);
  r.result.services.forEach(function (s) { assert.strictEqual(s.status, 'already-disabled'); });
});
test('transient timeout retries only that RPC once', function () {
  var r = scenario({fail: function (s, m, n) { return s === 'com.webos.rdxd' && m === 'getLogSettings' && n === 1; }});
  assert.strictEqual(r.calls.length, 7);
  assert.strictEqual(r.error, null);
});
test('persistent timeout stops after two calls per consumer', function () {
  var r = scenario({fail: function () { return true; }});
  assert(r.error);
  assert.strictEqual(r.result.status, 'failed');
  assert.strictEqual(r.calls.length, 4);
  r.calls.forEach(function (c) { assert.strictEqual(c.method, 'getLogSettings'); });
});
test('invalid JSON and oversized output are rejected without setters', function () {
  ['{bad', Array(9000).join('x')].forEach(function (bad) {
    var r = scenario({bad: function () { return true; }, badValue: bad});
    assert(r.error);
    assert.strictEqual(r.calls.length, 4);
    r.calls.forEach(function (c) { assert.strictEqual(c.method, 'getLogSettings'); });
  });
});
test('missing or nonboolean flags cannot be interpreted as disabled', function () {
  ['{"returnValue":true}', '{"returnValue":true,"analyticsLog":0,"crashLog":false}'].forEach(function (bad) {
    var r = scenario({bad: function () { return true; }, badValue: bad});
    assert(r.error);
    assert.strictEqual(r.calls.length, 4);
  });
});
test('setter denied gets two attempts and still handles the independent uploader', function () {
  var r = scenario({denySet: 'com.webos.rdxd'});
  assert(r.error);
  assert.strictEqual(r.result.services[0].status, 'set-failed');
  assert.strictEqual(r.result.services[1].status, 'disabled');
  assert.strictEqual(r.calls.filter(function (c) { return c.service === 'com.webos.rdxd' && c.method === 'setLogSettings'; }).length, 2);
});
test('acknowledged write with incorrect readback remains failure', function () {
  var r = scenario({ignoreSet: 'com.webos.rdxd'});
  assert(r.error);
  assert.strictEqual(r.result.services[0].status, 'readback-failed');
  assert.strictEqual(r.calls.filter(function (c) { return c.service === 'com.webos.rdxd' && c.method === 'setLogSettings'; }).length, 1);
});
test('synchronous child-process exception stays bounded', function () {
  var r = scenario({throwAll: true});
  assert(r.error);
  assert.strictEqual(r.calls.length, 4);
});
test('duplicate callbacks cannot write twice or finish twice', function () {
  var r = scenario({doubleReply: true});
  assert.strictEqual(r.error, null);
  assert.strictEqual(r.calls.length, 6);
});
test('hook only backgrounds the fixed helper and does not alter Home or spool policy', function () {
  assert.strictEqual(hook, '#!/bin/sh\numask 077\n/usr/bin/node /var/lib/personalhome-privacy/boot-flags.js < /dev/null > /var/lib/personalhome-privacy/boot-status.log 2>&1 &\n');
  assert(!/\b(?:const|let|class|async|await)\b|=>|`/.test(code), 'non-ES5 syntax introduced');
  assert(!/Buffer\.(?:alloc|from)|fs\.constants|Object\.(?:assign|entries)/.test(code), 'newer Node API introduced');
});
process.stdout.write(JSON.stringify({passed: count, failed: 0,
  nativeNodeExecuted: typeof TARGET_NODE_VERSION === 'string',
  nodeVersion: typeof TARGET_NODE_VERSION === 'string' ? TARGET_NODE_VERSION : process.version}) + '\n');
