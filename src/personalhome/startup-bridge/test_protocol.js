"use strict";
var assert = require("assert");
var createBridge = require("./bridge");
var register = require("./service/readiness");
var nonce = "0123456789abcdef0123456789abcdef";
var methods = {}, token = 0, timers = {}, subscriptions = [], launches = 0, activations = 0, storage = {};
register({register: function (name, request, cancel) { methods[name] = {request: request, cancel: cancel}; }}, nonce);
function ready() {
    var replies = [];
    methods.ready.request({payload: {nonce: nonce}, isSubscription: false,
        respond: function (reply) { replies.push(reply); return true; }});
    return replies[0];
}
var controller = createBridge({
    nonce: nonce,
    setTimeout: function (callback) { timers[++token] = callback; return token; },
    clearTimeout: function (id) { delete timers[id]; },
    storage: function () { return {
        getItem: function (key) { return storage[key]; },
        setItem: function (key, value) { storage[key] = value; },
        removeItem: function (key) { delete storage[key]; }
    }; },
    activate: function () { activations++; }, isVisible: function () { return true; },
    createServiceBridge: function () {
        var client = {
            cancel: function () { if (this.message) { methods.subscribe.cancel(this.message); } },
            call: function (uri, body) {
                if (uri.indexOf("/subscribe") < 0) { launches++; return; }
                var message = {
                    payload: JSON.parse(body), isSubscription: true, uniqueToken: String(++token),
                    respond: function (reply) { client.onservicecallback(JSON.stringify(reply)); return true; },
                    cancel: function (reply) { this.respond(reply); methods.subscribe.cancel(this); }
                };
                this.message = message;
                subscriptions.push(this);
                methods.subscribe.request(message);
            }
        };
        return client;
    }
});
assert.strictEqual(ready().errorCode, 2);
controller.launch({boot: true});
assert.strictEqual(Object.keys(timers).length, 1);
assert.strictEqual(ready().returnValue, true);
assert.strictEqual(Object.keys(timers).length, 0);
assert.strictEqual(activations, 1);
controller.launch({boot: true});
subscriptions[0].onservicecallback(JSON.stringify({returnValue: true, nonce: nonce, ready: true}));
assert.strictEqual(Object.keys(timers).length, 1);
assert.strictEqual(ready().returnValue, true);
assert.strictEqual(Object.keys(timers).length, 0);
assert.strictEqual(activations, 2);
assert.strictEqual(launches, 0);
assert.strictEqual(ready().errorCode, 2);
console.log(JSON.stringify({passed: true, node: process.version, foregroundActions: 0,
    scope: "bridge plus readiness service with mocked bus and PalmServiceBridge"}));
