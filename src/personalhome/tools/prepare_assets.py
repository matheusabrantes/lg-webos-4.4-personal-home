import hashlib,json,math,pathlib,re,shutil,sys
from fontTools.ttLib import TTFont
from PyQt5.QtCore import Qt,QRectF
from PyQt5.QtGui import QImage,QPainter,QColor,QLinearGradient,QGuiApplication
from PyQt5.QtSvg import QSvgRenderer
ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'lg-home-webos/app/assets'
OUT=ROOT/'qml/assets'
app=QGuiApplication(sys.argv)
OUT.mkdir(parents=True,exist_ok=True)
rows=[]
for name in ['tv.png','abrantesflix.png','prime-video.png','apple-tv.png','foto-cerimonia.jpg','foto-casal.jpg','foto-balanco.jpg','foto-canal.jpg','foto-altar.jpg','GoogleSansFlex-OFL.txt','GoogleSansFlex-TRADEMARKS.txt']:
 shutil.copyfile(SOURCE/name,OUT/name)
for name in ['netflix','youtube']:
 svg=QSvgRenderer(str(SOURCE/(name+'.svg')));assert svg.isValid()
 image=QImage(280,280,QImage.Format_ARGB32_Premultiplied);image.fill(Qt.transparent)
 p=QPainter(image);svg.render(p,QRectF(0,0,280,280));p.end();assert image.save(str(OUT/(name+'.png')))
html=(SOURCE.parent/'index.html').read_text()
icons={name:re.search(r'data-tool="'+name+r'"[^>]*>\s*(<svg.*?</svg>)',html,re.S).group(1) for name in ['inputs','wifi','settings']}
icons['back']=re.search(r'data-tool="original"[^>]*>(<svg.*?</svg>)',html,re.S).group(1)
icons['store']='<svg viewBox="0 0 24 24"><path d="M4 9v11h16V9M3 9l2-5h14l2 5M3 9c0 3 4 3 4 0 0 3 5 3 5 0 0 3 5 3 5 0 0 3 4 3 4 0M9 20v-6h6v6"/></svg>'
for name,source in icons.items():
 for tone,color in [('white','#ffffff'),('dark','#14232c')]:
  source_svg=source.replace('currentColor',color).replace('<svg ','<svg fill="none" stroke="'+color+'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ')
  renderer=QSvgRenderer(source_svg.encode());assert renderer.isValid()
  image=QImage(64,64,QImage.Format_ARGB32_Premultiplied);image.fill(Qt.transparent)
  painter=QPainter(image);renderer.render(painter,QRectF(0,0,64,64));painter.end();assert image.save(str(OUT/(name+'-'+tone+'.png')))
fonts=[]
for weight in ['400','500']:
 font=TTFont(SOURCE/('google-sans-'+weight+'.woff2'))
 assert 'glyf' in font
 font.flavor=None;path=OUT/('google-sans-'+weight+'.ttf');font.save(path)
 check=TTFont(path);assert check.getGlyphOrder()==font.getGlyphOrder()
 fonts.append({'weight':weight,'family':check['name'].getDebugName(1),'subfamily':check['name'].getDebugName(2),'glyphs':len(check.getGlyphOrder()),'sfntVersion':check.sfntVersion})
# These small static textures preserve the approved diagonal gradients without a blur/shader.
for name,w,h,angle,start,end,radius in [
 ('dock',440,57,160,(208,230,238,87),(118,155,170,71),9.5),
 ('card',264,168,150,(233,245,249,71),(152,185,197,33),24),
 ('card-focused',264,168,150,(244,251,255,112),(172,205,218,66),24)]:
 dx=math.sin(math.radians(angle));dy=-math.cos(math.radians(angle));length=abs(w*dx)+abs(h*dy)
 gradient=QLinearGradient(w/2-dx*length/2,h/2-dy*length/2,w/2+dx*length/2,h/2+dy*length/2)
 gradient.setColorAt(0,QColor(*start));gradient.setColorAt(1,QColor(*end))
 image=QImage(w,h,QImage.Format_ARGB32_Premultiplied);image.fill(Qt.transparent)
 p=QPainter(image);p.setRenderHint(QPainter.Antialiasing);p.setPen(Qt.NoPen);p.setBrush(gradient);p.drawRoundedRect(QRectF(0,0,w,h),radius,radius);p.end();assert image.save(str(OUT/(name+'.png')))
for p in sorted(OUT.iterdir()):
 data=p.read_bytes();rows.append({'file':p.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
(ROOT/'qa/assets.json').write_text(json.dumps({'fonts':fonts,'files':rows,'source':'approved local assets; no remote image acquisition'},indent=2)+'\n')
print(json.dumps({'assets':len(rows),'fonts':fonts}))
