import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import profile_control as control


class FakeTV:
    def __init__(self):
        self.state = copy.deepcopy(control.GROUPS)
        self.state['rdxd'] = {'analyticsLog': True, 'crashLog': True}
        self.state['uploader'] = {'analyticsLog': True, 'crashLog': False}
        self.state['general']['adCookie'] = 'on'
        self.state['option']['watchedListCollection'] = 'on'
        self.state['consents'].update({'networkAllowed': True, 'generalTermsAllowed': True,
                                       'chpAllowed': True, 'unrelatedFutureConsent': False,
                                       'voiceAllowed': True, 'voice2Allowed': True,
                                       'additionalDataAllowed': True, 'acrOnAllowed': True})
        self.calls = []
        self.fail = None
        self.ignore = None
        self.fingerprint = 'a' * 64
        self.consent_resets_cookie = False

    def identity(self):
        return {'originalSha': control.ORIGINAL_SHA, 'knownHostsSha': self.fingerprint}

    def luna(self, method, payload):
        self.calls.append((method, copy.deepcopy(payload)))
        group = next((k for k, v in control.SERVICES.items() if method.startswith(v)), payload.get('category'))
        if payload.get('keys') == ['eulaStatus'] or 'eulaStatus' in payload.get('settings', {}):
            group = 'consents'
        if 'get' in method.rsplit('/', 1)[1]:
            value = copy.deepcopy(self.state[group])
            return dict(value, returnValue=True) if group in control.SERVICES else {'returnValue': True, 'settings': {'eulaStatus': value} if group == 'consents' else value}
        if self.fail == group:
            return {'returnValue': False}
        if self.ignore != group:
            self.state[group] = copy.deepcopy(payload if group in control.SERVICES else payload['settings']['eulaStatus'] if group == 'consents' else payload['settings'])
            if group == 'consents' and self.consent_resets_cookie:
                self.state['general']['adCookie'] = 'on'
        return {'returnValue': True}

    def writes(self):
        return [v for v in self.calls if v[0].rsplit('/', 1)[1].startswith('set')]


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve() / 'before.json'
        self.tv = FakeTV()

    def apply(self):
        return control.run(self.tv, 'apply', self.path, True)

    def test_status_no_writes_or_backup(self):
        self.assertEqual(control.run(self.tv, 'status')['status'], 'read-only')
        self.assertEqual(self.tv.writes(), [])
        self.assertFalse(self.path.exists())

    def test_authorization_refused_before_remote_calls(self):
        with self.assertRaises(PermissionError):
            control.run(self.tv, 'apply', self.path)
        self.assertEqual(self.tv.calls, [])

    def test_apply_and_restore_exact_state_in_dependency_order(self):
        before = copy.deepcopy(self.tv.state)
        self.assertEqual(self.apply()['changedGroups'], list(control.ORDER))
        self.assertEqual(self.tv.state, control.desired(before))
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(control.run(self.tv, 'restore', self.path, True)['changedGroups'], list(control.ORDER))
        self.assertEqual(self.tv.state, before)

    def test_failure_keeps_backup_and_restores_completed_groups(self):
        before = copy.deepcopy(self.tv.state)
        self.tv.fail = 'general'
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertTrue(self.path.exists())
        self.tv.fail = None
        control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.state, before)

    def test_partial_group_can_be_restored(self):
        before = copy.deepcopy(self.tv.state)
        self.apply()
        self.tv.state['rdxd']['crashLog'] = True
        self.tv.state['option']['watchedListCollection'] = 'on'
        control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.state, before)

    def test_no_unrelated_preferences_sent(self):
        self.apply()
        for service, args in self.tv.writes():
            if service.startswith('com.webos.settingsservice/'):
                if 'eulaStatus' in args.get('settings', {}):
                    self.assertEqual(set(args), {'settings'})
                    self.assertEqual(args['settings']['eulaStatus']['networkAllowed'], True)
                    self.assertEqual(args['settings']['eulaStatus']['generalTermsAllowed'], True)
                    self.assertEqual(args['settings']['eulaStatus']['chpAllowed'], True)
                    self.assertEqual(args['settings']['eulaStatus']['unrelatedFutureConsent'], False)
                    continue
                self.assertEqual(set(args), {'category', 'settings'})
                self.assertEqual(set(args['settings']), set(control.GROUPS[args['category']]))
            else:
                self.assertEqual(set(args), {'analyticsLog', 'crashLog'})

    def test_existing_backup_refused_without_any_set(self):
        self.apply()
        self.tv.calls.clear()
        with self.assertRaises(FileExistsError):
            self.apply()
        self.assertEqual(self.tv.writes(), [])

    def test_bad_response_type_no_set(self):
        self.tv.state['uploader']['crashLog'] = 'false'
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.tv.writes(), [])
        self.assertFalse(self.path.exists())

    def test_readback_mismatch_can_restore(self):
        before = copy.deepcopy(self.tv.state)
        self.tv.ignore = 'uploader'
        with self.assertRaises(RuntimeError):
            self.apply()
        self.tv.ignore = None
        control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.state, before)

    def test_foreign_identity_prevents_restore_writes(self):
        self.apply()
        self.tv.calls.clear()
        self.tv.fingerprint = 'b' * 64
        with self.assertRaises(ValueError):
            control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.writes(), [])

    def test_symlink_refused(self):
        other = self.path.parent / 'keep'
        other.write_text('unchanged')
        self.path.symlink_to(other)
        with self.assertRaises(OSError):
            self.apply()
        self.assertEqual(other.read_text(), 'unchanged')
        self.assertEqual(self.tv.writes(), [])

    def test_invalid_schema_refused(self):
        self.apply()
        value = json.loads(self.path.read_text())
        value['before']['option']['surprise'] = 'on'
        self.path.write_text(json.dumps(value))
        self.tv.calls.clear()
        with self.assertRaises(ValueError):
            control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.writes(), [])

    def test_essential_and_unknown_consents_preserved(self):
        before = copy.deepcopy(self.tv.state['consents'])
        self.apply()
        for k in ['networkAllowed', 'generalTermsAllowed', 'chpAllowed', 'unrelatedFutureConsent']:
            self.assertEqual(self.tv.state['consents'][k], before[k])
        for k in control.GROUPS['consents']:
            self.assertIs(self.tv.state['consents'][k], False)

    def test_missing_essential_consent_blocks_before_set(self):
        del self.tv.state['consents']['networkAllowed']
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.tv.writes(), [])

    def test_concurrent_preference_change_refused_before_that_group_set(self):
        original = self.tv.luna
        count = [0]
        def changed(method, payload):
            if method.endswith('/getSystemSettings') and payload.get('category') == 'general':
                count[0] += 1
                if count[0] == 2:
                    self.tv.state['general']['homePromotion'] = 'on'
            return original(method, payload)
        self.tv.luna = changed
        with self.assertRaisesRegex(ValueError, 'Unexpected consent side effect'):
            self.apply()
        self.assertTrue(self.path.exists())
        self.assertFalse(any(args.get('category') == 'general' for _, args in self.tv.writes()))

    def test_restore_refuses_new_unknown_consent_field(self):
        self.apply()
        self.tv.state['consents']['newSystemConsent'] = True
        self.tv.calls.clear()
        with self.assertRaisesRegex(ValueError, 'Restore conflict'):
            control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.writes(), [])

    def test_native_consent_write_cookie_reset_then_apply_restore(self):
        self.tv.consent_resets_cookie = True
        before = copy.deepcopy(self.tv.state)
        self.apply()
        self.assertEqual(self.tv.state, control.desired(before))
        self.assertIn('eulaStatus', self.tv.writes()[0][1]['settings'])
        self.tv.calls.clear()
        control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.state, before)
        self.assertIn('eulaStatus', self.tv.writes()[0][1]['settings'])

    def test_native_consent_cookie_reset_restores_original_cookie_off(self):
        self.tv.consent_resets_cookie = True
        self.tv.state['general']['adCookie'] = 'off'
        before = copy.deepcopy(self.tv.state)
        self.apply()
        self.assertEqual(self.tv.state, control.desired(before))
        control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.state, before)

    def test_cookie_off_backup_restored_after_failure_after_consent_write(self):
        self.tv.consent_resets_cookie = True
        self.tv.state['general']['adCookie'] = 'off'
        self.tv.fail = 'rdxd'
        before = copy.deepcopy(self.tv.state)
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertEqual(self.tv.state['general']['adCookie'], 'on')
        self.tv.fail = None
        control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.state, before)

    def test_cookie_reset_without_acknowledged_consent_write_refused(self):
        self.tv.state['consents'].update(control.GROUPS['consents'])
        self.tv.state['general']['adCookie'] = 'off'
        original = self.tv.luna
        count = [0]
        def changed(method, payload):
            if method.endswith('/getSystemSettings') and payload.get('category') == 'general':
                count[0] += 1
                if count[0] == 2:
                    self.tv.state['general']['adCookie'] = 'on'
            return original(method, payload)
        self.tv.luna = changed
        with self.assertRaisesRegex(ValueError, 'Concurrent preference change'):
            self.apply()
        self.assertFalse(any('eulaStatus' in args.get('settings', {}) for _, args in self.tv.writes()))
        self.assertFalse(any(args.get('category') == 'general' for _, args in self.tv.writes()))

    def test_concurrent_change_after_owned_cookie_read_refused(self):
        self.tv.consent_resets_cookie = True
        original = self.tv.luna
        count = [0]
        def changed(method, payload):
            if method.endswith('/getSystemSettings') and payload.get('category') == 'general':
                count[0] += 1
                if count[0] == 3:
                    self.tv.state['general']['homePromotion'] = 'on'
            return original(method, payload)
        self.tv.luna = changed
        with self.assertRaisesRegex(ValueError, 'Concurrent preference change'):
            self.apply()
        self.assertFalse(any(args.get('category') == 'general' for _, args in self.tv.writes()))


if __name__ == '__main__':
    unittest.main()
