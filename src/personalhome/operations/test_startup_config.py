import copy
import json
import unittest

from startup_config import BRIDGE_ID, prepare


class StartupConfigTests(unittest.TestCase):
    def setUp(self):
        self.original = {'common': {
            'firstApp': {'firstAppInNormal': '{LAST_INPUT_APP}', 'firstAppInFirstUse': 'firstuse'},
            'firstAppByPowerOnReason': {'remoteKey': '{LAST_APP}', 'localKey': '{LAST_APP}',
                                      'amazon': 'com.abrantesflix.app', 'netflix': 'netflix'}},
            'inputApps': {'DTV': 'com.webos.app.livetv'}, 'other': [1, 2]}

    def test_only_normal_power_and_cold_first_app_change(self):
        raw = json.dumps(self.original).encode()
        candidate, contract = prepare(raw)
        expected = copy.deepcopy(self.original)
        expected['common']['firstApp']['firstAppInNormal'] = BRIDGE_ID
        expected['common']['firstAppByPowerOnReason']['remoteKey'] = BRIDGE_ID
        expected['common']['firstAppByPowerOnReason']['localKey'] = BRIDGE_ID
        self.assertEqual(json.loads(candidate), expected)
        self.assertNotEqual(contract['originalSha256'], contract['candidateSha256'])
        self.assertEqual(json.loads(raw), self.original)

    def test_missing_or_already_replaced_config_cannot_become_original_backup(self):
        with self.assertRaises(KeyError):
            prepare(b'{}')
        self.original['common']['firstApp']['firstAppInNormal'] = BRIDGE_ID
        with self.assertRaises(ValueError):
            prepare(json.dumps(self.original).encode())

    def test_oversized_or_nonbyte_input_rejected(self):
        for raw in ['{}', b'', b'x' * 65537]:
            with self.assertRaises(ValueError):
                prepare(raw)


if __name__ == '__main__':
    unittest.main()
