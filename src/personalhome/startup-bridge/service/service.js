"use strict";
var Service = require("webos-service");
require("./readiness")(new Service("com.personalhome.startup.service", null, {noBuiltinMethods: true}), "__NONCE__");
