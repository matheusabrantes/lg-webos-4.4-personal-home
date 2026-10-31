"""Controlled TV-session actions. Physical changes require the recorded Mode 2 approval."""
import argparse,hashlib,json,shlex,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parents[1]/'work/abrantesflix'))
import tv

def shell(command,timeout=25):
    r=subprocess.run(tv.SSH+[tv.target(),command],capture_output=True,timeout=timeout)
    if r.returncode:raise RuntimeError(r.stderr.decode(errors='replace'))
    return r.stdout.decode(errors='replace')
def node(source,*args):return shell('/usr/bin/node -e '+shlex.quote(source)+' '+' '.join(map(shlex.quote,args)))
def authorize(meta,approved):
    if not approved:raise RuntimeError('Physical-session authorization flag missing')
    record=json.loads((HERE/'physical-authorization.json').read_text())
    if record.get('approved') is not True or record.get('expiresAt',0)<=time.time():raise RuntimeError('No current user authorization')
    if meta['releaseSha256'] not in record.get('releaseSha256',[]):raise RuntimeError('Release outside approved session')
    return record

def state(meta):
    code="""var f=require('fs'),c=require('crypto'),base=process.argv[1],runtime=process.argv[2];function read(p){try{return JSON.parse(f.readFileSync(p,'utf8'));}catch(e){return null;}}console.log(JSON.stringify({uptime:parseFloat(f.readFileSync('/proc/uptime','utf8')),bootId:f.readFileSync('/proc/sys/kernel/random/boot_id','utf8').trim(),targetSha256:c.createHash('sha256').update(f.readFileSync('/usr/bin/surface-manager-starfish')).digest('hex'),productionDisabled:f.existsSync('/var/lib/personalhome/disabled'),productionHookPresent:f.existsSync('/var/lib/webosbrew/init.d/90-personalhome'),validationHookPresent:f.existsSync('/var/lib/webosbrew/init.d/89-personalhome-validation'),health:read(runtime+'/health.json'),restored:read(runtime+'/restored.json'),context:read(runtime+'/context-restored.json'),activation:read(base+'/boot-activation.json'),failsafe:read(runtime+'/fault-failsafe-result.json')}));"""
    return json.loads(node(code,meta['validationState'],meta['runtime']))

def start(meta,boot_session):
    checks=json.loads((HERE/'stage-checks.json').read_text());entry=next(v for v in checks['releases'].values() if v['nonce']==meta['nonce']);stage=meta['remoteStage']
    actual=shell('sha256sum '+stage+'/install-validation.js').split()[0];assert actual==entry['helperSha256']['install-validation.js']
    return shell('/usr/bin/node '+stage+'/install-validation.js --install-validation-approved '+stage+' '+meta['releaseSha256']+' '+('boot-session' if boot_session else 'manual'),40)

