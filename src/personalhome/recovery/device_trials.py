"""Bounded device recovery gates. No installation or boot hook."""
import argparse
import hashlib
import json
import io
import secrets
import tarfile
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
sys.path.insert(0, str(WORKSPACE / 'work/abrantesflix'))
import tv

ORIGINAL_SHA = '5d2c9872f8b2c918c605cd05a7c49844645a8b683d8c1f8ee55f7bb1be6738e9'
OUT = ROOT / 'physical'
sys.path.insert(0, str(ROOT / 'diagnostics'))
from instrument_trial import instrument
from view_health import validate as validate_health


def remote(command, content=None):
    run = subprocess.run(tv.SSH + [tv.target(), command], input=content,
                         capture_output=True, timeout=25)
    if run.returncode:
        raise RuntimeError('Trial command failed: ' + run.stderr.decode(errors='replace'))
    return run.stdout.decode(errors='replace')


def put(path, content, mode='600'):
    remote('umask 077; cat > ' + shlex.quote(path) + ' && chmod ' + mode + ' ' + shlex.quote(path), content)
    assert remote('sha256sum ' + shlex.quote(path)).split()[0] == hashlib.sha256(content).hexdigest()


def prepare(kind, duration, label, identical=False, native_candidate=False, candidate_build=None, profile=False):
    assert kind in ('canary', 'freeze', 'native')
    directory = remote('umask 077; mktemp -d /tmp/lg-native-trial.XXXXXXXX').strip()
    assert directory.startswith('/tmp/lg-native-trial.') and directory.replace('.', '').replace('-', '').replace('/', '').isalnum()
    if kind == 'canary':
        original, candidate = b"#!/bin/sh\nprintf '%s\\n' original\n", b"#!/bin/sh\nprintf '%s\\n' candidate\n"
        if identical: candidate = original
        target = directory + '/target'
        put(target, original, '700')
        pid = start = None
    else:
        target = '/usr/bin/surface-manager-starfish'
        original = tv.shell('cat ' + target, raw=True)
        assert hashlib.sha256(original).hexdigest() == ORIGINAL_SHA
        candidate = original
        if native_candidate:
            build = Path(candidate_build or ROOT / 'build/native-candidate-final')
            build_manifest = json.loads((build / 'manifest.json').read_text())
            candidate = (build / 'surface-manager-starfish.candidate').read_bytes()
            assert hashlib.sha256(candidate).hexdigest() == build_manifest['candidateSha256']
        pid = int(remote('pidof surface-manager-starfish').strip())
        raw = remote('cat /proc/' + str(pid) + '/stat')
        start = raw[raw.rfind(')') + 2:].split()[19]
        assert remote('readlink /proc/' + str(pid) + '/exe').strip() == target
    put(directory + '/original', original, '700')
    put(directory + '/candidate', candidate, '700')
    put(directory + '/guard.js', (ROOT / 'recovery/device-guard.js').read_bytes())
    namespace = remote('readlink /proc/self/ns/mnt').strip()
    assert remote('readlink /proc/1/ns/mnt').strip() == namespace
    nonce = secrets.token_hex(16) if native_candidate else None
    module_identity = prepare_trial_module(directory, nonce, candidate_build, profile) if native_candidate else None
    manifest = {'kind': kind, 'directory': directory, 'target': target,
                'original': directory + '/original', 'candidate': directory + '/candidate',
                'originalSha': hashlib.sha256(original).hexdigest(),
                'candidateSha': hashlib.sha256(candidate).hexdigest(),
                'candidateIdentity': remote("stat -c '%d:%i' " + directory + '/candidate').strip(),
                'namespace': namespace, 'deadline': float(remote('cut -d " " -f 1 /proc/uptime')) + duration,
                'pid': pid, 'processStart': start, 'requireViewHealth': native_candidate,
                'nonce': nonce, 'moduleIdentity': module_identity}
    put(directory + '/manifest.json', (json.dumps(manifest) + '\n').encode())
    for role in ('lifeline', 'primary'):
        command = 'setsid /usr/bin/node ' + directory + '/guard.js ' + directory + '/manifest.json ' + role
        remote(command + ' < /dev/null > ' + directory + '/' + role + '.log 2>&1 &')
    for _ in range(20):
        if remote('test -s ' + directory + '/lifeline-pid.json && test -s ' + directory + '/primary-pid.json && printf ready || true').strip() == 'ready':
            break
        time.sleep(.1)
    else:
        raise RuntimeError('Guards did not start')
    return manifest


