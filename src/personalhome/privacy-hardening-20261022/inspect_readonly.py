"""Bounded metadata-only inspection; no remote writes or packet payloads."""
import datetime
import json
from pathlib import Path
import shlex
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'work/abrantesflix'))

PROBE = r'''
import os,json,re,hashlib
names=set(['admanager','acr2','nlp','nlpmanager','uploadd','rdxd','remotelogger'])
result={'processes':[], 'files':[], 'limits':{'maxFiles':100,'maxBytesPerFile':65536,'socketPayloads':False}}
for pid in os.listdir('/proc'):
 if not pid.isdigit(): continue
 try:
  name=open('/proc/'+pid+'/comm').read().strip()
  if name not in names: continue
  sockets=[]
  for fd in os.listdir('/proc/'+pid+'/fd'):
   try:
    link=os.readlink('/proc/'+pid+'/fd/'+fd)
    if link.startswith('socket:['): sockets.append(link[8:-1])
   except OSError: pass
  counts={}
  for protocol in ['tcp','tcp6','udp','udp6']:
   try:
    rows=open('/proc/net/'+protocol).readlines()[1:]
    counts[protocol]=sum(1 for row in rows if len(row.split())>9 and row.split()[9] in sockets)
   except IOError: counts[protocol]=None
  result['processes'].append({'name':name,'pid':int(pid),'internetSocketCounts':counts})
 except (OSError,IOError): pass
for base in ['/etc/init','/etc/palm','/usr/share/luna-service2','/etc/rdxd','/etc/uploadd','/etc/acr']:
 for directory,dirs,files in os.walk(base):
  dirs[:]=sorted(d for d in dirs if not os.path.islink(os.path.join(directory,d)))
  for name in sorted(files):
   path=os.path.join(directory,name)
   if not any(n in path.lower() for n in names): continue
   if os.path.islink(path) or not os.path.isfile(path): continue
   if len(result['files'])>=100: break
   size=os.path.getsize(path)
   if size>65536: result['files'].append({'path':path,'skipped':'size','size':size});continue
   data=open(path,'rb').read(65537)
   if b'\x00' in data: continue
   text=data.decode('utf-8','replace')
   lines=[line for line in text.splitlines() if re.match(r'^\s*(?:start on|stop on|respawn|exec|Name=|Exec=)',line)]
   domains=sorted(set(re.findall(r'https?://([A-Za-z0-9.-]+)',text)))
   result['files'].append({'path':path,'sha256':hashlib.sha256(data).hexdigest(),'size':size,'jobOrServiceLines':lines,'configuredHttpHosts':domains})
print(json.dumps(result))
'''

if __name__ == '__main__':
    import tv
    value = json.loads(tv.shell('/usr/bin/python -c ' + shlex.quote(PROBE)))
    value['checkedAtUtc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    value['limitations'] = ['Socket existence is not evidence of transmitted content or endpoint purpose.',
                           'Configured hosts are not observed DNS or traffic.',
                           'No packet capture, microphone activation, standby or app switching.']
    target = Path(__file__).parent / 'evidence/native-metadata-current.json'
    target.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'processes': len(value['processes']), 'files': len(value['files']), 'report': str(target)}))
