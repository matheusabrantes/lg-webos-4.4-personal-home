"""Transport checks with every subprocess mocked; no device access."""
from pathlib import Path
import json
import shlex
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import tv


class Transport(unittest.TestCase):
    def test_missing_host_fails_before_subprocess(self):
        with patch.object(tv, 'HOST', ''), patch.object(tv.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                tv.shell('true')
            run.assert_not_called()

    def test_invalid_host_is_rejected(self):
        for value in ['host -o ProxyCommand=bad', '-invalid', 'host;bad']:
            with patch.object(tv, 'HOST', value):
                with self.assertRaises(ValueError):
                    tv.target()

    def test_luna_preserves_payload_and_host_key_checks(self):
        payload = {'value': "literal $(text) and 'quotes'"}
        result = SimpleNamespace(returncode=0, stdout=b'header\n{"returnValue":true}\n')
        with patch.object(tv, 'HOST', '192.0.2.10'), patch.object(tv.subprocess, 'run', return_value=result) as run:
            self.assertEqual(tv.luna('example.service/method', payload), {'returnValue': True})
            command = run.call_args.args[0]
            self.assertIn('StrictHostKeyChecking=yes', command)
            self.assertEqual(command[-2], 'root@192.0.2.10')
            parsed = shlex.split(command[-1])
            self.assertEqual(parsed[-2], 'luna://example.service/method')
            self.assertEqual(json.loads(parsed[-1]), payload)


if __name__ == '__main__':
    unittest.main()
