"""Prepare the existing writable BootManager override; no device operations."""
import copy
import hashlib
import json

BRIDGE_ID = 'com.personalhome.startup'
BOOTD_SHA256 = 'bfcea033f28c7e90688b70cade2dac22fedff7f46bc8d41111daade21f934e43'


def prepare(original):
    if not isinstance(original, bytes) or not 0 < len(original) <= 65536:
        raise ValueError('Expected the bounded original bootd configuration bytes')
    before = json.loads(original)
    after = copy.deepcopy(before)
    common = after['common']
    first = common['firstApp']
    reasons = common['firstAppByPowerOnReason']
    for value in [first['firstAppInNormal'], reasons['remoteKey'], reasons['localKey']]:
        if not isinstance(value, str) or value == BRIDGE_ID:
            raise ValueError('Existing startup override requires its original owned backup')
    first['firstAppInNormal'] = BRIDGE_ID
    reasons['remoteKey'] = reasons['localKey'] = BRIDGE_ID
    candidate = (json.dumps(after, indent=2) + '\n').encode()
    contract = {'schema': 1, 'path': '/var/luna/preferences/bootd.json',
                'originalSha256': hashlib.sha256(original).hexdigest(),
                'candidateSha256': hashlib.sha256(candidate).hexdigest()}
    return candidate, contract
