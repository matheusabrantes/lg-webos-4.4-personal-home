"use strict";
const assert = require("assert");
const register = require("./service/readiness");
const nonce = "0123456789abcdef0123456789abcdef";
let count = 0;

function fixture(token) {
    const methods = {};
    let next = 0;
    register({register(name, request, cancel) { methods[name] = {request, cancel}; }}, token || nonce);
    function request(method, payload, subscription, delivered) {
        const message = {
            payload, isSubscription: subscription === true, uniqueToken: String(++next), replies: [],
            respond(reply) { this.replies.push(reply); return delivered !== false; },
            cancel(reply) { this.respond(reply); if (methods[method].cancel) { methods[method].cancel(this); } }
        };
        methods[method].request(message);
        return message;
    }
    return {methods, request};
}

function test(name, run) { run(); count++; console.log("PASS " + name); }

test("only subscribe and ready are registered", () => {
    assert.deepStrictEqual(Object.keys(fixture().methods).sort(), ["ready", "subscribe"]);
});

test("readiness requires an active pending subscription", () => {
    assert.strictEqual(fixture().request("ready", {nonce}).replies[0].errorCode, 2);
});

test("matching ready notifies the pending subscriber once", () => {
    const f = fixture();
    const pending = f.request("subscribe", {nonce, boot: true, subscribe: true}, true);
    assert.deepStrictEqual(pending.replies, [{returnValue: true, nonce, ready: false, generation: 1}]);
    const ack = f.request("ready", {nonce});
    assert.strictEqual(ack.replies[0].returnValue, true);
    assert.strictEqual(pending.replies[1].ready, true);
    assert.strictEqual(f.request("ready", {nonce}).replies[0].errorCode, 2);
});

test("every boot subscription starts pending after previous acceptance", () => {
    const f = fixture();
    f.request("subscribe", {nonce, boot: true}, true);
    f.request("ready", {nonce});
    const next = f.request("subscribe", {nonce, boot: true}, true);
    assert.strictEqual(next.replies[0].ready, false);
    assert.strictEqual(next.replies[0].generation, 2);
    assert.strictEqual(next.replies.length, 1);
});

test("replaced subscription is cancelled and late cancellation cannot clear its successor", () => {
    const f = fixture();
    const first = f.request("subscribe", {nonce, boot: true}, true);
    const second = f.request("subscribe", {nonce, boot: true}, true);
    assert.strictEqual(first.replies[1].errorCode, 3);
    f.methods.subscribe.cancel(first);
    assert.strictEqual(f.request("ready", {nonce}).replies[0].returnValue, true);
    assert.strictEqual(second.replies[1].ready, true);
});

test("cancelled subscription cannot be acknowledged", () => {
    const f = fixture();
    const pending = f.request("subscribe", {nonce, boot: true}, true);
    f.methods.subscribe.cancel(pending);
    assert.strictEqual(f.request("ready", {nonce}).replies[0].errorCode, 2);
});

test("wrong nonce and malformed requests do not consume pending readiness", () => {
    const f = fixture();
    const pending = f.request("subscribe", {nonce, boot: true}, true);
    for (const payload of [{}, {nonce: nonce.toUpperCase()}, {nonce: null}]) {
        assert.strictEqual(f.request("ready", payload).replies[0].errorCode, 1);
    }
    assert.strictEqual(f.request("subscribe", {nonce, boot: true}, false).replies[0].errorCode, 1);
    assert.strictEqual(f.request("subscribe", {nonce}, true).replies[0].errorCode, 1);
    assert.strictEqual(f.request("ready", {nonce}).replies[0].returnValue, true);
    assert.strictEqual(pending.replies[1].ready, true);
});

test("failed delivery cannot claim acknowledgement success", () => {
    const f = fixture();
    f.request("subscribe", {nonce, boot: true}, true, false);
    assert.strictEqual(f.request("ready", {nonce}).replies[0].errorCode, 4);
});

test("unexpanded service nonce rejects requests", () => {
    assert.strictEqual(fixture("__NONCE__").request("ready", {nonce: "__NONCE__"}).replies[0].errorCode, 1);
});

console.log("PASS readiness service: " + count + " tests");