def prepare_trial_module(directory, nonce, candidate_build=None, profile=False):
    build = Path(candidate_build or ROOT / 'build/native-candidate-final')
    report = json.loads((build / 'manifest.json').read_text())
    files = {}
    for name, digest in report['moduleFiles'].items():
        assert name.startswith('YSM/') and '..' not in Path(name).parts
        content = (build / 'module' / name).read_bytes()
        assert hashlib.sha256(content).hexdigest() == digest
        files[name] = content
    files = instrument(files, directory, nonce, profile=profile)
    assert remote('test ! -e /tmp/YSM && printf absent').strip() == 'absent'
    remote('mkdir -m 700 /tmp/YSM')
    memory = io.BytesIO()
    with tarfile.open(fileobj=memory, mode='w:gz') as archive:
        for name, content in files.items():
            member = tarfile.TarInfo(name);member.size=len(content);member.mode=0o600
            archive.addfile(member, io.BytesIO(content))
    put(directory + '/module.tgz', memory.getvalue())
    remote('tar -xzf ' + directory + '/module.tgz -C /tmp')
    expected = {name:hashlib.sha256(content).hexdigest() for name,content in files.items()}
    put(directory + '/module-hashes.json', (json.dumps(expected)+'\n').encode())
    verifier = "var fs=require('fs'),c=require('crypto'),m=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));Object.keys(m).forEach(function(p){var b=fs.readFileSync('/tmp/'+p);if(c.createHash('sha256').update(b).digest('hex')!==m[p])throw Error('Module mismatch');});console.log('verified');"
    assert remote('/usr/bin/node -e ' + shlex.quote(verifier) + ' ' + directory + '/module-hashes.json').strip() == 'verified'
    (OUT / 'candidate-trial-module-hashes.json').write_text(json.dumps(expected, indent=2)+'\n')
    return remote("stat -c '%d:%i' /tmp/YSM").strip()


def result(manifest, label):
    directory = manifest['directory']
    deadline = time.monotonic() + (40 if manifest['kind'] == 'native' else 22)
    while time.monotonic() < deadline:
        if remote('test -s ' + directory + '/restored.json && printf restored || true').strip() == 'restored':
            report = {'label': label, 'manifest': manifest,
                      'restoration': json.loads(remote('cat ' + directory + '/restored.json')),
                      'events': [json.loads(line) for line in remote('cat ' + directory + '/guard-events.jsonl').splitlines()],
                      'guardLogs': remote('cat ' + directory + '/lifeline.log ' + directory + '/primary.log'),
                      'remainingTargetMounts': remote('awk -v target=' + shlex.quote(manifest['target']) + " '$5==target{print}' /proc/self/mountinfo")}
            assert report['restoration']['originalSha'] == manifest['originalSha']
            assert not report['remainingTargetMounts']
            OUT.mkdir(exist_ok=True)
            (OUT / (label + '.json')).write_text(json.dumps(report, indent=2) + '\n')
            return report
        time.sleep(.3)
    raise RuntimeError('No verified restoration; inspect ' + directory + ' guards immediately')


def request_apply(manifest):
    directory = manifest['directory']
    put(directory + '/apply-request', b'apply\n')
    for _ in range(80):
        if remote('test -s ' + directory + '/restored.json && printf restored || true').strip() == 'restored':
            raise RuntimeError('Trial restored before apply acknowledgment')
        if remote('test -s ' + directory + '/applied.json && printf applied || true').strip() == 'applied':
            assert_active(manifest)
            return
        time.sleep(.1)
    raise RuntimeError('No apply acknowledgment')


