import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import analytics_control as control


class FakeTV:
    def __init__(self, analytics=True, crash=True):
        self.state = {'analyticsLog': analytics, 'crashLog': crash}
        self.writes = []
        self.reads = 0
        self.reject = False
        self.ignore = False
        self.mutate = False
        self.fingerprint = 'a' * 64

    def identity(self):
        return {'originalSha': control.ORIGINAL_SHA, 'knownHostsSha': self.fingerprint}

    def luna(self, method, payload):
        if method.endswith('/getLogSettings'):
            self.reads += 1
            if self.mutate and self.reads == 2:
                self.state['crashLog'] = not self.state['crashLog']
            return dict(self.state, returnValue=True)
        if not method.endswith('/setLogSettings'):
            raise AssertionError('Unrelated service call')
        self.writes.append(copy.deepcopy(payload))
        if self.reject:
            return {'returnValue': False}
        if not self.ignore:
            self.state = copy.deepcopy(payload)
        return {'returnValue': True}


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.backup = Path(self.temp.name).resolve() / 'before.json'
        self.tv = FakeTV()

    def apply(self):
        return control.run(self.tv, 'apply', self.backup, True)

    def test_status_never_writes(self):
        self.assertEqual(control.run(self.tv, 'status')['status'], 'read-only')
        self.assertFalse(self.backup.exists())
        self.assertEqual(self.tv.writes, [])

    def test_authorization_checked_before_any_remote_operation(self):
        for mode in ('apply', 'restore'):
            with self.assertRaises(ValueError):
                control.run(self.tv, mode, self.backup)
        self.assertEqual(self.tv.reads, 0)
        self.assertEqual(self.tv.writes, [])

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            control.run(self.tv, 'disable-all', self.backup, True)
        self.assertEqual(self.tv.reads, 0)

    def test_apply_preserves_crash_and_private_backup(self):
        self.apply()
        self.assertEqual(self.tv.writes, [{'analyticsLog': False, 'crashLog': True}])
        self.assertEqual(self.backup.stat().st_mode & 0o777, 0o600)
        self.assertTrue(control.backup_file(self.backup)['before']['analyticsLog'])

    def test_apply_preserves_crash_false(self):
        self.tv.state['crashLog'] = False
        self.apply()
        self.assertEqual(self.tv.state, {'analyticsLog': False, 'crashLog': False})

    def test_existing_backup_cannot_be_overwritten(self):
        self.apply()
        old = self.backup.read_bytes()
        with self.assertRaises(FileExistsError):
            self.apply()
        self.assertEqual(self.backup.read_bytes(), old)
        self.assertEqual(len(self.tv.writes), 1)

    def test_already_disabled_no_rpc_write(self):
        self.tv.state['analyticsLog'] = False
        self.apply()
        self.assertEqual(self.tv.writes, [])
        control.run(self.tv, 'restore', self.backup, True)
        self.assertEqual(self.tv.writes, [])

    def test_restore_preserves_current_crash_not_historical_value(self):
        self.apply()
        self.tv.state['crashLog'] = False
        control.run(self.tv, 'restore', self.backup, True)
        self.assertEqual(self.tv.state, {'analyticsLog': True, 'crashLog': False})

    def test_cross_device_backup_rejected(self):
        self.apply()
        self.tv.fingerprint = 'b' * 64
        with self.assertRaises(ValueError):
            control.run(self.tv, 'restore', self.backup, True)
        self.assertEqual(len(self.tv.writes), 1)

    def test_concurrent_change_no_write(self):
        self.tv.mutate = True
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.tv.writes, [])
        self.assertTrue(self.backup.exists())

    def test_invalid_and_missing_booleans_rejected(self):
        for key in ('analyticsLog', 'crashLog', 'returnValue'):
            for value in (None, 'false', 0, 1):
                reply = dict(analyticsLog=True, crashLog=True, returnValue=True)
                reply[key] = value
                with self.assertRaises(ValueError):
                    control.flags(reply)

    def test_set_failure_retains_backup(self):
        self.tv.reject = True
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertTrue(self.backup.exists())

    def test_readback_mismatch_retains_backup(self):
        self.tv.ignore = True
        with self.assertRaises(RuntimeError):
            self.apply()
        self.assertTrue(self.backup.exists())

    def test_symlink_rejected(self):
        other = self.backup.parent / 'other'
        other.write_text('unchanged')
        self.backup.symlink_to(other)
        with self.assertRaises(OSError):
            self.apply()
        self.assertEqual(other.read_text(), 'unchanged')
        self.assertEqual(self.tv.writes, [])

    def test_hardlink_and_broad_permissions_rejected(self):
        self.apply()
        os.link(self.backup, self.backup.parent / 'link')
        with self.assertRaises(ValueError):
            control.backup_file(self.backup)
        (self.backup.parent / 'link').unlink()
        self.backup.chmod(0o644)
        with self.assertRaises(ValueError):
            control.backup_file(self.backup)

    def test_invalid_backup_schema_blocks_restore(self):
        self.apply()
        value = json.loads(self.backup.read_text())
        value['before']['analyticsLog'] = 'false'
        self.backup.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            control.run(self.tv, 'restore', self.backup, True)
        self.assertEqual(len(self.tv.writes), 1)

    def test_transport_timeout_propagates_no_automatic_retry(self):
        def fail(method, payload):
            raise TimeoutError('No response')
        self.tv.luna = fail
        with self.assertRaises(TimeoutError):
            self.apply()
        self.assertFalse(self.backup.exists())


if __name__ == '__main__':
    unittest.main()
