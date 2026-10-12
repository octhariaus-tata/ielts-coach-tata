"""Scheduled backup tests with temporary packages and no production/network writes."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

PROJECT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
spec = importlib.util.spec_from_file_location('hourly_module', PROJECT / 'scripts/hourly_sync.py')
hourly = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hourly)


class HourlySyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(PROJECT / 'materials', self.root / 'materials')
        shutil.copytree(PROJECT / 'coach_refs', self.root / 'coach_refs')
        self.catalog = json.loads((PROJECT / 'materials.json').read_text(encoding='utf-8'))
        (self.root / 'materials.json').write_text(json.dumps(self.catalog), encoding='utf-8')
        for name in ('PROFILE.md', 'PLAN.md', 'STATUS.md', 'PROGRESS.md'):
            (self.root / name).write_text('# TEST ONLY ' + name + '\nNo real learner progress.\n', encoding='utf-8')
        self.patch = mock.patch.object(hourly.git_sync, 'synchronize', side_effect=self.synced)
        self.synchronize = self.patch.start()
        self.addCleanup(self.patch.stop)

    def report(self, state='synced', verified=True):
        return {'action': 'push', 'status': state, 'remote_verified': verified,
                'ahead': 0, 'behind': 0, 'pending_files': [], 'foreign_files': [],
                'branch': 'main', 'local_head': 'TEST-ONLY-head', 'remote_head': 'TEST-ONLY-head',
                'message': 'TEST ONLY backup report'}

    def synced(self, root, action, message, **kwargs):
        return self.report(), 0

    def local_log(self):
        return json.loads((self.root / '.local' / 'scheduled-sync.json').read_text(encoding='utf-8'))

    def system_record(self):
        record = hourly.session.start(self.root, 'TEST-ONLY-rehearsal', 'Listening', 'system_test', 20)['session']
        result = {'mode': 'answers_key', 'scope': 'partial', 'score': {'correct': 1, 'total': 1},
                  'key_task_id': record['task_id'], 'key_version_verified': True,
                  'key_url': 'https://example.invalid/TEST-ONLY-key',
                  'verification_method': 'TEST ONLY source comparison',
                  'source_response': {'text': 'TEST ONLY raw answer 1 A',
                                      'provenance': {'method': 'TEST ONLY input observed', 'reference': 'chat:TEST-ONLY-message'}},
                  'answers': [{'number': '1', 'given': 'A', 'expected': 'A', 'correct': True,
                               'proof': 'TEST ONLY synthetic source proof'}],
                  'feedback': {'strength': 'TEST ONLY observed', 'patterns': [],
                               'action': 'TEST ONLY action', 'next_task': 'TEST ONLY follow up'}}
        return hourly.session.finalize(self.root, record['id'], result)['session']

    def test_idle_validated_run_pushes_once_and_records_current_verified_status(self):
        result, code = hourly.run(self.root)
        self.assertEqual(code, 0)
        self.assertTrue(result['synced'])
        self.assertTrue(result['remote_verified'])
        self.assertEqual(result['status'], 'synced')
        self.assertTrue(result['saved_locally'])
        self.assertFalse(result['learning_readiness_changed'])
        self.synchronize.assert_called_once()
        self.assertEqual(self.synchronize.call_args.args[1], 'push')
        self.assertEqual(self.local_log()['status'], 'synced')
        self.assertFalse((self.root / 'feedback').exists())
        self.assertFalse((self.root / 'learning').exists())

    def test_offline_run_preserves_completed_record_and_reports_unsynced(self):
        record = self.system_record()
        path = hourly.session.session_path(self.root, record['id'])
        original = path.read_bytes()
        offline = dict(self.report('error', False), error='network_error', message='TEST ONLY offline')
        self.synchronize.side_effect = lambda *args, **kwargs: (offline, 1)
        result, code = hourly.run(self.root)
        self.assertEqual(code, 1)
        self.assertFalse(result['synced'])
        self.assertTrue(result['saved_locally'])
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.local_log()['error'], 'network_error')

    def test_locked_writer_defers_without_push_or_summary_mutation(self):
        original_progress = (self.root / 'PROGRESS.md').read_bytes()
        with hourly.session.mutation_lock(self.root):
            result, code = hourly.run(self.root)
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'busy')
        self.assertTrue(result['deferred'])
        self.assertFalse(result['synced'])
        self.synchronize.assert_not_called()
        self.assertEqual((self.root / 'PROGRESS.md').read_bytes(), original_progress)
        self.assertEqual(self.local_log()['status'], 'busy')
        recovered, code = hourly.run(self.root)
        self.assertEqual(code, 0)
        self.assertTrue(recovered['synced'])

    def test_git_operation_busy_defers_without_claiming_sync(self):
        self.synchronize.side_effect = lambda *args, **kwargs: (
            dict(self.report('error', False), error='sync_busy', message='TEST ONLY other Git operation'), 1)
        result, code = hourly.run(self.root)
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'busy')
        self.assertTrue(result['deferred'])
        self.assertFalse(result['synced'])
        self.assertEqual(self.local_log()['status'], 'busy')

    def test_invalid_correction_cache_blocks_before_push_and_keeps_source_file(self):
        task = next(t for t in self.catalog['tasks'] if t['id'] == 'listening-packham-form')
        path = self.root / task['coach_reference']['path']
        path.write_text(path.read_text() + '\nTEST ONLY corrupted cache')
        original = path.read_bytes()
        result, code = hourly.run(self.root)
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['synced'])
        self.synchronize.assert_not_called()
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(self.local_log()['error'], 'local_validation_failed')

    def test_invalid_persisted_feedback_blocks_before_push_without_repairing_event(self):
        hourly.adaptation.record_feedback(self.root, {
            'event_id': 'TEST-ONLY-feedback', 'category': 'preference', 'actor': 'learner',
            'text': 'TEST ONLY explicit preference', 'signals': {'available_minutes': 15},
            'provenance': {'method': 'TEST ONLY input observed', 'reference': 'chat:TEST-ONLY-feedback-message'}})
        path = self.root / 'feedback' / 'TEST-ONLY-feedback.json'
        event = json.loads(path.read_text())
        event['payload']['signals']['available_minutes'] = 9999
        path.write_text(json.dumps(event))
        original = path.read_bytes()
        result, code = hourly.run(self.root)
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['synced'])
        self.synchronize.assert_not_called()
        self.assertEqual(path.read_bytes(), original)
        with hourly.session.mutation_lock(self.root):
            pass

    def test_invalid_session_envelope_blocks_without_overwriting_record(self):
        record = self.system_record()
        path = hourly.session.session_path(self.root, record['id'])
        bad = dict(record, schema_version=99)
        path.write_text(json.dumps(bad))
        original = path.read_bytes()
        result, code = hourly.run(self.root)
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'blocked')
        self.synchronize.assert_not_called()
        self.assertEqual(path.read_bytes(), original)

    def test_scheduled_run_never_grades_restarts_or_counts_system_tests_as_progress(self):
        record = self.system_record()
        path = hourly.session.session_path(self.root, record['id'])
        original = path.read_bytes()
        with mock.patch.object(hourly.session, 'finalize', side_effect=AssertionError('Must not grade')):
            with mock.patch.object(hourly.session, 'start', side_effect=AssertionError('Must not start a new attempt')):
                result, code = hourly.run(self.root)
        self.assertEqual(code, 0)
        self.assertTrue(result['synced'])
        self.assertEqual(path.read_bytes(), original)
        self.assertNotIn(record['id'], (self.root / 'PROGRESS.md').read_text())
        self.assertIn('Sesi belajar selesai: 0', (self.root / 'STATUS.md').read_text())
        self.assertEqual(len(list((self.root / 'sessions').glob('*.json'))), 1)

    def test_repeated_synced_idle_runs_do_not_change_records_or_summary_contents(self):
        record = self.system_record()
        path = hourly.session.session_path(self.root, record['id'])
        original = path.read_bytes()
        hourly.run(self.root)
        summaries = {name: (self.root / name).read_bytes() for name in ('PROGRESS.md', 'STATUS.md')}
        self.synchronize.reset_mock()
        result, code = hourly.run(self.root)
        self.assertEqual(code, 0)
        self.assertTrue(result['synced'])
        self.synchronize.assert_called_once()
        self.assertEqual(path.read_bytes(), original)
        for name, content in summaries.items():
            self.assertEqual((self.root / name).read_bytes(), content)

    def test_summary_failure_blocks_push_and_releases_writer_lock(self):
        with mock.patch.object(hourly.session, '_rebuild', side_effect=OSError('TEST ONLY summary storage failure')):
            result, code = hourly.run(self.root)
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['synced'])
        self.synchronize.assert_not_called()
        with hourly.session.mutation_lock(self.root):
            pass
        recovered, code = hourly.run(self.root)
        self.assertEqual(code, 0)
        self.assertTrue(recovered['synced'])

    def test_unknown_remote_verification_never_claims_synced(self):
        self.synchronize.side_effect = lambda *args, **kwargs: (self.report('synced', False), 0)
        result, code = hourly.run(self.root)
        self.assertEqual(code, 0)
        self.assertFalse(result['synced'])
        self.assertFalse(result['remote_verified'])
        self.assertFalse(self.local_log()['synced'])

    def test_clean_clone_uses_fresh_pull_and_avoids_empty_push(self):
        view = {'pending_files': [], 'ahead': 0, 'staged_foreign_files': []}
        with mock.patch.object(hourly.git_sync, 'Git'):
            with mock.patch.object(hourly.git_sync, 'repository'):
                with mock.patch.object(hourly.git_sync, 'snapshot', return_value=view):
                    result, code = hourly.run(self.root)
        self.assertEqual(code, 0)
        self.assertTrue(result['synced'])
        self.synchronize.assert_called_once()
        self.assertEqual(self.synchronize.call_args.args[1], 'pull')

    def test_unsafe_local_cache_is_blocked_without_writing_through_symlink(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        target = Path(outside.name)
        (self.root / '.local').symlink_to(target, target_is_directory=True)
        result, code = hourly.run(self.root)
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['synced'])
        self.assertFalse(result['run_log_saved'])
        self.assertEqual(list(target.iterdir()), [])
        self.synchronize.assert_not_called()

    def test_missing_project_is_blocked_without_creating_a_folder(self):
        missing = self.root / 'TEST-ONLY-missing-project'
        result, code = hourly.run(missing)
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'blocked')
        self.assertFalse(result['run_log_saved'])
        self.assertFalse(missing.exists())
        self.synchronize.assert_not_called()


if __name__ == '__main__':
    unittest.main()
