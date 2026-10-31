"""Build from the latest approved release; never installs or contacts the TV."""
import hashlib,json,re,secrets,shutil,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'diagnostics'))
from instrument_trial import instrument_ui
sys.path.insert(0,str(ROOT/'integration'))
from build_candidate import preserve_startup_home,integrate_power_wake

def sha(data):return hashlib.sha256(data).hexdigest()
def refresh_runtime_probe(text,nonce):
    start_marker='        property int trialSequence: 0'
    end_marker='        property bool personalHomeEnabled: true'
    assert text.count(start_marker)==1 and text.count(end_marker)==1,'Runtime probe anchors changed'
    start=text.index(start_marker);end=text.index(end_marker,start)
    controller='        QtObject {\n            id: personalHomePowerWakeController'
    assert text.count(controller)<=1,'Power wake controller is ambiguous'
    existing=text.find(controller,start,end)
    if existing>=0:end=existing
    probe=(HERE/'runtime_probe.qml.inc').read_text().replace('__DIRECTORY__','/tmp/lg-native-production.'+nonce).replace('__NONCE__',nonce)
    return text[:start]+probe+text[end:]

def update_native_wake(destination,nonce):
    names=['YSM/YSM.qml','YSM/compositor.js','YSM/StarfishKeyFilter.qml']
    resources={name:(destination/'module'/name).read_bytes() for name in names}
    for name,data in integrate_power_wake(resources).items():(destination/'module'/name).write_bytes(data.replace(b'__NONCE__',nonce.encode()))

