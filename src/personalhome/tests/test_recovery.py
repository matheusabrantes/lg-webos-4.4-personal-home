import hashlib
import importlib.util
import json
from pathlib import Path
import random
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('trial', ROOT / 'recovery/trial.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Trial, SandboxOverlay, RecoveryRefused = module.Trial, module.SandboxOverlay, module.RecoveryRefused


class Clock:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value
    def advance(self, seconds): self.value += seconds


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.original = self.directory / 'original'
        self.candidate = self.directory / 'candidate'
        self.original.write_bytes(b'original-renderer-copy')
        self.candidate.write_bytes(b'candidate-renderer-copy')
        self.original_sha = module.digest(self.original)
        self.candidate_sha = module.digest(self.candidate)
        self.sandbox = self.directory / 'sandbox'
        self.sandbox.mkdir()
        self.ops = SandboxOverlay(self.sandbox, self.original, self.candidate)
        self.clock = Clock()
        self.trial = Trial(self.ops, self.ops.target, self.original_sha, self.candidate_sha,
                           timeout=20, heartbeat_timeout=3, clock=self.clock)

    def assert_restored(self, reason):
        self.assertEqual(self.trial.state, 'rolled_back')
        self.assertEqual(self.trial.reason, reason)
        self.assertEqual(self.ops.target.read_bytes(), self.original.read_bytes())
        self.assertEqual((self.ops.apply_count, self.ops.restore_count, self.ops.restart_count), (1, 1, 1))

    def test_crash_before_confirmation_restores_once(self):
        self.trial.start()
        self.trial.crash()
        self.trial.crash()
        self.trial.rollback()
        self.trial.poll()
        self.assert_restored('compositor-crash')

    def test_no_heartbeat_rolls_back_even_if_process_would_be_alive(self):
        self.trial.start()
        self.clock.advance(3)
        self.trial.poll()
        self.assert_restored('heartbeat-expired')

    def test_ui_error_and_unhealthy_navigation(self):
        self.trial.start()
        self.trial.heartbeat(1, True, False)
        self.assert_restored('unhealthy-view-or-navigation')

    def test_ui_error_reason(self):
        self.trial.start()
        self.trial.heartbeat(1, True, True, error='Loader.Error')
        self.assert_restored('ui-error')

    def test_not_ready_is_not_health(self):
        self.trial.start()
        self.trial.heartbeat(1, False, True)
        self.assert_restored('unhealthy-view-or-navigation')

    def test_confirmation_requires_health_and_does_not_disable_fixed_expiry(self):
        self.trial.start()
        with self.assertRaises(RecoveryRefused): self.trial.confirm()
        for i in range(10):
            self.trial.heartbeat(i, True, True)
            self.trial.confirm()
            self.clock.advance(2)
        self.trial.heartbeat(10, True, True)
        self.assert_restored('trial-expired')

    def test_replayed_heartbeat_does_not_extend_deadline_or_health(self):
        self.trial.start()
        self.trial.heartbeat(5, True, True)
        self.clock.advance(2)
        self.trial.heartbeat(5, True, True)
        self.clock.advance(1)
        self.trial.poll()
        self.assert_restored('heartbeat-expired')

    def test_late_heartbeat_cannot_revive_expired_trial(self):
        self.trial.start()
        self.clock.advance(20)
        self.trial.heartbeat(1, True, True)
        self.assert_restored('trial-expired')

    def test_source_corruption_rejected_before_start(self):
        self.candidate.write_bytes(b'corrupted')
        with self.assertRaises(RecoveryRefused): self.trial.start()
        self.assertEqual(self.trial.state, 'prepared')
        self.assertEqual(self.ops.target.read_bytes(), self.original.read_bytes())
        self.assertEqual(self.ops.apply_count, 0)

    def test_candidate_change_during_trial_restores_original(self):
        self.trial.start()
        self.candidate.write_bytes(b'corrupted')
        self.trial.poll()
        self.assert_restored('candidate-changed')

    def test_changed_original_refuses_automatic_restore(self):
        self.trial.start()
        self.original.write_bytes(b'foreign-original')
        with self.assertRaises(RecoveryRefused): self.trial.crash()
        self.assertEqual(self.trial.state, 'trial')
        self.assertEqual(self.ops.target.read_bytes(), self.candidate.read_bytes())
        self.assertEqual(self.ops.restore_count, 0)

    def test_external_target_change_is_never_overwritten(self):
        self.trial.start()
        self.ops.target.write_bytes(b'foreign-change')
        with self.assertRaises(RecoveryRefused): self.trial.poll()
        self.assertEqual(self.ops.target.read_bytes(), b'foreign-change')
        self.assertEqual(self.trial.state, 'trial')
        self.assertEqual(self.ops.restore_count, 0)

    def test_symlink_target_is_rejected_and_link_destination_unchanged(self):
        self.trial.start()
        other = self.directory / 'do-not-touch'
        other.write_bytes(b'keep')
        self.ops.target.unlink()
        self.ops.target.symlink_to(other)
        with self.assertRaises(RecoveryRefused): self.trial.rollback()
        self.assertEqual(other.read_bytes(), b'keep')

    def test_wrong_target_is_rejected(self):
        with self.assertRaises(RecoveryRefused):
            Trial(self.ops, self.directory / 'outside', self.original_sha, self.candidate_sha)
        self.assertEqual(self.ops.apply_count, 0)

    def test_source_identities_and_deadlines_are_validated(self):
        for original, candidate, timeout, heartbeat in [
            ('bad', self.candidate_sha, 10, 3),
            (None, self.candidate_sha, 10, 3),
            (self.original_sha, self.original_sha, 10, 3),
            (self.original_sha, self.candidate_sha, float('inf'), 3),
            (self.original_sha, self.candidate_sha, 0, 3),
            (self.original_sha, self.candidate_sha, 10, 11),
            (self.original_sha, self.candidate_sha, 121, 3),
        ]:
            with self.assertRaises(ValueError): Trial(self.ops, self.ops.target, original, candidate, timeout, heartbeat)

    def test_duplicate_start_applies_once_and_rollback_is_final(self):
        self.trial.start()
        self.trial.start()
        self.trial.heartbeat(1, True, True)
        self.trial.confirm()
        self.trial.start()
        self.assertEqual(self.ops.apply_count, 1)
        self.trial.rollback()
        with self.assertRaises(RecoveryRefused): self.trial.start()
        self.assert_restored('operator-ended-trial')

    def test_foreign_temporary_file_is_preserved(self):
        foreign = self.sandbox / 'replacement.tmp'
        foreign.write_bytes(b'foreign')
        with self.assertRaises(FileExistsError): self.trial.start()
        self.assertEqual(foreign.read_bytes(), b'foreign')
        self.assertEqual(self.ops.target.read_bytes(), self.original.read_bytes())
        self.assertEqual(self.trial.state, 'prepared')

    def test_recovery_operation_failure_does_not_claim_rollback(self):
        self.trial.start()
        restore = self.ops.restore
        def fail(*args): raise OSError('simulated unavailable recovery backend')
        self.ops.restore = fail
        with self.assertRaises(OSError): self.trial.rollback()
        self.assertEqual(self.trial.state, 'trial')
        self.ops.restore = restore
        self.trial.rollback()
        self.assert_restored('operator-ended-trial')

    def test_symlink_sandbox_and_source_are_rejected(self):
        linked = self.directory / 'linked-sandbox'
        linked.symlink_to(self.sandbox, target_is_directory=True)
        with self.assertRaises(RecoveryRefused): SandboxOverlay(linked, self.original, self.candidate)
        linked_source = self.directory / 'linked-original'
        linked_source.symlink_to(self.original)
        fresh = self.directory / 'fresh-sandbox'
        fresh.mkdir()
        with self.assertRaises(RecoveryRefused): SandboxOverlay(fresh, linked_source, self.candidate)
        self.assertFalse((fresh / 'surface-manager-starfish').exists())

    def test_5000_deterministic_trials(self):
        randomizer = random.Random(6310)
        outcomes = {'crash': 0, 'heartbeat-expired': 0, 'ui-error': 0, 'trial-expired': 0, 'operator-ended-trial': 0}
        for i in range(5000):
            self.ops.target.unlink()
            ops = SandboxOverlay(self.sandbox, self.original, self.candidate)
            clock = Clock()
            trial = Trial(ops, ops.target, self.original_sha, self.candidate_sha,
                          timeout=10, heartbeat_timeout=2, clock=clock)
            trial.start()
            trial.start()
            action = randomizer.randrange(5)
            if action == 0:
                trial.crash(); outcomes['crash'] += 1
            elif action == 1:
                clock.advance(2); trial.poll(); outcomes['heartbeat-expired'] += 1
            elif action == 2:
                trial.heartbeat(1, True, True, 'error'); outcomes['ui-error'] += 1
            elif action == 3:
                for sequence in range(10):
                    trial.heartbeat(sequence, True, True)
                    trial.confirm()
                    clock.advance(1)
                trial.poll(); outcomes['trial-expired'] += 1
            else:
                trial.heartbeat(1, True, True); trial.confirm(); trial.rollback(); outcomes['operator-ended-trial'] += 1
            trial.rollback(); trial.crash(); trial.poll()
            self.assertEqual(trial.state, 'rolled_back')
            self.assertEqual(ops.target.read_bytes(), self.original.read_bytes())
            self.assertEqual((ops.apply_count, ops.restore_count, ops.restart_count), (1, 1, 1))
        output = ROOT / 'qa/recovery-stress.json'
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps({'scope': 'local-file simulation; no TV or system mounts', 'seed': 6310,
                                       'cycles': 5000, 'outcomes': outcomes, 'exactlyOneRestorePerCycle': True,
                                       'originalSha256': self.original_sha, 'candidateSha256': self.candidate_sha,
                                       'tvRecoveryVerified': False}, indent=2) + '\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
