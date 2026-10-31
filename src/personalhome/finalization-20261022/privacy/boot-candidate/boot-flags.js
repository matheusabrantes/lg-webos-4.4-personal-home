'use strict';

var SERVICES = ['com.webos.rdxd', 'com.palm.uploadd'];
var OFF = {analyticsLog: false, crashLog: false};
var MAX = 8192;

function object(value) { return value !== null && typeof value === 'object' && !Array.isArray(value); }
function flags(value) {
  return object(value) && value.returnValue === true &&
    typeof value.analyticsLog === 'boolean' && typeof value.crashLog === 'boolean';
}
function disabled(value) { return flags(value) && !value.analyticsLog && !value.crashLog; }

function run(execFile, done) {
  var result = {status: 'disabled', services: []};
  var index = 0;
  function rpc(service, method, payload, needFlags, next) {
    var attempts = 0;
    function attempt() {
      attempts += 1;
      var answered = false;
      function reply(error, stdout) {
        if (answered) return;
        answered = true;
        var value = null;
        if (!error && typeof stdout === 'string' && Buffer.byteLength(stdout, 'utf8') <= MAX) {
          try { value = JSON.parse(stdout); } catch (ignored) {}
        }
        if (object(value) && value.returnValue === true && (!needFlags || flags(value))) return next(value);
        if (attempts < 2) return attempt();
        next(null);
      }
      try {
        execFile('/usr/bin/luna-send', ['-n', '1', '-w', '5000', '-f',
          'luna://' + service + '/' + method, JSON.stringify(payload)],
        {timeout: 5000, killSignal: 'SIGKILL', maxBuffer: MAX, encoding: 'utf8'}, reply);
      } catch (ignored) { reply(Error('rpc-failed')); }
    }
    attempt();
  }
  function nextService() {
    if (index === SERVICES.length) {
      return done(result.status === 'disabled' ? null : Error('privacy-flags-not-verified'), result);
    }
    var service = SERVICES[index++];
    function finish(status) {
      if (status === 'read-failed' || status === 'set-failed' || status === 'readback-failed') result.status = 'failed';
      result.services.push({service: service, status: status});
      nextService();
    }
    rpc(service, 'getLogSettings', {}, true, function (current) {
      if (!current) return finish('read-failed');
      if (disabled(current)) return finish('already-disabled');
      rpc(service, 'setLogSettings', OFF, false, function (ack) {
        if (!ack) return finish('set-failed');
        rpc(service, 'getLogSettings', {}, true, function (after) {
          finish(disabled(after) ? 'disabled' : 'readback-failed');
        });
      });
    });
  }
  nextService();
}

module.exports = {run: run};
if (require.main === module) {
  run(require('child_process').execFile, function (error, result) {
    process.stdout.write(JSON.stringify(result) + '\n');
    if (error) process.exitCode = 1;
  });
}