def build_runtime_update(base, expected_sha, destination):
    """Update runtime actors from a verified installed release, preserving its UI."""
    base=Path(base);destination=Path(destination)
    raw=(base/'release.json').read_bytes()
    assert re.fullmatch('[a-f0-9]{64}',expected_sha) and sha(raw)==expected_sha,'Baseline manifest changed'
    previous=json.loads(raw)
    assert previous['schema']==1 and previous['healthSchema']==3
    assert previous['originalSha']=='5d2c9872f8b2c918c605cd05a7c49844645a8b683d8c1f8ee55f7bb1be6738e9'
    assert re.fullmatch('[a-f0-9]{32}',previous['nonce']) and 250<=len(previous['files'])<=400
    for name,digest in previous['files'].items():
        assert re.fullmatch(r'(original|candidate|guard.js|bootstrap.js|rollback.js|policy.js|module/YSM/[A-Za-z0-9_.\/-]+)',name) and '..' not in name
        assert not (base/name).is_symlink() and sha((base/name).read_bytes())==digest,name
    assert previous['files']['original']==previous['originalSha'] and previous['files']['candidate']==previous['candidateSha']
    nonce=secrets.token_hex(16);shutil.copytree(base,destination)
    actors=['guard.js','bootstrap.js','rollback.js','policy.js']
    for name in previous['files']:
        data=(HERE/'runtime'/name).read_bytes() if name in actors else (base/name).read_bytes().replace(previous['nonce'].encode(),nonce.encode())
        if name=='module/YSM/YSM.qml':data=preserve_startup_home(refresh_runtime_probe(data.decode(),nonce)).encode()
        (destination/name).write_bytes(data)
    update_native_wake(destination,nonce)
    current=dict(previous);current.update(nonce=nonce,runtimeDirectory='/tmp/lg-native-production.'+nonce,physicalDailyLifecycleValidated=False,directPowerWakeValidated=False,coldBootFirstHomeValidated=False,warning='Warm Power first-Home candidate; first-frame physical validation, cold-boot integration and persistent deployment approval pending.')
    current['files']={name:sha((destination/name).read_bytes()) for name in previous['files']}
    for name in previous['files']:
        if name not in actors and name not in ['module/YSM/YSM.qml','module/YSM/compositor.js','module/YSM/StarfishKeyFilter.qml']:
            assert (destination/name).read_bytes()==(base/name).read_bytes().replace(previous['nonce'].encode(),nonce.encode()),name
    expected={name:(base/'module'/name).read_bytes().replace(previous['nonce'].encode(),nonce.encode()) for name in ['YSM/YSM.qml','YSM/compositor.js','YSM/StarfishKeyFilter.qml']}
    expected['YSM/YSM.qml']=preserve_startup_home(refresh_runtime_probe(expected['YSM/YSM.qml'].decode(),nonce)).encode()
    for name,data in integrate_power_wake(expected).items():assert (destination/'module'/name).read_bytes()==data.replace(b'__NONCE__',nonce.encode()),name
    assert current['files']['original']==previous['originalSha'] and current['files']['candidate']==previous['candidateSha']
    for p in destination.rglob('*'):p.chmod(0o700 if p.is_dir() else 0o600)
    raw=(json.dumps(current,indent=2)+'\n').encode();(destination/'release.json').write_bytes(raw)
    return {'nonce':nonce,'release':str(destination.resolve()),'releaseSha256':sha(raw),'baselineSha256':expected_sha,'remoteStage':'/tmp/personalhome-release.'+nonce,'validationState':'/var/lib/personalhome-validation.'+nonce,'runtime':current['runtimeDirectory'],'files':len(current['files']),'installed':False}

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
    ysm=destination/'module/YSM/YSM.qml';text=refresh_runtime_probe(ysm.read_text(),nonce)
    signature='function launchPointActivated(item, issued) {'
    assert text.count(signature)==1
    text=text.replace(signature,'function launchPointActivated(item, issued, restoreHidden) {')
    nativeGuard='''function launchPointActivated(item, issued, restoreHidden) {
        if (ysm.state === "hidden") {'''
    assert text.count(nativeGuard)==1
    text=text.replace(nativeGuard,nativeGuard.replace('ysm.state === "hidden"','ysm.state === "hidden" && restoreHidden !== true'))
    ysm.write_text(preserve_startup_home(text))
    for name in ['guard.js','bootstrap.js','rollback.js','policy.js']:(destination/name).write_bytes((HERE/'runtime'/name).read_bytes())
    for name in ['PersonalHome.qml','InputDropdown.qml']:
        data=(ROOT/'qml'/name).read_text()
        if name=='PersonalHome.qml':data=instrument_ui(data)
        (destination/'module/YSM/PersonalHome'/name).write_text(data)
    update_native_wake(destination,nonce)
    current=dict(previous);current.update(nonce=nonce,runtimeDirectory=runtime,healthSchema=3,physicalDailyLifecycleValidated=False,warning='Boot/recovery correction candidate. Original LG remains active. Physical acceptance and final deployment approval required.')
    current['files']={str(p.relative_to(destination)):sha(p.read_bytes()) for p in sorted(destination.rglob('*')) if p.is_file() and p.name!='release.json'}
    allowed=set(identity+['module/YSM/YSM.qml','module/YSM/compositor.js','module/YSM/StarfishKeyFilter.qml','module/YSM/PersonalHome/PersonalHome.qml','module/YSM/PersonalHome/InputDropdown.qml','guard.js','bootstrap.js','rollback.js','policy.js'])
    for name,digest in previous['files'].items():
        if name not in allowed:assert current['files'][name]==digest,'Unrelated change: '+name
    assert current['files']['original']==previous['files']['original'] and current['files']['candidate']==previous['files']['candidate']
    for p in destination.rglob('*'):p.chmod(0o700 if p.is_dir() else 0o600)
    raw=(json.dumps(current,indent=2)+'\n').encode();(destination/'release.json').write_bytes(raw)
    result={'nonce':nonce,'release':str(destination),'releaseSha256':sha(raw),'remoteStage':'/tmp/personalhome-release.'+nonce,'validationState':'/var/lib/personalhome-validation.'+nonce,'runtime':runtime,'files':len(current['files']),'installed':False,'baselineSha256':baseline['releaseSha256']}
    (HERE/'prepared.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
    if len(sys.argv)==1:print(json.dumps(build()))
    else:
        import argparse
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--baseline',required=True);parser.add_argument('--baseline-sha256',required=True);parser.add_argument('--output',required=True)
        args=parser.parse_args();print(json.dumps(build_runtime_update(args.baseline,args.baseline_sha256,args.output)))
