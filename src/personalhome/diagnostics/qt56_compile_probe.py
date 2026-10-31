"""Compile real captured native QML without constructing it or replacing a compositor."""
from qt56_runtime import *
import hashlib
import struct
base = sys.argv[1]
raw = open('/usr/bin/surface-manager-starfish', 'rb').read()
assert hashlib.sha256(raw).hexdigest() == '5d2c9872f8b2c918c605cd05a7c49844645a8b683d8c1f8ee55f7bb1be6738e9'
shoff = struct.unpack_from('<I', raw, 32)[0]
shsize, shnum = struct.unpack_from('<HH', raw, 46)
sections = [struct.unpack_from('<10I', raw, shoff+i*shsize) for i in range(shnum)]
def offset(va):
    matches = [s[4]+va-s[3] for s in sections if s[1] != 8 and s[3] <= va < s[3]+s[5]]
    assert len(matches) == 1
    return matches[0]
arrays = [(0x3ce8c+0x1e4e0+0x53c,0x3ac9e+0x1e4de+0xec0,0x1842+0x1e4ea),
          (0x3fe28+0x1e540+0x874,0x3fe28+0x1e540+0x74c,0x3dc2e+0x1e54a),
          (0x98738+0x1e598-0x74,0x97642+0x1e596+0x3c8,0x406c8+0x1e5a0)]
elf = C.create_string_buffer(raw)
register = function(core, '_Z21qRegisterResourceDataiPKhS0_S0_', [C.c_int,p,p,p], C.c_bool)
for group in arrays:
    assert register(1, *[C.byref(elf, offset(va)) for va in group])
library = '/usr/lib/libWebOSCoreCompositor.so.0'
assert hashlib.sha256(open(library,'rb').read()).hexdigest() == '6c5ed1375c8e7ccc648389a0f46969c719d5bc8643e7a39d01ddb6f341a1b947'
webos = C.CDLL(library, mode=C.RTLD_GLOBAL)
# This exact shipped registration path discards this; its helpers only register Qt types.
function(webos, '_ZN19WebOSCoreCompositor13registerTypesEv', [p])(None)
function(qml,'_ZN10QQmlEngine13addImportPathERK7QString',[p,p])(engine,string(base))
components=[]
status = function(qml,'_ZNK13QQmlComponent6statusEv',[p],C.c_int)
events = function(core,'_ZN16QCoreApplication13processEventsE6QFlagsIN10QEventLoop17ProcessEventsFlagEE',[C.c_int])
for source in sys.argv[3:]+sys.argv[2:3]:
    url=storage();function(core,'_ZN4QUrlC1ERK7QStringNS_11ParsingModeE',[p,p,C.c_int])(url,string(source),0)
    component=storage();components.append(component)
    function(qml,'_ZN13QQmlComponentC1EP10QQmlEngineP7QObject',[p,p,p])(component,engine,None)
    function(qml,'_ZN13QQmlComponent7loadUrlERK4QUrl',[p,p])(component,url)
    for n in range(200):
        if status(component)!=2:break
        events(0);time.sleep(.01)
    error=storage();function(qml,'_ZNK13QQmlComponent11errorStringEv',[p,p])(error,component)
    emit({'stage':'native-compile','qt':qversion().decode(),'url':source,'status':status(component),'error':text(error),'nativeRootCreated':False,'windowCreated':False})
os._exit(0 if status(component)==1 else 1)
