"""Offline trial controller. Its only operations adapter is a local file simulation."""
import hashlib
import math
import os
from pathlib import Path
import re
import time


class RecoveryRefused(RuntimeError):
    pass


def digest(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RecoveryRefused('Expected a regular, non-symlink file: ' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SandboxOverlay:
    """Models overlay/unmount/restart without system calls, processes or networking."""
    def __init__(self, directory, original, candidate):
        if Path(directory).is_symlink():
            raise RecoveryRefused('Sandbox directory must not be a symlink')
        self.directory = Path(directory).resolve(strict=True)
        if not self.directory.is_dir():
            raise RecoveryRefused('Sandbox must already exist')
        self.target = self.directory / 'surface-manager-starfish'
        self.original = Path(original)
        self.candidate = Path(candidate)
        if self.target.exists() or self.target.is_symlink():
            raise RecoveryRefused('Sandbox target must be new')
        digest(self.original)
        digest(self.candidate)
        self.target.write_bytes(self.original.read_bytes())
        self.apply_count = self.restore_count = self.restart_count = 0

    def validate_target(self, target):
        target = Path(target)
        if target != self.target or target.is_symlink() or target.resolve(strict=True).parent != self.directory:
            raise RecoveryRefused('Target is outside the one owned sandbox path')

    def _replace(self, data):
        temporary = self.directory / 'replacement.tmp'
        # A foreign file or symlink is not ours to replace.
        with temporary.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.target)

    def apply(self, original_sha, candidate_sha):
        self.validate_target(self.target)
        if digest(self.target) != original_sha or digest(self.candidate) != candidate_sha:
            raise RecoveryRefused('Source/target changed before simulated overlay')
        self._replace(self.candidate.read_bytes())
        self.apply_count += 1

    def restore(self, original_sha, candidate_sha):
        self.validate_target(self.target)
        if digest(self.original) != original_sha:
            raise RecoveryRefused('Original changed; cannot restore safely')
        current = digest(self.target)
        if current == original_sha:
            return
        if current != candidate_sha:
            raise RecoveryRefused('Target was modified externally; refusing overwrite')
        self._replace(self.original.read_bytes())
        self.restore_count += 1
        self.restart_count += 1


class Trial:
    def __init__(self, operations, target, original_sha, candidate_sha,
                 timeout=30, heartbeat_timeout=3, clock=time.monotonic):
        if not all(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) for value in (original_sha, candidate_sha)):
            raise ValueError('Expected SHA256 identities')
        if original_sha == candidate_sha:
            raise ValueError('Candidate must differ from original')
        if not (math.isfinite(timeout) and math.isfinite(heartbeat_timeout)
                and 0 < heartbeat_timeout <= timeout <= 120):
            raise ValueError('Trial needs finite positive deadlines, at most120 seconds')
        operations.validate_target(target)
        if digest(operations.original) != original_sha or digest(operations.candidate) != candidate_sha:
            raise RecoveryRefused('Prepared source identity mismatch')
        if digest(target) != original_sha:
            raise RecoveryRefused('Prepared target is not the original')
        self.operations = operations
        self.target = Path(target)
        self.original_sha = original_sha
        self.candidate_sha = candidate_sha
        self.timeout = timeout
        self.heartbeat_timeout = heartbeat_timeout
        self.clock = clock
        self.state = 'prepared'
        self.reason = None
        self.deadline = self.last_heartbeat = None
        self.sequence = -1
        self.healthy = False

    def start(self):
        if self.state in ('trial', 'confirmed'):
            return self.state
        if self.state != 'prepared':
            raise RecoveryRefused('A rolled-back trial cannot restart')
        if digest(self.operations.original) != self.original_sha or digest(self.operations.candidate) != self.candidate_sha:
            raise RecoveryRefused('Sources changed since prepare')
        self.operations.apply(self.original_sha, self.candidate_sha)
        now = self.clock()
        self.deadline = now + self.timeout
        self.last_heartbeat = now
        self.state = 'trial'
        return self.state

    def heartbeat(self, sequence, view_ready, navigation_ok, error=None):
        if self.state == 'rolled_back':
            return self.state
        if self.state not in ('trial', 'confirmed'):
            raise RecoveryRefused('No active trial')
        if type(sequence) is not int or sequence < 0:
            raise ValueError('Heartbeat sequence must be a nonnegative integer')
        if self.poll() == 'rolled_back':
            return self.state
        if sequence <= self.sequence:
            return self.state
        self.sequence = sequence
        if error or view_ready is not True or navigation_ok is not True:
            return self.rollback('ui-error' if error else 'unhealthy-view-or-navigation')
        self.last_heartbeat = self.clock()
        self.healthy = True
        return self.state

    def confirm(self):
        if self.state == 'confirmed':
            return self.poll()
        if self.state != 'trial':
            raise RecoveryRefused('Only a live trial can be confirmed')
        if self.poll() == 'rolled_back':
            return self.state
        if not self.healthy:
            raise RecoveryRefused('View readiness and navigation health not proved')
        self.state = 'confirmed'
        return self.state

    def poll(self):
        if self.state not in ('trial', 'confirmed'):
            return self.state
        now = self.clock()
        if digest(self.operations.original) != self.original_sha:
            raise RecoveryRefused('Original changed; automatic restoration unsafe')
        if digest(self.operations.candidate) != self.candidate_sha:
            return self.rollback('candidate-changed')
        if digest(self.target) != self.candidate_sha:
            return self.rollback('target-changed')
        if now >= self.deadline:
            return self.rollback('trial-expired')
        if now - self.last_heartbeat >= self.heartbeat_timeout:
            return self.rollback('heartbeat-expired')
        return self.state

    def crash(self):
        if self.state not in ('trial', 'confirmed'):
            return self.state
        return self.rollback('compositor-crash')

    def rollback(self, reason='operator-ended-trial'):
        if self.state == 'rolled_back':
            return self.state
        if self.state == 'prepared':
            self.state, self.reason = 'rolled_back', reason
            return self.state
        self.operations.restore(self.original_sha, self.candidate_sha)
        self.state, self.reason = 'rolled_back', reason
        return self.state