def assert_active(manifest):
    directory = manifest['directory']
    assert remote('test ! -e ' + directory + '/restored.json && printf active').strip() == 'active'
    if manifest['kind'] != 'freeze':
        mount_id = remote('awk -v target=' + manifest['target'] + " '$5==target{print $1}' /proc/self/mountinfo").strip()
        assert mount_id and mount_id == remote('cat ' + directory + '/mount-id').strip()
        assert remote("stat -c '%d:%i' " + manifest['target']).strip() == manifest['candidateIdentity']
        if manifest['kind'] == 'native':
            pid = int(remote('pidof surface-manager-starfish').strip())
            assert remote('sha256sum /proc/'+str(pid)+'/exe').split()[0] == manifest['candidateSha']
            assert remote("stat -Lc '%d:%i' /proc/"+str(pid)+'/exe').strip() == manifest['candidateIdentity']



def request_abort(manifest):
    put(manifest['directory'] + '/abort.json', b'{"reason":"host-abort"}\n')
    return result(manifest, 'host-abort-' + manifest['kind'])


def ensure_home():
    assert tv.luna('com.webos.service.networkinput/sendSpecialKey', {'key': 'BACK'}).get('returnValue')
    time.sleep(.2)
    assert tv.luna('com.webos.service.networkinput/sendSpecialKey', {'key': 'HOME'}).get('returnValue')
    stable = 0
    for n in range(30):
        state = tv.luna('com.webos.surfacemanager/getCurrentState', {})
        stable = stable + 1 if state.get('currentState') == 'home' else 0
        if stable >= 3: return state
        if n == 12:
            tv.luna('com.webos.service.networkinput/sendSpecialKey', {'key': 'BACK'})
            tv.luna('com.webos.service.networkinput/sendSpecialKey', {'key': 'HOME'})
        time.sleep(.1)
    raise RuntimeError('Original Home did not remain ready')


def capture(label):
    assert label.replace('-', '').isalnum()
    path = '/tmp/lg-native-shot-' + label + '.png'
    assert tv.luna('com.webos.service.tv.capture/executeOneShot', {'path': path, 'method': 'DISPLAY', 'format': 'PNG', 'width': 1920, 'height': 1080}).get('returnValue')
    content = tv.shell('cat ' + path + ' && rm -f ' + path, raw=True)
    assert content.startswith(b'\x89PNG\r\n\x1a\n')
    (OUT / (label + '.png')).write_bytes(content)


def canary(label, kill_role=None, identical=False):
    manifest = prepare('canary', 5, label, identical=identical)
    directory, target = manifest['directory'], manifest['target']
    try:
        request_apply(manifest)
        assert remote(target).strip() == ('original' if identical else 'candidate')
        assert remote("stat -c '%d:%i' " + target).strip() == manifest['candidateIdentity']
        if kill_role:
            assert kill_role in ('primary', 'lifeline')
            guard = json.loads(remote('cat ' + directory + '/' + kill_role + '-pid.json'))
            raw = remote('cat /proc/' + str(guard['pid']) + '/stat')
            assert raw[raw.rfind(')') + 2:].split()[19] == guard['start']
            assert directory + '/guard.js' in remote("tr '\\000' ' ' < /proc/" + str(guard['pid']) + '/cmdline')
            remote('kill -KILL ' + str(guard['pid']))
        # The launching SSH sessions have already ended; recovery runs on the TV.
        report = result(manifest, label)
        assert remote(target).strip() == 'original'
        return report
    except BaseException:
        request_abort(manifest)
        raise


