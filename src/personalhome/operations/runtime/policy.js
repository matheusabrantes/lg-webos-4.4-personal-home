'use strict';
var transient = ['com.webos.app.cpcover','com.webos.app.coverui'];
function appId(value) {
 return typeof value === 'string' && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(value) && transient.indexOf(value) < 0;
}
function foreground(reply) {
 if (!reply || reply.returnValue !== true || !Array.isArray(reply.foregroundAppInfo)) return '';
 var cards = reply.foregroundAppInfo.filter(function(row) { return row && row.windowType === '_WEBOS_WINDOW_TYPE_CARD' && appId(row.appId); });
 return cards.length === 1 ? cards[0].appId : '';
}
function bootReady(snapshot) {
 return !!(snapshot && snapshot.power && snapshot.power.returnValue === true && snapshot.power.state === 'Active'
  && snapshot.boot && snapshot.boot.returnValue === true && snapshot.boot.signals && snapshot.boot.signals['boot-done'] === true
  && snapshot.cover && snapshot.cover.returnValue === true && snapshot.cover.isRunning === false
  && snapshot.ui && snapshot.ui.returnValue === true && ['none','home','launcher','smartHome'].indexOf(snapshot.ui.currentState) >= 0
  && foreground(snapshot.surface));
}
function bootGate(state, snapshot, identity) {
 var app = foreground(snapshot && snapshot.surface);
 if (!bootReady(snapshot) || !identity) { state.app = ''; state.identity = ''; state.samples = 0; return false; }
 if (state.app !== app || state.identity !== identity) { state.app = app; state.identity = identity; state.samples = 1; return false; }
 return ++state.samples >= 2;
}
function number(value) { return typeof value === 'number' && isFinite(value) && Math.floor(value) === value && value >= 0; }
function healthShape(h, nonce) {
 return !!(h && h.schema === 3 && h.nonce === nonce && number(h.frameSequence) && number(h.renderProbe)
  && typeof h.powerActive === 'boolean' && typeof h.focusRequired === 'boolean' && typeof h.coverOpen === 'boolean'
  && typeof h.overlayOpen === 'boolean' && typeof h.foregroundAppId === 'string'
  && (!h.foregroundAppId || appId(h.foregroundAppId) || h.coverOpen && transient.indexOf(h.foregroundAppId)>=0));
}
function failure(state, h, nonce, now) {
 if (!healthShape(h, nonce)) return 'invalid-runtime-health';
 if (!h.powerActive) { state.unusableSince = null; state.reason = ''; return null; }
 var reason = !h.ready || !h.nativeContextAttached || !h.windowAttached ? 'native-view-not-ready'
  : h.shown && !h.visible ? 'home-not-visible'
  : h.shown && h.focusRequired && !h.activeFocus ? 'home-focus-unavailable'
  : !h.shown && !h.overlayOpen && !h.coverOpen && !appId(h.foregroundAppId) ? 'no-usable-foreground'
  : h.coverOpen ? 'startup-cover-did-not-finish' : '';
 if (!reason) { state.unusableSince = null; state.reason = ''; return null; }
 if (state.reason !== reason) { state.reason = reason; state.unusableSince = now; }
 var limit = reason === 'native-view-not-ready' ? 35 : reason === 'startup-cover-did-not-finish' ? 30 : 8;
 return now - state.unusableSince >= limit ? reason : null;
}
module.exports = {appId:appId,foreground:foreground,bootReady:bootReady,bootGate:bootGate,healthShape:healthShape,failure:failure};
