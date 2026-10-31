        property bool personalHomeEnabled: true
        property bool personalHomeInputsStarted: false
        property bool personalHomeInputBackPending: false
        readonly property bool personalHomeOwnsRibbon: personalHomeLoader.status === Loader.Ready
            && personalHomeLoader.item !== null && personalHomeLoader.item.readyForActivation
            && personalHomeEnabled && personalHomeLoader.homeState
            && personalHomeLoader.powerActive
        readonly property bool personalHomeShown: personalHomeOwnsRibbon && ysm.state === "visible"

        function focusPersonalHome() {
            if (personalHomeShown && !!notificationView && !notificationView.modalAlertActive
                    && !globalActions.popupOpen && FocusHandler.getTopItem() === uiScope)
                if(typeof personalHomeLoader.item.focusHome==="function")personalHomeLoader.item.focusHome();else personalHomeLoader.item.forceActiveFocus();
        }

        Loader {
            id: personalHomeInputs
            objectName: "personalHomeInputsController"
            active: uiScope.personalHomeInputsStarted && personalHomeLoader.powerActive
            source: "PersonalHome/InputsController.qml"
            onLoaded: {
                item.appId=ysm.appId;
                var fallback=[];
                for(var port=1;port<=3;port++){
                    var point=ysm.launchPointsModel.getLaunchPointByAppId("com.webos.app.hdmi"+port);
                    if(point)fallback.push({id:"HDMI_"+port,port:port,appId:point.id,label:point.title||"HDMI "+port,chosen:true});
                }
                item.fallbackInputs=fallback;item.start();
            }
        }
        Binding {target:personalHomeInputs.item;property:"currentAppId";value:compositor.fullscreen?compositor.fullscreen.appId:"";when:personalHomeInputs.item!==null}
        Binding {target:personalHomeInputs.item;property:"lockOut";value:systemSettings.lockOutControl;when:personalHomeInputs.item!==null}
        Binding {target:personalHomeLoader.item;property:"inputEntries";value:personalHomeInputs.item?personalHomeInputs.item.rows:[];when:personalHomeLoader.item!==null&&typeof personalHomeLoader.item.inputEntries!=="undefined"}
        Binding {target:personalHomeLoader.item;property:"inputLoading";value:personalHomeInputs.status===Loader.Loading||!!personalHomeInputs.item&&personalHomeInputs.item.loading;when:personalHomeLoader.item!==null&&typeof personalHomeLoader.item.inputLoading!=="undefined"}
        Binding {target:personalHomeLoader.item;property:"inputError";value:personalHomeInputs.status===Loader.Error?"Não foi possível atualizar as entradas.":personalHomeInputs.item?personalHomeInputs.item.errorMessage:"";when:personalHomeLoader.item!==null&&typeof personalHomeLoader.item.inputError!=="undefined"}
        Connections {
            target:personalHomeInputs.item
            onLaunchRequested: {
                if(!uiScope.personalHomeShown||!personalHomeLoader.item||notificationView.modalAlertActive)return;
                var generation=++personalHomeLoader.launchGeneration;
                personalHomeLoader.pendingLaunchId=entry.appId;
                personalHomeLoader.pendingLaunchToken=-1;personalHomeLoader.launchAccepted=false;
                personalHomeLoader.item.launchPending=true;
                try {
                    ysm.appManagerService.checkLaunch(entry.appId,JSON.stringify(entry.params),false,false,"personalHomeInputs",function(token){personalHomeLoader.issued(generation,token);});
                } catch(error){personalHomeLoader.finishLaunch(false);}
            }
            onSelectionFailed:if(personalHomeLoader.item)personalHomeLoader.item.completeAction(false,message)
        }

        Loader {
            id: personalHomeLoader
            objectName: "personalHomeLoader"
            anchors.fill: parent
            z: 1
            active: uiScope.personalHomeEnabled
            visible: uiScope.personalHomeShown
            source: "PersonalHome/PersonalHome.qml"
            property string pendingLaunchId: ""
            property int pendingLaunchToken: -1
            property bool launchAccepted: false
            property int launchGeneration: 0
            readonly property bool homeState: superRibbon.state === "home"
                || superRibbon.state === "launcher" || superRibbon.state === "smartHome"
            readonly property bool powerActive: systemSettings.powerState === "Active"
                && systemSettings.powerProcessing !== "Prepare Suspend"
                && systemSettings.powerProcessing !== "Prepare Active Standby"
                && systemSettings.powerProcessing !== "Prepare Power Off"

            function useOriginal() {
                forgetLaunch();
                uiScope.personalHomeEnabled = false;
                superRibbon.takeFocus(true);
            }

            function forgetLaunch() {
                pendingLaunchId = "";
                pendingLaunchToken = -1;
                launchAccepted = false;
                launchGeneration++;
            }

            function finishLaunch(success) {
                forgetLaunch();
                if (item !== null) item.completeAction(success, success ? "" : "Não foi possível abrir. Tente novamente.");
            }

            function issued(generation, token) {
                if (generation !== launchGeneration || !pendingLaunchId) return;
                if (token === null) {
                    launchAccepted = true;
                    if (!uiScope.personalHomeShown) finishLaunch(true);
                } else if (typeof token === "number" && isFinite(token) && token > 0 && Math.floor(token) === token) {
                    pendingLaunchToken = token;
                } else finishLaunch(false);
            }

            function launchResult(identifier, token, success) {
                if (identifier !== pendingLaunchId || token !== pendingLaunchToken || pendingLaunchToken < 0) return;
                if (!success) finishLaunch(false);
                else {
                    launchAccepted = true;
                    if (!uiScope.personalHomeShown) finishLaunch(true);
                }
            }

            function handleAction(action) {
                if (!uiScope.personalHomeShown || item === null || !notificationView || notificationView.modalAlertActive) return;
                if (action === "original") { useOriginal(); return; }
                if (action === "back") {
                    forgetLaunch();
                    item.completeAction(true, "");
                    ysm.gotoState("hidden");
                    return;
                }
                var apps = {
                    livetv: "com.webos.app.livetv", abrantesflix: "com.abrantesflix.app",
                    netflix: "netflix", youtube: "youtube.leanback.v4",
                    amazon: "amazon", appletv: "com.apple.appletv", store: "com.webos.app.discovery"
                };
                try {
                    var generation = ++launchGeneration;
                    pendingLaunchToken = -1;
                    launchAccepted = false;
                    var callback = function(token) { personalHomeLoader.issued(generation, token); };
                    if (apps.hasOwnProperty(action)) {
                        var point = ysm.launchPointsModel.getLaunchPointByAppId(apps[action]);
                        if (!point) { item.completeAction(false, "Aplicativo indisponível."); return; }
                        if (appList.getAppInfoValue(point.id, "subType") === "hcap" && !hcapSurfaceView.isInputAppSurface(compositor.fullscreen)) {
                            item.completeAction(false, "Este aplicativo exige uma entrada de TV ativa.");
                            return;
                        }
                        pendingLaunchId = apps[action];
                        ysm.launchPointActivated(point, callback);
                    } else if (action === "inputs") {
                        uiScope.personalHomeInputsStarted=true;
                        finishLaunch(true);
                    } else if (action === "wifi") {
                        pendingLaunchId = "com.palm.app.settings";
                        ysm.appManagerService.checkLaunch(pendingLaunchId, JSON.stringify({target:"network", item:"Wireless"}), false, false, "globalActions", callback);
                    } else if (action === "settings") {
                        pendingLaunchId = "com.palm.app.settings";
                        ysm.appManagerService.checkLaunch(pendingLaunchId, undefined, undefined, undefined, undefined, callback);
                    } else { item.completeAction(false, "Ação indisponível."); return; }
                } catch (error) {
                    finishLaunch(false);
                }
            }

            onLoaded: {
                if (typeof item.completeAction !== "function" || typeof item.readyForActivation !== "boolean" || typeof item.launchPending !== "boolean")
                    useOriginal();
            }
            onStatusChanged: {
                if (status === Loader.Error) useOriginal();
            }
        }

        Binding {
            target: personalHomeLoader.item
            property: "homeShown"
            value: ysm.state === "visible" && personalHomeLoader.homeState
        }
        Binding {
            target: personalHomeLoader.item
            property: "powerActive"
            value: personalHomeLoader.powerActive
        }
        Binding {
            target: personalHomeLoader.item
            property: "inputAllowed"
            value: !!notificationView && !notificationView.modalAlertActive
                && uiScope.activeFocus && !globalActions.popupOpen
        }
        Binding {
            target: personalHomeLoader.item
            property: "ssid"
            value: systemSettings.personalHomeSsid
        }
        Connections {
            target: personalHomeLoader.item
            ignoreUnknownSignals:true
            onActionRequested: personalHomeLoader.handleAction(action)
            onInputsRequested:if(uiScope.personalHomeShown)uiScope.personalHomeInputsStarted=true
            onInputChosen:if(uiScope.personalHomeShown&&personalHomeInputs.item)personalHomeInputs.item.choose(key)
            onFatalError: personalHomeLoader.useOriginal()
            onLaunchPendingChanged: if (personalHomeLoader.item && !personalHomeLoader.item.launchPending) personalHomeLoader.forgetLaunch()
        }
        Connections {
            target: ysm.appManagerService
            onLaunched: personalHomeLoader.launchResult(identifier, token, true)
            onLaunchFailed: personalHomeLoader.launchResult(identifier, token, false)
        }
        Timer {
            interval: 5000
            running: personalHomeLoader.active && !uiScope.personalHomeShown
                && personalHomeLoader.status !== Loader.Error && personalHomeLoader.item !== null
                && !personalHomeLoader.item.readyForActivation
            onTriggered: personalHomeLoader.useOriginal()
        }
        Timer {
            id: personalHomeFocusTimer
            interval: 0
            onTriggered: uiScope.focusPersonalHome()
        }
        onPersonalHomeShownChanged: {
            if (personalHomeShown) {
                personalHomeLoader.forgetLaunch();
                personalHomeFocusTimer.restart();
            } else {
                if(personalHomeInputs.item)personalHomeInputs.item.cancelSelection();
                if(personalHomeLoader.launchAccepted)personalHomeLoader.finishLaunch(true);
            }
        }
        Connections {
            target: t1
            onRunningChanged: if (!t1.running) personalHomeFocusTimer.restart()
        }
        Connections {
            target: compositorWindow
            onActiveFocusItemChanged: {
                if (uiScope.personalHomeShown && personalHomeLoader.item
                        && !personalHomeLoader.item.activeFocus)
                    personalHomeFocusTimer.restart();
            }
        }