def fault(meta,actor):
    stage=meta['remoteStage'];runtime=meta['runtime'];checks=json.loads((HERE/'stage-checks.json').read_text());entry=next(v for v in checks['releases'].values() if v['nonce']==meta['nonce'])
    for name in ['fault-failsafe.js']:
        assert shell('sha256sum '+stage+'/'+name).split()[0]==entry['helperSha256'][name]
    code=r'''var f=require('fs'),cp=require('child_process'),c=require('crypto'),runtime=process.argv[1],stage=process.argv[2],actor=process.argv[3],legacySha=process.argv[4];function ok(v){if(!v)throw Error('Fault preflight failed');}function start(pid){var s=f.readFileSync('/proc/'+pid+'/stat','utf8');return s.slice(s.lastIndexOf(')')+2).split(' ')[19];}
var m=JSON.parse(f.readFileSync(runtime+'/manifest.json')),h=JSON.parse(f.readFileSync(runtime+'/health.json')),context=JSON.parse(f.readFileSync(runtime+'/context-restored.json'));ok(h.nonce===m.nonce&&h.ready&&h.nativeContextAttached&&h.windowAttached&&h.renderProbe>0&&context.verified===true);
function luna(method){var r=cp.spawnSync('/usr/bin/timeout',['-t','2','/usr/bin/luna-send','-n','1','-w','1000','luna://'+method,'{}'],{encoding:'utf8'});ok(!r.error&&r.status===0);var reply=JSON.parse(r.stdout.slice(r.stdout.indexOf('{')));ok(reply.returnValue===true);return reply;}
var foreground=luna('com.webos.surfacemanager/getForegroundAppInfo');ok(foreground.foregroundAppInfo.some(function(row){return row.appId==='com.abrantesflix.app'&&row.windowType==='_WEBOS_WINDOW_TYPE_CARD';})&&luna('com.webos.surfacemanager/getCurrentState').currentState==='none');
var p=JSON.parse(f.readFileSync(runtime+'/'+(actor==='primary'?'primary-pid':'candidate-process')+'.json'));ok(p.pid>1&&start(p.pid)===p.start);
if(actor==='primary'){var command=f.readFileSync('/proc/'+p.pid+'/cmdline','utf8');ok(command.indexOf(runtime+'/guard.js')>=0&&command.indexOf('primary')>=0);}else ok(c.createHash('sha256').update(f.readFileSync('/proc/'+p.pid+'/exe')).digest('hex')===m.candidateSha);
var log=f.openSync(runtime+'/fault-failsafe.log','a',384),child=cp.spawn('/usr/bin/node',[stage+'/fault-failsafe.js',runtime,stage+'/legacy-guard.js',legacySha],{detached:true,stdio:['ignore',log,log]});f.closeSync(log);child.unref();
var until=Date.now()+5000;while(!f.existsSync(runtime+'/fault-failsafe-armed.json')){if(Date.now()>until)throw Error('Independent safety net did not arm');cp.spawnSync('/bin/sleep',['1']);}
ok(start(p.pid)===p.start);process.kill(p.pid,'SIGSTOP');f.writeFileSync(runtime+'/fault-injection.json',JSON.stringify({actor:actor,pid:p.pid,start:p.start,signal:'SIGSTOP',utc:new Date().toISOString()})+'\n',{mode:384});console.log(JSON.stringify({injected:true,actor:actor,independentSafetyNetArmed:true}));'''
    return node(code,runtime,stage,actor,entry['legacyGuardSha256'])

def session_limits():
    path=HERE/'physical-authorization.json'
    record=json.loads(path.read_text()) if path.exists() else {}
    limits=record.get('scopeOverride',{}) if record.get('approved') is True and record.get('expiresAt',0)>time.time() else {}
    cycles=limits.get('minimumCyclesPerButton',5);restarts=limits.get('maximumOSRestarts',3)
    if type(cycles) is not int or cycles not in [1,5] or type(restarts) is not int or restarts not in [1,3]:raise RuntimeError('Invalid approved session limits')
    return cycles,restarts

def reboot(meta):
    cycles,restarts=session_limits()
    matrix=json.loads((HERE/'qa-matrix.json').read_text());required=['REC-PRIMARY','REC-COMPOSITOR']+['%s-%s'%(prefix,i) for prefix in ['A','B','C'] for i in range(1,cycles+1)]
    passed={row['id'] for row in matrix['rows'] if row['status']=='PASS' and row['execution']=='physical'}
    if not set(required)<=passed:raise RuntimeError('Earlier physical recovery and startup gates have not passed')
    path=HERE/'os-restart-count.json';count=json.loads(path.read_text())['issued'] if path.exists() else 0
    if count>=restarts:raise RuntimeError('Approved OS restart limit already reached')
    before=state(meta);assert before['health'] and before['health']['ready'] and before['health']['renderProbe']>0
    path.write_text(json.dumps({'issued':count+1,'previousBootId':before['bootId']},indent=2)+'\n')
    try:return tv.luna('com.webos.service.sleep/shutdown/machineReboot',{'reason':'remoteKey'})
    except Exception:return {'issued':True,'replyLostDuringRestart':True,'automaticRetryAllowed':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['status','start-manual','start-boot-session','rollback','fault-primary','fault-compositor','reboot']);parser.add_argument('--release',choices=['guard-interruption','compositor-stall','lifecycle'],default='lifecycle');parser.add_argument('--approved',action='store_true');args=parser.parse_args()
    meta=json.loads((HERE/'release-pool.json').read_text())[args.release]
    if args.action!='status':authorize(meta,args.approved)
    if args.action=='status':result=state(meta)
    elif args.action.startswith('start-'):result=start(meta,args.action=='start-boot-session')
    elif args.action=='rollback':result=shell('/usr/bin/node '+meta['validationState']+'/release/rollback.js --rollback-validation-approved '+meta['validationState'])
    elif args.action.startswith('fault-'):result=fault(meta,'primary' if args.action=='fault-primary' else 'compositor')
    else:result=reboot(meta)
    print(json.dumps(result,ensure_ascii=False) if not isinstance(result,str) else result)
if __name__=='__main__':main()
