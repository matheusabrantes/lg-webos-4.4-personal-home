"""Generate an isolated Qt 5.6 adapter probe; never contacts the TV."""
import argparse
import hashlib
import json
import pathlib
import re
import shutil
from instrument_trial import instrument_ui

ROOT = pathlib.Path(__file__).resolve().parents[1]


def generate(destination, health_file, nonce):
    destination = pathlib.Path(destination)
    if destination.exists():
        raise ValueError('Probe destination already exists')
    match = re.fullmatch(r'/tmp/([A-Za-z0-9_.-]+)/health\.json', health_file)
    if not match or match.group(1) in ('.', '..'):
        raise ValueError('Health file must be inside one private /tmp directory')
    if not re.fullmatch(r'[a-f0-9]{32}', nonce):
        raise ValueError('Nonce must contain 32 lowercase hexadecimal characters')
    adapter = (ROOT / 'integration/native_home_loader.qml.inc').read_text()
    ui = instrument_ui((ROOT / 'qml/PersonalHome.qml').read_text())
    template = (pathlib.Path(__file__).with_name('adapter_probe.qml.in')).read_text()
    harness = template.replace('@@ADAPTER@@', adapter).replace('@@NONCE@@', json.dumps(nonce)).replace('@@HEALTH_URL@@', json.dumps('file://' + health_file))
    destination.mkdir(parents=True)
    shutil.copytree(ROOT / 'qml', destination / 'PersonalHome',
                    copy_function=lambda source, target: pathlib.Path(target).write_bytes(pathlib.Path(source).read_bytes()))
    (destination / 'PersonalHome/PersonalHome.qml').write_text(ui)
    (destination / 'AdapterProbe.qml').write_text(harness)
    focus_source = ROOT.parent / 'lg-native-home-feasibility-2026-10-22/resources/ysm/YSM/Common/FocusHandler.js'
    (destination / 'FocusHandler.js').write_bytes(focus_source.read_bytes())
    manifest = {'kind': 'isolated-adapter-probe', 'compositorContext': 'simulated',
                'nativeContextAttached': False, 'physicalRenderingProven': False,
                'healthFile': health_file, 'nonce': nonce, 'intervalMs': 250, 'maximumDurationMs': 10000,
                'adapterSha256': hashlib.sha256(adapter.encode()).hexdigest(),
                'actualUiSourceSha256': hashlib.sha256((ROOT / 'qml/PersonalHome.qml').read_bytes()).hexdigest()}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=pathlib.Path)
    parser.add_argument('--health-file', required=True)
    parser.add_argument('--nonce', required=True)
    args = parser.parse_args()
    print(json.dumps(generate(args.destination, args.health_file, args.nonce), indent=2))
