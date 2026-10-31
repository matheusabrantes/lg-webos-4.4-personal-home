import argparse,json,os,pathlib,sys,time
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
os.environ.setdefault('QT_QUICK_BACKEND','software')
os.environ.setdefault('QT_SCALE_FACTOR','1')
from PyQt5.QtCore import QUrl,QTimer,Qt,qVersion,QT_VERSION_STR
from PyQt5.QtWidgets import QApplication
from PyQt5.QtQuickWidgets import QQuickWidget
ROOT=pathlib.Path(__file__).resolve().parents[1]
def create_view(app):
 view=QQuickWidget();view.setResizeMode(QQuickWidget.SizeRootObjectToView);view.resize(1920,1080)
 qml=pathlib.Path(os.environ.get('PERSONALHOME_QML_DIR',str(ROOT/'qml')))
 view.setSource(QUrl.fromLocalFile(str(qml/'PersonalHome.qml')))
 if view.status()==QQuickWidget.Error:raise RuntimeError('\n'.join(e.toString() for e in view.errors()))
 view.show();return view
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'qa/preview.png'));args=parser.parse_args()
 app=QApplication(sys.argv);view=create_view(app);root=view.rootObject();root.setProperty('ssid','Rede de exemplo')
 started=time.monotonic()
 def finish():
  if not root.property('readyForActivation'):
   if time.monotonic()-started>15:print('Asset readiness failed',flush=True);app.exit(1)
   else:QTimer.singleShot(50,finish)
   return
  image=view.grabFramebuffer();assert not image.isNull() and image.save(args.output)
  print(json.dumps({'ready':True,'output':args.output,'hostQtRuntime':qVersion(),'bindingQt':QT_VERSION_STR,'targetQt':'5.6.2 not executed'}),flush=True);app.quit()
 QTimer.singleShot(500,finish);sys.exit(app.exec_())
