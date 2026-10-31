"use strict";
module.exports = function (service, nonce) {
    var pending = null;
    var generation = 0;
    var validNonce = /^[a-f0-9]{32}$/.test(nonce);

    function valid(message) {
        return validNonce && message.payload && message.payload.nonce === nonce;
    }

    function error(message, code, text) {
        var reply = {returnValue: false, errorCode: code, errorText: text};
        if (message.isSubscription) { message.cancel(reply); }
        else { message.respond(reply); }
    }

    service.register("subscribe", function (message) {
        if (!valid(message) || !message.isSubscription || message.payload.boot !== true) {
            error(message, 1, "Expected release nonce and a boot subscription");
            return;
        }
        if (pending) { pending.cancel({returnValue: false, errorCode: 3, errorText: "Startup subscription replaced"}); }
        pending = message;
        generation++;
        message.respond({returnValue: true, nonce: nonce, ready: false, generation: generation});
    }, function (message) {
        if (pending && pending.uniqueToken === message.uniqueToken) { pending = null; }
    });

    service.register("ready", function (message) {
        if (!valid(message) || message.isSubscription) {
            error(message, 1, "Expected release nonce");
            return;
        }
        if (!pending) {
            error(message, 2, "No pending startup subscription");
            return;
        }
        var subscriber = pending;
        pending = null;
        var delivered = subscriber.respond({returnValue: true, nonce: nonce, ready: true, generation: generation});
        if (delivered === false) { error(message, 4, "Startup subscriber unavailable"); }
        else { message.respond({returnValue: true, nonce: nonce, ready: true, generation: generation}); }
    });
};
