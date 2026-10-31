"use strict";
const assert = require("assert");
const fs = require("fs");
const vm = require("vm");
const path = require("path");
const source = fs.readFileSync(path.join(__dirname, "bridge.js"), "utf8");
const exported = {exports: {}};
vm.runInNewContext(source, {module: exported});
const createBridge = exported.exports;
const nonce = "0123456789abcdef0123456789abcdef";
let count = 0;

function fixture(options) {
    options = options || {};
    let now = 0;
    let nextTimer = 0;
    let hidden = options.hidden;
    const timers = new Map();
    const storage = options.storage || new Map();
    const calls = [];
    const subscriptions = [];
    const order = [];
    const environment = {
        nonce: options.nonce || nonce,
        setTimeout(callback, delay) {
            const id = nextTimer++;
            timers.set(id, {callback, due: now + delay});
            return id;
        },
        clearTimeout(id) { timers.delete(id); },
        storage() {
            if (options.storageThrows) { throw new Error("storage unavailable"); }
            return {
                getItem: key => storage.get(key),
                setItem: (key, value) => storage.set(key, value),
                removeItem: key => storage.delete(key)
            };
        },
        activate() { order.push("activate"); },
        isVisible() { return hidden === false || options.visible === true; },
        isHidden() { return hidden === true; },
        createServiceBridge() {
            if (options.bridgeThrows) { throw new Error("bridge unavailable"); }
            const bridge = {cancelled: false, cancel() { this.cancelled = true; }, call(uri, body) {
                if (uri.endsWith("/subscribe")) { subscriptions.push(this); return; }
                order.push("fallback");
                calls.push({uri, body: JSON.parse(body)});
            }};
            return bridge;
        }
    };
    const controller = createBridge(environment);
    function tick(ms) {
        const end = now + ms;
        while (true) {
            const ready = [...timers].filter(([, timer]) => timer.due <= end)
                .sort((left, right) => left[1].due - right[1].due)[0];
            if (!ready) { break; }
            now = ready[1].due;
            timers.delete(ready[0]);
            ready[1].callback();
        }
        now = end;
    }
    function ack(reply, index) {
        const subscription = subscriptions[index === undefined ? subscriptions.length - 1 : index];
        subscription.onservicecallback(JSON.stringify(reply || {returnValue: true, nonce, ready: true}));
    }
    function setHidden(value, notify) {
        hidden = value;
        if (notify !== false) { controller.visibilityChanged(); }
    }
    return {controller, tick, calls, storage, timers, order, subscriptions, ack, setHidden};
}

function test(name, run) {
    run();
    count++;
    console.log("PASS " + name);
}

test("75 second watchdog forwards once and persists disabled", () => {
    const f = fixture();
    f.controller.launch({boot: true});
    assert.strictEqual(f.timers.size, 1);
    f.tick(74999);
    assert.strictEqual(f.calls.length, 0);
    f.tick(1);
    assert.deepStrictEqual(f.calls, [{
        uri: "luna://com.webos.applicationManager/launch",
        body: {id: "com.webos.app.livetv"}
    }]);
    f.tick(1000000);
    assert.strictEqual(f.calls.length, 1);
    assert.strictEqual(f.storage.get("personalhome.startup.disabled." + nonce), "1");
});

test("exact native ready acknowledgement cancels without activation", () => {
    const f = fixture();
    f.controller.launch({});
    f.tick(1000);
    f.ack();
    f.tick(1000000);
    assert.strictEqual(f.calls.length, 0);
    assert.strictEqual(f.timers.size, 0);
    assert.deepStrictEqual(f.order, ["activate"]);
});

test("wrong acknowledgement does not extend watchdog", () => {
    const f = fixture();
    f.controller.launch({});
    f.tick(74000);
    f.ack({returnValue: true, nonce: "fedcba9876543210fedcba9876543210", ready: true});
    f.tick(1000);
    assert.strictEqual(f.calls.length, 1);
});

test("new boot and default relaunch replace the old timer", () => {
    const f = fixture();
    f.controller.launch({boot: true});
    f.tick(70000);
    f.controller.launch({});
    assert.strictEqual(f.timers.size, 1);
    f.tick(70000);
    assert.strictEqual(f.calls.length, 0);
    f.ack();
    f.controller.launch({boot: true});
    assert.strictEqual(f.timers.size, 1);
    f.tick(75000);
    assert.strictEqual(f.calls.length, 1);
});

