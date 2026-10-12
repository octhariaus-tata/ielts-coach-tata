"""Git operation serialization, using OS locks and mocked Git execution."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('sync_lock_module', Path(__file__).parents[1] / 'scripts/sync.py')
git_sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(git_sync)


class SyncLockTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'README.md').write_text('TEST ONLY unchanged project data\n')

    def test_held_git_lock_defers_before_any_git_or_commit_operation(self):
        original = (self.root / 'README.md').read_bytes()
        with git_sync.sync_lock(self.root):
            with mock.patch.object(git_sync, '_synchronize', side_effect=AssertionError('Must not invoke Git')) as execute:
                report, code = git_sync.synchronize(self.root, 'push', 'TEST ONLY backup')
        self.assertEqual(code, 1)
        self.assertEqual(report['status'], 'busy')
        self.assertEqual(report['error'], 'sync_busy')
        self.assertFalse(report['remote_verified'])
        execute.assert_not_called()
        self.assertEqual((self.root / 'README.md').read_bytes(), original)
        self.assertFalse((self.root / '.git').exists())

    def test_exception_releases_git_lock_for_the_next_operation(self):
        with mock.patch.object(git_sync, '_synchronize', side_effect=RuntimeError('TEST ONLY interrupted Git operation')):
            with self.assertRaises(RuntimeError):
                git_sync.synchronize(self.root, 'push', 'TEST ONLY interrupted')
        verified = {'status': 'synced', 'remote_verified': True, 'action': 'push'}
        with mock.patch.object(git_sync, '_synchronize', return_value=(verified, 0)) as execute:
            report, code = git_sync.synchronize(self.root, 'push', 'TEST ONLY retry')
        self.assertEqual(code, 0)
        self.assertEqual(report, verified)
        execute.assert_called_once()
        with git_sync.sync_lock(self.root):
            pass


if __name__ == '__main__':
    unittest.main()