def late_apply():
    manifest = prepare('canary', 4, 'late-apply')
    report = result(manifest, 'late-apply')
    put(manifest['directory'] + '/apply-request', b'late\n')
    time.sleep(.5)
    assert remote(manifest['target']).strip() == 'original'
    assert not remote('awk -v target=' + manifest['target'] + " '$5==target{print}' /proc/self/mountinfo").strip()
    assert remote('test ! -e ' + manifest['directory'] + '/applied.json && printf never-applied').strip() == 'never-applied'
    report['lateRequestIgnored'] = True
    (OUT / 'late-apply.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def freeze():
    manifest = prepare('freeze', 6, 'freeze-original')
    directory, pid = manifest['directory'], manifest['pid']
    try:
        raw = remote('cat /proc/' + str(pid) + '/stat')
        assert raw[raw.rfind(')') + 2:].split()[19] == manifest['processStart']
        request_apply(manifest)
        raw = remote('cat /proc/' + str(pid) + '/stat')
        state = raw[raw.rfind(')') + 2:].split()[0]
        assert state == 'T', 'Original process did not stop as expected'
        ssh_while_stopped = remote('printf ssh-alive; cat /proc/uptime').strip()
        report = result(manifest, 'freeze-original')
        raw = remote('cat /proc/' + str(pid) + '/stat')
        assert raw[raw.rfind(')') + 2:].split()[0] != 'T'
        report['proof'] = {'stoppedState': state, 'sshWhileStopped': ssh_while_stopped,
                           'samePidAndStartAfterResume': raw[raw.rfind(')') + 2:].split()[19] == manifest['processStart'],
                           'surfaceManagerAfter': tv.luna('com.webos.surfacemanager/getCurrentState', {})}
        (OUT / 'freeze-original.json').write_text(json.dumps(report, indent=2) + '\n')
        return report
    except BaseException:
        request_abort(manifest)
        raise


def original_bind():
    assert remote('/usr/bin/timeout -t 1 /bin/true && initctl status surface-manager').startswith('surface-manager start/running')
    manifest = prepare('native', 90, 'original-bind')
    try:
        request_apply(manifest)
        during_pid = int(remote('pidof surface-manager-starfish').strip())
        assert during_pid != manifest['pid']
        assert remote('sha256sum /proc/' + str(during_pid) + '/exe').split()[0] == ORIGINAL_SHA
        during = ensure_home()
        assert_active(manifest)
        capture('identity-bind-during')
        assert_active(manifest)
        request_abort(manifest)
        report = result(manifest, 'original-bind')
        after_pid = int(remote('pidof surface-manager-starfish').strip())
        assert after_pid != during_pid
        assert remote('sha256sum /proc/' + str(after_pid) + '/exe').split()[0] == ORIGINAL_SHA
        after = ensure_home()
        assert tv.luna('com.webos.service.networkinput/sendSpecialKey', {'key': 'RIGHT'}).get('returnValue')
        capture('identity-bind-restored')
        report['proof'] = {'pidBefore': manifest['pid'], 'pidDuring': during_pid, 'pidAfter': after_pid,
                           'duringState': during, 'afterState': after, 'originalExecutableAfter': True}
        (OUT / 'original-bind.json').write_text(json.dumps(report, indent=2) + '\n')
        return report
    except BaseException:
        request_abort(manifest)
        raise


def candidate_trial(candidate_build=None, physical_authorized=False):
    if not physical_authorized:
        raise ValueError("Explicit authorization is required before interacting with the compositor")
    prior = json.loads((OUT / 'original-bind.json').read_text())
    assert prior['proof']['originalExecutableAfter'] and prior['restoration']['mountAbsent']
    manifest = prepare('native', 120, 'diagnostic-candidate-trial', native_candidate=True, candidate_build=candidate_build)
    directory = manifest['directory']
    report = {'manifest': manifest, 'candidateActivated': False, 'viewHealth': [], 'keys': [], 'physicalVisualReview': 'pending', 'candidateBuild':str(candidate_build)}
    (OUT/'diagnostic-candidate-trial.json').write_text(json.dumps(report,indent=2)+'\n')
    try:
        request_apply(manifest)
        report['candidateActivated'] = True
        ensure_home()
        def health(previous=None, key=None, expected_index=None):
            failure = 'No fresh accepted view heartbeat'
            for _ in range(40):
                if remote('test -s '+directory+'/restored.json && printf restored || true').strip() == 'restored':
                    raise RuntimeError('Candidate reverted before accepted view health')
                raw = remote('test ! -s '+directory+'/health.json || cat '+directory+'/health.json').strip()
                if raw:
                    try:
                        value = validate_health(json.loads(raw), manifest['nonce'], previous, key, expected_index)
                    except ValueError as error:
                        failure = str(error)
                    else:
                        report['viewHealth'].append(value)
                        return value
                time.sleep(.15)
            raise RuntimeError(failure)
        first = health()
        assert_active(manifest)
        capture('diagnostic-native-candidate')
        index = first['focusIndex']
        if index > 5:
            raise RuntimeError('Initial selection is outside the application row; aborting controlled navigation')
        direction, reverse, expected = ('RIGHT','LEFT',index+1) if index < 5 else ('LEFT','RIGHT',index-1)
        previous = first
        for key, key_code, selection in [(direction,16777236 if direction=='RIGHT' else 16777234,expected),
                                          (reverse,16777236 if reverse=='RIGHT' else 16777234,index)]:
            assert tv.luna('com.webos.service.networkinput/sendSpecialKey', {'key':key}).get('returnValue')
            value = health(previous, key_code, selection)
            report['keys'].append({'key':key,'expected':selection,'actual':value['focusIndex']})
            previous = value
        capture('diagnostic-native-candidate-navigated')
        for _ in range(10):
            raw = remote('test ! -s '+directory+'/health-received.json || cat '+directory+'/health-received.json').strip()
            try: receipt = json.loads(raw)
            except ValueError: receipt = {}
            if receipt.get('nonce')==manifest['nonce'] and receipt.get('sequence',-1)>=previous['sequence']:
                report['independentMonitorReceipt'] = receipt
                break
            time.sleep(.15)
        else: raise RuntimeError('Independent monitor did not receive the accepted heartbeat')
        assert report['independentMonitorReceipt']['ready'] is True
        assert report['independentMonitorReceipt']['nativeContextAttached'] is True
        assert_active(manifest)
        report['acceptanceSignalsPassed'] = True
        report['benchmarkExecuted'] = False
    except BaseException as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        (OUT/'diagnostic-candidate-trial.json').write_text(json.dumps(report,indent=2)+'\n')
    finally:
        try:
            diagnostic = remote('test ! -s '+directory+'/diagnostics.json || cat '+directory+'/diagnostics.json').strip()
            if diagnostic:
                try: report['entryDiagnostics'] = json.loads(diagnostic)
                except ValueError: report['entryDiagnosticsRaw'] = diagnostic
        except Exception as error:
            report['diagnosticReadError'] = str(error)
        restoration = request_abort(manifest)
        report['restoration'] = restoration
        (OUT/'diagnostic-candidate-trial.json').write_text(json.dumps(report,indent=2)+'\n')
        report['originalAfter'] = ensure_home()
        original_pid = int(remote('pidof surface-manager-starfish').strip())
        assert remote('sha256sum /proc/'+str(original_pid)+'/exe').split()[0] == ORIGINAL_SHA
        capture('diagnostic-native-trial-restored')
        assert remote("stat -c '%d:%i' /tmp/YSM").strip() == manifest['moduleIdentity']
        assert remote('cat /tmp/YSM/.trial-owner').strip() == manifest['nonce']
        remote('rm -rf /tmp/YSM')
        (OUT/'diagnostic-candidate-trial.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gate', choices=['canary', 'identity-canary', 'monitor-death', 'lifeline-death', 'late-apply', 'freeze', 'original-bind', 'candidate'])
    parser.add_argument('--candidate-build', type=Path)
    parser.add_argument('--physical-authorized', action='store_true', help='Use only after explicit authorization for this trial')
    args = parser.parse_args()
    if args.gate == 'candidate':
        if not args.physical_authorized or args.candidate_build is None:
            parser.error("candidate requires a reviewed --candidate-build and explicit --physical-authorized")
        report = candidate_trial(args.candidate_build, physical_authorized=True)
        print(json.dumps({'gate':'candidate', 'acceptanceSignalsPassed':report.get('acceptanceSignalsPassed',False), 'error':report.get('error'), 'originalRestored':True, 'report':str(OUT/'diagnostic-candidate-trial.json')},indent=2))
        sys.exit(1 if 'error' in report else 0)
    if args.gate == 'freeze': report = freeze()
    elif args.gate == 'original-bind': report = original_bind()
    elif args.gate == 'late-apply': report = late_apply()
    else: report = canary(args.gate, kill_role={'monitor-death':'primary','lifeline-death':'lifeline'}.get(args.gate), identical=args.gate == 'identity-canary')
    print(json.dumps({'gate': args.gate, 'restoration': report['restoration'],
                      'deviceUiChanged': args.gate in ('freeze', 'original-bind'), 'report': str(OUT / (('freeze-original' if args.gate == 'freeze' else args.gate) + '.json'))}, indent=2))