test("disabled boots immediately forward once per boot after activation", () => {
    const f = fixture();
    f.controller.launch({});
    f.tick(75000);
    f.controller.launch({boot: true});
    assert.strictEqual(f.calls.length, 2);
    assert.strictEqual(f.timers.size, 1);
    assert.deepStrictEqual(f.order, ["activate", "fallback", "activate", "fallback"]);
    const restarted = fixture({storage: f.storage});
    restarted.controller.launch({});
    assert.strictEqual(restarted.calls.length, 1);
    assert.strictEqual(restarted.timers.size, 1);
    restarted.tick(75000);
    assert.strictEqual(restarted.calls.length, 1);
    assert.strictEqual(restarted.timers.size, 0);
});

test("ready clears the persistent disabled latch for the next boot", () => {
    const f = fixture();
    f.controller.launch({});
    f.tick(75000);
    f.controller.launch({boot: true});
    f.ack();
    assert.strictEqual(f.storage.has("personalhome.startup.disabled." + nonce), false);
    f.controller.launch({boot: true});
    assert.strictEqual(f.calls.length, 2);
    f.tick(75000);
    assert.strictEqual(f.calls.length, 3);
});

test("nonce isolation prevents old releases from disabling a new release", () => {
    const f = fixture();
    f.controller.launch({});
    f.controller.launch({personalHomeDisabled: "fedcba9876543210fedcba9876543210"});
    assert.strictEqual(f.timers.size, 1);
    assert.strictEqual(f.storage.size, 0);
    const next = fixture({nonce: "fedcba9876543210fedcba9876543210", storage: f.storage});
    next.controller.launch({});
    assert.strictEqual(next.calls.length, 0);
    assert.strictEqual(next.timers.size, 1);
});

test("disabled control forwards only when explicitly visible", () => {
    const hidden = fixture();
    hidden.controller.launch({});
    hidden.controller.launch({personalHomeDisabled: nonce});
    hidden.tick(75000);
    assert.strictEqual(hidden.calls.length, 0);
    assert.strictEqual(hidden.timers.size, 0);
    hidden.controller.launch({});
    assert.strictEqual(hidden.calls.length, 1);
    const visible = fixture({visible: true});
    visible.controller.launch({});
    visible.controller.launch({personalHomeDisabled: nonce});
    visible.controller.launch({personalHomeDisabled: nonce});
    assert.strictEqual(visible.calls.length, 1);
});

test("unexpanded nonce cannot acknowledge a packaged watchdog", () => {
    const f = fixture({nonce: "__NONCE__"});
    f.controller.launch({});
    f.controller.launch({personalHomeReady: "__NONCE__"});
    f.tick(75000);
    assert.strictEqual(f.calls.length, 1);
});

test("unavailable storage and native bridge do not create retry loops", () => {
    const f = fixture({storageThrows: true, bridgeThrows: true});
    f.controller.launch({});
    assert.doesNotThrow(() => f.tick(1000000));
    assert.strictEqual(f.timers.size, 0);
    f.controller.launch({});
    assert.strictEqual(f.timers.size, 1);
    f.tick(75000);
    assert.strictEqual(f.timers.size, 0);
});

test("browser adapter reads PalmSystem and event detail without foregrounding ACK", () => {
    const listeners = {};
    const calls = [];
    const clock = new Map();
    let next = 0;
    let activated = 0;
    const storage = new Map();
    const context = {
        document: {hidden: true, addEventListener(name, handler) { listeners[name] = handler; }},
        PalmSystem: {launchParams: '{"boot":true}', activate() { activated++; }},
        PalmServiceBridge: function () {
            this.cancel = () => {};
            this.call = (uri, body) => calls.push({uri, body: JSON.parse(body), bridge: this});
        },
        localStorage: {
            getItem: key => storage.get(key),
            setItem: (key, value) => storage.set(key, value),
            removeItem: key => storage.delete(key)
        },
        setTimeout: callback => { clock.set(next, callback); return next++; },
        clearTimeout: id => clock.delete(id)
    };
    vm.runInNewContext(source.replace("__NONCE__", nonce), context);
    assert.strictEqual(clock.size, 1);
    listeners.webOSRelaunch({detail: {personalHomeReady: nonce}});
    assert.strictEqual(clock.size, 1);
    calls[calls.length - 1].bridge.onservicecallback(JSON.stringify({returnValue: true, nonce, ready: true}));
    assert.strictEqual(clock.size, 0);
    assert.strictEqual(activated, 1);
    context.PalmSystem.launchParams = '{"boot":true}';
    listeners.webOSRelaunch({});
    assert.strictEqual(clock.size, 1);
    assert.strictEqual(activated, 2);
    listeners.webOSRelaunch({detail: "{malformed"});
    assert.strictEqual(clock.size, 1);
    listeners.webOSRelaunch({detail: JSON.stringify({personalHomeReady: nonce})});
    assert.strictEqual(clock.size, 1);
    calls[calls.length - 1].bridge.onservicecallback(JSON.stringify({returnValue: true, nonce, ready: true}));
    assert.strictEqual(clock.size, 0);
    assert.strictEqual(calls.filter(call => call.uri.endsWith("/launch")).length, 0);
});

