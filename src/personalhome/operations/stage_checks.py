"""Stage immutable sources and run isolated compatibility checks. No Home activation."""
import hashlib,io,json,shlex,subprocess,sys,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT.parents[1]/'work/abrantesflix'))
import tv

def run(cmd,timeout=45):
    result=subprocess.run(tv.SSH+[tv.target(),cmd],capture_output=True,timeout=timeout)
    if result.returncode:raise RuntimeError(result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
    return result.stdout.decode(errors='replace')
def stage(meta):
    release=Path(meta['release']);m=json.loads((release/'release.json').read_text());assert hashlib.sha256((release/'release.json').read_bytes()).hexdigest()==meta['releaseSha256']
    baseline=json.loads((HERE/'baseline.json').read_text());legacy=Path(baseline['release'])/'guard.js'
    for name in ['guard.js','policy.js','bootstrap.js','rollback.js']:assert (release/name).read_bytes()==(HERE/'runtime'/name).read_bytes(),'Source changed after build: '+name
    extra={'release.json':(release/'release.json').read_bytes(),'install.js':(HERE/'runtime/install.js').read_bytes(),'install-validation.js':(HERE/'runtime/install-validation.js').read_bytes(),'fault-failsafe.js':(HERE/'fault_failsafe.js').read_bytes(),'legacy-guard.js':legacy.read_bytes(),'native_asset_probe.py':(HERE/'native_asset_probe.py').read_bytes(),'qt56_runtime.py':(ROOT/'diagnostics/qt56_runtime.py').read_bytes(),'compile.py':(ROOT/'diagnostics/qt56_compile_probe.py').read_text().replace("open('/usr/bin/surface-manager-starfish', 'rb')","open('/var/lib/personalhome/release/original', 'rb')").encode()}
    for name in ['test_guard.js','test_policy.js','test_bootstrap.js']:extra['tests/'+name]=(HERE/name).read_bytes()
    for name in ['guard.js','policy.js','bootstrap.js','rollback.js']:extra['tests/runtime/'+name]=(HERE/'runtime'/name).read_bytes()
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w:gz') as tar:
        data={name:(release/name).read_bytes() for name in m['files']}
        for name,digest in m['files'].items():assert hashlib.sha256(data[name]).hexdigest()==digest
        for name,body in dict(data,**extra).items():
            info=tarfile.TarInfo(name);info.size=len(body);info.mode=0o600;tar.addfile(info,io.BytesIO(body))
    remote=meta['remoteStage'];command='umask 077; mkdir '+shlex.quote(remote)+' && tar -xz -C '+shlex.quote(remote)
    reply=subprocess.run(tv.SSH+[tv.target(),command],input=archive.getvalue(),capture_output=True,timeout=45);assert reply.returncode==0,reply.stderr.decode(errors='replace')
    urls=['YSM.qml','PersonalHome/PersonalHome.qml','PersonalHome/InputsController.qml','PersonalHome/InputDropdown.qml']
    text=run('python '+remote+'/compile.py '+remote+'/module '+' '.join('file://'+remote+'/module/YSM/'+name for name in urls))
    rows=[json.loads(line) for line in text.splitlines() if line.strip().startswith('{')];assert len(rows)==4 and all(row['status']==1 and row['error']=='' and row['nativeRootCreated'] is False for row in rows)
    return {'nonce':meta['nonce'],'releaseSha256':meta['releaseSha256'],'qtCompile':rows,'legacyGuardSha256':hashlib.sha256(legacy.read_bytes()).hexdigest(),'helperSha256':{name:hashlib.sha256(extra[name]).hexdigest() for name in ['install-validation.js','fault-failsafe.js','install.js']}}
if __name__=='__main__':
    pool=json.loads((HERE/'release-pool.json').read_text());reports={}
    for name,meta in pool.items():reports[name]=stage(meta);print(json.dumps({'staged':name,'qt':'5.6.2','components':4,'activated':False}),flush=True)
    native={};remote=pool['lifecycle']['remoteStage']
    for script in ['test_guard.js','test_policy.js','test_bootstrap.js']:
        out=run('/usr/bin/timeout -t 30 /usr/bin/node '+remote+'/tests/'+script+(' '+remote if script=='test_bootstrap.js' else ''),38)
        (HERE/'evidence'/('native-'+script+'.log')).write_text(out);last=json.loads([line for line in out.splitlines() if line.startswith('{')][-1]);assert last['passed'];native[script]=last
    assets=run('python '+remote+'/native_asset_probe.py '+remote+'/module/YSM/PersonalHome');(HERE/'evidence/native-assets.jsonl').write_text(assets);assetResult=json.loads([line for line in assets.splitlines() if line.startswith('{')][-1]);assert assetResult['passed']
    syntax=run('/usr/bin/node -e '+shlex.quote("var f=require('fs'),vm=require('vm');process.argv.slice(1).forEach(function(p){new vm.Script(f.readFileSync(p,'utf8'));});console.log(JSON.stringify({passed:true,nativeOperations:0}));")+' '+remote+'/install-validation.js '+remote+'/fault-failsafe.js '+remote+'/install.js');assert json.loads(syntax)['passed']
    (HERE/'stage-checks.json').write_text(json.dumps({'releases':reports,'nativeSimulatedTests':native,'nativeAssets':assetResult,'helperSyntax':json.loads(syntax),'activated':False},indent=2)+'\n');print(json.dumps({'nativeTests':native,'nativePhotoDecodes':assetResult['photos'],'activated':False}))
