        property int trialSequence: 0
        property int runtimeFrameSequence: 0
        property int runtimeRenderProbe: 0
        property int runtimePendingProbe: 0
        property bool runtimeLaunchConsumed: false
        property string runtimeLaunchError: ""
        property var runtimeLaunchRequest: TextFile { name: "file://__DIRECTORY__/foreground-request.json" }
        property var trialHealth: TextFile { name: "file://__DIRECTORY__/health.json" }
        property var runtimeRenderRequest: TextFile { name: "file://__DIRECTORY__/render-request.json" }
        Connections {
            target: uiScope.runtimePendingProbe > 0 && typeof compositorWindow !== "undefined" ? compositorWindow : null
            onFrameSwapped: {
                if (uiScope.runtimePendingProbe > 0) {
                    uiScope.runtimeFrameSequence++;
                    uiScope.runtimeRenderProbe=uiScope.runtimePendingProbe;
                    uiScope.runtimePendingProbe=0;
                }
            }
        }
        Timer {
            interval:250;repeat:true;running:true
            onTriggered: {
                var item=personalHomeLoader.item;
                var attached=!!item && !!item.Window.contentItem;
                var nativeContext=typeof compositor!=="undefined" && compositor!==null
                    && typeof compositorWindow!=="undefined" && compositorWindow!==null
                    && !!ysm.Window.contentItem && attached && item.Window.contentItem===ysm.Window.contentItem
                    && item.Window.contentItem===compositorWindow.contentItem;
                var overlay=notificationView.alertActive || globalActions.popupOpen
                    || overlayView.state==="opened" || overlaySurfaceGroupView.state==="opened";
                if (personalHomeLoader.powerActive && nativeContext && item.readyForActivation && !ysm.coverUIOpen && !uiScope.runtimeLaunchConsumed) {
                    var launch=null;
                    try { launch=JSON.parse(uiScope.runtimeLaunchRequest.read()); } catch(error) {}
                    if (launch && launch.nonce==="__NONCE__" && typeof launch.appId==="string" && /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/.test(launch.appId)) {
                        uiScope.runtimeLaunchConsumed=true;
                        try {
                            var point=ysm.launchPointsModel.getLaunchPointByAppId(launch.appId);
                            if (!point) throw new Error("Saved app has no installed launch point");
                            ysm.launchPointActivated(point, undefined, true);
                        } catch(launchError) { uiScope.runtimeLaunchError=String(launchError); }
                    }
                }
                if (personalHomeLoader.powerActive && nativeContext && !uiScope.runtimePendingProbe) {
                    var request=null;
                    try { request=JSON.parse(uiScope.runtimeRenderRequest.read()); } catch(error) {}
                    if (request && request.nonce==="__NONCE__" && typeof request.sequence==="number"
                            && isFinite(request.sequence) && Math.floor(request.sequence)===request.sequence
                            && request.sequence>uiScope.runtimeRenderProbe) {
                        uiScope.runtimePendingProbe=request.sequence;
                        compositorWindow.update();
                    }
                }
                uiScope.trialHealth.write(JSON.stringify({schema:3,nonce:"__NONCE__",sequence:++uiScope.trialSequence,
                    frameSequence:uiScope.runtimeFrameSequence,renderProbe:uiScope.runtimeRenderProbe,
                    foregroundRequestConsumed:uiScope.runtimeLaunchConsumed,foregroundRequestError:uiScope.runtimeLaunchError,
                    powerActive:personalHomeLoader.powerActive,coverOpen:ysm.coverUIOpen,overlayOpen:overlay,
                    focusRequired:uiScope.personalHomeShown && !overlay && !ysm.coverUIOpen,
                    foregroundAppId:compositor.fullscreen ? compositor.fullscreen.appId : "",
                    moduleResolved:true,rootSource:Qt.resolvedUrl("YSM.qml").toString(),
                    componentInstantiated:item!==null,initialized:!!item && item.diagnosticInitialized,
                    windowAttached:attached,nativeContextAttached:nativeContext,
                    ready:typeof root!=="undefined" && root.ysm===ysm && !!item && item.readyForActivation,
                    shown:uiScope.personalHomeShown,visible:!!item && item.visible,activeFocus:!!item && item.activeFocus,
                    focusIndex:item ? item.focusIndex : -1,keyEvents:item ? item.diagnosticKeyCount : 0,
                    lastKey:item ? item.diagnosticLastKey : 0,originalFallback:!uiScope.personalHomeEnabled,
                    photoIndex:item ? item.photoIndex : -1,photoCount:item ? item.photoCount : 0,
                    photoLoading:!!item && item.photoLoading,photoFailures:item ? item.photoFailures : 0,
                    photoTimerActive:!!item && item.photoTimerActive,
                    inputMenuOpen:!!item && !!item.inputMenuOpen,inputMenuFocusIndex:item ? item.inputMenuFocusIndex : -1,
                    inputMenuBuildMs:item ? item.lastInputMenuMs : -1,inputEntryCount:item && item.inputEntries ? item.inputEntries.length : 0,
                    inputLoading:!!item && item.inputLoading,
                    originalRibbonVisible:superRibbon.visible,originalRibbonEnabled:superRibbon.enabled}));
            }
        }
