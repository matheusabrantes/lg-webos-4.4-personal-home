"""Build from the latest approved release; never installs or contacts the TV."""
import hashlib,json,re,secrets,shutil,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'diagnostics'))
from instrument_trial import instrument_ui

def sha(data):return hashlib.sha256(data).hexdigest()
def build():
    baseline=json.loads((HERE/'baseline.json').read_text());base=Path(baseline['release']);previous=json.loads((base/'release.json').read_text())
    assert sha((base/'release.json').read_bytes())==baseline['releaseSha256']
    for name,digest in previous['files'].items():assert sha((base/name).read_bytes())==digest,name
    destination=Path(tempfile.mkdtemp(prefix='personalhome-recovery-20261023.'))/'release';shutil.copytree(base,destination)
    nonce=secrets.token_hex(16);runtime='/tmp/lg-native-production.'+nonce
    identity=[]
    for name in previous['files']:
        path=destination/name;data=path.read_bytes()
        if previous['nonce'].encode() in data:path.write_bytes(data.replace(previous['nonce'].encode(),nonce.encode()));identity.append(name)
    ysm=destination/'module/YSM/YSM.qml';text=ysm.read_text();start=text.index('        property int trialSequence: 0');end=text.index('        property bool personalHomeEnabled: true',start)
    probe=(HERE/'runtime_probe.qml.inc').read_text().replace('__DIRECTORY__',runtime).replace('__NONCE__',nonce)
    text=text[:start]+probe+text[end:]
    signature='function launchPointActivated(item, issued) {'
    assert text.count(signature)==1
    text=text.replace(signature,'function launchPointActivated(item, issued, restoreHidden) {')
    nativeGuard='''function launchPointActivated(item, issued, restoreHidden) {
        if (ysm.state === "hidden") {'''
    assert text.count(nativeGuard)==1
    text=text.replace(nativeGuard,nativeGuard.replace('ysm.state === "hidden"','ysm.state === "hidden" && restoreHidden !== true'))
    ysm.write_text(text)
    for name in ['guard.js','bootstrap.js','rollback.js','policy.js']:(destination/name).write_bytes((HERE/'runtime'/name).read_bytes())
    for name in ['PersonalHome.qml','InputDropdown.qml']:
        data=(ROOT/'qml'/name).read_text()
        if name=='PersonalHome.qml':data=instrument_ui(data)
        (destination/'module/YSM/PersonalHome'/name).write_text(data)
    current=dict(previous);current.update(nonce=nonce,runtimeDirectory=runtime,healthSchema=3,physicalDailyLifecycleValidated=False,warning='Boot/recovery correction candidate. Original LG remains active. Physical acceptance and final deployment approval required.')
    current['files']={str(p.relative_to(destination)):sha(p.read_bytes()) for p in sorted(destination.rglob('*')) if p.is_file() and p.name!='release.json'}
    allowed=set(identity+['module/YSM/YSM.qml','module/YSM/PersonalHome/PersonalHome.qml','module/YSM/PersonalHome/InputDropdown.qml','guard.js','bootstrap.js','rollback.js'])
    for name,digest in previous['files'].items():
        if name not in allowed:assert current['files'][name]==digest,'Unrelated change: '+name
    assert current['files']['original']==previous['files']['original'] and current['files']['candidate']==previous['files']['candidate']
    for p in destination.rglob('*'):p.chmod(0o700 if p.is_dir() else 0o600)
    raw=(json.dumps(current,indent=2)+'\n').encode();(destination/'release.json').write_bytes(raw)
    result={'nonce':nonce,'release':str(destination),'releaseSha256':sha(raw),'remoteStage':'/tmp/personalhome-release.'+nonce,'validationState':'/var/lib/personalhome-validation.'+nonce,'runtime':runtime,'files':len(current['files']),'installed':False,'baselineSha256':baseline['releaseSha256']}
    (HERE/'prepared.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':print(json.dumps(build()))
