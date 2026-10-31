"""Isolated ARM Qt5.6 import-resolution probe. Never creates a window or compositor."""
from __future__ import print_function
import ctypes as C
import json
import os
import sys
import time
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
core = C.CDLL('/usr/lib/libQt5Core.so.5', mode=C.RTLD_GLOBAL)
gui = C.CDLL('/usr/lib/libQt5Gui.so.5', mode=C.RTLD_GLOBAL)
qml = C.CDLL('/usr/lib/libQt5Qml.so.5', mode=C.RTLD_GLOBAL)
p = C.c_void_p

def function(lib, name, types, result=None):
    f = getattr(lib, name); f.argtypes = types; f.restype = result
    return f

def storage(): return C.create_string_buffer(16384)

def string(value):
    raw = value.encode('utf-16-le'); chars = C.create_string_buffer(raw); result = storage()
    function(core, '_ZN7QStringC1EPK5QChari', [p, p, C.c_int])(result, chars, len(raw)//2)
    return result

def text(value):
    address = C.cast(value, C.POINTER(p))[0]
    if not address: return ''
    size = C.c_int.from_address(address + 4).value
    offset = C.c_int.from_address(address + 12).value
    assert 0 <= size <= 100000
    return C.string_at(address + offset, size*2).decode('utf-16-le')

def emit(value):
    sys.stdout.write(json.dumps(value)+'\n'); sys.stdout.flush()

qversion = function(core, 'qVersion', [], C.c_char_p)
assert C.sizeof(p) == 4 and qversion() == b'5.6.2'
warn_count = [0]
@C.CFUNCTYPE(None, C.c_int, p, p)
def warning(kind, context, message):
    if warn_count[0] < 100: emit({'stage': 'qt-message', 'kind': kind, 'message': text(message)})
    warn_count[0] += 1
function(core, '_Z22qInstallMessageHandlerPFv9QtMsgTypeRK18QMessageLogContextRK7QStringE', [p], p)(warning)
app = storage(); argc = C.c_int(3)
argv = (C.c_char_p*4)(b'home-resolution-probe', b'-platform', b'offscreen', None)
function(gui, '_ZN15QGuiApplicationC1ERiPPci', [p, C.POINTER(C.c_int), C.POINTER(C.c_char_p), C.c_int])(app, C.byref(argc), argv, 0x050602)
engine = storage(); function(qml, '_ZN10QQmlEngineC1EP7QObject', [p, p])(engine, None)