test("stale service callback cannot acknowledge the next boot", () => {
    const f = fixture();
    f.controller.launch({boot: true});
    f.ack();
    f.controller.launch({boot: true});
    f.ack(undefined, 0);
    assert.strictEqual(f.timers.size, 1);
    f.tick(75000);
    assert.strictEqual(f.calls.length, 1);
});

test("hidden bridge cannot replace a legitimate app or persist a failure", () => {
    const f = fixture({hidden: false});
    f.controller.launch({boot: true});
    f.tick(40000);
    f.setHidden(true);
    assert.strictEqual(f.timers.size, 0);
    assert.strictEqual(f.subscriptions[0].cancelled, true);
    f.tick(100000);
    assert.strictEqual(f.calls.length, 0);
    assert.strictEqual(f.storage.size, 0);
    f.controller.launch({boot: true});
    assert.strictEqual(f.timers.size, 1);
    f.setHidden(false);
    f.tick(75000);
    assert.strictEqual(f.calls.length, 1);
});

test("transient startup hide pauses until visible without activating again", () => {
    const f = fixture({hidden: false});
    f.controller.launch({boot: true});
    f.setHidden(true);
    f.setHidden(false);
    assert.strictEqual(f.timers.size, 1);
    assert.strictEqual(f.subscriptions.length, 2);
    assert.deepStrictEqual(f.order, ["activate"]);
    f.ack(undefined, 0);
    assert.strictEqual(f.timers.size, 1);
    f.ack();
    f.setHidden(true);
    f.setHidden(false);
    assert.strictEqual(f.timers.size, 0);
    f.tick(100000);
    assert.strictEqual(f.calls.length, 0);
    assert.strictEqual(f.storage.size, 0);
});

test("timeout independently checks for a missed hide event", () => {
    const f = fixture({hidden: false});
    f.controller.launch({});
    f.setHidden(true, false);
    f.tick(75000);
    assert.strictEqual(f.calls.length, 0);
    assert.strictEqual(f.storage.size, 0);
    assert.strictEqual(f.subscriptions[0].cancelled, true);
    f.setHidden(false);
    assert.strictEqual(f.timers.size, 1);
    f.tick(75000);
    assert.strictEqual(f.calls.length, 1);
});

test("unknown visibility retains the foreground black-screen failsafe", () => {
    const f = fixture();
    f.controller.launch({});
    f.setHidden(undefined);
    assert.strictEqual(f.timers.size, 1);
    f.tick(75000);
    assert.strictEqual(f.calls.length, 1);
    assert.strictEqual(f.storage.get("personalhome.startup.disabled." + nonce), "1");
});

test("browser adapter handles standard and prefixed visibility without rearming accepted Home", () => {
    const listeners = {}, timers = new Map(), subscriptions = [], storage = new Map();
    let next = 0, activated = 0;
    const context = {
        document: {hidden: false, addEventListener(name, handler) { listeners[name] = handler; }},
        PalmSystem: {launchParams: '{"boot":true}', activate() { activated++; }},
        PalmServiceBridge: function () {
            this.cancelled = false;
            this.cancel = () => { this.cancelled = true; };
            this.call = uri => { assert(uri.endsWith("/subscribe")); subscriptions.push(this); };
        },
        localStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
        setTimeout: callback => { timers.set(next, callback); return next++; },
        clearTimeout: id => timers.delete(id)
    };
    vm.runInNewContext(source.replace("__NONCE__", nonce), context);
    context.document.hidden = true;
    listeners.visibilitychange();
    assert.strictEqual(timers.size, 0);
    assert.strictEqual(subscriptions[0].cancelled, true);
    context.document.hidden = false;
    listeners.visibilitychange();
    assert.strictEqual(timers.size, 1);
    subscriptions[1].onservicecallback(JSON.stringify({returnValue: true, nonce, ready: true}));
    context.document.hidden = true;
    listeners.visibilitychange();
    context.document.hidden = false;
    listeners.visibilitychange();
    assert.strictEqual(timers.size, 0);
    delete context.document.hidden;
    context.document.webkitHidden = true;
    listeners.webOSRelaunch({detail: {boot: true}});
    listeners.webkitvisibilitychange();
    assert.strictEqual(timers.size, 0);
    context.document.webkitHidden = false;
    listeners.webkitvisibilitychange();
    assert.strictEqual(timers.size, 1);
    assert.strictEqual(activated, 2);
    assert.strictEqual(storage.size, 0);
});

console.log("PASS startup bridge: " + count + " tests");
