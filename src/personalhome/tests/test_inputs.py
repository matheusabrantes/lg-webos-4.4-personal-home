import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PyQt5.QtCore import QObject, QUrl
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtQml import QQmlComponent, QQmlEngine, QQmlExpression

ROOT=Path(__file__).resolve().parents[1]


class InputsControllerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QGuiApplication.instance() or QGuiApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        base=Path(self.temp.name);module=base/'WebOSServices';module.mkdir()
        (module/'qmldir').write_text('module WebOSServices\nService 1.0 Service.qml\n')
        (module/'Service.qml').write_text('''import QtQuick 2.4
QtObject {
 property string appId:""
 property string service:""
 property string method:""
 property var requests:[]
 signal response(string payload)
 function callService(args){requests=requests.concat([args]);}
}
''')
        for f in ['InputsController.qml','InputLogic.js']:shutil.copyfile(ROOT/'qml'/f,base/f)
        self.engine=QQmlEngine();self.engine.addImportPath(str(base))
        self.component=QQmlComponent(self.engine,QUrl.fromLocalFile(str(base/'InputsController.qml')))
        self.root=self.component.create();self.assertIsNotNone(self.root,[e.toString() for e in self.component.errors()])
        self.addCleanup(self.root.deleteLater);self.engine.rootContext().setContextProperty('controller',self.root)
        self.chosen=[];self.errors=[]
        self.root.launchRequested.connect(lambda x:self.chosen.append(x.toVariant()))
        self.root.selectionFailed.connect(self.errors.append)
        self.call('controller.start()')
        self.respond('inputsEimService',{'returnValue':True,'devices':[{'id':'HDMI_2','port':2,'label':'HDMI 2','appId':'com.webos.app.hdmi2','activate':False,'chosen':True}]})
        self.respond('inputsStorageService',{'returnValue':True,'devices':[{'deviceId':'usb-test','deviceType':'usb','deviceStatus':'NORMAL','deviceName':'Fixture USB'}]})

    def call(self,source):
        expression=QQmlExpression(self.engine.rootContext(),None,source);value=expression.evaluate()
        self.assertFalse(expression.hasError(),expression.error().toString())
        return value

    def respond(self,name,value):self.root.findChild(QObject,name).response.emit(json.dumps(value))

    def test_disconnected_hdmi_is_grey_but_selectable(self):
        self.call('controller.choose("HDMI_2",false)')
        self.assertEqual(len(self.chosen),1);row=self.chosen[0]
        self.assertTrue(row['enabled']);self.assertTrue(row['disconnected']);self.assertEqual(row['status'],'Sem sinal')
        self.assertEqual(row['appId'],'com.webos.app.hdmi2')

    def test_usb_is_revalidated_and_removed_usb_never_launches(self):
        self.call('controller.choose("usb:usb-test",false)');self.assertEqual(self.chosen,[])
        self.respond('inputsValidationService',{'returnValue':True,'devices':[]})
        self.assertEqual(self.chosen,[]);self.assertEqual(len(self.errors),1)

    def test_usb_launch_only_opens_browser_for_selected_device(self):
        self.call('controller.choose("usb:usb-test",false)')
        self.respond('inputsValidationService',{'returnValue':True,'devices':[{'deviceId':'usb-test','deviceType':'usb','deviceStatus':'NORMAL'}]})
        self.assertEqual(self.chosen[0]['appId'],'com.webos.app.photovideo')
        self.assertEqual(self.chosen[0]['params'],{'requestDevice':'usb-test'})

    def test_parental_pin_and_cancel_are_not_bypassed(self):
        self.root.setProperty('lockOut',['inputpicker']);self.call('controller.choose("HDMI_2",false)')
        self.assertEqual(self.chosen,[])
        self.respond('inputsPinService',{'returnValue':True,'matched':False});self.assertEqual(self.chosen,[])
        self.call('controller.cancelSelection()')
        self.respond('inputsPinService',{'returnValue':True,'matched':True});self.assertEqual(self.chosen,[])
        self.call('controller.choose("HDMI_2",false)');self.respond('inputsPinService',{'returnValue':True,'matched':True})
        self.assertEqual(len(self.chosen),1)

    def test_unknown_targets_bad_payload_and_late_usb_response_fail_closed(self):
        self.call('controller.choose("http://untrusted",false)');self.assertEqual(self.chosen,[])
        self.respond('inputsEimService',{'returnValue':True,'devices':[{'id':'HDMI_2','label':'Bad target','appId':'other.app','chosen':True}]})
        self.call('controller.choose("HDMI_2",false)');self.assertEqual(self.chosen,[])
        self.call('controller.choose("usb:usb-test",false)');self.call('controller.cancelSelection()')
        self.respond('inputsValidationService',{'returnValue':True,'devices':[{'deviceId':'usb-test','deviceType':'usb','deviceStatus':'NORMAL'}]})
        self.assertEqual(self.chosen,[])


if __name__=='__main__':unittest.main(verbosity=2)
