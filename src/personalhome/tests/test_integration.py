import hashlib
import importlib.util
import json
import pathlib
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_build', ROOT / 'integration/build_candidate.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class IntegrationBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = pathlib.Path(self.temp.name)
        self.qml = self.base / 'qml'
        self.qml.mkdir()
        (self.qml / 'PersonalHome.qml').write_text('import QtQuick 2.4\nFocusScope {}\n')

    def test_exact_binary_and_native_diff(self):
        target = self.base / 'candidate'
        before = (builder.EVIDENCE / 'artifacts/usr_bin_surface-manager-starfish').read_bytes()
        report = builder.build(target, self.qml)
        after = (target / 'surface-manager-starfish.candidate').read_bytes()
        self.assertEqual(len(before), len(after))
        self.assertEqual(report['changedByteOffsets'], [0xF884, 0xF886, 0xF888, 0xF88A])
        self.assertEqual(before[:0xF884], after[:0xF884])
        self.assertEqual(before[0xF88E:], after[0xF88E:])
        self.assertEqual(after[0xF884:0xF88E], '/tmp/'.encode('utf-16-le'))
        resources = builder.native_files(builder.EVIDENCE)
        changed = []
        for name, original in resources.items():
            result = (target / 'module' / name).read_bytes()
            if result != original:
                changed.append(name)
        self.assertEqual(sorted(changed), ['YSM/StarfishKeyFilter.qml', 'YSM/SystemSettings.qml', 'YSM/YSM.qml', 'YSM/compositor.js'])
        self.assertEqual(report['unchangedNativeResources'], 213)
        self.assertFalse(report['tvExecuted'])
        self.assertFalse(report['runtimeQt56Validated'])
        self.assertEqual(hashlib.sha256(before).hexdigest(), builder.SOURCE_SHA)

    def test_reject_binary_byte_mutation_and_truncation(self):
        original = (builder.EVIDENCE / 'artifacts/usr_bin_surface-manager-starfish').read_bytes()
        for value in [b'', original[:-1], bytes([original[0] ^ 1]) + original[1:], original[:0xF884] + b'X' + original[0xF885:]]:
            with self.assertRaises(ValueError):
                builder.patch_elf(value)

    def test_reject_resource_or_manifest_corruption(self):
        evidence = self.base / 'evidence'
        shutil.copytree(builder.EVIDENCE / 'resources', evidence / 'resources')
        shutil.copy(builder.EVIDENCE / 'resources-manifest.json', evidence / 'resources-manifest.json')
        target = evidence / 'resources/ysm/YSM/YSM.qml'
        target.write_bytes(target.read_bytes() + b'corrupt')
        with self.assertRaises(ValueError):
            builder.native_files(evidence)
        manifest = evidence / 'resources-manifest.json'
        data = json.loads(manifest.read_text())
        data['resources'][0]['resourcePath'] = '../../escape'
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'manifest identity'):
            builder.native_files(evidence)

    def test_reject_existing_destination_and_ui_symlink(self):
        destination = self.base / 'existing'
        destination.mkdir()
        marker = destination / 'keep'
        marker.write_text('untouched')
        with self.assertRaises(ValueError):
            builder.build(destination, self.qml)
        self.assertEqual(marker.read_text(), 'untouched')
        (self.qml / 'bad').symlink_to(marker)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            builder.build(self.base / 'new', self.qml)
        self.assertFalse((self.base / 'new').exists())

    def test_native_anchors_and_fallback_contract(self):
        with self.assertRaises(ValueError):
            builder.replace_once('a a', 'a', 'b')
        with self.assertRaises(ValueError):
            builder.replace_once('a', 'x', 'b')
        resources = builder.native_files(builder.EVIDENCE)
        integrated = builder.integrate(dict(resources))
        code = integrated['YSM/YSM.qml'].decode()
        self.assertIn('item.readyForActivation', code)
        self.assertIn('status === Loader.Error) useOriginal()', code)
        self.assertIn('onFatalError: personalHomeLoader.useOriginal()', code)
        self.assertIn('interval: 5000', code)
        self.assertIn('ysm.launchPointActivated(point, callback)', code)
        self.assertIn('getLaunchPointByAppId(apps[action])', code)
        self.assertIn('if (action === "back")', code)
        self.assertIn('uiScope.personalHomeEnabled = false', code)
        self.assertNotIn('sendSpecialKey', code)
        self.assertEqual(resources['YSM/main.qml'], integrated['YSM/main.qml'])
        self.assertEqual(resources['YSM/compositorcreator.js'], integrated['YSM/compositorcreator.js'])
        self.assertEqual(resources['YSM/SuperRibbon/SuperRibbon.qml'], integrated['YSM/SuperRibbon/SuperRibbon.qml'])

    def test_deterministic_repeat_builds(self):
        expected = None
        for index in range(20):
            report = builder.build(self.base / ('repeat-' + str(index)), self.qml)
            observed = (report['candidateSha256'], report['moduleFiles'])
            if expected is None:
                expected = observed
            self.assertEqual(observed, expected)

