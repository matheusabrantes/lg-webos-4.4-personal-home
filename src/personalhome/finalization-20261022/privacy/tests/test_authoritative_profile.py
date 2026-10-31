import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import authoritative_profile as control
from test_profile_control import FakeTV as BasicTV

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/authoritative-eula.json').read_text())


class FakeTV(BasicTV):
    def __init__(self):
        super().__init__()
        self.state['agreements'] = copy.deepcopy(FIXTURE['agreements'])
        self.descriptor = copy.deepcopy(FIXTURE['mapping'])
        self.consent_resets_cookie = True
        self.derive()

    def derive(self):
        rows = {r['id']: r['accepted'] for r in self.state['agreements']['eulaList']}
        for group in self.descriptor['eulaInfo']:
            key = group['settingKey']
            if key in self.state['consents'] and group.get('mandatory'):
                self.state['consents'][key] = all(rows[k] for k in group['mandatory'])

    def luna(self, method, payload):
        if method.endswith('/getSystemSettingValues'):
            self.calls.append((method, copy.deepcopy(payload)))
            return {'returnValue': True, 'eulaMappingList': copy.deepcopy(self.descriptor)}
        if payload.get('keys') == ['eulaInfoNetwork']:
            self.calls.append((method, copy.deepcopy(payload)))
            return {'returnValue': True, 'settings': {'eulaInfoNetwork': copy.deepcopy(self.state['agreements'])}}
        if 'eulaInfoNetwork' in payload.get('settings', {}):
            self.calls.append((method, copy.deepcopy(payload)))
            if self.fail == 'agreements':
                return {'returnValue': False}
            if self.ignore != 'agreements':
                self.state['agreements'] = copy.deepcopy(payload['settings']['eulaInfoNetwork'])
                self.derive()
                self.state['general']['adCookie'] = 'on'
            return {'returnValue': True}
        return super().luna(method, payload)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name).resolve() / 'authoritative.json'
        self.tv = FakeTV()

    def apply(self):
        return control.run(self.tv, 'apply', self.path, True)

    def test_exact_transaction_order_and_rollback(self):
        before = copy.deepcopy(self.tv.state)
        self.assertEqual(self.apply()['changedGroups'], list(control.ORDER))
        self.assertEqual(self.tv.state, control.desired(before))
        self.assertEqual(control.run(self.tv, 'restore', self.path, True)['status'], 'restore-verified')
        self.assertEqual(self.tv.state, before)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_only_three_accepted_values_change_with_all_metadata_preserved(self):
        self.tv.state['agreements']['futureMetadata'] = {'revision': 7, 'values': [1, 'x']}
        self.tv.state['agreements']['eulaList'].append({'id': 'FUTURE', 'accepted': True, 'type': 'N', 'unknown': {'keep': True}})
        before = copy.deepcopy(self.tv.state)
        self.apply()
        expected = copy.deepcopy(before['agreements'])
        for row in expected['eulaList']:
            if row['id'] in control.OPTIONAL_IDS:
                row['accepted'] = False
        self.assertEqual(self.tv.state['agreements'], expected)
        for key in ('networkAllowed', 'generalTermsAllowed', 'chpAllowed', 'unrelatedFutureConsent'):
            self.assertEqual(self.tv.state['consents'][key], before['consents'][key])
        self.assertTrue(next(r for r in expected['eulaList'] if r['id'] == 'S_SVC')['accepted'])
        control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.state, before)

    def test_missing_malformed_or_shared_essential_mapping_refused_before_write(self):
        for change in ('missing', 'essential', 'target', 'unknown'):
            with self.subTest(change=change):
                self.tv = FakeTV()
                if change == 'missing':
                    self.tv.descriptor['eulaInfo'] = self.tv.descriptor['eulaInfo'][1:3]
                elif change == 'essential':
                    self.tv.descriptor['eulaInfo'][1]['mandatory'].append('S_ADG')
                elif change == 'target':
                    self.tv.descriptor['eulaInfo'][2]['settingKey'] = 'generalTermsAllowed'
                else:
                    self.tv.descriptor['eulaInfo'].append({'eulaGroupName': 'futureEssential', 'mandatory': ['S_ADG']})
                with self.assertRaises(ValueError):
                    self.apply()
                self.assertEqual(self.tv.writes(), [])
                self.assertFalse(self.path.exists())

    def test_duplicate_missing_or_nonboolean_documents_refused(self):
        for change in ('duplicate', 'missing', 'type'):
            self.tv = FakeTV()
            if change == 'duplicate':
                self.tv.state['agreements']['eulaList'].append(copy.deepcopy(self.tv.state['agreements']['eulaList'][0]))
            elif change == 'missing':
                self.tv.state['agreements']['eulaList'] = [r for r in self.tv.state['agreements']['eulaList'] if r['id'] != 'S_ADG']
            else:
                self.tv.state['agreements']['eulaList'][0]['accepted'] = 1
            with self.assertRaises(ValueError):
                self.apply()
            self.assertEqual(self.tv.writes(), [])

    def test_metadata_or_unknown_consent_change_blocks_restore_before_write(self):
        for group in ('agreements', 'consents'):
            self.tv = FakeTV(); self.path = self.path.parent / (group + '.json')
            self.apply()
            self.tv.state[group]['foreign'] = True
            self.tv.calls.clear()
            with self.assertRaisesRegex(ValueError, 'Restore conflict'):
                control.run(self.tv, 'restore', self.path, True)
            self.assertEqual(self.tv.writes(), [])

    def test_partial_failure_after_consents_can_restore_cookie_off_baseline(self):
        self.tv.state['general']['adCookie'] = 'off'
        before = copy.deepcopy(self.tv.state); self.tv.fail = 'agreements'
        with self.assertRaises(RuntimeError):
            self.apply()
        self.tv.fail = None
        control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.state, before)

    def test_derived_consent_different_from_expected_is_failure(self):
        old = self.tv.derive
        def wrong():
            old(); self.tv.state['consents']['networkAllowed'] = False
        self.tv.derive = wrong
        with self.assertRaisesRegex(RuntimeError, 'Derived consent'):
            self.apply()
        self.assertTrue(self.path.exists())
        self.assertFalse(any(m.startswith('com.webos.rdxd/set') for m, _ in self.tv.writes()))

    def test_original_cookie_off_and_derived_uploader_reset_are_owned_sideeffects(self):
        self.tv.state['general']['adCookie'] = 'off'
        before = copy.deepcopy(self.tv.state)
        self.apply()
        old = self.tv.derive
        def native_reset():
            old(); self.tv.state['uploader'] = copy.deepcopy(before['uploader'])
        self.tv.derive = native_reset
        control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.state, before)

    def test_existing_backup_authorization_and_foreign_identity_refused(self):
        with self.assertRaises(PermissionError):
            control.run(self.tv, 'apply', self.path)
        self.assertEqual(self.tv.calls, [])
        self.apply(); self.tv.calls.clear()
        with self.assertRaises(FileExistsError):
            self.apply()
        self.assertEqual(self.tv.writes(), [])
        self.tv.fingerprint = 'b' * 64; self.tv.calls.clear()
        with self.assertRaises(ValueError):
            control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.writes(), [])

    def test_native_liveplus_reset_after_owned_restore_is_restored_exactly(self):
        before = copy.deepcopy(self.tv.state)
        self.apply()
        native = self.tv.luna
        def changed(method, payload):
            result = native(method, payload)
            if 'eulaInfoNetwork' in payload.get('settings', {}):
                self.tv.state['option']['livePlus'] = 'on'
            return result
        self.tv.luna = changed
        control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.state, before)

    def test_unowned_liveplus_or_other_option_change_remains_refused(self):
        self.apply()
        self.tv.state['option']['livePlus'] = 'on'
        self.tv.calls.clear()
        with self.assertRaisesRegex(ValueError, 'Restore conflict: option'):
            control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.writes(), [])
        self.tv.state['option']['livePlus'] = 'off'
        native = self.tv.luna
        def changed(method, payload):
            result = native(method, payload)
            if 'eulaInfoNetwork' in payload.get('settings', {}):
                self.tv.state['option']['webOSPromotionVideo'] = 'on'
            return result
        self.tv.luna = changed
        with self.assertRaisesRegex(ValueError, 'Concurrent preference change: option'):
            control.run(self.tv, 'restore', self.path, True)
        self.assertFalse(any(args.get('category') == 'option' for _, args in self.tv.writes()))

    def test_already_wanted_option_after_owned_restore_needs_no_overwrite(self):
        before = copy.deepcopy(self.tv.state)
        self.apply(); self.tv.calls.clear()
        native = self.tv.luna
        def changed(method, payload):
            result = native(method, payload)
            if 'eulaInfoNetwork' in payload.get('settings', {}):
                self.tv.state['option'] = copy.deepcopy(before['option'])
            return result
        self.tv.luna = changed
        control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.state, before)
        self.assertFalse(any(args.get('category') == 'option' for _, args in self.tv.writes()))

    def test_changed_descriptor_and_unsafe_backup_refused(self):
        self.apply(); self.tv.descriptor['maxEulaMappingGroupId'] = 'new'; self.tv.calls.clear()
        with self.assertRaises(ValueError):
            control.run(self.tv, 'restore', self.path, True)
        self.assertEqual(self.tv.writes(), [])
        self.tv = FakeTV(); self.path = self.path.parent / 'link.json'
        target = self.path.parent / 'keep'; target.write_text('keep'); self.path.symlink_to(target)
        with self.assertRaises(OSError):
            self.apply()
        self.assertEqual(target.read_text(), 'keep')
        self.assertEqual(self.tv.writes(), [])


if __name__ == '__main__':
    unittest.main()
