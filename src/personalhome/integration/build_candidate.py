#!/usr/bin/env python3
"""Build a local, hash-guarded native Home candidate. No target execution or SSH."""
import argparse
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE = ROOT.parent / 'lg-native-home-feasibility-2026-10-22'
SOURCE_SHA = '5d2c9872f8b2c918c605cd05a7c49844645a8b683d8c1f8ee55f7bb1be6738e9'
MANIFEST_SHA = 'd03e144f02fecbf083c9e9d15d7a35ee8b64a96ccbc008faf011ce4709250b69'
IMPORT_DATA_OFFSET = 0xF884
IMPORT_LENGTH_OFFSET = 0xF878


def digest(data):
    return hashlib.sha256(data).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Native insertion anchor changed or is ambiguous')
    return text.replace(old, new, 1)


def preserve_startup_home(text):
    old = 'id: launcherOnBootTimer\n        interval: ysm.launcherOnBootTimeout\n        onTriggered: ysm.gotoState("hidden")'
    new = old.replace('onTriggered: ', 'onTriggered: if (!uiScope.personalHomeShown) ')
    if new in text:
        return text
    return replace_once(text, old, new)


def integrate_power_wake(resources):
    text = resources['YSM/YSM.qml'].decode()
    if 'function personalHomeStartupPending()' not in text:
        anchor = '    objectName: "ysm"'
        text = replace_once(text, anchor, anchor + '\n' + (ROOT / 'integration/startup_hold.qml.inc').read_text())
        text = replace_once(text, '            if (ysm.allowEmptyFullScreen)\n                ret.reason = "forceMinimize";',
                            '            if (ysm.allowEmptyFullScreen || ysm.personalHomeStartupEmptyHold(ret.foregroundAppInfo))\n                ret.reason = "forceMinimize";')
    else:
        marker = '    property var personalHomeStartupIntentFile: TextFile'
        if text.count(marker) != 1:
            raise ValueError('Native startup-hold insertion anchor changed or is ambiguous')
        start = text.index(marker)
        end = text.index('    property string appId:', start)
        text = text[:start] + (ROOT / 'integration/startup_hold.qml.inc').read_text() + '\n' + text[end:]
    alias = '    property alias personalHomePowerWake: personalHomePowerWakeController'
    if text.count(alias) > 1:
        raise ValueError('Native Power-wake alias is ambiguous')
    if alias not in text:
        text = replace_once(text, '    objectName: "ysm"', '    objectName: "ysm"\n' + alias)
    for event, method in [('onSystemSuspended', 'nativePowerOff'), ('onSystemPowerOff', 'nativePowerOff'), ('onSystemPowerOn', 'nativePowerOn')]:
        old = '        ' + event + ': {'
        new = old + '\n            ysm.personalHomePowerWake.' + method + '();'
        if new not in text:
            text = replace_once(text, old, new)
    if 'id: personalHomePowerWakeController' not in text:
        anchor = '        property bool personalHomeEnabled: true'
        text = replace_once(text, anchor, (ROOT / 'integration/power_wake.qml.inc').read_text() + '\n' + anchor)
        text = replace_once(text, '        function showHome(msg) {\n            ysm.goHome();', '        function showHome(msg) {\n            if (ysm.personalHomePowerWake.nativeShowHome()) return;\n            ysm.goHome();')
        text = replace_once(text, '            function handleAction(action) {', '            function handleAction(action) {\n                ysm.personalHomePowerWake.cancel();')
        text = replace_once(text, '            onLaunchRequested: {', '            onLaunchRequested: {\n                ysm.personalHomePowerWake.cancel();')
    marker = '        QtObject {\n            id: personalHomePowerWakeController'
    if text.count(marker) != 1:
        raise ValueError('Native Power-wake insertion anchor changed or is ambiguous')
    start = text.index(marker)
    end = text.index('        property bool personalHomeEnabled: true', start)
    text = text[:start] + (ROOT / 'integration/power_wake.qml.inc').read_text() + '\n' + text[end:]
    old = '            if (superRibbon.state === "home") {\n                gotoState("hidden");'
    new = old.replace('                gotoState', '                if (uiScope.personalHomeShown && !ysm.personalHomePowerWake.resumePausedInput()) return;\n                gotoState')
    if new not in text:
        text = replace_once(text, old, new)
    old = '                if (action === "back") {\n                    forgetLaunch();'
    new = old.replace('                    forgetLaunch();', '                    if (!ysm.personalHomePowerWake.resumePausedInput()) { item.completeAction(false, "Não foi possível voltar à TV."); return; }\n                    forgetLaunch();')
    if new not in text:
        text = replace_once(text, old, new)
    text = text.replace('function handleAction(action) {\n                ysm.personalHomePowerWake.cancel();',
                        'function handleAction(action) {\n                ysm.personalHomePowerWake.cancel(action === "inputs");')
    old = '            if (ysm.state == "visible") {\n                ysm.gotoState("hidden", function() {\n                    if(superRibbon.state !== "home")'
    new = old.replace('ysm.state == "visible"', 'ysm.state == "visible" && !uiScope.personalHomeShown')
    if new not in text:
        text = replace_once(text, old, new)
    resources['YSM/YSM.qml'] = text.encode()
    text = resources['YSM/compositor.js'].decode()
    anchor = '        if (ysm.state === "visible"\n            && !ysm.foregroundSufaceWasHidden'
    legacy = anchor + '\n            && !ysm.personalHomePowerWake.keepHomeForSurface(compositor.fullscreen)'
    replacement = '        var personalHomeWakeKeep = ysm.personalHomePowerWake.keepHomeForSurface(compositor.fullscreen);\n' + anchor + '\n            && !personalHomeWakeKeep'
    if replacement not in text:
        if legacy in text:
            text = replace_once(text, legacy, anchor)
        text = replace_once(text, anchor, replacement)
    resources['YSM/compositor.js'] = text.encode()
    text = resources['YSM/StarfishKeyFilter.qml'].decode()
    anchor = '    function preProcess(key, pressed, autoRepeat) {\n        speakKeyEvents(key, pressed);'
    legacy = anchor + '\n        if (pressed && key !== Qt.Key_PowerOff) ysm.personalHomePowerWake.cancel();'
    previous = anchor + '\n        if (pressed && key !== Qt.Key_PowerOff) ysm.personalHomePowerWake.cancel(key === Qt.Key_Left || key === Qt.Key_Right || key === Qt.Key_Up || key === Qt.Key_Down || key === Qt.Key_Return || key === Qt.Key_Enter);'
    replacement = previous.replace('key !== Qt.Key_PowerOff', 'key !== Qt.Key_PowerOff && key !== 0x01200201 && key !== 0x01200202')
    if replacement not in text:
        if previous in text:
            text = replace_once(text, previous, anchor)
        elif legacy in text:
            text = replace_once(text, legacy, anchor)
        text = replace_once(text, anchor, replacement)
    resources['YSM/StarfishKeyFilter.qml'] = text.encode()
    return resources