# This exercises adapter bindings with Qt5.15 and mocked native objects, not TVQt5.6.
try:
    from PyQt5.QtCore import QObject, QMetaObject, QUrl, Q_ARG
    from PyQt5.QtGui import QGuiApplication
    from PyQt5.QtQuick import QQuickView
    from PyQt5.QtTest import QTest
    HAS_QT = True
except ImportError:
    HAS_QT = False


@unittest.skipUnless(HAS_QT, 'Qt5 host runtime not installed in this interpreter')
class AdapterQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ.setdefault('QT_QUICK_BACKEND', 'software')
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def make_view(self, missing=False, invalid_contract=False, actual_ui=False):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        directory = pathlib.Path(temp.name)
        (directory / 'PersonalHome').mkdir()
        (directory / 'FocusHandler.js').write_bytes(
            (builder.EVIDENCE / 'resources/ysm/YSM/Common/FocusHandler.js').read_bytes())
        if not missing:
            (directory / 'PersonalHome/PersonalHome.qml').write_text('''import QtQuick 2.4
FocusScope {
 property bool readyForActivation: false
 property bool homeShown: false
 property bool powerActive: false
 property bool inputAllowed: true
 property bool launchPending: false
 property string ssid: ""
 property var results: []
 signal actionRequested(string action)
 signal fatalError(string message)
 function completeAction(success,message) { launchPending=false;results = results.concat([[success,message]]); }
}
''')
        if invalid_contract:
            path = directory / 'PersonalHome/PersonalHome.qml'
            path.write_text(path.read_text().replace('function completeAction(', 'function unavailableAction('))
        if actual_ui:
            shutil.copytree(ROOT / 'qml', directory / 'PersonalHome', dirs_exist_ok=True)
        adapter = (ROOT / 'integration/native_home_loader.qml.inc').read_text()
        harness = '''import QtQuick 2.4
import QtQuick.Window 2.2
import "FocusHandler.js" as FocusHandler
Item {
 id: ysm
 width: 1920; height: 1080
 state: "visible"
 property var compositorWindow: ysm.Window.window
 Component.onCompleted: FocusHandler.requestFocus(uiScope)
 property var calls: []
 property bool unavailable: false
 property int nextLaunchToken: 1
 property bool holdResponse: false
 property bool deferIssued: false
 property bool reuseSurface: false
 property bool throwLaunch: false
 property var savedIssued: null
 property var previousIssued: null
 function invokeOldIssued(token) { previousIssued(token); }
 property string requestedId: ""
 property int requestedToken: -1
 function dispatch(appId, issued) {
  if(throwLaunch)throw Error("test launch failure");
  requestedId=appId;requestedToken=nextLaunchToken++;
  previousIssued=savedIssued;savedIssued=issued;
  if(deferIssued)return;
  issued(reuseSurface?null:requestedToken);
  if(!holdResponse&&!reuseSurface)appManagerService.launched(appId,requestedToken);
 }
 property QtObject appList: QtObject { property string subType:""; function getAppInfoValue(id,key){return subType;} }
 property QtObject hcapSurfaceView: QtObject { function isInputAppSurface(surface){return false;} }
 property QtObject compositor: QtObject { property var fullscreen:null }
 function launchPointActivated(point, issued) {
  ysm.calls = ysm.calls.concat([{point:point,index:0}]);
  dispatch(point.id,issued);
 }
 function gotoState(value) { state = value; }
 property QtObject launchPointsModel: QtObject {
  function getLaunchPointByAppId(appId) { return ysm.unavailable ? null : {id:appId, params:{preserved:true}}; }
 }
 property QtObject appManagerService: QtObject {
  signal launched(string identifier,int token)
  signal launchFailed(string identifier,int token,int errorCode)
  function checkLaunch(appId, params, update, install, reason, issued) {
   ysm.calls = ysm.calls.concat([{id:appId,params:params,reason:reason}]);
   ysm.dispatch(appId,issued);
  }
 }
 property QtObject notificationView: QtObject { objectName: "notificationView"; property bool modalAlertActive: false }
 Item {
  id: globalActions
  objectName: "globalActions"
  property int layerNumber: 4
  property bool popupOpen: false
  function toggleInputs(value) { popupOpen=!popupOpen; }
  onPopupOpenChanged: {
   if(popupOpen){ysm.gotoState("hidden");FocusHandler.requestFocus(globalActions);}
   else FocusHandler.releaseFocus(globalActions);
  }
 }
 QtObject { id: t1; property bool running: false }
 QtObject {
  id: systemSettings
  objectName: "systemSettings"
  property string powerState: "Active"
  property string powerProcessing: ""
  property string personalHomeSsid: "Rede de teste"
 }
 FocusScope {
  id: uiScope
  objectName: "adapterScope"
  property int layerNumber: 3
  anchors.fill: parent
''' + adapter + '''
  Item {
   id: superRibbon
   objectName: "stockRibbon"
   property int focusRequests: 0
   property QtObject launcherRibbon: QtObject {
    signal launchPointActivated(variant item, int index)
    onLaunchPointActivated: ysm.calls = ysm.calls.concat([{point:item,index:index}])
   }
   state: "home"
   visible: !uiScope.personalHomeShown
   enabled: !uiScope.personalHomeShown
   function takeFocus(force) { focusRequests++; }
  }
 }
}
'''
        (directory / 'Harness.qml').write_text(harness)
        view = QQuickView()
        view.setSource(QUrl.fromLocalFile(str(directory / 'Harness.qml')))
        self.assertFalse(view.errors(), [error.toString() for error in view.errors()])
        view.show()
        QTest.qWait(80)
        self.addCleanup(view.close)
        return view, view.rootObject()

    @staticmethod
    def emit_action(item, name):
        QMetaObject.invokeMethod(item, 'actionRequested', Q_ARG(str, name))
        QTest.qWait(1)

    def test_readiness_gate_actions_and_native_fallback(self):
        view, root = self.make_view()
        scope = root.findChild(QObject, 'adapterScope')
        loader = root.findChild(QObject, 'personalHomeLoader')
        stock = root.findChild(QObject, 'stockRibbon')
        item = loader.property('item')
        self.assertIsNotNone(item)
        self.assertFalse(scope.property('personalHomeShown'))
        self.assertFalse(loader.property('visible'))
        self.assertTrue(stock.property('visible'))
        item.setProperty('readyForActivation', True)
        QTest.qWait(5)
        self.assertTrue(scope.property('personalHomeShown'))
        self.assertTrue(loader.property('visible'))
        self.assertFalse(stock.property('visible'))
        self.assertFalse(stock.property('enabled'))
        self.assertEqual(item.property('ssid'), 'Rede de teste')
        for action, app_id in [('livetv','com.webos.app.livetv'),('abrantesflix','com.abrantesflix.app'),('netflix','netflix'),('youtube','youtube.leanback.v4'),('amazon','amazon'),('appletv','com.apple.appletv'),('store','com.webos.app.discovery')]:
            self.emit_action(item, action)
            calls = root.property('calls').toVariant()
            self.assertEqual(calls[-1]['point'], {'id':app_id,'params':{'preserved':True}})
        self.emit_action(item, 'wifi')
        calls = root.property('calls').toVariant()
        self.assertEqual(json.loads(calls[-1]['params']), {'target':'network','item':'Wireless'})
        self.emit_action(item, 'inputs')
        actions = root.findChild(QObject, 'globalActions')
        self.assertFalse(actions.property('popupOpen'))
        self.assertEqual(root.property('state'), 'visible')
        actions.setProperty('popupOpen', False)
        root.setProperty('state', 'visible')
        QTest.qWait(5)
        self.emit_action(item, 'settings')
        self.assertEqual(root.property('calls').toVariant()[-1]['id'], 'com.palm.app.settings')
        root.setProperty('unavailable', True)
        before = len(root.property('calls').toVariant())
        self.emit_action(item, 'netflix')
        self.assertEqual(len(root.property('calls').toVariant()), before)
        self.assertFalse(item.property('results').toVariant()[-1][0])
        self.emit_action(item, 'arbitrary.app')
        self.assertEqual(len(root.property('calls').toVariant()), before)
        self.assertFalse(item.property('results').toVariant()[-1][0])
        self.emit_action(item, 'back')
        self.assertEqual(root.property('state'), 'hidden')
        root.setProperty('state', 'visible')
        self.emit_action(item, 'original')
        self.assertFalse(scope.property('personalHomeEnabled'))
        self.assertTrue(stock.property('visible'))
        self.assertTrue(stock.property('enabled'))
        self.assertGreater(stock.property('focusRequests'), 0)

    def test_missing_component_and_fatal_error_restore_stock(self):
        view, root = self.make_view(missing=True)
        scope = root.findChild(QObject, 'adapterScope')
        self.assertFalse(scope.property('personalHomeEnabled'))
        self.assertTrue(root.findChild(QObject, 'stockRibbon').property('visible'))
        view.close()
        view, root = self.make_view(invalid_contract=True)
        self.assertFalse(root.findChild(QObject, 'adapterScope').property('personalHomeEnabled'))
        self.assertTrue(root.findChild(QObject, 'stockRibbon').property('visible'))
        view.close()
        view, root = self.make_view()
        scope = root.findChild(QObject, 'adapterScope')
        item = root.findChild(QObject, 'personalHomeLoader').property('item')
        QMetaObject.invokeMethod(item, 'fatalError', Q_ARG(str, 'missing asset'))
        QTest.qWait(5)
        self.assertFalse(scope.property('personalHomeEnabled'))
        self.assertTrue(root.findChild(QObject, 'stockRibbon').property('visible'))

    def test_assets_not_ready_timeout_restores_stock(self):
        view, root = self.make_view()
        scope = root.findChild(QObject, 'adapterScope')
        self.assertTrue(scope.property('personalHomeEnabled'))
        self.assertTrue(root.findChild(QObject, 'stockRibbon').property('visible'))
        # QML timers follow the event loop; wait for the condition with bounded scheduling slack.
        for _ in range(120):
            if not scope.property('personalHomeEnabled'):
                break
            QTest.qWait(50)
        self.assertFalse(scope.property('personalHomeEnabled'))
        self.assertTrue(root.findChild(QObject, 'stockRibbon').property('visible'))

    def test_power_and_modal_focus_guards(self):
        view, root = self.make_view()
        scope = root.findChild(QObject, 'adapterScope')
        item = root.findChild(QObject, 'personalHomeLoader').property('item')
        settings = root.findChild(QObject, 'systemSettings')
        item.setProperty('readyForActivation', True)
        QTest.qWait(2)
        settings.setProperty('powerProcessing', 'Prepare Active Standby')
        QTest.qWait(2)
        self.assertFalse(scope.property('personalHomeShown'))
        self.assertFalse(item.property('powerActive'))
        before = len(root.property('calls').toVariant())
        self.emit_action(item, 'netflix')
        self.assertEqual(len(root.property('calls').toVariant()), before)

        settings.setProperty('powerProcessing', '')
        QTest.qWait(2)
        self.assertTrue(scope.property('personalHomeShown'))
        notification = root.findChild(QObject, 'notificationView')
        notification.setProperty('modalAlertActive', True)
        QTest.qWait(2)
        self.assertFalse(item.property('inputAllowed'))
        before = len(root.property('calls').toVariant())
        self.emit_action(item, 'netflix')
        self.assertEqual(len(root.property('calls').toVariant()), before)
        notification.setProperty('modalAlertActive', False)
        QTest.qWait(2)
        self.assertTrue(item.property('inputAllowed'))
        self.emit_action(item, 'netflix')
        self.assertEqual(len(root.property('calls').toVariant()), before + 1)
        root.setProperty('notificationView', None)
        QTest.qWait(2)
        self.assertFalse(item.property('inputAllowed'))
        before = len(root.property('calls').toVariant())
        self.emit_action(item, 'netflix')
        self.assertEqual(len(root.property('calls').toVariant()), before)

    def test_actual_ui_through_adapter(self):
        view, root = self.make_view(actual_ui=True)
        scope = root.findChild(QObject, 'adapterScope')
        item = root.findChild(QObject, 'personalHomeLoader').property('item')
        for _ in range(200):
            if scope.property('personalHomeShown'): break
            QTest.qWait(10)
        self.assertTrue(scope.property('personalHomeShown'))
        self.assertTrue(item.property('readyForActivation'))
        self.assertTrue(item.property('visible'))
        self.assertEqual(item.property('ssid'), 'Rede de teste')
        self.assertEqual((item.property('width'), item.property('height')), (1920, 1080))
        QMetaObject.invokeMethod(item, 'requestAction', Q_ARG('QVariant', 'wifi'))
        self.assertEqual(json.loads(root.property('calls').toVariant()[-1]['params']), {'target':'network','item':'Wireless'})
        self.assertTrue(item.property('launchPending'))
        root.setProperty('state', 'hidden');QTest.qWait(5)
        self.assertFalse(item.property('launchPending'))
        root.setProperty('state', 'visible');QTest.qWait(5)
        root.setProperty('unavailable', True)
        QMetaObject.invokeMethod(item, 'requestAction', Q_ARG('QVariant', 'netflix'))
        self.assertTrue(item.property('dialogOpen'))
        QMetaObject.invokeMethod(item, 'closeError')
        root.setProperty('state', 'hidden')
        QTest.qWait(5)
        self.assertFalse(item.property('timersRunning'))
        root.setProperty('state', 'visible')
        QTest.qWait(5)
        self.assertTrue(scope.property('personalHomeShown'))
        self.assertTrue(item.property('timersRunning'))
        QMetaObject.invokeMethod(item, 'requestAction', Q_ARG('QVariant', 'original'))
        QTest.qWait(5)
        self.assertFalse(scope.property('personalHomeEnabled'))
        self.assertTrue(root.findChild(QObject, 'stockRibbon').property('visible'))



if __name__ == '__main__':
    unittest.main()
