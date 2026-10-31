"""Isolated Qt 5.6 ABI probe; owns no compositor, window or application service."""
from __future__ import print_function
import ctypes as C
import json
import os
import sys
import time
os.environ['QT_QPA_PLATFORM']='offscreen'
core=C.CDLL('/usr/lib/libQt5Core.so.5',mode=C.RTLD_GLOBAL)
gui=C.CDLL('/usr/lib/libQt5Gui.so.5',mode=C.RTLD_GLOBAL)
qml=C.CDLL('/usr/lib/libQt5Qml.so.5',mode=C.RTLD_GLOBAL)
def func(lib,name,types,result=None):
 f=getattr(lib,name);f.argtypes=types;f.restype=result;return f
def storage():return C.create_string_buffer(16384)
p=C.c_void_p
qversion=func(core,'qVersion',[],C.c_char_p)
assert C.sizeof(C.c_void_p)==4 and qversion()==b'5.6.2', 'Probe is specific to this ARM32 Qt 5.6.2 ABI'
sys.stdout.write(json.dumps({'stage':'library-symbols','qt':qversion().decode()})+'\n');sys.stdout.flush()
app=storage();argc=C.c_int(3);argv=(C.c_char_p*4)(b'home-qa-probe',b'-platform',b'offscreen',None)
func(gui,'_ZN15QGuiApplicationC1ERiPPci',[p,C.POINTER(C.c_int),C.POINTER(C.c_char_p),C.c_int])(app,C.byref(argc),argv,0x050602)
engine=storage();func(qml,'_ZN10QQmlEngineC1EP7QObject',[p,p])(engine,None)
text=sys.argv[1];raw=text.encode('utf-16-le');chars=C.create_string_buffer(raw);string=storage()
func(core,'_ZN7QStringC1EPK5QChari',[p,p,C.c_int])(string,chars,len(raw)//2)
url=storage();func(core,'_ZN4QUrlC1ERK7QStringNS_11ParsingModeE',[p,p,C.c_int])(url,string,0)
component=storage();func(qml,'_ZN13QQmlComponentC1EP10QQmlEngineP7QObject',[p,p,p])(component,engine,None)
func(qml,'_ZN13QQmlComponent7loadUrlERK4QUrl',[p,p])(component,url)
status=func(qml,'_ZNK13QQmlComponent6statusEv',[p],C.c_int)
events=func(core,'_ZN16QCoreApplication13processEventsE6QFlagsIN10QEventLoop17ProcessEventsFlagEE',[C.c_int])
for n in range(100):
 if status(component)!=2:break
 events(0);time.sleep(.01)
error=storage();func(qml,'_ZNK13QQmlComponent11errorStringEv',[p,p])(error,component)
def qstring(value):
 address=C.c_void_p.from_buffer(value).value
 if not address:return ''
 size=C.c_int.from_address(address+4).value;offset=C.c_int.from_address(address+12).value
 assert 0<=size<=100000
 return C.string_at(address+offset,size*2).decode('utf-16-le')
report={'stage':'component','qt':qversion().decode(),'status':status(component),'error':qstring(error),'windowCreated':False}
if report['status']==1:
 root=func(qml,'_ZN13QQmlComponent6createEP11QQmlContext',[p,p],p)(component,None)
 report['created']=bool(root)
 prop=func(core,'_ZNK7QObject8propertyEPKc',[p,p,C.c_char_p])
 boolean=func(core,'_ZNK8QVariant6toBoolEv',[p],C.c_bool)
 if root:
  ready=storage()
  for n in range(300):
   events(0);prop(ready,root,b'readyForActivation')
   if boolean(ready):break
   time.sleep(.01)
  report['readyForActivation']=bool(boolean(ready))
sys.stdout.write(json.dumps(report)+'\n');sys.stdout.flush()
# Avoid destructing Qt objects through an unverified destructor ABI.
os._exit(0 if report.get('readyForActivation') else 1)
