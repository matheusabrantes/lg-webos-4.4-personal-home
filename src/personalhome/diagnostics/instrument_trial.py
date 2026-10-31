"""Add genuine lifecycle/input telemetry to trial copies only; no readiness overrides."""
import json
import re


def instrument_ui(text):
    anchors = ['    property bool homeShown: true', '    Keys.onPressed: {', 'Component.onCompleted: {updateClock();']
    if any(text.count(anchor) != 1 for anchor in anchors):
        raise ValueError('Actual PersonalHome diagnostic anchors changed')
    text = text.replace(anchors[0], '    property int diagnosticKeyCount: 0\n    property int diagnosticLastKey: 0\n    property bool diagnosticInitialized: false\n' + anchors[0])
    text = text.replace(anchors[1], anchors[1] + '\n        diagnosticKeyCount++;diagnosticLastKey=event.key;')
    return text.replace(anchors[2], 'Component.onCompleted: {diagnosticInitialized=true;updateClock();')


def instrument(files, directory, nonce, profile=False):
    if not re.fullmatch(r'/tmp/lg-native-trial\.[A-Za-z0-9]+', directory) or not re.fullmatch(r'[a-f0-9]{32}', nonce):
        raise ValueError('Invalid private trial identity')
    text = files['YSM/YSM.qml'].decode()
    text = text.replace('import QtQuick 2.4', 'import QtQuick 2.4\nimport QtQuick.Window 2.2\nimport TextFile 1.0', 1)
    probe = '''
        property int trialSequence: 0
        property var trialHealth: TextFile { name: %s }
        Timer {
            interval:250;repeat:true;running:true
            onTriggered: {
                var item=personalHomeLoader.item;
                var nativeRootReady=typeof root!=="undefined" && root.ysm===ysm;
                var attached=!!item && !!item.Window.contentItem;
                var nativeContext=typeof compositor!=="undefined" && compositor!==null
                    && typeof compositorWindow!=="undefined" && compositorWindow!==null
                    && !!ysm.Window.contentItem && attached && item.Window.contentItem===ysm.Window.contentItem
                    && item.Window.contentItem===compositorWindow.contentItem;
                uiScope.trialHealth.write(JSON.stringify({schema:2,nonce:%s,sequence:++uiScope.trialSequence,
                    moduleResolved:true,rootSource:Qt.resolvedUrl("YSM.qml").toString(),
                    componentInstantiated:item!==null,initialized:!!item && item.diagnosticInitialized,
                    windowAttached:attached,nativeContextAttached:nativeContext,
                    ready:nativeRootReady && !!item && item.readyForActivation,shown:uiScope.personalHomeShown,
                    visible:!!item && item.visible,activeFocus:!!item && item.activeFocus,
                    focusIndex:item ? item.focusIndex : -1,keyEvents:item ? item.diagnosticKeyCount : 0,
                    lastKey:item ? item.diagnosticLastKey : 0,originalFallback:!uiScope.personalHomeEnabled,
                    photoIndex:item ? item.photoIndex : -1,photoCount:item ? item.photoCount : 0,photoLoading:!!item && item.photoLoading,
                    photoFailures:item ? item.photoFailures : 0,photoTimerActive:!!item && item.photoTimerActive,
                    originalRibbonVisible:superRibbon.visible,originalRibbonEnabled:superRibbon.enabled}));
            }
        }
''' % (json.dumps('file://' + directory + '/health.json'), json.dumps(nonce))
    if profile:
        observer = """
        property var profileCounts: ({swaps:0, animationSteps:0})
        Connections {
            target: typeof compositorWindow !== "undefined" ? compositorWindow : null
            onFrameSwapped: uiScope.profileCounts.swaps++
            onAfterAnimating: uiScope.profileCounts.animationSteps++
        }
"""
        probe = observer + probe.replace('moduleResolved:true,',
            'profile:uiScope.profileCounts,moduleResolved:true,')
    anchor = '        property bool personalHomeEnabled: true'
    if text.count(anchor) != 1: raise ValueError('External root diagnostic anchor changed')
    files['YSM/YSM.qml'] = text.replace(anchor, probe+anchor).encode()
    name = 'YSM/PersonalHome/PersonalHome.qml'
    files[name] = instrument_ui(files[name].decode()).encode()
    files['YSM/trial-config.json'] = (json.dumps({'nonce':nonce,'directory':directory})+'\n').encode()
    files['YSM/.trial-owner'] = nonce.encode()
    return files