def patch_elf(data):
    if digest(data) != SOURCE_SHA or data[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('Firmware executable identity mismatch')
    original, replacement = 'qrc:/'.encode('utf-16-le'), '/tmp/'.encode('utf-16-le')
    if data[IMPORT_LENGTH_OFFSET:IMPORT_LENGTH_OFFSET + 4] != (5).to_bytes(4, 'little'):
        raise ValueError('QString literal length mismatch')
    if data[IMPORT_DATA_OFFSET:IMPORT_DATA_OFFSET + 10] != original:
        raise ValueError('QString import-path bytes mismatch')
    return data[:IMPORT_DATA_OFFSET] + replacement + data[IMPORT_DATA_OFFSET + 10:]


def native_files(evidence):
    manifest_bytes = (evidence / 'resources-manifest.json').read_bytes()
    if digest(manifest_bytes) != MANIFEST_SHA:
        raise ValueError('Captured resource manifest identity mismatch')
    manifest = json.loads(manifest_bytes)
    if manifest['sourceSha256'] != SOURCE_SHA:
        raise ValueError('Resource manifest belongs to another firmware')
    result = {}
    for entry in manifest['resources']:
        if entry['group'] not in ('base', 'ysm', 'content'):
            raise ValueError('Unknown resource group')
        path = pathlib.PurePosixPath(entry['resourcePath'])
        if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'YSM':
            raise ValueError('Unsafe resource path')
        source = evidence / 'resources' / entry['group'] / str(path)
        if source.is_symlink() or not source.is_file():
            raise ValueError('Resource is missing or is not a regular file')
        data = source.read_bytes()
        if len(data) != entry['decodedBytes'] or digest(data) != entry['sha256']:
            raise ValueError('Resource bytes differ from the captured manifest: ' + str(path))
        if str(path) in result:
            raise ValueError('Resource namespace collision: ' + str(path))
        result[str(path)] = data
    if len(result) != 217:
        raise ValueError('Resource inventory is incomplete')
    return result


def integrate_input_back(text):
    text=replace_once(text,'        onBackPressed: {}', '''        onBackPressed: {
            uiScope.personalHomeInputBackPending = uiScope.personalHomeShown && personalHomeLoader.item !== null && personalHomeLoader.item.inputMenuOpen;
        }''')
    return replace_once(text,'        onBackReleased: {','''        onBackReleased: {
            if (uiScope.personalHomeInputBackPending || (uiScope.personalHomeShown && personalHomeLoader.item !== null && personalHomeLoader.item.inputMenuOpen)) {
                uiScope.personalHomeInputBackPending = false;
                if (uiScope.personalHomeShown && personalHomeLoader.item !== null && personalHomeLoader.item.inputMenuOpen)
                    personalHomeLoader.item.closeInputs();
                return;
            }''')


def integrate(resources):
    original = resources['YSM/YSM.qml'].decode()
    insertion = (ROOT / 'integration/native_home_loader.qml.inc').read_text()
    target = '    FocusableView {\n        id: uiScope\n        objectName: "uiScope"\n'
    changed = replace_once(original, target, target + '\n' + insertion)
    changed = integrate_input_back(changed)
    changed = preserve_startup_home(changed)
    old = '            visible: anchors.bottomMargin > 80 - hideMargin'
    changed = replace_once(changed, old, old + ' && !uiScope.personalHomeOwnsRibbon\n            enabled: !uiScope.personalHomeOwnsRibbon')
    changed = replace_once(changed,
        '                enabled: true\n                focus: true\n                visible: true',
        '                enabled: !uiScope.personalHomeOwnsRibbon\n                focus: !uiScope.personalHomeOwnsRibbon\n                visible: !uiScope.personalHomeOwnsRibbon')
    changed = replace_once(changed,
        'function checkLaunch(appId, params, checkUpdateOnLaunch, autoInstallation, reason) {',
        'function checkLaunch(appId, params, checkUpdateOnLaunch, autoInstallation, reason, issued) {')
    changed = replace_once(changed,
        '                existingSurface.requestFullscreen();\n            } else {\n                console.log("initiating launch " + appId);',
        '                existingSurface.requestFullscreen();\n                if (typeof issued === "function") issued(null);\n            } else {\n                console.log("initiating launch " + appId);')
    changed = replace_once(changed,
        '                applicationManagerService.launch(appId, params,',
        '                var personalHomeToken = applicationManagerService.launch(appId, params,')
    changed = replace_once(changed,
        '                                                        reason === undefined ? "" : reason);',
        '                                                        reason === undefined ? "" : reason);\n                if (typeof issued === "function") issued(personalHomeToken);')
    changed = replace_once(changed,
        'function launchUnsurfacedItem(appId, launchParams, launchReason) {',
        'function launchUnsurfacedItem(appId, launchParams, launchReason, issued) {')
    changed = replace_once(changed,
        '            applicationManagerService.launch(appId, JSON.stringify(params), null, null, launchReason === undefined ? "" : launchReason);',
        '            var personalHomeToken = applicationManagerService.launch(appId, JSON.stringify(params), null, null, launchReason === undefined ? "" : launchReason);\n            if (typeof issued === "function") issued(personalHomeToken);')
    changed = replace_once(changed,
        'function launchPointActivated(item) {', 'function launchPointActivated(item, issued) {')
    forwarded = 'ysm.launchUnsurfacedItem(appId, item.params, "launcher");'
    if changed.count(forwarded) != 2:
        raise ValueError('Native launch forwarding anchors changed')
    changed = changed.replace(forwarded, 'ysm.launchUnsurfacedItem(appId, item.params, "launcher", issued);')
    changed = replace_once(changed,
        '                    existingSurface.requestFullscreen();\n                }\n            });',
        '                    existingSurface.requestFullscreen();\n                    if (typeof issued === "function") issued(null);\n                } else if (typeof issued === "function") issued(-1);\n            });')
    resources['YSM/YSM.qml'] = changed.encode()
    original = resources['YSM/SystemSettings.qml'].decode()
    target = '    property bool networkConnected: networkService.networkConnected'
    changed = replace_once(original, target, target + '\n    property string personalHomeSsid: ""')
    target = '''        onConnectedChanged: {
            if (connected) {
                subscribeGetStatus();
            }
        }'''
    changed = replace_once(changed, target, target.replace('            }\n', '            } else root.personalHomeSsid = "";\n'))
    target = '            if (method === getStatusMethod)\n                var ret = JSON.parse(payload);\n                if (ret.returnValue) {'
    changed = replace_once(changed, target, target + '\n                    root.personalHomeSsid = ret.wifi && ret.wifi.state === "connected" && typeof ret.wifi.ssid === "string" ? ret.wifi.ssid : "";')
    resources['YSM/SystemSettings.qml'] = changed.encode()
    return integrate_power_wake(resources)


def build(destination, qml_dir=None, evidence=EVIDENCE):
    destination = pathlib.Path(destination)
    qml_dir = pathlib.Path(qml_dir or ROOT / 'qml')
    if destination.exists():
        raise ValueError('Destination already exists; refusing to overwrite it')
    original_binary = evidence / 'artifacts/usr_bin_surface-manager-starfish'
    data = original_binary.read_bytes()
    candidate = patch_elf(data)
    resources = integrate(native_files(evidence))
    additions = {}
    for source in qml_dir.rglob('*'):
        if source.is_symlink():
            raise ValueError('UI tree contains a symlink')
        if source.is_file():
            name = 'YSM/PersonalHome/' + source.relative_to(qml_dir).as_posix()
            if name in resources:
                raise ValueError('UI would overwrite another native resource: ' + name)
            additions[name] = source.read_bytes()
    if 'YSM/PersonalHome/PersonalHome.qml' not in additions:
        raise ValueError('PersonalHome.qml is missing')
    # All inputs are checked before any output is created.
    destination.mkdir(parents=True)
    for name, content in {**resources, **additions}.items():
        target = destination / 'module' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    binary = destination / 'surface-manager-starfish.candidate'
    binary.write_bytes(candidate)
    binary.chmod(0o600)
    changed = [i for i, pair in enumerate(zip(data, candidate)) if pair[0] != pair[1]]
    report = {
        'sourceSha256': SOURCE_SHA, 'candidateSha256': digest(candidate),
        'candidateBytes': len(candidate), 'changedByteOffsets': changed,
        'literalByteRange': [IMPORT_DATA_OFFSET, IMPORT_DATA_OFFSET + 10],
        'unchangedNativeResources': len(resources) - 4,
        'modifiedNativeResources': ['YSM/YSM.qml', 'YSM/SystemSettings.qml', 'YSM/compositor.js', 'YSM/StarfishKeyFilter.qml'],
        'addedFiles': {name: digest(value) for name, value in additions.items()},
        'moduleFiles': {name: digest(value) for name, value in {**resources, **additions}.items()},
        'requiredRuntimeModulePath': '/tmp/YSM',
        'tvExecuted': False, 'installed': False, 'runtimeQt56Validated': False,
        'warning': 'Offline candidate only. Native module redirection, API bindings and recovery have not been executed on this TV.'
    }
    (destination / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=pathlib.Path)
    parser.add_argument('--qml', type=pathlib.Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.destination, args.qml), indent=2))
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit('Candidate refused: ' + str(error))
