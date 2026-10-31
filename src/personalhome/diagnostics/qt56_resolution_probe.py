"""Replay competing resource and disk modules, with no native objects or window."""
from qt56_runtime import *
base = sys.argv[1]
buffers = [C.create_string_buffer(open(base+'/'+name, 'rb').read()) for name in ['qt_resource_struct_v1.bin', 'qt_resource_name.bin', 'qt_resource_data.bin']]
assert function(core, '_Z21qRegisterResourceDataiPKhS0_S0_', [C.c_int, p, p, p], C.c_bool)(1, *buffers)
function(qml, '_ZN10QQmlEngine13addImportPathERK7QString', [p, p])(engine, string(base+'/external'))
url = storage(); function(core, '_ZN4QUrlC1ERK7QStringNS_11ParsingModeE', [p, p, C.c_int])(url, string('qrc:/YSM/UiWrapper.qml'), 0)
component = storage(); function(qml, '_ZN13QQmlComponentC1EP10QQmlEngineP7QObject', [p, p, p])(component, engine, None)
function(qml, '_ZN13QQmlComponent7loadUrlERK4QUrl', [p, p])(component, url)
status = function(qml, '_ZNK13QQmlComponent6statusEv', [p], C.c_int)
events = function(core, '_ZN16QCoreApplication13processEventsE6QFlagsIN10QEventLoop17ProcessEventsFlagEE', [C.c_int])
for n in range(100):
    if status(component) != 2: break
    events(0); time.sleep(.01)
error = storage(); function(qml, '_ZNK13QQmlComponent11errorStringEv', [p, p])(error, component)
report = {'stage': 'resolution', 'qt': qversion().decode(), 'status': status(component), 'error': text(error), 'windowCreated': False}
if report['status'] == 1:
    root = function(qml, '_ZN13QQmlComponent6createEP11QQmlContext', [p, p], p)(component, None)
    report['created'] = bool(root)
    if root:
        marker = storage(); function(core, '_ZNK7QObject8propertyEPKc', [p, p, C.c_char_p])(marker, root, b'marker')
        value = storage(); function(core, '_ZNK8QVariant8toStringEv', [p, p])(value, marker)
        report['resolvedMarker'] = text(value)
emit(report)
os._exit(0 if report.get('resolvedMarker') == 'external' else 1)
