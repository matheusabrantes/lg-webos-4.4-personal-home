"""Native agreement-document transaction; historical profile backups stay unchanged."""
import argparse
import copy
import json
import os
from pathlib import Path
import stat

import profile_control as core

OPTIONAL_IDS = {'S_ADG', 'S_VNG', 'S_TAG'}
BINDINGS = {
    'generalTerms': ('generalTermsAllowed', ['S_SVC']),
    'chp': ('chpAllowed', ['S_SVC']),
    'additionalData': ('additionalDataAllowed', ['S_SVC', 'S_ADG']),
    'customAd': ('customAdAllowed', ['S_SVC', 'S_TAG']),
    'voice': ('voiceAllowed', ['S_SVC', 'S_VNG']),
    'voice2': ('voice2Allowed', ['S_SVC', 'S_ADG', 'S_VNG']),
    'thirdPartySharing': ('thirdPartySharingAllowed', ['S_SVC', 'S_ADG']),
    'acrOn': ('acrOnAllowed', ['S_SVC', 'S_ADG']),
    'acrAd': ('acrAdAllowed', ['S_SVC', 'S_ADG', 'S_TAG']),
    'all': ('allAllowed', ['S_SVC', 'S_ADG', 'S_VNG', 'S_TAG']),
}
ORDER = ('consents', 'agreements', 'rdxd', 'uploader', 'general', 'option')
LIMIT = 65536


def mapping(transport):
    value = transport.luna('com.webos.settingsservice/getSystemSettingValues', {'key': 'eulaInfoNetwork'})
    if not isinstance(value, dict) or value.get('returnValue') is not True:
        raise ValueError('Agreement mapping read failed')
    return value.get('eulaMappingList')


def validate(agreements, descriptor):
    if (not isinstance(agreements, dict) or not isinstance(agreements.get('eulaList'), list) or
            not 4 <= len(agreements['eulaList']) <= 64 or
            len(json.dumps(agreements, allow_nan=False).encode()) > LIMIT):
        raise ValueError('Invalid authoritative agreement object')
    rows = {}
    for row in agreements['eulaList']:
        if (not isinstance(row, dict) or not isinstance(row.get('id'), str) or
                not row['id'] or len(row['id']) > 64 or row['id'] in rows or
                type(row.get('accepted')) is not bool):
            raise ValueError('Malformed or duplicate agreement row')
        rows[row['id']] = row
    if not (OPTIONAL_IDS | {'S_SVC'}).issubset(rows):
        raise ValueError('Required agreement document missing')
    if any(rows[key].get('type') != 'M' for key in OPTIONAL_IDS | {'S_SVC'}):
        raise ValueError('Required agreement document type differs')
    if not isinstance(descriptor, dict) or not isinstance(descriptor.get('eulaInfo'), list):
        raise ValueError('Agreement mapping missing')
    groups = {}
    for group in descriptor['eulaInfo']:
        if not isinstance(group, dict) or not isinstance(group.get('eulaGroupName'), str):
            raise ValueError('Malformed agreement group')
        name = group['eulaGroupName']
        if name in groups:
            raise ValueError('Duplicate agreement group')
        groups[name] = group
        mandatory = group.get('mandatory', [])
        if (not isinstance(mandatory, list) or any(not isinstance(k, str) or k not in rows for k in mandatory) or
                len(set(mandatory)) != len(mandatory)):
            raise ValueError('Invalid mandatory document references')
        if name not in BINDINGS and OPTIONAL_IDS.intersection(mandatory):
            raise ValueError('Unknown agreement group depends on target documents')
    for name, (setting, ids) in BINDINGS.items():
        if name not in groups or groups[name].get('settingKey') != setting or groups[name].get('mandatory') != ids:
            raise ValueError('Authoritative binding differs: ' + name)
    return rows


def read(transport, group):
    if group != 'agreements':
        return core.read(transport, group)
    reply = transport.luna('com.webos.settingsservice/getSystemSettings', {'keys': ['eulaInfoNetwork']})
    if not isinstance(reply, dict) or reply.get('returnValue') is not True:
        raise ValueError('Authoritative agreement read failed')
    return reply.get('settings', {}).get('eulaInfoNetwork')


def write(transport, group, value):
    if group != 'agreements':
        return core.write(transport, group, value)
    reply = transport.luna('com.webos.settingsservice/setSystemSettings', {'settings': {'eulaInfoNetwork': value}})
    if not isinstance(reply, dict) or reply.get('returnValue') is not True:
        raise RuntimeError('Agreement write not acknowledged')
    if read(transport, group) != value:
        raise RuntimeError('Authoritative agreement readback mismatch')


def desired(before):
    result = core.desired(before)
    result['agreements'] = copy.deepcopy(before['agreements'])
    for row in result['agreements']['eulaList']:
        if row['id'] in OPTIONAL_IDS:
            row['accepted'] = False
    return result


