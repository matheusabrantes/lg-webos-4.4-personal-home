"""Run only the simulated-context adapter offscreen; no full native YSM objects."""
from qt56_runtime import *
url=storage();function(core,'_ZN4QUrlC1ERK7QStringNS_11ParsingModeE',[p,p,C.c_int])(url,string(sys.argv[1]),0)
component=storage();function(qml,'_ZN13QQmlComponentC1EP10QQmlEngineP7QObject',[p,p,p])(component,engine,None)
function(qml,'_ZN13QQmlComponent7loadUrlERK4QUrl',[p,p])(component,url)
status=function(qml,'_ZNK13QQmlComponent6statusEv',[p],C.c_int)
events=function(core,'_ZN16QCoreApplication13processEventsE6QFlagsIN10QEventLoop17ProcessEventsFlagEE',[C.c_int])
for n in range(200):
    if status(component)!=2:break
    events(0);time.sleep(.01)
error=storage();function(qml,'_ZNK13QQmlComponent11errorStringEv',[p,p])(error,component)
report={'stage':'isolated-adapter','qt':qversion().decode(),'status':status(component),'error':text(error),'windowCreated':False,'nativeContextAttached':False}
if report['status']==1:
    root=function(qml,'_ZN13QQmlComponent6createEP11QQmlContext',[p,p],p)(component,None)
    report['created']=bool(root)
    if root:
        value=storage()
        for n in range(400):
            events(0);time.sleep(.01)
        function(core,'_ZNK7QObject8propertyEPKc',[p,p,C.c_char_p])(value,root,b'readyForActivation')
        report['readyForActivation']=bool(function(core,'_ZNK8QVariant6toBoolEv',[p],C.c_bool)(value))
emit(report)
os._exit(0 if report.get('readyForActivation') else 1)
