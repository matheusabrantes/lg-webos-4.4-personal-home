(function (root, createBridge) {
    "use strict";
    if (typeof module === "object" && module.exports) {
        module.exports = createBridge;
        return;
    }

    var controller = createBridge({
        nonce: "__NONCE__",
        setTimeout: function (callback, delay) { return root.setTimeout(callback, delay); },
        clearTimeout: function (timer) { root.clearTimeout(timer); },
        storage: function () { return root.localStorage; },
        activate: function () {
            if (root.PalmSystem && root.PalmSystem.activate) { root.PalmSystem.activate(); }
        },
        isVisible: function () {
            if (typeof root.document.hidden === "boolean") { return !root.document.hidden; }
            if (typeof root.document.webkitHidden === "boolean") { return !root.document.webkitHidden; }
            return false;
        },
        isHidden: function () {
            if (typeof root.document.hidden === "boolean") { return root.document.hidden; }
            if (typeof root.document.webkitHidden === "boolean") { return root.document.webkitHidden; }
            return false;
        },
        createServiceBridge: function () { return new root.PalmServiceBridge(); }
    });

    function launchParams(event) {
        var params = event && event.detail;
        if (params === undefined && root.PalmSystem) { params = root.PalmSystem.launchParams; }
        try { if (typeof params === "string") { params = JSON.parse(params); } }
        catch (error) { return {}; }
        return params && typeof params === "object" && !Array.isArray(params) ? params : {};
    }

    root.document.addEventListener("webOSRelaunch", function (event) {
        controller.launch(launchParams(event));
    }, true);
    root.document.addEventListener("visibilitychange", controller.visibilityChanged, true);
    root.document.addEventListener("webkitvisibilitychange", controller.visibilityChanged, true);
    controller.launch(launchParams());
}(this, function (environment) {
    "use strict";
    var nonce = environment.nonce;
    var validNonce = /^[a-f0-9]{32}$/.test(nonce);
    var key = "personalhome.startup.disabled." + nonce;
    var timer = null;
    var fallbackSent = false;
    var serviceBridge = null;
    var readinessBridge = null;
    var readinessGeneration = 0;
    var disabled = false;
    var cyclePending = false;

    try { disabled = environment.storage().getItem(key) === "1"; }
    catch (error) {}

    function persistDisabled(value) {
        disabled = value;
        try {
            if (value) { environment.storage().setItem(key, "1"); }
            else { environment.storage().removeItem(key); }
        } catch (error) {}
    }

    function stopTimer() {
        if (timer !== null) {
            environment.clearTimeout(timer);
            timer = null;
        }
    }

    function fallback() {
        if (fallbackSent) { return; }
        fallbackSent = true;
        try {
            serviceBridge = environment.createServiceBridge();
            serviceBridge.onservicecallback = function () { serviceBridge = null; };
            serviceBridge.call("luna://com.webos.applicationManager/launch",
                               JSON.stringify({id: "com.webos.app.livetv"}));
        } catch (error) { serviceBridge = null; }
    }

    function stopSubscription() {
        readinessGeneration++;
        var previous = readinessBridge;
        readinessBridge = null;
        if (previous && previous.cancel) {
            try { previous.cancel(); } catch (error) {}
        }
    }

    function subscribeReady() {
        stopSubscription();
        var generation = readinessGeneration;
        try {
            readinessBridge = environment.createServiceBridge();
            readinessBridge.onservicecallback = function (raw) {
                if (generation !== readinessGeneration) { return; }
                var reply;
                try { reply = JSON.parse(raw); } catch (error) { return; }
                if (validNonce && reply.returnValue === true && reply.nonce === nonce && reply.ready === true) {
                    cyclePending = false;
                    stopTimer();
                    persistDisabled(false);
                    stopSubscription();
                }
            };
            readinessBridge.call("luna://com.personalhome.startup.service/subscribe",
                                 JSON.stringify({nonce: nonce, subscribe: true, boot: true}));
        } catch (error) { readinessBridge = null; }
    }

    function explicitlyHidden() {
        return typeof environment.isHidden === "function" && environment.isHidden() === true;
    }

    function startWatchdog() {
        stopTimer();
        timer = environment.setTimeout(function () {
            timer = null;
            stopSubscription();
            if (explicitlyHidden()) { return; }
            cyclePending = false;
            persistDisabled(true);
            fallback();
        }, 75000);
        subscribeReady();
    }

    function visibilityChanged() {
        if (explicitlyHidden()) {
            stopTimer();
            stopSubscription();
        } else if (cyclePending && timer === null && environment.isVisible()) {
            startWatchdog();
        }
    }

    function launch(params) {
        params = params || {};
        if (Object.prototype.hasOwnProperty.call(params, "personalHomeReady")) {
            return;
        }
        if (Object.prototype.hasOwnProperty.call(params, "personalHomeDisabled")) {
            if (validNonce && params.personalHomeDisabled === nonce) {
                cyclePending = false;
                stopTimer();
                stopSubscription();
                persistDisabled(true);
                if (environment.isVisible()) { fallback(); }
            }
            return;
        }

        stopTimer();
        stopSubscription();
        cyclePending = true;
        fallbackSent = false;
        environment.activate();
        startWatchdog();
        if (disabled) { fallback(); }
    }

    return {launch: launch, visibilityChanged: visibilityChanged};
}));
