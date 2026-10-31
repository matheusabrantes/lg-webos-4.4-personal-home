import os
import pathlib
import re
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

from PyQt5.QtCore import QObject, QMetaObject, QUrl, Qt
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQuick import QQuickView
from PyQt5.QtTest import QTest

from test_integration import ROOT, builder


class NativeRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        native = builder.EVIDENCE / 'resources/ysm/YSM'
        cls.resources = builder.integrate({
            'YSM/' + name: (native / name).read_bytes()
            for name in ['YSM.qml', 'SystemSettings.qml', 'compositor.js', 'StarfishKeyFilter.qml']
        })
        for name in ['Common/FocusHandler.js', 'HomeToHiddenAnimation.qml']:
            cls.resources['YSM/' + name] = (native / name).read_bytes()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        directory = pathlib.Path(self.temp.name)
        (directory / 'PersonalHome').mkdir()
        (directory / 'PersonalHome/PersonalHome.qml').write_text('''import QtQuick 2.4
FocusScope {
 property bool readyForActivation:true
 property bool homeShown:false
 property bool powerActive:true
 property bool inputAllowed:true
 property bool launchPending:false
 property string ssid:""
 property int focusIndex:0
 visible:homeShown && powerActive
 enabled:inputAllowed
 signal actionRequested(string action)
 signal fatalError(string message)
 function completeAction(success,message){launchPending=false}
 onInputAllowedChanged:if(inputAllowed&&visible)forceActiveFocus()
 Keys.onPressed:if(event.key===Qt.Key_Right){focusIndex++;event.accepted=true}
}
''')
        for name in ['Common/FocusHandler.js', 'HomeToHiddenAnimation.qml']:
            (directory / pathlib.Path(name).name).write_bytes(self.resources['YSM/' + name])
        code = self.resources['YSM/YSM.qml'].decode()
        states = code[code.index('    states: [', code.index('    SystemUIViewStateTransitionManager {')):]
        hidden, visible = re.findall(r'PropertyChanges \{\s+target: superRibbon\s+.*?\n            \}', states, re.S)[:2]
        visibility = re.search(r'            visible: anchors.bottomMargin.*', code).group().strip()
        enabled = re.search(r'            enabled: !uiScope.*', code).group().strip()
        adapter = (ROOT / 'integration/native_home_loader.qml.inc').read_text()
        harness = '''import QtQuick 2.4
import QtQuick.Window 2.2
import "FocusHandler.js" as FocusHandler
Item {
 id: ysm; width:1920; height:1080; state:"hidden"
 property bool transitionsVisible:true
 property QtObject style:QtObject { property int ribbonBubbleHideDuration:150; property real bubbleFactor:0 }
 property var compositorWindow: ysm.Window.window
 property QtObject notificationView:QtObject { property bool modalAlertActive:false }
 property QtObject appManagerService:QtObject { signal launched(string identifier,int token); signal launchFailed(string identifier,int token,int code) }
 QtObject { id:systemSettings; property string powerState:"Active"; property string powerProcessing:""; property string personalHomeSsid:"Test" }
 function gotoState(value){state=value}
 function openHome(){state="visible"}
 function stealNativeFocus(){focusVoid.forceActiveFocus()}
 function showNativeOverlay(){FocusHandler.requestFocus(nativeOverlay)}
 function closeNativeOverlay(){FocusHandler.releaseFocus(nativeOverlay)}
 Item { id:nativeOverlay; objectName:"nativeOverlay"; property int layerNumber:6 }
 FocusScope {
  id:uiScope; objectName:"adapterScope"; anchors.fill:parent; property int layerNumber:3
''' + adapter + '''
  Item { id:focusVoid; objectName:"focusVoid" }
  Item {
   id:superRibbon; objectName:"stockRibbon"; state:"home"; width:1920; height:300
   property real hideMargin:300
   property real bubbleFactor:0
   property QtObject showsNavButton:QtObject { property bool visible:true }
   anchors.bottom:parent.bottom
   ''' + visibility + '\n' + enabled + '''
   function takeFocus(force){forceActiveFocus()}
  }
  Item {
   id:globalActions; objectName:"globalActions"; property int layerNumber:4
   property bool popupOpen:false; property int inputRequests:0
   function toggleInputs(value){inputRequests++;popupOpen=!popupOpen}
   onPopupOpenChanged: {
    if(popupOpen){ysm.gotoState("hidden");FocusHandler.requestFocus(globalActions)}
    else FocusHandler.releaseFocus(globalActions)
   }
  }
 }
 Item { id:loader_overlaySwitcher; opacity:1 }
 states:[State{name:"hidden";''' + hidden + '''},State{name:"visible";''' + visible + '''}]
 transitions:[
  Transition {id:t1;from:"hidden";to:"visible";SequentialAnimation {
   ScriptAction {script:{FocusHandler.requestFocus(uiScope);superRibbon.takeFocus(true)}}
   PauseAnimation {duration:30}
  }},
  Transition {id:t2;from:"visible";to:"hidden";SequentialAnimation {
   HomeToHiddenAnimation {}
   ScriptAction {script:FocusHandler.releaseFocus(uiScope)}
  }}
 ]
}
'''
        (directory / 'Harness.qml').write_text(harness)
        self.view = QQuickView()
        self.view.setSource(QUrl.fromLocalFile(str(directory / 'Harness.qml')))
        self.assertFalse(self.view.errors(), [error.toString() for error in self.view.errors()])
        self.view.show()
        self.addCleanup(self.view.close)
        self.root = self.view.rootObject()
        self.scope = self.root.findChild(QObject, 'adapterScope')
        self.stock = self.root.findChild(QObject, 'stockRibbon')
        self.home = self.root.findChild(QObject, 'personalHomeLoader').property('item')
        for _ in range(200):
            if self.home.property('readyForActivation'):
                break
            QTest.qWait(10)
        self.assertTrue(self.home.property('readyForActivation'))
        QMetaObject.invokeMethod(self.root, 'openHome')
        QTest.qWait(60)

    def test_native_visible_state_cannot_reenable_stock_ribbon(self):
        self.assertTrue(self.scope.property('personalHomeShown'))
        self.assertFalse(self.stock.property('visible'))
        self.assertFalse(self.stock.property('enabled'))

    def test_cursor_focus_handoff_keeps_real_directional_keys_working(self):
        QMetaObject.invokeMethod(self.root, 'stealNativeFocus')
        QTest.qWait(20)
        QTest.keyClick(self.view, Qt.Key_Right)
        self.assertEqual(self.home.property('focusIndex'), 1)

    def test_closing_never_exposes_stock_during_native_hide_animation(self):
        self.root.setProperty('state', 'hidden')
        for _ in range(20):
            self.assertFalse(self.stock.property('visible'))
            QTest.qWait(10)

    def test_repeated_home_toggles_keep_original_hidden_and_keys_active(self):
        for _ in range(3):
            self.root.setProperty('state', 'hidden')
            QTest.qWait(180)
            self.root.setProperty('state', 'visible')
            QTest.qWait(50)
            self.assertFalse(self.stock.property('visible'))
            previous = self.home.property('focusIndex')
            QTest.keyClick(self.view, Qt.Key_Right)
            self.assertEqual(self.home.property('focusIndex'), previous + 1)

    def test_fatal_asset_failure_restores_original_with_native_state_active(self):
        self.home.fatalError.emit('missing asset')
        QTest.qWait(5)
        self.assertFalse(self.scope.property('personalHomeEnabled'))
        self.assertTrue(self.stock.property('visible'))
        self.assertTrue(self.stock.property('enabled'))

    def test_native_overlay_keeps_its_focus_then_returns_to_home(self):
        QMetaObject.invokeMethod(self.root, 'showNativeOverlay')
        QTest.qWait(20)
        overlay = self.root.findChild(QObject, 'nativeOverlay')
        self.assertTrue(overlay.property('activeFocus'))
        previous = self.home.property('focusIndex')
        QTest.keyClick(self.view, Qt.Key_Right)
        self.assertEqual(self.home.property('focusIndex'), previous)
        QMetaObject.invokeMethod(self.root, 'closeNativeOverlay')
        QTest.qWait(20)
        QTest.keyClick(self.view, Qt.Key_Right)
        self.assertEqual(self.home.property('focusIndex'), previous + 1)

    def test_inputs_no_longer_opens_native_popup_or_hides_home(self):
        self.home.actionRequested.emit('inputs')
        QTest.qWait(20)
        actions = self.root.findChild(QObject, 'globalActions')
        self.assertEqual(actions.property('inputRequests'), 0)
        self.assertFalse(actions.property('popupOpen'))
        self.assertTrue(self.scope.property('personalHomeShown'))


if __name__ == '__main__':
    unittest.main()
