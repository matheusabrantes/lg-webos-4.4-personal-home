"""Authorization and restart sequencing tests; no device calls."""
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import device_session as session

class SessionSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.patcher=patch.object(session,'HERE',self.root);self.patcher.start()
        self.meta={'releaseSha256':'a'*64}
    def tearDown(self):
        self.patcher.stop();self.tmp.cleanup()
    def auth(self,**overrides):
        record=dict(approved=True,expiresAt=10**12,releaseSha256=['a'*64]);record.update(overrides)
        (self.root/'physical-authorization.json').write_text(json.dumps(record))
    def test_flag_cannot_be_omitted(self):
        self.auth()
        with self.assertRaisesRegex(RuntimeError,'flag missing'):session.authorize(self.meta,False)
    def test_record_cannot_be_omitted(self):
        with self.assertRaises(FileNotFoundError):session.authorize(self.meta,True)
    def test_expired_or_unapproved_record(self):
        for overrides in [dict(expiresAt=1),dict(approved=False)]:
            self.auth(**overrides)
            with self.assertRaisesRegex(RuntimeError,'current user authorization'):session.authorize(self.meta,True)
    def test_release_scope_and_valid_approval(self):
        self.auth(releaseSha256=['b'*64])
        with self.assertRaisesRegex(RuntimeError,'outside approved'):session.authorize(self.meta,True)
        self.auth();self.assertTrue(session.authorize(self.meta,True)['approved'])
    def test_restart_needs_earlier_physical_gates(self):
        (self.root/'qa-matrix.json').write_text(json.dumps({'rows':[{'id':'REC-PRIMARY','status':'PASS','execution':'simulated'}]}))
        with patch.object(session,'state',side_effect=AssertionError('No device calls allowed')):
            with self.assertRaisesRegex(RuntimeError,'Earlier physical'):session.reboot(self.meta)
    def test_restart_limit_blocks_a_fourth_attempt(self):
        required=['REC-PRIMARY','REC-COMPOSITOR']+[f'{key}-{i}' for key in 'ABC' for i in range(1,6)]
        (self.root/'qa-matrix.json').write_text(json.dumps({'rows':[dict(id=key,status='PASS',execution='physical') for key in required]}))
        (self.root/'os-restart-count.json').write_text(json.dumps({'issued':3}))
        with patch.object(session,'state',side_effect=AssertionError('No device calls allowed')):
            with self.assertRaisesRegex(RuntimeError,'restart limit'):session.reboot(self.meta)

    def test_reduced_scope_requires_all_recovery_and_single_cycles(self):
        self.auth(scopeOverride=dict(minimumCyclesPerButton=1,maximumOSRestarts=1))
        required=['REC-PRIMARY','REC-COMPOSITOR','A-1','B-1','C-1']
        (self.root/'qa-matrix.json').write_text(json.dumps({'rows':[dict(id=key,status='PASS',execution='physical') for key in required]}))
        with patch.object(session,'state',return_value=dict(health=dict(ready=True,renderProbe=1),bootId='boot')),patch.object(session.tv,'luna',return_value={'issued':True}) as native:
            self.assertEqual(session.reboot(self.meta),{'issued':True});native.assert_called_once()
        self.assertEqual(json.loads((self.root/'os-restart-count.json').read_text())['issued'],1)
        with self.assertRaisesRegex(RuntimeError,'restart limit'):session.reboot(self.meta)
    def test_reduced_scope_cannot_remove_recovery_gates(self):
        self.auth(scopeOverride=dict(minimumCyclesPerButton=1,maximumOSRestarts=1))
        (self.root/'qa-matrix.json').write_text(json.dumps({'rows':[dict(id=key,status='PASS',execution='physical') for key in ['A-1','B-1','C-1']]}))
        with patch.object(session,'state',side_effect=AssertionError('No device calls allowed')):
            with self.assertRaisesRegex(RuntimeError,'Earlier physical'):session.reboot(self.meta)

if __name__=='__main__':unittest.main()
