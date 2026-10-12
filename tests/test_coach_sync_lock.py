"""Entry-point lock guards, with no Git/network or production data mutations."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

PROJECT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('coach_sync_lock_module', PROJECT / 'scripts/coach.py')
coach = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coach)


class SyncEntryPointLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'README.md').write_text('TEST ONLY project data remains unchanged\n')

    def test_sync_cli_defers_while_session_writer_lock_is_held(self):
        original = (self.root / 'README.md').read_bytes()
        with coach.session.mutation_lock(self.root):
            process = subprocess.run([sys.executable, str(PROJECT / 'scripts/sync.py'), 'push',
                                      '--root', str(self.root), '--message', 'TEST ONLY blocked sync'],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8', timeout=10)
        self.assertEqual(process.returncode, 1, process.stdout + process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(report['status'], 'busy')
        self.assertEqual(report['error'], 'session_busy')
        self.assertFalse(report['remote_verified'])
        self.assertFalse((self.root / '.git').exists())
        self.assertFalse((self.root / '.local' / 'sync.lock').exists())
        self.assertEqual((self.root / 'README.md').read_bytes(), original)
        self.assertEqual(json.loads((self.root / '.local' / 'sync.json').read_text())['status'], 'busy')

    def test_coach_session_lock_io_failure_is_structured_without_native_git(self):
        original = (self.root / 'README.md').read_bytes()
        with mock.patch.object(coach.session, 'mutation_lock', side_effect=OSError('TEST ONLY lock storage unavailable')):
            with mock.patch.object(coach.git_sync, 'synchronize', side_effect=AssertionError('Git must not be called')) as native:
                report = coach.sync_action(self.root, 'push', 'TEST ONLY blocked sync')
        self.assertEqual(report['status'], 'error')
        self.assertEqual(report['error'], 'session_lock_io')
        self.assertEqual(report['exit_code'], 1)
        self.assertFalse(report['remote_verified'])
        native.assert_not_called()
        self.assertFalse((self.root / '.git').exists())
        self.assertEqual((self.root / 'README.md').read_bytes(), original)
        self.assertEqual(json.loads((self.root / '.local' / 'sync.json').read_text())['error'], 'session_lock_io')


if __name__ == '__main__':
    unittest.main()
