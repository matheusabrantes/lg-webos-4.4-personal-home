"""Replay generated native wake handlers without a TV or Qt process."""
import json
import pathlib
import subprocess
import unittest

from test_integration import builder


@unittest.skipUnless(builder.EVIDENCE.exists(), 'matching private native firmware capture is unavailable')
class PowerWakeTests(unittest.TestCase):
    def test_generated_native_wake_chain(self):
        resources = builder.integrate(builder.native_files(builder.EVIDENCE))
        source = resources['YSM/YSM.qml'].decode()
        self.assertTrue('id: personalHomePowerWakeController' in source, 'generated native Power-wake controller is missing')
        self.assertIn('onFrameSwapped: personalHomePowerWakeController.acknowledgeBridgeFrame()', source)
        result = subprocess.run(['node', str(pathlib.Path(__file__).with_name('test_power_wake.js'))],
                                input=json.dumps({key: value.decode() for key, value in resources.items()
                                                  if key in ['YSM/YSM.qml', 'YSM/SystemSettings.qml', 'YSM/compositor.js', 'YSM/StarfishKeyFilter.qml']}),
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS native Power wake chain', result.stdout)

    def test_captured_input_lifecycle_reaches_owned_media_pause(self):
        capture = builder.ROOT.parents[1] / '.local/startup-reliability-20261031/audio-native'
        names = ['main.qml', 'DisplayVideoModel.qml', 'AcbController.qml', 'AcbService.qml']
        if not all((capture / name).is_file() for name in names):
            self.skipTest('matching private inputcommon lifecycle capture is unavailable')
        resources = builder.integrate(builder.native_files(builder.EVIDENCE))
        data = {key: value.decode() for key, value in resources.items()
                if key in ['YSM/YSM.qml', 'YSM/SystemSettings.qml', 'YSM/compositor.js', 'YSM/StarfishKeyFilter.qml']}
        data.update({'native/' + name: (capture / name).read_text() for name in names})
        result = subprocess.run(['node', str(pathlib.Path(__file__).with_name('test_power_wake.js'))],
                                input=json.dumps(data), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS captured inputcommon media lifecycle', result.stdout)

    def test_generated_idle_callback_retains_only_personal_home(self):
        native = builder.native_files(builder.EVIDENCE)
        original = native['YSM/YSM.qml'].decode()
        resources = builder.integrate(native)
        data = {key: value.decode() for key, value in resources.items()
                if key in ['YSM/YSM.qml', 'YSM/SystemSettings.qml', 'YSM/compositor.js', 'YSM/StarfishKeyFilter.qml']}
        data['baseline/YSM.qml'] = original
        data['native/ScreenSaverView.qml'] = resources['YSM/ScreenSaver/ScreenSaverView.qml'].decode()
        result = subprocess.run(['node', str(pathlib.Path(__file__).with_name('test_power_wake.js'))],
                                input=json.dumps(data), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PASS native idle callback and watchdog policy', result.stdout)

    def test_changed_native_anchor_fails_closed(self):
        resources = builder.native_files(builder.EVIDENCE)
        resources['YSM/compositor.js'] = resources['YSM/compositor.js'].replace(b'!ysm.foregroundSufaceWasHidden', b'changedNativeCondition')
        with self.assertRaisesRegex(ValueError, 'anchor'):
            builder.integrate(resources)

    def test_repeated_wake_update_preserves_root_alias(self):
        alias = b'    property alias personalHomePowerWake: personalHomePowerWakeController\n'
        resources = builder.integrate(builder.native_files(builder.EVIDENCE))
        source = resources['YSM/YSM.qml'].replace(alias, b'')
        resources['YSM/YSM.qml'] = source.replace(b'    property string appId:', alias + b'    property string appId:', 1)
        cases = {'legacy alias after startup hold': resources}
        captured = builder.ROOT.parents[1] / '.local/startup-reliability-20261031/candidate-silent-transaction'
        if (captured / 'release.json').is_file():
            nonce = json.loads((captured / 'release.json').read_text())['nonce'].encode()
            cases['captured release'] = {name: (captured / 'module' / name).read_bytes().replace(nonce, b'__NONCE__')
                                         for name in ['YSM/YSM.qml', 'YSM/compositor.js', 'YSM/StarfishKeyFilter.qml']}
        for name, original in cases.items():
            with self.subTest(name=name):
                first = dict(builder.integrate_power_wake(dict(original)))
                second = builder.integrate_power_wake(dict(first))
                self.assertEqual(first, second)
                self.assertEqual(first['YSM/YSM.qml'].count(alias), 1)


if __name__ == '__main__':
    unittest.main()
