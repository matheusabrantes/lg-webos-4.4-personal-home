#!/usr/bin/env python3
"""Build a diagnostic native entry point locally; never contacts the TV."""
import argparse
import importlib.util
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_home_base_build', ROOT / 'integration/build_candidate.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

ORIGINAL_ENTRY = 'qrc:///YSM/main.qml'
DIAGNOSTIC_ENTRY = 'file:/tmp/YSM/m.qml'
ENTRY_OFFSET = 0xF928

MAIN_DIAGNOSTICS = '''
    property string trialNonce: ""
    property string trialDirectory: ""
    property var trialEvents: []
    property var trialConfig: TextFile { name: "file:///tmp/YSM/trial-config.json" }
    property var trialWriter: TextFile {
        name: root.trialDirectory ? "file://" + root.trialDirectory + "/diagnostics.json" : ""
    }

    function initializeTrialDiagnostics() {
        try {
            var config = JSON.parse(trialConfig.read());
            if (typeof config.nonce !== "string" || !/^[a-f0-9]{32}$/.test(config.nonce)
                || typeof config.directory !== "string"
                || !/^\\/tmp\\/lg-native-trial\\.[A-Za-z0-9]+$/.test(config.directory)) return;
            trialNonce = config.nonce;
            trialDirectory = config.directory;
        } catch (error) {
            console.warn("HOME_TRIAL_DIAGNOSTIC_CONFIG", String(error));
        }
    }

    function reportTrialStage(stage, details) {
        if (!trialNonce || !trialDirectory || trialEvents.length >= 32) return;
        trialEvents = trialEvents.concat([{stage:stage, at:Date.now(), details:details}]);
        try {
            trialWriter.write(JSON.stringify({schema:1, nonce:trialNonce, diagnosticOnly:true,
                events:trialEvents}));
        } catch (error) {
            console.warn("HOME_TRIAL_DIAGNOSTIC_WRITE", String(error));
        }
    }
'''


def patch_entrypoint(original):
    candidate = base.patch_elf(original)
    before = ORIGINAL_ENTRY.encode('ascii')
    after = DIAGNOSTIC_ENTRY.encode('ascii')
    if len(before) != len(after) or original.count(before + b'\0') != 1:
        raise ValueError('Native main URL literal is missing or ambiguous')
    position = original.index(before + b'\0')
    if position != ENTRY_OFFSET:
        raise ValueError('Native main URL ASCII offset differs')
    return candidate[:position] + after + candidate[position + len(before):], position


def instrument_main(text):
    text = base.replace_once(text, 'import QtQuick 2.4',
                             'import QtQuick 2.4\nimport QtQuick.Window 2.2\nimport TextFile 1.0')
    text = base.replace_once(text, '    id:root\n', '    id:root\n' + MAIN_DIAGNOSTICS)
    text = base.replace_once(text, '    Component.onCompleted: {', '''    Component.onCompleted: {
        initializeTrialDiagnostics();
        reportTrialStage("entry-initialized", {
            windowAttached:!!root.Window.contentItem,
            compositorPresent:typeof compositor !== "undefined" && compositor !== null,
            compositorWindowPresent:typeof compositorWindow !== "undefined" && compositorWindow !== null,
            expectedWindow:typeof compositorWindow !== "undefined" && !!root.Window.contentItem && root.Window.contentItem === compositorWindow.contentItem
        });''')
    text = base.replace_once(text, '            ysm = loadedObject;', '''            reportTrialStage("root-callback", {instantiated:loadedObject !== null});
            ysm = loadedObject;''')
    return base.replace_once(text, '                                loaderCallback);',
                             '                                loaderCallback, root.reportTrialStage);')


def instrument_creator(text):
    text = base.replace_once(text, 'function create(parentObject, parameters, callback) {',
                             'function create(parentObject, parameters, callback, diagnostic) {')
    text = base.replace_once(text, '    component = load("UiWrapper.qml") || load("YSM.qml");', '''    function report(stage, details) {
        if (typeof diagnostic === "function") diagnostic(stage, details);
    }
    component = load("UiWrapper.qml", report) || load("YSM.qml", report);''')
    text = base.replace_once(text, '    incubator = component.incubateObject(parentObject, parameters, Qt.Asynchronous);', '''    incubator = component.incubateObject(parentObject, parameters, Qt.Asynchronous);
    report("incubation-started", {status:incubator.status, instantiated:!!incubator.object,
        error:String(component.errorString()).slice(0,4096)});''')
    text = base.replace_once(text, '        incubator.onStatusChanged = function(status) {', '''        incubator.onStatusChanged = function(status) {
            report("incubation-status", {status:status, instantiated:!!incubator.object,
                error:String(component.errorString()).slice(0,4096)});''')
    text = base.replace_once(text, 'function load(target) {', 'function load(target, diagnostic) {')
    text = base.replace_once(text, '    var c = Qt.createComponent(target);', '''    var c = Qt.createComponent(target);
    if (typeof diagnostic === "function") diagnostic("component-status", {
        target:target, status:c.status, error:String(c.errorString()).slice(0,4096)
    });''')
    return text


def build(destination, qml_dir=None, evidence=base.EVIDENCE):
    destination = pathlib.Path(destination)
    original = (evidence / 'artifacts/usr_bin_surface-manager-starfish').read_bytes()
    candidate, position = patch_entrypoint(original)
    report = base.build(destination, qml_dir, evidence)
    module = destination / 'module'
    main = instrument_main((module / 'YSM/main.qml').read_text())
    creator = instrument_creator((module / 'YSM/compositorcreator.js').read_text())
    (module / 'YSM/m.qml').write_text(main)
    (module / 'YSM/compositorcreator.js').write_text(creator)
    (destination / 'surface-manager-starfish.candidate').write_bytes(candidate)
    report.update({
        'candidateSha256':base.digest(candidate),
        'changedByteOffsets':[i for i, pair in enumerate(zip(original,candidate)) if pair[0] != pair[1]],
        'entryLiteralByteRange':[position, position + len(ORIGINAL_ENTRY)],
        'entryLiteralEncoding':'NUL-terminated ASCII; converted to QString by the original helper',
        'diagnosticEntryUrl':DIAGNOSTIC_ENTRY,
        'diagnosticConfigPath':'/tmp/YSM/trial-config.json',
        'diagnosticOutputName':'diagnostics.json',
        'diagnosticEventsMaximum':32,
        'unchangedNativeResources':214,
        'modifiedNativeResources':['YSM/YSM.qml','YSM/SystemSettings.qml','YSM/compositorcreator.js'],
        'warning':'Diagnostic candidate only. Entry loading, diagnostics and physical operation are not validated by this build.'
    })
    report['addedFiles']['YSM/m.qml'] = base.digest(main.encode())
    report['moduleFiles'] = {name:base.digest((module / name).read_bytes())
                             for name in sorted(set(report['moduleFiles']) | {'YSM/m.qml'})}
    (destination / 'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=pathlib.Path)
    parser.add_argument('--qml',type=pathlib.Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.destination,args.qml),indent=2))
    except (OSError,ValueError,KeyError) as error:
        raise SystemExit('Diagnostic candidate refused: '+str(error))
