"""Run the actual controller fault gate in a VM; all signals and spawns are mocked."""
import ast,json,subprocess,unittest
from pathlib import Path
ROOT=Path(__file__).parent
function=next(n for n in ast.parse((ROOT/'device_session.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='fault')
SOURCE=next(ast.literal_eval(n.value) for n in ast.walk(function) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='code' for t in n.targets))
RUNNER=r'''var vm=require('vm'),assert=require('assert'),config=JSON.parse(require('fs').readFileSync(0,'utf8')),runtime='/tmp/lg-native-production.test',kills=[],spawns=0;
var health={nonce:'nonce',ready:true,nativeContextAttached:true,windowAttached:true,renderProbe:2,foregroundAppId:'com.webos.app.livetv',shown:true};
var stat=['R'];while(stat.length<22)stat.push('0');stat[19]='123';
var data={};data[runtime+'/manifest.json']=JSON.stringify({nonce:'nonce'});data[runtime+'/health.json']=JSON.stringify(health);data[runtime+'/context-restored.json']=JSON.stringify({verified:true});data[runtime+'/primary-pid.json']=JSON.stringify({pid:55,start:'123'});data['/proc/55/stat']='55 (guard) '+stat.join(' ');data['/proc/55/cmdline']=runtime+'/guard.js primary';
var filesystem={readFileSync:function(p){assert(p in data,p);return data[p];},existsSync:function(p){assert.equal(p,runtime+'/fault-failsafe-armed.json');return true;},openSync:function(){return 1;},closeSync:function(){},writeFileSync:function(p,body){data[p]=body;}};
var child={spawnSync:function(cmd,args){assert.equal(cmd,'/usr/bin/timeout');var method=args[args.length-2],reply={returnValue:true};if(method.indexOf('getForegroundAppInfo')>=0)reply.foregroundAppInfo=[{appId:config.app,windowType:'_WEBOS_WINDOW_TYPE_CARD'}];else if(method.indexOf('getCurrentState')>=0)reply.currentState=config.state;else throw Error('Unexpected native command');return {status:0,stdout:JSON.stringify(reply)};},spawn:function(){spawns++;return {unref:function(){}};}};
var error=null;try{vm.runInNewContext(config.source,{require:function(n){if(n==='fs')return filesystem;if(n==='child_process')return child;if(n==='crypto')return require('crypto');throw Error(n);},Date:Date,console:{log:function(){}},process:{argv:['node',runtime,'/tmp/stage','primary','legacy-sha'],kill:function(pid,signal){kills.push([pid,signal]);}}});}catch(e){error=String(e);}
console.log(JSON.stringify({kills:kills,spawns:spawns,error:error}));'''
class FaultGate(unittest.TestCase):
    def run_gate(self,app,state):
        r=subprocess.run(['node','-e',RUNNER],input=json.dumps(dict(source=SOURCE,app=app,state=state)),text=True,capture_output=True,check=True);return json.loads(r.stdout)
    def test_native_card_can_prove_target_while_hidden_qml_fields_are_stale(self):
        result=self.run_gate('com.abrantesflix.app','none');self.assertIsNone(result['error']);self.assertEqual(result['kills'],[[55,'SIGSTOP']]);self.assertEqual(result['spawns'],1)
    def test_another_native_app_cannot_be_faulted(self):
        result=self.run_gate('netflix','none');self.assertIsNotNone(result['error']);self.assertEqual(result['kills'],[]);self.assertEqual(result['spawns'],0)
    def test_visible_home_cannot_be_faulted(self):
        result=self.run_gate('com.abrantesflix.app','home');self.assertIsNotNone(result['error']);self.assertEqual(result['kills'],[]);self.assertEqual(result['spawns'],0)
if __name__=='__main__':unittest.main()
