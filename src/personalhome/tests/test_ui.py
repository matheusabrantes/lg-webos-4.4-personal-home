import json,os,pathlib,random,sys,time,unittest
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
from PyQt5.QtCore import QObject,Q_ARG,QMetaObject,Qt,qInstallMessageHandler,qVersion,QT_VERSION_STR,QCoreApplication,QEvent
from PyQt5.QtQml import QQmlExpression
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from run_preview import create_view
APP=QApplication.instance() or QApplication([])
WARNINGS=[]
qInstallMessageHandler(lambda kind,context,text:WARNINGS.append(text))
def wait_for(test,timeout=5000):
 end=time.monotonic()+timeout/1000
 while time.monotonic()<end:
  APP.processEvents()
  if test():return
  QTest.qWait(5)
 raise AssertionError('Qt condition timed out')
def call(obj,method,*args):
 return QMetaObject.invokeMethod(obj,method,*[Q_ARG('QVariant',a) for a in args])
def expression(view,text):
 e=QQmlExpression(view.rootContext(),view.rootObject(),text);result=e.evaluate()
 if e.hasError():raise AssertionError(e.error().toString())
 return result[0] if isinstance(result,tuple) else result
class UI(unittest.TestCase):
 def setUp(self):
  self.view=create_view(APP);self.root=self.view.rootObject();self.calls=[]
  self.root.actionRequested.connect(self.calls.append)
  wait_for(lambda:self.root.property('readyForActivation'))
  self.view.setFocus();self.root.forceActiveFocus()
 def tearDown(self):
  self.view.close();self.view.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);APP.processEvents()
 def test_assets_and_geometry(self):
  self.assertTrue(self.root.property('readyForActivation'));self.assertEqual(self.root.property('iconsReady'),6)
  self.assertEqual(self.root.property('photoInterval'),600000)
  self.assertEqual(self.root.property('photoCount'),21)
  for size in [(1920,1080),(1280,720),(960,540)]:
   self.view.resize(*size);QTest.qWait(20)
   image=self.view.grabFramebuffer();self.assertFalse(image.isNull());self.assertEqual((image.width(),image.height()),size)
  self.view.resize(1920,1080);QTest.qWait(20)
  self.root.setProperty('ssid','Rede de exemplo');self.root.setProperty('clockText','10:03')
  self.assertTrue(self.view.grabFramebuffer().save(str(ROOT/'qa/native-preview.png')))
 def test_real_keys_and_pointer(self):
  QTest.keyClick(self.view,Qt.Key_Right);self.assertEqual(self.root.property('focusIndex'),1)
  QTest.keyClick(self.view,Qt.Key_Return);self.assertEqual(self.calls,['abrantesflix'])
  call(self.root,'completeAction',True,'')
  QTest.keyClick(self.view,Qt.Key_Up);self.assertIn(self.root.property('focusIndex'),[6,7,8,9])
  self.assertEqual(self.root.property('lastAppIndex'),1)
  from PyQt5.QtCore import QPoint
  QTest.mouseClick(self.view,Qt.LeftButton,pos=QPoint(1660,840));self.assertEqual(self.calls[-1],'appletv')
 def test_all_destinations_and_pending_guard(self):
  for index,action in enumerate(['livetv','abrantesflix','netflix','youtube','amazon','appletv','inputs','wifi','store','settings','original']):
   if action=='inputs':
    self.root.setProperty('focusIndex',index);call(self.root,'activate');self.assertTrue(self.root.property('inputMenuOpen'));call(self.root,'closeInputs');continue
   self.root.setProperty('focusIndex',index);call(self.root,'activate');self.assertEqual(self.calls[-1],action)
   before=len(self.calls);call(self.root,'activate');self.assertEqual(len(self.calls),before)
   call(self.root,'completeAction',True,'')
  call(self.root,'requestAction','shell-command');self.assertNotIn('shell-command',self.calls)
 def test_modal_and_back(self):
  call(self.root,'requestAction','livetv');call(self.root,'completeAction',False,'Erro <b>literal</b>')
  self.assertTrue(self.root.property('dialogOpen'));old=self.root.property('focusIndex')
  QTest.keyClick(self.view,Qt.Key_Right);self.assertEqual(self.root.property('focusIndex'),old)
  QTest.keyClick(self.view,Qt.Key_Escape);self.assertFalse(self.root.property('dialogOpen'))
  QTest.keyClick(self.view,Qt.Key_Escape);self.assertEqual(self.calls[-1],'back')
 def test_action_timeout(self):
  call(self.root,'requestAction','netflix');wait_for(lambda:self.root.property('dialogOpen'),timeout=9000)
  self.assertFalse(self.root.property('launchPending'))
 def test_native_launch_prompt_pauses_timeout(self):
  call(self.root,'requestAction','appletv');self.root.setProperty('inputAllowed',False)
  QTest.qWait(8300)
  self.assertFalse(self.root.property('dialogOpen'));self.assertTrue(self.root.property('launchPending'))
  self.root.setProperty('inputAllowed',True);call(self.root,'completeAction',True,'')
 def test_return_to_home_clears_previous_launch_error(self):
  call(self.root,'completeAction',False,'Erro anterior');self.assertTrue(self.root.property('dialogOpen'))
  self.root.setProperty('homeShown',False);self.root.setProperty('homeShown',True)
  self.assertFalse(self.root.property('dialogOpen'));self.assertEqual(self.root.property('errorMessage'),'')
  QTest.keyClick(self.view,Qt.Key_Right);self.assertEqual(self.root.property('focusIndex'),1)
 def test_visibility_and_power_pause(self):
  self.root.setProperty('photoInterval',40)
  wait_for(lambda:self.root.property('photoIndex')>0)
  self.root.setProperty('homeShown',False);QTest.qWait(100)
  previous=self.root.property('photoIndex');self.assertFalse(self.root.property('timersRunning'))
  QTest.qWait(140);self.assertEqual(self.root.property('photoIndex'),previous)
  call(self.root,'requestAction','netflix');self.assertEqual(self.calls,[])
  self.root.setProperty('homeShown',True);wait_for(lambda:self.root.property('photoIndex')!=previous)
  self.root.setProperty('powerActive',False);QTest.qWait(100)
  previous=self.root.property('photoIndex');QTest.qWait(140)
  self.assertFalse(self.root.property('timersRunning'));self.assertEqual(self.root.property('photoIndex'),previous)
 def test_native_modal_blocks_input(self):
  self.root.setProperty('inputAllowed',False)
  before=self.root.property('focusIndex')
  QTest.keyClick(self.view,Qt.Key_Right);call(self.root,'requestAction','netflix')
  self.assertEqual(self.calls,[]);self.assertEqual(self.root.property('focusIndex'),before)
  self.root.setProperty('inputAllowed',True);QTest.keyClick(self.view,Qt.Key_Right)
  self.assertEqual(self.root.property('focusIndex'),1)
 def test_ssid_treated_as_text(self):
  value='<img src=x onerror=bad()> '+('rede '*40)
  self.root.setProperty('ssid',value);button=self.root.findChild(QObject,'wifiButton')
  self.assertEqual(button.property('text'),value);self.assertLessEqual(button.property('width'),327)
  self.root.setProperty('ssid','');self.assertEqual(button.property('text'),'Wi-Fi')
 def test_failed_next_photo_preserves_current(self):
  self.root.setProperty('photoAssetPrefix','missing/')
  previous=self.root.property('photoIndex');call(self.root,'stepPhoto')
  wait_for(lambda:self.root.property('photoFailures')>0)
  self.assertEqual(self.root.property('photoIndex'),previous)
  current=self.root.findChild(QObject,'photoFirst')
  self.assertEqual(current.property('status'),1)
  self.assertIn('tv-02.jpg',current.property('source').toString())
  self.assertTrue(self.root.property('readyForActivation'));self.assertFalse(self.root.property('photoLoading'))
 def test_keyboard_stress_100000_moves(self):
  result=expression(self.view,"(function(){for(var n=0;n<100000;n++){moveFocus(['left','right','up','down','next','previous'][n%6]);if(focusIndex<0||focusIndex>10)throw Error('focus escaped');}return focusIndex;})()")
  self.assertIn(result,range(11))
 def test_real_key_event_stress_2000(self):
  for n in range(2000):
   QTest.keyClick(self.view,[Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down][n%4])
   self.assertIn(self.root.property('focusIndex'),range(11))
  self.assertEqual(self.calls,[])
 def test_photo_stress_200_transitions(self):
  self.root.setProperty('photoInterval',600000)
  start=time.monotonic()
  slots=[self.root.findChild(QObject,name) for name in ['photoFirst','photoSecond']]
  for n in range(200):
   call(self.root,'stepPhoto');wait_for(lambda:not self.root.property('photoLoading'))
   self.assertEqual(self.root.property('photoIndex'),(n+1)%self.root.property('photoCount'))
   self.assertEqual(sum(not slot.property('source').isEmpty() for slot in slots),1)
   self.assertEqual(sum(slot.property('status')==1 for slot in slots),1)
   if n<5:
    QTest.qWait(20)
    self.assertTrue(self.view.grabFramebuffer().save(str(ROOT/('qa/photo-%d.png'%((n+1)%5)))))
  self.root.setProperty('focusIndex',7);QTest.qWait(20)
  self.assertTrue(self.view.grabFramebuffer().save(str(ROOT/'qa/wifi-focused.png')))
  (ROOT/'qa/photo-stress.json').write_text(json.dumps({'transitions':200,'seconds':round(time.monotonic()-start,3),'imageSlotsInComponent':2,'nonemptySourcesAfterEveryTransition':1,'readyImagesAfterEveryTransition':1,'hostQtRuntime':qVersion(),'runtime':'host software renderer; not TV','tvRamMeasured':False},indent=2)+'\n')
if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(UI)
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 (ROOT/'qa/ui-tests.json').write_text(json.dumps({'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'hostQtRuntime':qVersion(),'bindingQt':QT_VERSION_STR,'targetQtExecuted':False,'warnings':WARNINGS},indent=2)+'\n')
 sys.exit(not result.wasSuccessful())