def document(path, value=None):
    path = Path(path).absolute()
    parent = path.parent.stat()
    if path.parent.resolve() != path.parent or parent.st_uid != os.getuid() or parent.st_mode & 0o022:
        raise ValueError('Unsafe backup parent')
    flags = os.O_RDONLY if value is None else os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, 'r' if value is None else 'w') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or
                stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > LIMIT):
            raise ValueError('Unsafe authoritative backup')
        if value is None:
            value = json.loads(stream.read(LIMIT + 1))
        else:
            text = json.dumps(value, allow_nan=False)
            if len(text.encode()) > LIMIT:
                raise ValueError('Authoritative backup too large')
            stream.write(text + '\n'); stream.flush(); os.fsync(stream.fileno())
    if not isinstance(value, dict) or set(value) != {'schema', 'identity', 'mapping', 'before'} or type(value['schema']) is not int or value['schema'] != 2:
        raise ValueError('Invalid authoritative backup schema')
    identity = value['identity']
    if (not isinstance(identity, dict) or set(identity) != {'originalSha', 'knownHostsSha'} or
            identity['originalSha'] != core.ORIGINAL_SHA or
            not isinstance(identity['knownHostsSha'], str) or len(identity['knownHostsSha']) != 64):
        raise ValueError('Invalid authoritative backup identity')
    before = value['before']
    if not isinstance(before, dict) or set(before) != set(ORDER):
        raise ValueError('Invalid authoritative backup groups')
    validate(before['agreements'], value['mapping']); core.validate_consents(before['consents'])
    if type(before['consents'].get('chpAllowed')) is not bool:
        raise ValueError('Essential chp consent missing')
    for group in ('rdxd', 'uploader', 'general', 'option'):
        if not isinstance(before[group], dict) or set(before[group]) != set(core.GROUPS[group]):
            raise ValueError('Invalid authoritative backup group')
        if group in core.SERVICES:
            core.flags(dict(before[group], returnValue=True))
        elif any(v not in ('on', 'off') for v in before[group].values()):
            raise ValueError('Invalid authoritative backup preference')
    return value


def run(transport, mode, path=None, authorized=False):
    if mode not in ('status', 'apply', 'restore'):
        raise ValueError('Invalid operation')
    if mode != 'status' and (not authorized or path is None):
        raise PermissionError('Approved transaction and new private backup required')
    identity = transport.identity()
    current = {group: read(transport, group) for group in ORDER}
    descriptor = mapping(transport)
    validate(current['agreements'], descriptor)
    if type(current['consents'].get('chpAllowed')) is not bool:
        raise ValueError('Essential chp consent missing')
    if mode == 'status':
        return {'status': 'read-only', 'settings': current, 'mapping': descriptor}
    if mode == 'apply':
        document(path, {'schema': 2, 'identity': identity, 'mapping': descriptor, 'before': current})
    saved = document(path)
    if saved['identity'] != identity or saved['mapping'] != descriptor:
        raise ValueError('Backup identity or agreement mapping differs')
    applied = desired(saved['before'])
    wanted = applied if mode == 'apply' else saved['before']
    if mode == 'restore':
        for group in ORDER:
            now = current[group]
            if group in ('consents', 'agreements'):
                allowed = now in (saved['before'][group], applied[group])
            else:
                allowed = set(now) == set(applied[group]) and all(now[k] in (saved['before'][group][k], applied[group][k]) for k in now)
                if group == 'general' and not allowed and any(current[g] != wanted[g] for g in ('consents', 'agreements')):
                    allowed = now in (dict(saved['before'][group], adCookie='on'), dict(applied[group], adCookie='on'))
            if not allowed:
                raise ValueError('Restore conflict: ' + group)
    observed = copy.deepcopy(current)
    changes = []
    agreement_written = False
    for group in ORDER:
        now = read(transport, group)
        if now != observed[group]:
            if mode == 'restore' and now == wanted[group]:
                observed[group] = copy.deepcopy(now)
            elif (mode == 'restore' and group == 'option' and agreement_written and
                    now == dict(observed['option'], livePlus='on')):
                observed['ownedLivePlusReset'] = copy.deepcopy(now)
                observed[group] = copy.deepcopy(now)
            else:
                raise ValueError('Concurrent preference change: ' + group)
        if mode == 'restore':
            if group in ('consents', 'agreements'):
                allowed = now in (saved['before'][group], applied[group])
            else:
                allowed = set(now) == set(applied[group]) and all(now[k] in (saved['before'][group][k], applied[group][k]) for k in now)
            if not allowed and not ((group == 'general' and now == observed.get('ownedCookieReset')) or
                                    (group == 'option' and now == observed.get('ownedLivePlusReset'))):
                raise ValueError('Restore conflict: ' + group)
        if now == wanted[group]:
            continue
        write(transport, group, copy.deepcopy(wanted[group])); changes.append(group)
        observed[group] = copy.deepcopy(wanted[group])
        if group in ('consents', 'agreements'):
            agreement_written = True
            general = read(transport, 'general')
            if general not in (observed['general'], dict(observed['general'], adCookie='on')):
                raise ValueError('Unexpected agreement side effect: general')
            if general['adCookie'] == 'on':
                observed['ownedCookieReset'] = general
            observed['general'] = general
            if read(transport, 'consents') != wanted['consents']:
                raise RuntimeError('Derived consent state differs after agreement write')
            for flag_group in ('rdxd', 'uploader'):
                flags = read(transport, flag_group)
                if flags not in (observed[flag_group], saved['before'][flag_group], applied[flag_group]):
                    raise ValueError('Unexpected agreement side effect: ' + flag_group)
                observed[flag_group] = flags
    final = {group: read(transport, group) for group in ORDER}
    if final != wanted:
        raise RuntimeError('Final authoritative profile verification failed')
    return {'status': mode + '-verified', 'changedGroups': changes, 'settings': final,
            'scope': 'native two-object agreement transaction; no boot/service/network mutation'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['status', 'apply', 'restore'])
    parser.add_argument('--backup', type=Path)
    parser.add_argument('--authorized-trial-or-deployment', action='store_true')
    args = parser.parse_args()
    print(json.dumps(run(core.Television(), args.mode, args.backup, args.authorized_trial_or_deployment)))
