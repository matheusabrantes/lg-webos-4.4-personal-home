"""Read-only session sampling. A sample is not a physical QA confirmation."""
import argparse,datetime,json,time
from pathlib import Path
import device_session as session

PROBE=r'''var f=require('fs'),cp=require('child_process'),runtime=process.argv[1];function read(p){try{return f.readFileSync(p,'utf8');}catch(e){return null;}}function json(p){try{return JSON.parse(read(p));}catch(e){return null;}}var pid=cp.spawnSync('/bin/pidof',['surface-manager-starfish'],{encoding:'utf8'}).stdout.trim();if(!/^\d+$/.test(pid))throw Error('Expected one compositor');var stat=read('/proc/'+pid+'/stat'),fields=stat.slice(stat.lastIndexOf(')')+2).split(' '),smaps=read('/proc/'+pid+'/smaps')||'',memory={};['Rss','Pss','Private_Clean','Private_Dirty','Swap'].forEach(function(key){var pattern=new RegExp('^'+key+':\\s+(\\d+) kB','gm'),m,total=0;while((m=pattern.exec(smaps)))total+=Number(m[1]);memory[key+'KiB']=total;});var cpu=read('/proc/stat').split('\n')[0].trim().split(/\s+/).slice(1,9).map(Number).reduce(function(a,b){return a+b;},0);console.log(JSON.stringify({uptime:parseFloat(read('/proc/uptime')),bootId:read('/proc/sys/kernel/random/boot_id').trim(),pid:Number(pid),processStart:fields[19],processTicks:Number(fields[11])+Number(fields[12]),systemTicks:cpu,compositorMemory:memory,meminfo:read('/proc/meminfo'),health:json(runtime+'/health.json'),acceptedHealth:json(runtime+'/health-received.json'),context:json(runtime+'/context-restored.json'),restored:json(runtime+'/restored.json'),faultFailsafe:json(runtime+'/fault-failsafe-result.json')}));'''

def cpu_fraction(previous,current):
    if not previous or (previous['bootId'],previous['pid'],previous['processStart'])!=(current['bootId'],current['pid'],current['processStart']):return None
    elapsed=current['systemTicks']-previous['systemTicks'];used=current['processTicks']-previous['processTicks']
    return used/elapsed if elapsed>0 and used>=0 else None

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--release',choices=['guard-interruption','compositor-stall','lifecycle'],default='lifecycle');parser.add_argument('--minutes',type=int,default=75);args=parser.parse_args();assert 1<=args.minutes<=180
    meta=json.loads((session.HERE/'release-pool.json').read_text())[args.release]
    output=session.HERE/'private';output.mkdir(exist_ok=True);path=output/('observation-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'.jsonl')
    started=time.monotonic();previous=None;count=0
    with path.open('x') as log:
        while time.monotonic()-started<args.minutes*60:
            sample={'hostUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'hostElapsedSeconds':time.monotonic()-started,'releaseSha256':meta['releaseSha256'],'physicalConfirmation':False}
            try:
                current=json.loads(session.node(PROBE,meta['runtime']));sample.update(current);sample['cpuFractionAllCores']=cpu_fraction(previous,current);previous=current
            except Exception as error:sample['readError']=str(error);previous=None
            log.write(json.dumps(sample)+'\n');log.flush();count+=1
            if count%6==1:print(json.dumps({'samples':count,'elapsed':sample['hostElapsedSeconds'],'readError':sample.get('readError'),'physicalAcceptanceInferred':False}),flush=True)
            time.sleep(min(10,max(0,args.minutes*60-(time.monotonic()-started))))
    print(json.dumps({'log':str(path),'samples':count,'elapsedSeconds':time.monotonic()-started,'physicalAcceptanceInferred':False}))
if __name__=='__main__':main()
