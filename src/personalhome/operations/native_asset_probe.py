"""Decode the shipped assets with this TV's Qt 5.6; never creates a scene or window."""
from qt56_runtime import *
import re
base=sys.argv[1]
logic=open(base+'/HomeLogic.js','r').read()
photos=re.findall(r'file:"(tv-[0-9]+\.jpg)"',logic)
assert len(photos)==21 and len(set(photos))==21
ctor=function(gui,'_ZN6QImageC1ERK7QStringPKc',[p,p,C.c_char_p])
dtor=function(gui,'_ZN6QImageD1Ev',[p])
isnull=function(gui,'_ZNK6QImage6isNullEv',[p],C.c_bool)
width=function(gui,'_ZNK6QImage5widthEv',[p],C.c_int)
height=function(gui,'_ZNK6QImage6heightEv',[p],C.c_int)
alpha=function(gui,'_ZNK6QImage15hasAlphaChannelEv',[p],C.c_bool)
pixel=function(gui,'_ZNK6QImage5pixelEii',[p,C.c_int,C.c_int],C.c_uint)
rows=[]
for name in photos+['prime-video.png','apple-tv.png']:
    image=storage();ctor(image,string(base+'/assets/'+name),None)
    try:
        assert not isnull(image),name
        row={'asset':name,'width':width(image),'height':height(image),'hasAlpha':bool(alpha(image))}
        if name in photos:assert row['width']==1920 and row['height']==1080,name
        else:assert row['hasAlpha'] and pixel(image,0,0)>>24==0,name
        rows.append(row)
    finally:dtor(image)
emit({'passed':True,'qt':qversion().decode(),'photos':21,'transparentLogos':2,'nativeWindowCreated':False,'physicalDisplayProven':False,'assets':rows})
os._exit(0)
