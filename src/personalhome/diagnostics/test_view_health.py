import copy
import json
import math
from pathlib import Path
import subprocess
import unittest
from view_health import validate
from instrument_trial import instrument_ui, instrument

NONCE='a'*32

def sample():
    return dict(schema=2,nonce=NONCE,sequence=2,keyEvents=0,lastKey=0,focusIndex=0,
        rootSource='file:///tmp/YSM/YSM.qml',originalFallback=False,
        **dict.fromkeys(('moduleResolved','componentInstantiated','initialized','windowAttached',
                       'nativeContextAttached','ready','shown','visible','activeFocus'), True))

class HealthTests(unittest.TestCase):
    def test_child_ready_before_native_root_callback_is_not_accepted(self):
        root=Path(__file__).resolve().parents[1]
        files={'YSM/YSM.qml':b'import QtQuick 2.4\nItem {\n        property bool personalHomeEnabled: true\n}',
               'YSM/PersonalHome/PersonalHome.qml':(root/'qml/PersonalHome.qml').read_bytes()}
        instrument(files,'/tmp/lg-native-trial.TEST',NONCE)
        source=files['YSM/YSM.qml'].decode()
        body=source[source.index('                var item='):source.index('\n            }\n        }')]
        script=r'''
const vm=require('vm'),assert=require('assert');
const body=JSON.parse(process.argv[1]),window={};
const item={Window:{contentItem:window},diagnosticInitialized:true,readyForActivation:true,
 visible:false,activeFocus:false,focusIndex:0,diagnosticKeyCount:0,diagnosticLastKey:0};
let received;
const scope={root:{ysm:null},ysm:{Window:{contentItem:window}},compositor:{},
 compositorWindow:{contentItem:window},personalHomeLoader:{item},
 uiScope:{personalHomeShown:false,personalHomeEnabled:true,trialSequence:0,trialHealth:{write(value){received=JSON.parse(value);}}},
 Qt:{resolvedUrl(){return {toString(){return 'file:///tmp/YSM/YSM.qml';}};}}};
vm.runInNewContext(body,scope);
assert.strictEqual(received.ready,false,'child became ready before the native root callback');
scope.root.ysm=scope.ysm;
vm.runInNewContext(body,scope);
assert.strictEqual(received.ready,true);
assert.strictEqual(received.nativeContextAttached,true);
console.log('Native root readiness race reproduced and gated');
'''
        result=subprocess.run(['node','-e',script,json.dumps(body)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_loading_snapshot_is_never_accepted_as_ready_home(self):
        value=dict(sample(),focusIndex=-1,componentInstantiated=False,initialized=False,
                   windowAttached=False,nativeContextAttached=False,ready=False,shown=False,
                   visible=False,activeFocus=False)
        with self.assertRaises(ValueError):validate(value,NONCE)

    def test_genuine_navigation_and_freshness(self):
        before=sample();validate(before,NONCE)
        after=dict(before,sequence=3,keyEvents=1,lastKey=16777236,focusIndex=1)
        self.assertIs(validate(after,NONCE,before,key=16777236,expected_index=1),after)
        for field,bad in [('sequence',2),('keyEvents',0),('lastKey',16777234),('focusIndex',0)]:
            with self.assertRaises(ValueError):validate(dict(after,**{field:bad}),NONCE,before,key=16777236,expected_index=1)

    def test_wrong_identity_context_or_counters_fail(self):
        for key,bad in [('schema',1),('nonce','b'*32),('sequence',math.inf),('sequence',float('nan')),
                        ('sequence',True),('sequence',2.5),('keyEvents',-1),('focusIndex',11),
                        ('rootSource','qrc:/YSM/YSM.qml'),('originalFallback',True)]:
            with self.assertRaises(ValueError):validate(dict(sample(),**{key:bad}),NONCE)
        for key in ('moduleResolved','componentInstantiated','initialized','windowAttached','nativeContextAttached','ready','shown','visible','activeFocus'):
            with self.assertRaises(ValueError):validate(dict(sample(),**{key:False}),NONCE)

    def test_actual_trial_copy_is_instrumented_without_ready_override(self):
        root=Path(__file__).resolve().parents[1]
        text=(root/'qml/PersonalHome.qml').read_text()
        actual=instrument_ui(text)
        self.assertIn('diagnosticKeyCount++;diagnosticLastKey=event.key;',actual)
        self.assertIn('readonly property bool readyForActivation: !initialFailure',actual)
        files={'YSM/YSM.qml':b'import QtQuick 2.4\nItem {\n        property bool personalHomeEnabled: true\n}',
               'YSM/PersonalHome/PersonalHome.qml':text.encode()}
        instrument(files,'/tmp/lg-native-trial.TEST',NONCE)
        self.assertIn(b'item.Window.contentItem===ysm.Window.contentItem',files['YSM/YSM.qml'])
        self.assertEqual(json.loads(files['YSM/trial-config.json'])['nonce'],NONCE)
        with self.assertRaises(ValueError):instrument(files,'/tmp/../bad',NONCE)

    def test_attachment_api_exists_in_target_qt56_metadata(self):
        directory=Path(__file__).resolve().parent
        metadata=(directory/'evidence/qt56-window-attached-metadata.txt').read_text()
        self.assertIn('name: "contentItem"',metadata)
        self.assertNotIn('name: "window"',metadata)
        for name in ['instrument_trial.py','adapter_probe.qml.in','build_diagnostic_candidate.py']:
            code=(directory/name).read_text()
            self.assertNotIn('Window.window',code)
            self.assertIn('Window.contentItem',code)
        code=(directory/'instrument_trial.py').read_text()
        self.assertIn('item.Window.contentItem===compositorWindow.contentItem',code)

    def test_node_guard_rejects_malformed_actual_health(self):
        code=(Path(__file__).resolve().parents[1]/'recovery/device-guard.js').read_text()
        start=code.index('function validViewHealth(')
        end=code.index('\n}\n',start)+2
        run='var m={nonce:'+json.dumps(NONCE)+'};'+code[start:end]+'''
var good={schema:2,nonce:m.nonce,sequence:1,keyEvents:0,lastKey:0,focusIndex:0,rootSource:'file:///tmp/YSM/YSM.qml',originalFallback:false,moduleResolved:true,componentInstantiated:true,initialized:true,windowAttached:true,nativeContextAttached:true,ready:true,shown:true,visible:true,activeFocus:true};
if(!validViewHealth(good))throw Error('Valid health rejected');
[NaN,Infinity,-1,1.5,true].forEach(function(v){var h=Object.assign({},good,{sequence:v});if(validViewHealth(h))throw Error('Bad sequence accepted');});
if(validViewHealth(Object.assign({},good,{nonce:'wrong'})))throw Error('Wrong nonce accepted');
console.log('Node guard health boundary passed');
'''
        result=subprocess.run(['node','-e',run],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('boundary passed',result.stdout)

if __name__=='__main__':unittest.main()
