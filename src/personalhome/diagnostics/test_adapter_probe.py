import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')
from generate_adapter_probe import ROOT, generate

NONCE = 'a' * 32
HEALTH = '/tmp/lg-adapter-probe.TEST/health.json'


class GeneratorTests(unittest.TestCase):
    def test_actual_adapter_and_ui_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'probe'
            result = generate(target, HEALTH, NONCE)
            source = (target / 'AdapterProbe.qml').read_text()
            self.assertIn((ROOT / 'integration/native_home_loader.qml.inc').read_text(), source)
            self.assertNotIn('readyForActivation: true', source)
            self.assertIn('nativeContextAttached:false', source)
            self.assertIn('physicalRenderingProven:false', source)
            self.assertEqual(result['maximumDurationMs'], 10000)
            actual = (target / 'PersonalHome/PersonalHome.qml').read_text()
            self.assertIn('diagnosticKeyCount++;diagnosticLastKey=event.key;', actual)
            self.assertIn('readyForActivation: !initialFailure', actual)
            self.assertTrue((target / 'PersonalHome/assets/google-sans-400.ttf').is_file())
            with self.assertRaises(ValueError):
                generate(target, HEALTH, NONCE)

    def test_rejects_unsafe_output_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            for health, nonce in [('/tmp/../health.json', NONCE), ('/var/health.json', NONCE),
                                  (HEALTH, 'not-a-nonce')]:
                target = Path(directory) / 'probe'
                with self.assertRaises(ValueError):
                    generate(target, health, nonce)
                self.assertFalse(target.exists())


try:
    from PyQt5.QtCore import QObject, QUrl, pyqtProperty, pyqtSlot, Qt
    from PyQt5.QtGui import QGuiApplication
    from PyQt5.QtQml import qmlRegisterType
    from PyQt5.QtQuick import QQuickView
    from PyQt5.QtTest import QTest
    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, 'Requires the existing work/lg-native-home-env Python')
class QtHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])

        class HostTestTextFile(QObject):
            """Host-only writer; does not validate the TV's native TextFile plugin."""
            def __init__(self, parent=None):
                super().__init__(parent)
                self.path = ''

            @pyqtProperty(str)
            def name(self):
                return self.path

            @name.setter
            def name(self, value):
                self.path = value

            @pyqtSlot(str)
            def write(self, value):
                Path(QUrl(self.path).toLocalFile()).write_text(value)

        cls.writer = HostTestTextFile
        qmlRegisterType(HostTestTextFile, 'TextFile', 1, 0, 'TextFile')

    def test_exact_trial_producer_in_nested_ui_scope(self):
        self.check_exact_trial_producer(False)

    def test_profile_producer_in_nested_ui_scope(self):
        self.check_exact_trial_producer(True)

    def check_exact_trial_producer(self, profile):
        from instrument_trial import instrument
        with tempfile.TemporaryDirectory(prefix='lg-health-scope.', dir='/tmp') as directory:
            target=Path(directory)/'probe'
            health=Path(directory)/'health.json'
            generate(target,str(health),NONCE)
            files={'YSM/YSM.qml':b'import QtQuick 2.4\nItem {\n        property bool personalHomeEnabled: true\n}',
                   'YSM/PersonalHome/PersonalHome.qml':(ROOT/'qml/PersonalHome.qml').read_bytes()}
            instrument(files,'/tmp/lg-native-trial.HOSTTEST',NONCE,profile=profile)
            source=files['YSM/YSM.qml'].decode()
            start=source.index('        property var profileCounts:' if profile else '        property int trialSequence:')
            end=source.index('        property bool personalHomeEnabled: true',start)
            snippet=source[start:end].replace('file:///tmp/lg-native-trial.HOSTTEST/health.json',health.as_uri())
            path=target/'AdapterProbe.qml'
            source=path.read_text().replace(health.as_uri(),(Path(directory)/'harness.json').as_uri())
            path.write_text(source.replace('        id:uiScope\n','        id:uiScope\n'+snippet,1))
            view=QQuickView()
            try:
                view.rootContext().setContextProperty('compositorWindow',view)
                view.setSource(QUrl.fromLocalFile(str(path)))
                self.assertFalse(view.errors(),[error.toString() for error in view.errors()])
                view.show()
                for _ in range(30):
                    QTest.qWait(50)
                    if health.exists():break
                self.assertTrue(health.exists(),'Exact nested trial producer did not deliver health')
                first=json.loads(health.read_text())
                self.assertEqual(first['schema'],2)
                self.assertEqual(first['nonce'],NONCE)
                self.assertTrue(first['initialized'])
                if profile:
                    self.assertIn('animationSteps',first['profile'])
                    view.frameSwapped.emit()
                for _ in range(10):
                    QTest.qWait(50)
                    second=json.loads(health.read_text())
                    if second['sequence']>first['sequence']:break
                self.assertGreater(second['sequence'],first['sequence'])
                self.assertFalse(second['nativeContextAttached'])
                if profile:
                    self.assertGreater(second['profile']['swaps'],first['profile']['swaps'])
            finally:
                view.close();view.deleteLater();self.app.processEvents()

    def test_real_assets_key_events_and_health_schema(self):
        with tempfile.TemporaryDirectory(prefix='lg-adapter-probe.', dir='/tmp') as directory:
            target = Path(directory) / 'probe'
            health = Path(directory) / 'health.json'
            generate(target, str(health), NONCE)
            view = QQuickView()
            try:
                view.setSource(QUrl.fromLocalFile(str(target / 'AdapterProbe.qml')))
                self.assertFalse(view.errors(), [error.toString() for error in view.errors()])
                view.show()
                for _ in range(100):
                    QTest.qWait(50)
                    if health.exists() and json.loads(health.read_text())['ready']:
                        break
                before = json.loads(health.read_text())
                self.assertTrue(before['ready'])
                self.assertTrue(before['moduleResolved'])
                self.assertTrue(before['componentInstantiated'])
                self.assertTrue(before['initialized'])
                self.assertTrue(before['windowAttached'])
                self.assertFalse(before['nativeContextAttached'])
                self.assertFalse(before['physicalRenderingProven'])
                self.assertEqual(before['compositorContext'], 'simulated')
                self.assertTrue(before['activeFocus'])
                QTest.keyClick(view, Qt.Key_Right)
                for _ in range(20):
                    QTest.qWait(50)
                    after = json.loads(health.read_text())
                    if after['sequence'] > before['sequence']:
                        break
                self.assertGreater(after['sequence'], before['sequence'])
                self.assertGreater(after['keyEvents'], before['keyEvents'])
                self.assertEqual(after['lastKey'], Qt.Key_Right)
                self.assertEqual(after['focusIndex'], before['focusIndex'] + 1)
                self.assertEqual(after['nonce'], NONCE)
                self.assertEqual(set(after), {'schema','nonce','sequence','probe','compositorContext',
                    'nativeContextAttached','windowAttached','physicalRenderingProven','harnessInitialized',
                    'moduleResolved','componentInstantiated','initialized','loaderStatus','ready','shown',
                    'visible','activeFocus','focusIndex','keyEvents','lastKey','originalFallback'})
            finally:
                view.close()
                view.deleteLater()
                self.app.processEvents()


if __name__ == '__main__':
    unittest.main()
