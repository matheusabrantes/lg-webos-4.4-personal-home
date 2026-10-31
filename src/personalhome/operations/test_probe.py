import json,os,tempfile,time,unittest
from pathlib import Path
os.environ.setdefault('QT_QPA_PLATFORM','offscreen');os.environ.setdefault('QT_QUICK_BACKEND','software')
from PyQt5.QtCore import QObject,QUrl,pyqtSlot
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQuick import QQuickView
from PyQt5.QtQml import QQmlExpression
from PyQt5.QtTest import QTest
ROOT=Path(__file__).parent
class Files(QObject):
    def __init__(self,base):super().__init__();self.base=base
    def path(self,name):
        p=Path(QUrl(name).toLocalFile());assert p.parent==self.base and p.name in ['health.json','render-request.json','foreground-request.json'];return p
    @pyqtSlot(str,result=str)
    def read(self,name):
        p=self.path(name);return p.read_text() if p.exists() else ''
    @pyqtSlot(str,str)
    def write(self,name,data):self.path(name).write_text(data)
class Probe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QGuiApplication.instance() or QGuiApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ph-probe-');self.addCleanup(self.temp.cleanup);self.base=Path(self.temp.name)
        module=self.base/'TextFile';module.mkdir();(module/'qmldir').write_text('module TextFile\nTextFile 1.0 TextFile.qml\n')
        (module/'TextFile.qml').write_text('import QtQml 2.0\nQtObject {property string name;function read(){return files.read(name)} function write(data){files.write(name,data)}}')
        self.view=QQuickView();self.addCleanup(self.view.close);self.other=QQuickView();self.addCleanup(self.other.close)
        self.addCleanup(lambda:self.view.setSource(QUrl()))
        self.io=Files(self.base);self.view.engine().addImportPath(str(self.base));self.view.rootContext().setContextProperty('files',self.io);self.view.rootContext().setContextProperty('compositorWindow',self.view)
        probe=(ROOT/'runtime_probe.qml.inc').read_text().replace('__DIRECTORY__',str(self.base)).replace('__NONCE__','test-nonce')
        qml='''import QtQuick 2.4
import QtQuick.Window 2.2
import TextFile 1.0
Item {id:root;width:400;height:300;property alias ysm:ysm
 property alias homeItem:personalHomeLoader.item
 property alias nativeLaunchCount:ysm.launchCount
 property alias nativeLaunchId:ysm.launchId
 property alias nativeRestoreHidden:ysm.restoreHidden
 Item {id:ysm;property bool coverUIOpen:false;property int launchCount:0;property string launchId:"";property bool restoreHidden:false
 property var launchPointsModel:({getLaunchPointByAppId:function(id){return id==="com.abrantesflix.app"?{id:id}:null}})
 function launchPointActivated(point,callback,allowHidden){launchCount++;launchId=point.id;restoreHidden=allowHidden===true;}}

 QtObject {id:compositor;property var fullscreen:({appId:"com.abrantesflix.app"})}
 QtObject {id:notificationView;property bool alertActive:false}
 QtObject {id:globalActions;property bool popupOpen:false}
 Item {id:overlayView;state:"closed"} Item {id:overlaySurfaceGroupView;state:"closed"}
 QtObject {id:superRibbon;property bool visible:false;property bool enabled:false}
 FocusScope {id:home;focus:true;property bool diagnosticInitialized:true;property bool readyForActivation:true;property int focusIndex:0;property int diagnosticKeyCount:0;property int diagnosticLastKey:0;property int photoIndex:0;property int photoCount:21;property bool photoLoading:false;property int photoFailures:0;property bool photoTimerActive:true;property bool inputMenuOpen:false;property int inputMenuFocusIndex:-1;property int lastInputMenuMs:0;property var inputEntries:[];property bool inputLoading:false}
 QtObject {id:personalHomeLoader;property var item:home;property bool powerActive:true}
 Item {id:uiScope;property bool personalHomeShown:true;property bool personalHomeEnabled:true;
'''+probe+'\n}}'
        p=self.base/'Probe.qml';p.write_text(qml);self.view.setSource(QUrl.fromLocalFile(str(p)));self.assertFalse(self.view.errors(),[e.toString() for e in self.view.errors()]);self.view.show();self.view.requestActivate();self.root=self.view.rootObject();self.wait(lambda h:h['sequence']>=1)
    def health(self):
        try:return json.loads((self.base/'health.json').read_text())
        except (FileNotFoundError,ValueError):return {}
    def wait(self,condition,seconds=4):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            QTest.qWait(20);h=self.health()
            if h and condition(h):return h
        self.fail('Health condition timed out: '+str(self.health()))
    def request(self,nonce='test-nonce',sequence=1):
        p=self.base/'render-request.new';p.write_text(json.dumps({'nonce':nonce,'sequence':sequence}));p.rename(self.base/'render-request.json')
    def test_actual_frame_signal_acknowledges_requested_challenge(self):
        h=self.health();self.assertTrue(h['nativeContextAttached']);self.assertTrue(h['windowAttached']);self.assertTrue(h['ready']);self.assertEqual(h['renderProbe'],0)
        self.request();h=self.wait(lambda h:h['renderProbe']==1);self.assertGreater(h['frameSequence'],0)
        self.request(sequence=2);self.wait(lambda h:h['renderProbe']==2)
    def test_wrong_nonce_cannot_forge_a_composition_confirmation(self):
        self.request(nonce='wrong');QTest.qWait(700);self.assertEqual(self.health()['renderProbe'],0)
    def test_unrelated_native_window_never_confirms(self):
        self.view.rootContext().setContextProperty('compositorWindow',self.other);self.request();h=self.wait(lambda h:not h['nativeContextAttached']);self.assertEqual(h['renderProbe'],0);self.assertTrue(h['windowAttached'])
    def test_missing_component_remains_unready_with_genuine_heartbeat(self):
        expression=QQmlExpression(self.view.rootContext(),self.root,'homeItem=null');expression.evaluate();self.assertFalse(expression.hasError());h=self.wait(lambda h:not h['componentInstantiated']);self.assertFalse(h['ready']);self.assertFalse(h['windowAttached']);self.assertEqual(h['focusIndex'],-1)
    def test_saved_app_is_dispatched_through_native_launchpoint_once(self):
        (self.base/'foreground-request.json').write_text(json.dumps(dict(nonce='test-nonce',appId='com.abrantesflix.app')))
        h=self.wait(lambda h:h['foregroundRequestConsumed']);self.assertEqual(h['foregroundRequestError'],'');self.assertEqual(self.root.property('nativeLaunchCount'),1);self.assertEqual(self.root.property('nativeLaunchId'),'com.abrantesflix.app');self.assertTrue(self.root.property('nativeRestoreHidden'))
        QTest.qWait(600);self.assertEqual(self.root.property('nativeLaunchCount'),1)
    def test_foreign_or_unknown_launch_request_cannot_open_an_app(self):
        (self.base/'foreground-request.json').write_text(json.dumps(dict(nonce='wrong',appId='com.abrantesflix.app')))
        QTest.qWait(500);self.assertFalse(self.health()['foregroundRequestConsumed']);self.assertEqual(self.root.property('nativeLaunchCount'),0)
        (self.base/'foreground-request.json').write_text(json.dumps(dict(nonce='test-nonce',appId='not.installed')))
        h=self.wait(lambda h:h['foregroundRequestConsumed']);self.assertIn('no installed launch point',h['foregroundRequestError']);self.assertEqual(self.root.property('nativeLaunchCount'),0)
if __name__=='__main__':unittest.main(verbosity=2)
