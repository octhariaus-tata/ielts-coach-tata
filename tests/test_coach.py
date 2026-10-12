"""End-to-end local coaching workflow tests; no network or learner data writes."""
import base64
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import wave
from unittest import mock

PROJECT = Path(__file__).parents[1]
sys.path.insert(0, str(PROJECT / 'scripts'))
spec = importlib.util.spec_from_file_location('coach_module', PROJECT / 'scripts/coach.py')
coach = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coach)


class CoachTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(PROJECT / 'materials', self.root / 'materials')
        shutil.copytree(PROJECT / 'coach_refs', self.root / 'coach_refs')
        shutil.copytree(PROJECT / 'scripts', self.root / 'scripts')
        self.catalog = json.loads((PROJECT / 'materials.json').read_text(encoding='utf-8'))
        (self.root / 'materials.json').write_text(json.dumps(self.catalog), encoding='utf-8')
        for name in ('PROFILE.md', 'PLAN.md', 'AGENTS.md', 'TASK_BANK.md', 'STATUS.md', 'PROGRESS.md'):
            (self.root / name).write_text('# TEST ONLY ' + name + '\n\nNo learner progress.\n', encoding='utf-8')
        self.sync = mock.patch.object(coach.git_sync, 'synchronize', side_effect=self.synced)
        self.synchronize = self.sync.start()
        self.addCleanup(self.sync.stop)
        self.task_id = 'listening-packham-form'

    def report(self, action, state='synced', verified=True):
        return {'action': action, 'status': state, 'remote_verified': verified,
                'ahead': 0, 'behind': 0, 'pending_files': [], 'foreign_files': [],
                'staged_foreign_files': [], 'conflicts': [],
                'branch': 'main', 'local_head': 'TEST-ONLY-head', 'remote_head': 'TEST-ONLY-head',
                'checked_at': '2026-10-12T00:00:00+00:00', 'message': 'TEST ONLY sync report'}

    def synced(self, root, action, message, **kwargs):
        return self.report(action), 0

    def offline(self, root, action, message, **kwargs):
        report = self.report(action, 'error', False)
        report.update(error='network_error', message='TEST ONLY network unavailable')
        return report, 1

    def records(self):
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted((self.root / 'sessions').glob('*.json'))]

    def prepare(self):
        coach.prepare(self.root, task_id=self.task_id, minutes=20, kind='practice')
        return self.records()[0]

    def input(self):
        return {'score': {'correct': 5, 'total': 8},
                'provenance': {'method': 'TEST ONLY total score observed',
                               'reference': 'chat:TEST-ONLY-score-message'}}

    def result(self):
        return {'mode': 'score_only', 'scope': 'partial', 'score': {'correct': 5, 'total': 8},
                'verification_method': 'TEST ONLY score-only input',
                'feedback': {'strength': 'TEST ONLY total score supports limited feedback', 'patterns': [],
                             'action': 'TEST ONLY use new questions next',
                             'next_task': 'TEST ONLY Reading next'}}

    def test_offline_prepare_uses_verified_local_materials(self):
        self.synchronize.side_effect = self.offline
        record = self.prepare()
        self.assertEqual(record['task_id'], self.task_id)
        self.assertEqual(record['status'], 'in_progress')
        self.assertEqual(record['phase'], 'working')
        self.assertTrue((self.root / record['material']['local']['prompt']).is_file())
        self.assertTrue((self.root / record['material']['local']['audio']).is_file())
        self.assertTrue(any(call.args[1] == 'pull' for call in self.synchronize.call_args_list))

    def test_prepare_resumes_same_attempt_while_ignoring_new_requested_task(self):
        original = self.prepare()
        coach.checkpoint(self.root, original['id'], {'phase': 'awaiting_evidence'})
        coach.prepare(self.root, task_id='reading-making-time-matching', minutes=10, kind='practice')
        records = self.records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['id'], original['id'])
        self.assertEqual(records[0]['phase'], 'awaiting_evidence')
        self.assertEqual(records[0]['available_minutes'], 20)

    def test_checkpoint_keeps_input_and_waiting_phase(self):
        record = self.prepare()
        coach.checkpoint(self.root, record['id'], self.input())
        coach.checkpoint(self.root, record['id'], {'phase': 'awaiting_evidence'})
        restored = self.records()[0]
        self.assertEqual(restored['id'], record['id'])
        self.assertEqual(restored['phase'], 'awaiting_evidence')
        self.assertEqual(restored['response_revisions'][0]['payload']['score'], self.input()['score'])
        self.assertIsNone(restored['result'])

    def test_checkpoint_missing_provenance_never_mutates_record(self):
        record = self.prepare()
        path = self.root / 'sessions' / (record['id'] + '.json')
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            coach.checkpoint(self.root, record['id'], {'text': 'TEST ONLY answer with no origin'})
        self.assertEqual(before, path.read_bytes())

    def test_complete_saved_locally_on_push_failure_and_retry_has_no_regrade(self):
        record = self.prepare()
        coach.checkpoint(self.root, record['id'], self.input())
        def fail_push(root, action, message, **kwargs):
            return self.offline(root, action, message) if action == 'push' else self.synced(root, action, message)
        self.synchronize.side_effect = fail_push
        outcome = coach.complete(self.root, record['id'], self.result())
        self.assertTrue(outcome['saved'])
        self.assertFalse(outcome['synced'])
        path = self.root / 'sessions' / (record['id'] + '.json')
        before = path.read_bytes()
        self.assertEqual(self.records()[0]['status'], 'completed')
        self.synchronize.side_effect = self.synced
        self.synchronize.reset_mock()
        with mock.patch.object(coach.session, 'finalize', side_effect=AssertionError('Retry must not regrade')):
            retried = coach.complete(self.root, record['id'])
        self.assertTrue(retried['retry_sync_only'])
        self.assertTrue(retried['synced'])
        self.assertEqual(before, path.read_bytes())
        self.assertEqual(len(self.records()), 1)
        self.assertTrue(any(call.args[1] == 'push' for call in self.synchronize.call_args_list))
        progress = (self.root / 'PROGRESS.md').read_text(encoding='utf-8')
        self.assertEqual(progress.count('| ['), 1)

    def test_missing_cache_during_done_leaves_response_pending(self):
        record = self.prepare()
        coach.checkpoint(self.root, record['id'], self.input())
        (self.root / record['material']['coach_reference']['path']).unlink()
        objective = dict(self.result(), mode='answers_key')
        outcome = coach.complete(self.root, record['id'], objective)
        self.assertEqual(outcome['waiting'], 'correction_cache')
        stored = self.records()[0]
        self.assertEqual(stored['id'], record['id'])
        self.assertEqual(stored['status'], 'in_progress')
        self.assertEqual(stored['phase'], 'awaiting_review')
        self.assertIsNone(stored['result'])
        self.assertEqual(stored['response_revisions'][0]['payload']['score'], self.input()['score'])

    def test_complete_without_evidence_stays_waiting(self):
        record = self.prepare()
        coach.complete(self.root, record['id'])
        stored = self.records()[0]
        self.assertEqual(stored['status'], 'in_progress')
        self.assertEqual(stored['phase'], 'awaiting_evidence')
        self.assertIsNone(stored['result'])

    def test_repeat_done_with_changed_result_never_overwrites_original(self):
        record = self.prepare()
        coach.checkpoint(self.root, record['id'], self.input())
        coach.complete(self.root, record['id'], self.result())
        path = self.root / 'sessions' / (record['id'] + '.json')
        before = path.read_bytes()
        changed = copy.deepcopy(self.result())
        changed['feedback']['action'] = 'TEST ONLY changed feedback'
        with self.assertRaises(ValueError):
            coach.complete(self.root, record['id'], changed)
        self.assertEqual(before, path.read_bytes())

    def screenshot(self):
        target = self.root / 'evidence' / 'TEST-ONLY-screenshot.png'
        target.parent.mkdir(exist_ok=True)
        target.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2n0UAAAAASUVORK5CYII='))
        return 'evidence/TEST-ONLY-screenshot.png'

    def recording(self):
        target = self.root / 'evidence' / 'TEST-ONLY-recording.wav'
        target.parent.mkdir(exist_ok=True)
        with wave.open(str(target), 'wb') as recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(8000)
            recording.writeframes(b'\x00\x00' * 800)
        return 'evidence/TEST-ONLY-recording.wav'

    def observation(self, capability, reference, evidence=None):
        return {'capability': capability, 'status': 'passed', 'evidence': evidence or [],
                'provenance': {'method': 'TEST ONLY simulated capability observation', 'reference': reference}}

    def test_prepare_learner_packet_never_exposes_key_transcript_or_cache(self):
        prepared = coach.prepare(self.root, task_id=self.task_id)
        packet = prepared['packet']
        self.assertEqual(packet['local']['prompt'], 'materials/listening-packham-form.pdf')
        self.assertTrue(packet['local']['audio'].startswith('materials/'))
        serialized = json.dumps(packet)
        for forbidden in ('coach_refs/', 'coach_reference', 'key_pages', 'answer_lines', 'page_texts', '"urls"', 'transcript_pages'):
            self.assertNotIn(forbidden, serialized)

    def test_checkpoint_summary_interruption_recovers_same_input_once(self):
        record = self.prepare()
        with mock.patch.object(coach.session, 'managed_section', side_effect=OSError('TEST ONLY interruption')):
            outcome = coach.checkpoint(self.root, record['id'], self.input())
        self.assertTrue(outcome['saved'])
        self.assertFalse(outcome['summaries_saved'])
        self.assertFalse(outcome['synced'])
        stored = self.records()[0]
        self.assertEqual(stored['response_revisions'][0]['payload']['score'], self.input()['score'])
        self.synchronize.side_effect = self.offline
        retried = coach.checkpoint(self.root, record['id'], self.input())
        self.assertTrue(retried['duplicate'])
        self.assertEqual(len(self.records()[0]['response_revisions']), 1)
        self.assertFalse(retried['synced'])

    def test_readiness_distinguishes_files_playback_speaking_and_transfer(self):
        prepared = coach.prepare(self.root, task_id=self.task_id)
        readiness = prepared['readiness']
        self.assertEqual(readiness['checks']['prompt']['status'], 'passed')
        self.assertEqual(readiness['checks']['audio_file']['status'], 'passed')
        self.assertEqual(readiness['checks']['correction_cache']['status'], 'passed')
        self.assertEqual(readiness['checks']['audio_playback']['status'], 'not_tested')
        self.assertFalse(readiness['ready_local_listening'])
        self.assertFalse(readiness['speaking_verified'])
        screenshot = self.screenshot()
        coach.status(self.root, self.observation('screenshot_capture', screenshot, [screenshot]))
        audio = prepared['session']['material']['local']['audio']
        report = coach.status(self.root, self.observation('audio_playback', audio))
        self.assertTrue(report['readiness']['ready_local_listening'])
        self.assertFalse(report['readiness']['speaking_verified'])
        self.assertFalse(report['readiness']['safe_switch_laptop'])
        recording = self.recording()
        report = coach.status(self.root, self.observation('speaking_audio', recording, [recording]))
        self.assertTrue(report['readiness']['speaking_verified'])
        self.assertFalse(report['readiness']['safe_switch_laptop'])
        (self.root / recording).unlink()
        self.assertFalse(coach.status(self.root)['readiness']['speaking_verified'])

    def test_readiness_rejects_invalid_observation_provenance_or_missing_artifact(self):
        invalid = [self.observation('screenshot_capture', 'chat:TEST-ONLY-no-image'),
                   self.observation('speaking_audio', 'chat:TEST-ONLY-no-recording'),
                   self.observation('screenshot_capture', 'evidence/missing.png', ['evidence/missing.png']),
                   self.observation('audio_playback', '../outside.wav'),
                   {'capability': 'audio_playback', 'status': 'passed', 'provenance': {}}]
        for value in invalid:
            with self.assertRaises(ValueError):
                coach.status(self.root, value)
        self.assertFalse((self.root / '.local' / 'readiness.json').exists())

    def test_playback_observation_requires_audio_material_and_matching_task(self):
        prepared = coach.prepare(self.root, task_id=self.task_id)
        screenshot = self.screenshot()
        coach.status(self.root, self.observation('screenshot_capture', screenshot, [screenshot]))
        for reference in ('PROFILE.md', prepared['session']['material']['coach_reference']['path']):
            with self.assertRaises(ValueError):
                coach.status(self.root, self.observation('audio_playback', reference))
        backup = next(t for t in self.catalog['tasks'] if t['id'] == 'listening-social-contact-short-answer')
        report = coach.status(self.root, self.observation('audio_playback', backup['local']['audio']))
        self.assertFalse(report['readiness']['ready_local_listening'])

    def test_historical_synced_cache_never_proves_current_transfer_readiness(self):
        self.prepare()
        stale = self.report('push')
        stale['checked_at'] = '2020-01-01T00:00:00+00:00'
        coach.git_sync.save_status(self.root, stale)
        self.synchronize.reset_mock()
        report = coach.status(self.root)
        self.assertFalse(report['readiness']['safe_switch_laptop'])
        self.assertFalse(report['sync']['remote_verified'])
        self.assertEqual(self.synchronize.call_count, 0)

    def test_current_sync_must_be_clean_verified_and_up_to_date_to_switch(self):
        self.prepare()
        verified = coach.status(self.root, verify_sync=True)
        self.assertTrue(verified['readiness']['safe_switch_laptop'])
        for change in ({'status': 'ahead', 'ahead': 1}, {'status': 'behind', 'behind': 1},
                       {'status': 'unpublished', 'pending_files': ['sessions/TEST-ONLY.json']},
                       {'status': 'synced', 'remote_verified': False},
                       {'status': 'synced', 'foreign_files': ['other-file']}):
            state = self.report('status')
            state.update(change)
            self.synchronize.side_effect = lambda *args, report=state, **kwargs: (report, 0)
            report = coach.status(self.root, verify_sync=True)
            self.assertFalse(report['readiness']['safe_switch_laptop'], change)

    def test_remote_behind_with_local_changes_requires_reconciliation_before_new_attempt(self):
        def diverged(root, action, message, **kwargs):
            state = self.report(action, 'behind')
            state.update(behind=1, pending_files=['STATUS.md'], error='dirty_worktree')
            return state, 1
        self.synchronize.side_effect = diverged
        prepared = coach.prepare(self.root, task_id=self.task_id)
        self.assertEqual(prepared['waiting'], 'reconciliation')
        self.assertEqual(self.records(), [])
        self.assertFalse(prepared['created'])

    def test_readiness_is_device_local_and_cannot_be_inherited_from_other_device(self):
        self.prepare()
        screenshot = self.screenshot()
        coach.status(self.root, self.observation('screenshot_capture', screenshot, [screenshot]))
        path = self.root / '.local' / 'readiness.json'
        cache = json.loads(path.read_text())
        cache['device_id'] = 'TEST-ONLY-other-device'
        path.write_text(json.dumps(cache))
        report = coach.status(self.root)
        self.assertEqual(report['readiness']['checks']['screenshot_capture']['status'], 'not_tested')

    def test_summary_failure_preserves_completed_record_and_retry_rebuilds_before_push(self):
        record = self.prepare()
        coach.checkpoint(self.root, record['id'], self.input())
        self.synchronize.reset_mock()
        with mock.patch.object(coach.session, '_rebuild', side_effect=OSError('TEST ONLY summaries unavailable')):
            outcome = coach.complete(self.root, record['id'], self.result())
        self.assertTrue(outcome['saved'])
        self.assertFalse(outcome['summaries_saved'])
        self.assertFalse(outcome['synced'])
        self.assertFalse(any(call.args[1] == 'push' for call in self.synchronize.call_args_list))
        path = self.root / 'sessions' / (record['id'] + '.json')
        before = path.read_bytes()
        self.assertEqual(self.records()[0]['status'], 'completed')
        self.assertNotIn('| [' + record['id'], (self.root / 'PROGRESS.md').read_text())
        with mock.patch.object(coach.session, 'finalize', side_effect=AssertionError('Retry must not regrade')):
            retry = coach.complete(self.root, record['id'])
        self.assertTrue(retry['saved'])
        self.assertTrue(retry['summaries_saved'])
        self.assertTrue(retry['synced'])
        self.assertTrue(retry['retry_sync_only'])
        self.assertEqual(before, path.read_bytes())
        self.assertIn(record['id'], (self.root / 'PROGRESS.md').read_text())
        self.assertEqual((self.root / 'PROGRESS.md').read_text().count('| ['), 1)
        self.assertTrue(any(call.args[1] == 'push' for call in self.synchronize.call_args_list))

    def test_unverified_response_is_kept_pending_without_completed_progress(self):
        record = self.prepare()
        coach.checkpoint(self.root, record['id'], {'text': 'TEST ONLY unreadable response excerpt',
                                                'provenance': self.input()['provenance']})
        result = self.result()
        result.update(mode='unverified', score=None)
        outcome = coach.complete(self.root, record['id'], result)
        self.assertFalse(outcome['saved'])
        stored = self.records()[0]
        self.assertEqual(stored['status'], 'in_progress')
        self.assertEqual(stored['phase'], 'awaiting_review')
        self.assertIsNone(stored['result'])
        self.assertEqual(len(stored['response_revisions']), 2)
        self.assertNotIn('| [' + record['id'], (self.root / 'PROGRESS.md').read_text())

    def test_direct_response_is_checkpointed_before_invalid_grade_stays_pending(self):
        record = self.prepare()
        result = self.result()
        result['score'] = None
        result['source_response'] = {'text': 'TEST ONLY original raw response before grading',
                                     'provenance': self.input()['provenance']}
        outcome = coach.complete(self.root, record['id'], result)
        self.assertFalse(outcome['saved'])
        stored = self.records()[0]
        self.assertEqual(stored['status'], 'in_progress')
        self.assertTrue(any(r['payload'].get('text') == result['source_response']['text']
                            for r in stored['response_revisions']))
        self.assertIsNone(stored['result'])

    def test_malformed_checkpoint_or_result_is_rejected_without_mutation(self):
        record = self.prepare()
        path = self.root / 'sessions' / (record['id'] + '.json')
        before = path.read_bytes()
        for payload in (None, [], 17, 'TEST ONLY scalar'):
            with self.assertRaises(ValueError):
                coach.checkpoint(self.root, record['id'], payload)
            self.assertEqual(before, path.read_bytes())
        for result in ([], 17, 'TEST ONLY scalar'):
            with self.assertRaises(ValueError):
                coach.complete(self.root, record['id'], result)
            self.assertEqual(before, path.read_bytes())

    def test_direct_source_checkpoint_summary_failure_preserves_input_before_grading(self):
        record = self.prepare()
        result = self.result()
        result['source_response'] = self.input()
        self.synchronize.reset_mock()
        with mock.patch.object(coach.session, 'finalize', wraps=coach.session.finalize) as finalize:
            with mock.patch.object(coach.session, '_rebuild', side_effect=OSError('TEST ONLY direct input summary unavailable')):
                pending = coach.complete(self.root, record['id'], result)
            self.assertFalse(pending['saved'])
            self.assertTrue(pending['response_saved'])
            self.assertFalse(pending['summaries_saved'])
            self.assertFalse(pending['synced'])
            self.assertEqual(pending['waiting'], 'summary_recovery')
            finalize.assert_not_called()
            self.assertFalse(any(call.args[1] == 'push' for call in self.synchronize.call_args_list))
            stored = self.records()[0]
            self.assertEqual(stored['status'], 'in_progress')
            self.assertIsNone(stored['result'])
            self.assertEqual(len(stored['response_revisions']), 1)
            original = copy.deepcopy(stored['response_revisions'][0])
            self.assertEqual(original['payload']['score'], result['source_response']['score'])
            repaired = coach.complete(self.root, record['id'], result)
            self.assertTrue(repaired['saved'])
            self.assertTrue(repaired['summaries_saved'])
            self.assertTrue(repaired['synced'])
            self.assertEqual(finalize.call_count, 1)
        completed = self.records()[0]
        self.assertEqual(completed['status'], 'completed')
        self.assertEqual(completed['response_revisions'], [original])
        self.assertEqual(completed['graded_response_revision_id'], original['revision_id'])
        self.assertEqual(completed['result'], result)
        self.assertTrue(any(call.args[1] == 'push' for call in self.synchronize.call_args_list))

    def test_malformed_nested_source_response_is_rejected_without_mutation(self):
        record = self.prepare()
        path = self.root / 'sessions' / (record['id'] + '.json')
        before = path.read_bytes()
        for malformed in ([], 17, 'TEST ONLY scalar source'):
            result = self.result()
            result['source_response'] = malformed
            with self.assertRaises(ValueError):
                coach.complete(self.root, record['id'], result)
            self.assertEqual(before, path.read_bytes())

    def test_replaced_playback_and_evidence_invalidate_cached_readiness(self):
        record = self.prepare()
        audio = record['material']['local']['audio']
        screenshot = self.screenshot()
        recording = self.recording()
        coach.status(self.root, self.observation('audio_playback', audio))
        coach.status(self.root, self.observation('screenshot_capture', screenshot, [screenshot]))
        baseline = coach.status(self.root, self.observation('speaking_audio', recording, [recording]))
        self.assertTrue(baseline['readiness']['ready_local_listening'])
        self.assertTrue(baseline['readiness']['speaking_verified'])
        for path, capability, flag in ((audio, 'audio_playback', 'ready_local_listening'),
                                      (screenshot, 'screenshot_capture', 'ready_local_listening'),
                                      (recording, 'speaking_audio', 'speaking_verified')):
            asset = self.root / path
            original = asset.read_bytes()
            asset.write_bytes(original + b'TEST ONLY replacement at same path')
            report = coach.status(self.root)
            self.assertEqual(report['readiness']['checks'][capability]['status'], 'failed')
            self.assertFalse(report['readiness'][flag])
            asset.write_bytes(original)
        recovered = coach.status(self.root)
        self.assertTrue(recovered['readiness']['ready_local_listening'])
        self.assertTrue(recovered['readiness']['speaking_verified'])

    def test_missing_or_wrong_audio_provenance_blocks_local_prepare(self):
        task = next(t for t in self.catalog['tasks'] if t['id'] == self.task_id)
        path = self.root / 'materials' / 'PROVENANCE.json'
        original = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(coach.task_checks(self.root, task)['audio_file']['status'], 'passed')
        for mutation in ('missing', 'url', 'hash', 'file'):
            provenance = copy.deepcopy(original)
            audio_id = self.task_id + '-audio'
            if mutation == 'missing':
                del provenance['outputs'][audio_id]
            elif mutation == 'url':
                provenance['outputs'][audio_id]['url'] = 'https://example.invalid/TEST-ONLY-wrong-source.mp3'
            elif mutation == 'hash':
                provenance['outputs'][audio_id]['sha256'] = '0' * 64
            else:
                provenance['outputs'][audio_id]['file'] = 'materials/TEST-ONLY-other-audio.mp3'
            path.write_text(json.dumps(provenance), encoding='utf-8')
            checks = coach.task_checks(self.root, task)
            self.assertEqual(checks['audio_file']['status'], 'failed', mutation)
            prepared = coach.prepare(self.root, task_id=self.task_id)
            self.assertEqual(prepared['waiting'], 'materials', mutation)
            self.assertFalse(prepared['created'])
            self.assertEqual(self.records(), [])
        path.write_text(json.dumps(original), encoding='utf-8')


if __name__ == '__main__':
    unittest.main()
