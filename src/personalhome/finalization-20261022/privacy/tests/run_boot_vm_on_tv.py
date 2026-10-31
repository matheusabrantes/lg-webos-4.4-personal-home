"""Optional native Node VM checks: all consumer RPCs mocked, stdin only, no files installed."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parents[4]
PRELUDE = r'''
var fs=require('fs'),vm=require('vm'),assert=require('assert');
if(process.version!=='v0.12.2')throw Error('Unexpected target Node version');
var value=JSON.parse(fs.readFileSync('/proc/self/fd/0','utf8'));
var virtualFs={readFileSync:function(path,encoding){
  if(encoding!=='utf8')throw Error('Unexpected encoding');
  if(/\/boot-flags\.js$/.test(path))return value.helper;
  if(/\/62-personalhome-privacy$/.test(path))return value.hook;
  throw Error('Virtual file not allowed');
}};
vm.runInNewContext(value.tests,{__dirname:'/virtual/tests',Buffer:Buffer,
  TARGET_NODE_VERSION:process.version,process:process,
  require:function(name){
    if(name==='fs')return virtualFs;
    if(name==='vm')return vm;
    if(name==='assert')return assert;
    throw Error('Module not allowed');
  }});
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-native-mocked-check', action='store_true')
    args = parser.parse_args()
    if not args.execute_native_mocked_check:
        parser.error('Explicit selection of the native mocked check is required')
    sys.path.insert(0, str(WORKSPACE / 'work/abrantesflix'))
    import tv
    payload = {'helper': (HERE.parent / 'boot-candidate/boot-flags.js').read_text(),
               'hook': (HERE.parent / 'boot-candidate/62-personalhome-privacy').read_text(),
               'tests': (HERE / 'test_boot_flags.js').read_text()}
    completed = subprocess.run(tv.SSH + [tv.target(), '/usr/bin/node -e ' + shlex.quote(PRELUDE)],
                               input=json.dumps(payload).encode(), capture_output=True, timeout=25)
    output = completed.stdout.decode(errors='replace')
    if completed.returncode:
        sys.stderr.write(completed.stderr.decode(errors='replace'))
        raise SystemExit(completed.returncode)
    result = json.loads(output.strip().splitlines()[-1])
    if result != {'passed': 11, 'failed': 0, 'nativeNodeExecuted': True, 'nodeVersion': 'v0.12.2'}:
        raise RuntimeError('Native mocked result differs')
    print(output, end='')


if __name__ == '__main__':
    main()
