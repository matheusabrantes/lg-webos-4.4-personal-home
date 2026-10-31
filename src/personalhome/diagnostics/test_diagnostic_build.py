import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('diagnostic_build',ROOT / 'diagnostics/build_diagnostic_candidate.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class DiagnosticBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (builder.base.EVIDENCE / 'artifacts/usr_bin_surface-manager-starfish').read_bytes()
        cls.resources = builder.base.native_files(builder.base.EVIDENCE)

    def test_exact_entry_patch_and_firmware_identity(self):
        candidate,position = builder.patch_entrypoint(self.original)
        self.assertEqual(len(candidate),len(self.original))
        self.assertEqual(len(builder.ORIGINAL_ENTRY),19)
        self.assertEqual(len(builder.DIAGNOSTIC_ENTRY),19)
        self.assertEqual(position,0xF928)
        self.assertEqual(self.original[position:position+20],builder.ORIGINAL_ENTRY.encode('ascii')+b'\0')
        self.assertEqual(candidate[position:position+20],builder.DIAGNOSTIC_ENTRY.encode('ascii')+b'\0')
        expected = builder.base.patch_elf(self.original)
        self.assertEqual(candidate[:position],expected[:position])
        self.assertEqual(candidate[position+19:],expected[position+19:])
        with self.assertRaisesRegex(ValueError,'identity'):
            builder.patch_entrypoint(self.original[:-1])

    def test_main_structure_and_non_health_diagnostics(self):
        original = self.resources['YSM/main.qml'].decode()
        result = builder.instrument_main(original)
        self.assertEqual(result.count('FocusScope {'),original.count('FocusScope {'))
        self.assertIn('    id:root\n',result)
        self.assertIn('root.Window.contentItem === compositorWindow.contentItem',result)
        self.assertIn('trialEvents.length >= 32',result)
        self.assertIn('diagnosticOnly:true',result)
        self.assertIn('JSON.parse(trialConfig.read())',result)
        self.assertIn('/^[a-f0-9]{32}$/',result)
        self.assertIn('/^\\/tmp\\/lg-native-trial\\.[A-Za-z0-9]+$/',result)
        self.assertNotIn('health.json',result)
        self.assertNotIn('Timer {',builder.MAIN_DIAGNOSTICS)
        self.assertEqual(result.count('Component.onCompleted:'),original.count('Component.onCompleted:'))
        for unchanged in ('FullscreenView {','WindowModel {','surfaceSource: compositor.surfaceModel',
                          'fullscreenView.model = root.ysm.fullscreenWindowModel;','proxyModel.destroy();'):
            self.assertIn(unchanged,result)

    def test_creator_preserves_fallback_and_async_lifecycle(self):
        original = self.resources['YSM/compositorcreator.js'].decode()
        result = builder.instrument_creator(original)
        self.assertIn('load("UiWrapper.qml", report) || load("YSM.qml", report)',result)
        self.assertIn('component.incubateObject(parentObject, parameters, Qt.Asynchronous)',result)
        self.assertIn('status == Component.Ready',result)
        self.assertIn('c.errorString()',result)
        self.assertIn('incubation-status',result)
        self.assertEqual(result.count('callback(incubator.object)'),original.count('callback(incubator.object)'))
        self.assertNotIn('forceCompletion',result)

    def test_creator_reports_real_status_and_keeps_optional_callback(self):
        creator = builder.instrument_creator(self.resources['YSM/compositorcreator.js'].decode())
        script = r'''
const vm=require('vm'),assert=require('assert'),fs=require('fs');
const code=fs.readFileSync(0,'utf8');
for (const asynchronous of [false,true]) {
 const attempts=[],events=[],created={marker:'native-object'};
 const incubator={status:asynchronous?2:1,object:asynchronous?null:created};
 let received=null;
 const context={console:{log(){},warn(){}},Component:{Ready:1,Error:3},
   Qt:{Asynchronous:0,createComponent(target){
     attempts.push(target);
     if(target==='UiWrapper.qml')return {status:3,errorString(){return 'deliberate compile failure';}};
     return {status:1,errorString(){return '';},incubateObject(parent,parameters,mode){
       assert.strictEqual(parent,'parent');assert.deepStrictEqual(parameters,{original:true});
       assert.strictEqual(mode,0);return incubator;
     }};
   }}};
 vm.runInNewContext(code,context);
 context.create('parent',{original:true},object=>{received=object;},
   (stage,details)=>events.push({stage,details}));
 assert.deepStrictEqual(attempts,['UiWrapper.qml','YSM.qml']);
 assert.strictEqual(events[0].details.error,'deliberate compile failure');
 assert.strictEqual(events[1].details.status,1);
 assert.strictEqual(events[2].details.instantiated,!asynchronous);
 if(asynchronous){
   assert.strictEqual(received,null);
   incubator.object=created;incubator.status=1;incubator.onStatusChanged(1);
   assert.strictEqual(events[3].stage,'incubation-status');
   assert.strictEqual(events[3].details.instantiated,true);
 }
 assert.strictEqual(received,created);
 context.create('parent',{original:true},()=>{});
}
console.log('Creator fallback, immediate/async callbacks, and optional diagnostics passed');
'''
        result = subprocess.run(['node','-e',script],input=creator,text=True,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_deterministic_build_manifest_and_preserved_native_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            qml = root / 'qml';qml.mkdir()
            (qml/'PersonalHome.qml').write_text('import QtQuick 2.4\nFocusScope {}\n')
            reports = [builder.build(root/('build'+str(i)),qml) for i in range(2)]
            self.assertEqual(reports[0],reports[1])
            for index,report in enumerate(reports):
                target = root / ('build'+str(index))
                saved = json.loads((target/'manifest.json').read_text())
                self.assertEqual(saved,report)
                self.assertEqual(report['candidateSha256'],builder.base.digest((target/'surface-manager-starfish.candidate').read_bytes()))
                self.assertFalse(report['tvExecuted'])
                self.assertFalse(report['installed'])
                self.assertFalse(report['runtimeQt56Validated'])
                self.assertEqual((target/'module/YSM/main.qml').read_bytes(),self.resources['YSM/main.qml'])
                changed = [name for name,content in self.resources.items() if (target/'module'/name).read_bytes()!=content]
                self.assertEqual(sorted(changed),sorted(report['modifiedNativeResources']))
                for name,digest in report['moduleFiles'].items():
                    self.assertEqual(builder.base.digest((target/'module'/name).read_bytes()),digest)
            with self.assertRaisesRegex(ValueError,'Destination already exists'):
                builder.build(root/'build0',qml)


if __name__ == '__main__':
    unittest.main()
