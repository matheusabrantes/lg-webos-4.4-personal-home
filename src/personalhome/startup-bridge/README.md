# PersonalHome startup bridge

This silent, opaque black web app covers the native first-app phase until the compositor is ready. It is never evidence that PersonalHome is healthy.

Build a fresh package with the same 32-hex nonce as the native release:

    python3 src/personalhome/startup-bridge/build.py --nonce RELEASE_NONCE --output NEW_OUTPUT_DIRECTORY

The builder uses the installed ares-package, generates an 80-pixel black icon, and checks the 20 GiB storage reserve with an 8 MiB peak estimate and 64 MiB margin. It never installs or changes boot configuration.

Run the logic tests with:

    node src/personalhome/startup-bridge/test_bridge.js
    node src/personalhome/startup-bridge/test_service.js
    node src/personalhome/startup-bridge/test_protocol.js

A default or boot:true launch/relaunch activates the cover and arms one 75-second watchdog. On expiry it forwards once to com.webos.app.livetv and persists a disabled latch for that release nonce. Later launches immediately forward while disabled.

The app holds a native PalmServiceBridge subscription to com.personalhome.startup.service/subscribe with {nonce,subscribe:true,boot:true}. Each default/boot launch cancels its previous subscription and creates a fresh pending one. The service uses the TV's installed webos-service module; it registers only subscribe and ready, with no application launch method. After independently verifying native Home composition and focus, call com.personalhome.startup.service/ready with {nonce}. It succeeds only for the current pending subscriber, not a prior acceptance. A matching service response cancels the watchdog and clears the disabled latch. Late callbacks from an earlier boot cannot acknowledge a new boot. A disabled launch forwards immediately but retains a bounded 75-second subscription so a genuine readiness acknowledgement can clear the latch.

Readiness errors are code 1 for invalid nonce/request, 2 for no pending subscriber, and 4 for failed delivery. A replaced subscription receives code 3. Callers must allow a bounded wait for the pending subscription to register. Cold guard and warm native controller each own one acknowledgement in their respective lifecycle.

Launch-based personalHomeReady messages are ignored: on this TV launchHidden:true foregrounded the bridge and hid Home. Visibility changes do not acknowledge readiness. An exact personalHomeDisabled nonce sets the latch and forwards once only if the bridge is explicitly visible; a hidden bridge waits for its next default/boot launch.

The app uses [LG's documented relaunch lifecycle](https://webostv.developer.lge.com/develop/guides/app-lifecycle-management) for boot/default relaunches and [JS service subscriptions](https://webostv.developer.lge.com/develop/guides/js-service-usage) for readiness. Only boot/default launches call PalmSystem.activate(). Launch parameters come from webOSRelaunch event detail or PalmSystem.launchParams. Native PalmServiceBridge performs the fallback request without a bundled SDK.

Power-reason boot configuration, app-key exceptions, native readiness checks, and restoration of the original first-app configuration belong to the host release and recovery guard.
