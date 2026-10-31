        QtObject {
            id: personalHomePowerWakeController
            property int generation: 0
            property int requestGeneration: -1
            property int requestToken: -1
            property bool sleeping: false
            property int nativeOffCount: 0
            property int nativeOnCount: 0
            property string lastReason: ""
            property bool queried: false
            property bool interrupted: false
            property bool armed: false
            property bool requested: false
            property bool mappingHeld: false
            property var pausedSurface: null
            property var bridgeSurface: null
            property int bridgeGeneration: -1
            property bool bridgeAcknowledged: false
            property bool bridgeReadyOwned: false
            property int bridgeReadyToken: -1
            property int bridgeReadyGeneration: -1
            property var bridgeReadySurface: null
            property double bridgeReadyUntil: -1
            property double bridgeReadyNext: 0
            property double bridgeReadySent: 0
            property int bridgeReadyAttempts: 0

            function cancel(preserveReadiness) {
                var keepReady = preserveReadiness === true && bridgeReadyOwned && uiScope.personalHomeShown
                    && bridgeSurface && compositor.fullscreen === bridgeSurface;
                generation++; requestToken = -1; armed = false;
                requested = false; interrupted = true;
                if (!keepReady) {
                    mappingHeld = false; bridgeReadyOwned = false; bridgeSurface = null; bridgeGeneration = -1;
                    if (bridgeReadyToken > 0) { try { reasonService.cancel(bridgeReadyToken); } catch (error) {} }
                    bridgeReadyToken = -1; bridgeReadyUntil = -1; bridgeReadyAttempts = 0;
                }
            }
            function nativePowerOff() {
                nativeOffCount++;
                if (sleeping) return;
                pausedSurface = null; bridgeAcknowledged = false; cancel();
                sleeping = true; queried = false; interrupted = false; lastReason = "";
            }
            function nativePowerOn() {
                nativeOnCount++;
            }
            function nativeResume() {
                if (!sleeping) return;
                sleeping = false;
                if (queried || interrupted) return;
                queried = true; requestGeneration = generation; lastReason = "pending";
                try {
                    requestToken = reasonService.call("luna://com.webos.service.tvpower", "/power/getPowerOnReason", "{}");
                } catch (error) { lastReason = "invalid"; cancel(); }
            }
            function powerChanged(resumeNotification) {
                var preparing = systemSettings.powerProcessing;
                if (resumeNotification === true && (preparing === "LastInput Ready" || preparing === "Screen On"))
                    nativeResume();
                if (systemSettings.powerState !== "Active" && systemSettings.powerState !== "Suspend" && systemSettings.powerState !== "Active Standby") {
                    if (!sleeping && !queried) cancel();
                    return;
                }
                tryShow();
            }
            function receive(token, method, payload) {
                if (method === "/ready") {
                    if (bridgeReadyToken <= 0 || token !== bridgeReadyToken || bridgeReadyGeneration !== bridgeGeneration) return;
                    bridgeReadyToken = -1;
                    var readyNow = ysm.personalHomeStartupClock();
                    if (!bridgeReadyContext() || bridgeReadySurface !== bridgeSurface || readyNow < 0 || readyNow > bridgeReadyUntil) return;
                    var readyReply;
                    try { readyReply = JSON.parse(payload); } catch (error) { return; }
                    if (readyReply.returnValue === true && readyReply.nonce === "__NONCE__" && readyReply.ready === true)
                        bridgeAcknowledged = true;
                    return;
                }
                if (requestGeneration !== generation || requestToken <= 0 || token !== requestToken || method !== "/power/getPowerOnReason") return;
                requestToken = -1;
                var reply;
                try { reply = JSON.parse(payload); } catch (error) { lastReason = "invalid"; cancel(); return; }
                lastReason = reply.returnValue !== true ? "invalid" : reply.reason === "remoteKey" ? "remoteKey" : reply.reason === "amazon" ? "amazon" : "other";
                if (reply.returnValue !== true || reply.reason !== "remoteKey") { cancel(); return; }
                armed = true; tryShow();
            }
            function tryShow() {
                if (!armed || requested || !uiScope.personalHomeOwnsRibbon || !ysm.smartTvReady || ysm.coverUIOpen
                        || !ysm.access.ribbon || !overlayView.accessRibbon || systemSettings.disableHome
                        || systemSettings.bootFirstUse || !notificationView || notificationView.modalAlertActive
                        || globalActions.popupOpen || fullscreenView.delegating) return;
                requested = true;
                if (ysm.state !== "visible") ysm.goHome();
                uiScope.focusPersonalHome();
            }
            function keepHomeForSurface(surface) {
                var shownBridge = !!surface && surface.appId === "com.personalhome.startup"
                    && compositor.fullscreen === surface && uiScope.personalHomeShown;
                if (bridgeReadyOwned && surface && surface !== bridgeSurface) cancel();
                if (ysm.personalHomeStartupBridgeMapped(surface)) return true;
                if (surface && surface === pausedSurface && surface.state === Qt.WindowMinimized) return true;
                if (surface && surface.appId === "com.personalhome.startup" && compositor.fullscreen === surface
                        && !interrupted && (sleeping || queried) && bridgeGeneration < 0) {
                    bridgeSurface = surface; bridgeGeneration = generation;
                }
                if (surface && surface === bridgeSurface && bridgeReadyOwned && mappingHeld) return true;
                if (!armed || !requested) return shownBridge;
                if (mappingHeld) { cancel(); return shownBridge; }
                if (!surface || compositor.fullscreen !== surface || !/^(com\.webos\.app\.livetv|com\.webos\.app\.hdmi[1-3]|com\.personalhome\.startup)$/.test(surface.appId)) { cancel(); return false; }
                mappingHeld = true;
                if (surface.appId === "com.personalhome.startup") bridgeReadyOwned = true;
                if (surface.appId === "com.webos.app.livetv") {
                    pausedSurface = surface;
                    try { CompositorLogic.minimizeByAppId(surface.appId); }
                    catch (error) { pausedSurface = null; cancel(); return false; }
                }
                return true;
            }
            function bridgeReadyContext() {
                return bridgeReadyOwned && mappingHeld && uiScope.personalHomeShown && !!personalHomeLoader.item
                    && personalHomeLoader.item.activeFocus && bridgeGeneration >= 0
                    && !!bridgeSurface && bridgeSurface.appId === "com.personalhome.startup"
                    && compositor.fullscreen === bridgeSurface;
            }
            function acknowledgeBridgeFrame() {
                ysm.personalHomeStartupComposed(uiScope.personalHomeShown, !!personalHomeLoader.item && personalHomeLoader.item.activeFocus);
                if (armed && requested && bridgeGeneration === generation && bridgeSurface === compositor.fullscreen && !mappingHeld)
                    keepHomeForSurface(bridgeSurface);
                if (bridgeAcknowledged || !bridgeReadyContext()) return;
                var now = ysm.personalHomeStartupClock();
                if (now < 0) return;
                if (bridgeReadyUntil < 0) bridgeReadyUntil = now + 6;
                if (now >= bridgeReadyUntil || bridgeReadyAttempts >= 6 || now < bridgeReadyNext) return;
                if (bridgeReadyToken > 0) {
                    if (now - bridgeReadySent < 2) return;
                    try { reasonService.cancel(bridgeReadyToken); } catch (error) {}
                    bridgeReadyToken = -1;
                }
                bridgeReadyAttempts++; bridgeReadyNext = now + 1; bridgeReadySent = now;
                bridgeReadyGeneration = bridgeGeneration; bridgeReadySurface = bridgeSurface;
                try {
                    bridgeReadyToken = reasonService.call("luna://com.personalhome.startup.service", "/ready", JSON.stringify({nonce:"__NONCE__"}));
                } catch (error) { bridgeReadyToken = -1; }
            }
            function resumePausedInput() {
                if (compositor.fullscreen && compositor.fullscreen.appId === "com.personalhome.startup") {
                    try {
                        var app = systemSettings.lastInputApp;
                        if (!/^(com\.webos\.app\.livetv|com\.webos\.app\.hdmi[1-3])$/.test(app)) app = "com.webos.app.livetv";
                        var point = ysm.launchPointsModel.getLaunchPointByAppId(app);
                        if (!point || point.id !== app) return false;
                        pausedSurface = null; cancel();
                        ysm.launchPointActivated(point);
                        return true;
                    } catch (error) { return false; }
                }
                var surface = pausedSurface;
                pausedSurface = null; cancel();
                if (!surface || compositor.fullscreen !== surface) return true;
                try {
                    if (surface.appId === "com.webos.app.livetv" && surface.state === Qt.WindowMinimized) surface.requestFullscreen();
                    return true;
                } catch (error) { pausedSurface = surface; return false; }
            }
            function nativeShowHome() {
                if (uiScope.personalHomeShown) return true;
                if (!armed) return false;
                tryShow();
                return true;
            }
            property Service reasonService: Service {
                appId: ysm.appId
                onResponse: personalHomePowerWakeController.receive(token, method, payload)
            }
        }
        Connections {
            target: systemSettings
            onPowerStateChanged: personalHomePowerWakeController.powerChanged()
            onPowerProcessingChanged: personalHomePowerWakeController.powerChanged(true)
            onDisableHomeChanged: personalHomePowerWakeController.tryShow()
            onBootFirstUseChanged: personalHomePowerWakeController.tryShow()
        }
        Connections {
            target: ysm
            onSmartTvReadyChanged: personalHomePowerWakeController.tryShow()
            onCoverUIOpenChanged: personalHomePowerWakeController.tryShow()
        }
        Connections { target: uiScope; onPersonalHomeOwnsRibbonChanged: personalHomePowerWakeController.tryShow() }
        Connections { target: notificationView; onModalAlertActiveChanged: personalHomePowerWakeController.tryShow() }
        Connections { target: globalActions; onPopupOpenChanged: personalHomePowerWakeController.tryShow() }
        Connections { target: ysm.access; onRibbonChanged: personalHomePowerWakeController.tryShow() }
        Connections { target: overlayView; onAccessRibbonChanged: personalHomePowerWakeController.tryShow() }
        Connections { target: fullscreenView; onDelegatingChanged: personalHomePowerWakeController.tryShow() }
        Connections { target: compositorWindow; onFrameSwapped: personalHomePowerWakeController.acknowledgeBridgeFrame() }
