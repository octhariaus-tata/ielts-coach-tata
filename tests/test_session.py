import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

spec = importlib.util.spec_from_file_location('session_module', Path(__file__).parents[1] / 'scripts/session.py')
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'PROGRESS.md').write_text('# Riwayat\n\nSkor historis 1/3 — bukan baseline.\n', encoding='utf-8')
        (self.root / 'STATUS.md').write_text('# Status\n\nLaptop Tata belum diperiksa.\n', encoding='utf-8')
        (self.root / 'materials.json').write_text(json.dumps({'tasks': [
            {'id': 'test-task', 'skill': 'Listening', 'source_version': 'TEST ONLY v1',
             'question_numbers': ['1', '2'],
             'urls': {'key': 'https://example.invalid/TEST-ONLY-key'}}]}))
        self.attempt = session.start(self.root, 'test-task', 'Listening', 'pilot', 20)['session']
        self.result = {
            'mode': 'answers_key', 'scope': 'partial', 'score': {'correct': 1, 'total': 2},
            'key_task_id': 'test-task', 'key_version_verified': True,
            'key_url': 'https://example.invalid/TEST-ONLY-key', 'verification_method': 'TEST ONLY partial screenshot',
            'answers': [
                {'number': '1', 'given': 'A', 'expected': 'A', 'correct': True, 'proof': 'TEST ONLY source statement 1'},
                {'number': '2', 'given': 'B', 'expected': 'C', 'correct': False, 'proof': 'TEST ONLY source statement 2'}
            ],
            'feedback': {'strength': 'TEST ONLY observed', 'patterns': ['TEST ONLY one pattern'],
                         'action': 'TEST ONLY correction', 'next_task': 'TEST ONLY new task'},
            'evidence': [], 'conditions': {'duration_actual': None},
            'source_response': {'text': 'TEST ONLY 1 A, 2 B',
                                'provenance': {'method': 'TEST ONLY screenshot inspected',
                                               'reference': 'TEST ONLY message 123'}}
        }

    def provenance(self):
        return {'method': 'TEST ONLY observed input', 'reference': 'chat:TEST-ONLY-message-123'}

    def test_resume_same_attempt_and_block_new_task(self):
        again = session.start(self.root, 'test-task', 'Listening', 'pilot', 20)
        self.assertFalse(again['created'])
        self.assertEqual(again['session']['id'], self.attempt['id'])
        with self.assertRaises(ValueError):
            session.start(self.root, 'another-task', 'Reading', 'practice', 20)

    def test_done_is_idempotent_and_historical_provenance_survives(self):
        first = session.finalize(self.root, self.attempt['id'], self.result)
        stored = (self.root / 'sessions' / (self.attempt['id'] + '.json')).read_bytes()
        second = session.finalize(self.root, self.attempt['id'], self.result)
        self.assertTrue(first['saved'])
        self.assertTrue(second['already_completed'])
        self.assertEqual(stored, (self.root / 'sessions' / (self.attempt['id'] + '.json')).read_bytes())
        progress = (self.root / 'PROGRESS.md').read_text(encoding='utf-8')
        self.assertIn('Skor historis 1/3', progress)
        self.assertEqual(progress.count('| [',), 1)
        self.assertIn('Laptop Tata belum diperiksa.', (self.root / 'STATUS.md').read_text(encoding='utf-8'))
        changed = copy.deepcopy(self.result)
        changed['feedback']['action'] = 'different'
        with self.assertRaises(ValueError):
            session.finalize(self.root, self.attempt['id'], changed)

    def test_partial_screenshot_score_only_counts_visible_answers(self):
        saved = session.finalize(self.root, self.attempt['id'], self.result)['session']
        self.assertEqual(saved['result']['score'], {'correct': 1, 'total': 2})
        self.assertNotIn('band', saved['result'])
        invalid = copy.deepcopy(self.result)
        invalid['score']['total'] = 7
        with self.assertRaises(ValueError):
            session.validate(self.root, self.attempt, invalid)

    def test_total_only_rejects_guessed_patterns(self):
        total = copy.deepcopy(self.result)
        total.update(mode='score_only', answers=[], score={'correct': 1, 'total': 2})
        total['feedback']['patterns'] = []
        total['source_response'] = {'score': total['score'], 'provenance': self.provenance()}
        session.validate(self.root, self.attempt, total)
        total['feedback']['patterns'] = ['guessed error']
        with self.assertRaises(ValueError):
            session.validate(self.root, self.attempt, total)

    def test_wrong_key_version_and_small_sample_band_rejected(self):
        wrong = copy.deepcopy(self.result)
        wrong['key_task_id'] = 'different-version'
        with self.assertRaises(ValueError):
            session.validate(self.root, self.attempt, wrong)

    def test_catalog_snapshot_survives_updates_and_wrong_source_is_rejected(self):
        (self.root / 'materials.json').write_text(json.dumps({'tasks': []}))
        self.assertEqual(self.attempt['material']['source_version'], 'TEST ONLY v1')
        wrong = copy.deepcopy(self.result)
        wrong['key_url'] = 'https://example.invalid/TEST-ONLY-other-version'
        with self.assertRaises(ValueError):
            session.validate(self.root, self.attempt, wrong)

    def test_unknown_catalog_task_cannot_start(self):
        session.finalize(self.root, self.attempt['id'], self.result)
        with self.assertRaises(ValueError):
            session.start(self.root, 'unknown', 'Reading', 'practice', 20)

    def test_completed_material_requires_review_label(self):
        session.finalize(self.root, self.attempt['id'], self.result)
        with self.assertRaises(ValueError):
            session.start(self.root, 'test-task', 'Listening', 'diagnostic', 20)
        review = session.start(self.root, 'test-task', 'Listening', 'retake', 20)
        self.assertTrue(review['created'])
        self.assertNotEqual(review['session']['id'], self.attempt['id'])
        wrong = copy.deepcopy(self.result)
        wrong['band'] = 6.0
        with self.assertRaises(ValueError):
            session.validate(self.root, self.attempt, wrong)

    def test_missing_proof_duplicate_answer_and_too_many_patterns(self):
        for mutation in ('proof', 'duplicate', 'patterns'):
            bad = copy.deepcopy(self.result)
            if mutation == 'proof':
                bad['answers'][1]['proof'] = ''
            elif mutation == 'duplicate':
                bad['answers'][1]['number'] = '1'
            else:
                bad['feedback']['patterns'] = ['1', '2', '3']
            with self.assertRaises(ValueError):
                session.validate(self.root, self.attempt, bad)

    def test_real_evidence_required_and_path_escape_rejected(self):
        bad = copy.deepcopy(self.result)
        for path in ('evidence/missing.png', '../secret.png', '/tmp/secret.png'):
            bad['evidence'] = [path]
            with self.assertRaises(ValueError):
                session.validate(self.root, self.attempt, bad)
        (self.root / 'evidence').mkdir()
        (self.root / 'evidence' / 'TEST-ONLY.png').write_bytes(b'TEST ONLY')
        bad['evidence'] = ['evidence/TEST-ONLY.png']
        session.validate(self.root, self.attempt, bad)

    def test_transcript_cannot_get_pronunciation_estimate(self):
        speaking = dict(self.attempt, skill='Speaking')
        estimate = dict(mode='ai_estimate', scope='sample', input_type='transcript',
                        criteria={'pronunciation': 6.0}, uncertainty='TEST ONLY',
                        verification_method='TEST ONLY transcript inspected',
                        source_response={'text': 'TEST ONLY spoken response', 'provenance': self.provenance()},
                        feedback=self.result['feedback'])
        with self.assertRaises(ValueError):
            session.validate(self.root, speaking, estimate)
        estimate['criteria']['pronunciation'] = None
        session.validate(self.root, speaking, estimate)

    def test_snippet_cannot_become_full_and_unknown_questions_rejected(self):
        wrong = copy.deepcopy(self.result)
        wrong['answers'][0]['number'] = '99'
        with self.assertRaises(ValueError):
            session.validate(self.root, self.attempt, wrong)
        wrong = copy.deepcopy(self.result)
        wrong.update(mode='score_only', scope='full', answers=[],
                     score={'correct': 30, 'total': 40}, band=6.5,
                     band_source_url='https://example.invalid/TEST-ONLY')
        wrong['feedback']['patterns'] = []
        with self.assertRaises(ValueError):
            session.validate(self.root, self.attempt, wrong)

    def test_pronunciation_requires_known_audio_input(self):
        speaking = dict(self.attempt, skill='Speaking')
        estimate = dict(mode='ai_estimate', scope='sample', criteria={'pronunciation': 6.0},
                        verification_method='TEST ONLY audio inspected',
                        source_response={'text': 'TEST ONLY spoken response', 'provenance': self.provenance()},
                        uncertainty='TEST ONLY', feedback=self.result['feedback'])
        with self.assertRaises(ValueError):
            session.validate(self.root, speaking, estimate)
        estimate['input_type'] = 'audio'
        with self.assertRaises(ValueError):
            session.validate(self.root, speaking, estimate)
        estimate.update(audio_inspected=True, audio_reference='chat:TEST-ONLY-audio-message')
        estimate['source_response'] = {'input_type': 'audio', 'audio_reference': estimate['audio_reference'],
                                       'provenance': self.provenance()}
        session.validate(self.root, speaking, estimate)

    def test_corrupt_record_rejected_before_mutation(self):
        path = self.root / 'sessions' / (self.attempt['id'] + '.json')
        bad = dict(self.attempt, schema_version=99)
        path.write_text(json.dumps(bad))
        before = path.read_bytes()
        with self.assertRaises(ValueError):
            session.finalize(self.root, self.attempt['id'], self.result)
        self.assertEqual(before, path.read_bytes())

    def test_system_tests_do_not_enter_learning_progress(self):
        simulation = session.start(self.root, 'simulation', 'Listening', 'system_test', 20)['session']
        result = copy.deepcopy(self.result)
        result['key_task_id'] = 'simulation'
        session.finalize(self.root, simulation['id'], result)
        self.assertNotIn(simulation['id'], (self.root / 'PROGRESS.md').read_text())
        self.assertNotIn(simulation['id'], (self.root / 'STATUS.md').read_text())

    def test_rebuild_recovers_after_summary_write_failure(self):
        original = session.managed_section
        def fail(*args):
            raise OSError('TEST ONLY disk unavailable')
        session.managed_section = fail
        try:
            with self.assertRaises(OSError):
                session.finalize(self.root, self.attempt['id'], self.result)
        finally:
            session.managed_section = original
        session.rebuild(self.root)
        self.assertIn(self.attempt['id'], (self.root / 'PROGRESS.md').read_text())

    def test_checkpoint_durable_idempotent_and_resume_without_grading(self):
        payload = {'text': 'TEST ONLY original response', 'provenance': self.provenance(),
                   'conditions': {'audio_plays': 1}}
        saved = session.checkpoint(self.root, self.attempt['id'], payload)
        self.assertTrue(saved['saved'])
        before = session.session_path(self.root, self.attempt['id']).read_bytes()
        retry = session.checkpoint(self.root, self.attempt['id'], payload)
        self.assertTrue(retry['duplicate'])
        self.assertEqual(before, session.session_path(self.root, self.attempt['id']).read_bytes())
        restored = session.start(self.root, 'test-task', 'Listening', 'pilot', 20)['session']
        self.assertEqual(restored['id'], self.attempt['id'])
        self.assertEqual(restored['phase'], 'awaiting_review')
        self.assertEqual(restored['response_revisions'][0]['payload']['text'], payload['text'])
        self.assertEqual(restored['conditions']['audio_plays'], 1)
        self.assertIsNone(restored['result'])

    def test_checkpoint_requires_provenance_and_rejects_unsafe_evidence(self):
        for payload in ({'text': 'TEST ONLY'}, {'score': {'correct': 1, 'total': 2}},
                        {'text': 'TEST ONLY', 'provenance': {'method': ' ', 'reference': 'TEST ONLY'}},
                        {'evidence': ['evidence/missing.png'], 'provenance': self.provenance()}):
            with self.assertRaises(ValueError):
                session.checkpoint(self.root, self.attempt['id'], payload)
        self.assertEqual(len(session.load_sessions(self.root)[0]['response_revisions']), 0)
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'secret.png').write_bytes(b'TEST ONLY')
        (self.root / 'evidence').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            session.checkpoint(self.root, self.attempt['id'],
                               {'evidence': ['evidence/secret.png'], 'provenance': self.provenance()})

    def test_phase_only_wait_keeps_same_attempt_and_cannot_complete_empty_result(self):
        saved = session.checkpoint(self.root, self.attempt['id'], {'phase': 'awaiting_evidence'})['session']
        self.assertEqual(saved['phase'], 'awaiting_evidence')
        bad = dict(mode='unverified', scope='partial', verification_method='TEST ONLY nothing readable',
                   feedback=dict(self.result['feedback'], patterns=[]))
        with self.assertRaises(ValueError):
            session.finalize(self.root, self.attempt['id'], bad)
        restored = session.load_sessions(self.root)[0]
        self.assertEqual(restored['status'], 'in_progress')
        self.assertEqual(restored['phase'], 'awaiting_evidence')

    def test_empty_total_score_cannot_close_session(self):
        empty = dict(self.result, mode='score_only', score=None, answers=[],
                     feedback=dict(self.result['feedback'], patterns=[]))
        with self.assertRaises(ValueError):
            session.finalize(self.root, self.attempt['id'], empty)
        missing_source_score = dict(empty, score={'correct': 1, 'total': 2})
        with self.assertRaises(ValueError):
            session.finalize(self.root, self.attempt['id'], missing_source_score)
        self.assertEqual(session.load_sessions(self.root)[0]['status'], 'in_progress')

    def test_total_score_checkpoint_only_can_close_without_invented_errors(self):
        session.checkpoint(self.root, self.attempt['id'],
                           {'score': {'correct': 1, 'total': 2}, 'provenance': self.provenance()})
        total = dict(self.result, mode='score_only', answers=[],
                     feedback=dict(self.result['feedback'], patterns=[]))
        total.pop('source_response')
        stored = session.finalize(self.root, self.attempt['id'], total)['session']
        self.assertEqual(stored['result']['score']['correct'], 1)
        self.assertIn('graded_response_revision_id', stored)
        self.assertEqual(stored['result']['feedback']['patterns'], [])

    def test_score_checkpoint_cannot_support_objective_answers(self):
        session.checkpoint(self.root, self.attempt['id'],
                           {'score': {'correct': 1, 'total': 2}, 'provenance': self.provenance()})
        with self.assertRaises(ValueError):
            session.finalize(self.root, self.attempt['id'], self.result)

    def test_checkpoint_original_review_and_conditions_are_preserved(self):
        evidence = self.root / 'evidence' / 'TEST-ONLY.png'
        evidence.parent.mkdir()
        evidence.write_bytes(b'TEST ONLY screenshot fixture')
        original = session.checkpoint(self.root, self.attempt['id'],
                    {'text': 'TEST ONLY original A B', 'evidence': ['evidence/TEST-ONLY.png'],
                     'provenance': self.provenance(), 'conditions': {'audio_plays': 1}})
        session.checkpoint(self.root, self.attempt['id'],
                           {'text': 'TEST ONLY rewrite A C', 'purpose': 'review', 'provenance': self.provenance()})
        result = dict(self.result, conditions={'duration_actual': 12})
        result.pop('source_response')
        stored = session.finalize(self.root, self.attempt['id'], result)['session']
        self.assertEqual(stored['graded_response_revision_id'], original['revision_id'])
        self.assertEqual(stored['conditions'], {'audio_plays': 1, 'duration_actual': 12})
        self.assertEqual(stored['evidence'], ['evidence/TEST-ONLY.png'])
        old_result = copy.deepcopy(stored['result'])
        session.checkpoint(self.root, self.attempt['id'],
                           {'text': 'TEST ONLY post-feedback rewrite', 'purpose': 'review',
                            'provenance': self.provenance(), 'conditions': {'audio_plays': 2}})
        after = session.load_sessions(self.root)[0]
        self.assertEqual(after['result'], old_result)
        self.assertEqual(after['conditions']['audio_plays'], 1)
        self.assertEqual(after['phase'], 'completed')
        self.assertEqual(len(after['response_revisions']), 3)
        with self.assertRaises(ValueError):
            session.checkpoint(self.root, self.attempt['id'], {'text': 'TEST ONLY changed attempt',
                                                              'provenance': self.provenance()})

    def test_review_revision_cannot_be_selected_for_original_grade(self):
        revision = session.checkpoint(self.root, self.attempt['id'],
                    {'text': 'TEST ONLY review', 'purpose': 'review', 'provenance': self.provenance()})
        result = dict(self.result, response_revision_id=revision['revision_id'])
        with self.assertRaises(ValueError):
            session.finalize(self.root, self.attempt['id'], result)

    def test_interrupted_checkpoint_recovers_without_input_loss(self):
        original = session.managed_section
        def fail(*args):
            raise OSError('TEST ONLY summary unavailable')
        session.managed_section = fail
        payload = {'text': 'TEST ONLY saved before interruption', 'provenance': self.provenance()}
        try:
            with self.assertRaises(OSError):
                session.checkpoint(self.root, self.attempt['id'], payload)
        finally:
            session.managed_section = original
        restored = session.load_sessions(self.root)[0]
        self.assertEqual(restored['response_revisions'][0]['payload']['text'], payload['text'])
        retry = session.checkpoint(self.root, self.attempt['id'], payload)
        self.assertTrue(retry['duplicate'])
        self.assertEqual(len(retry['session']['response_revisions']), 1)
        self.assertIn('awaiting_review', (self.root / 'STATUS.md').read_text())

    def test_missing_provenance_verification_and_unverified_score_rejected(self):
        for field in ('verification_method', 'source_response'):
            invalid = copy.deepcopy(self.result)
            invalid.pop(field)
            with self.assertRaises(ValueError):
                session.finalize(self.root, self.attempt['id'], invalid)
        unverified = dict(self.result, mode='unverified', answers=[],
                          feedback=dict(self.result['feedback'], patterns=[]))
        with self.assertRaises(ValueError):
            session.validate(self.root, self.attempt, unverified)
        unverified['score'] = None
        with self.assertRaises(ValueError):
            session.validate(self.root, self.attempt, unverified)
        session.checkpoint(self.root, self.attempt['id'],
                           {'text': 'TEST ONLY response awaiting verification', 'provenance': self.provenance()})
        with self.assertRaises(ValueError):
            session.finalize(self.root, self.attempt['id'], unverified)
        self.assertEqual(session.load_sessions(self.root)[0]['status'], 'in_progress')

    def writing_result(self, target='task2'):
        criterion = 'task_response' if target == 'task2' else 'task_achievement'
        return dict(mode='ai_estimate', scope='full', band=6.0, band_target=target,
                    response_complete=True, sample_text=' '.join(['TEST'] * 260),
                    provenance=self.provenance(), verification_method='TEST ONLY full sample inspected',
                    criteria={criterion: 6.0, 'coherence_cohesion': 6.0,
                              'lexical_resource': 6.0, 'grammatical_range_accuracy': 6.0},
                    uncertainty='TEST ONLY AI estimate, not examiner score',
                    feedback=self.result['feedback'])

    def test_writing_microtask_no_band_but_limited_feedback_allowed(self):
        writing = dict(self.attempt, skill='Writing', material={'title': 'Academic Writing Task 2'})
        result = self.writing_result()
        result.update(scope='sample', sample_text='TEST ONLY one short paragraph')
        with self.assertRaises(ValueError):
            session.validate(self.root, writing, result)
        result['band'] = None
        session.validate(self.root, writing, result)
        result.update(scope='full', band=6.0)
        with self.assertRaises(ValueError):
            session.validate(self.root, writing, result)

    def test_writing_full_requires_complete_sample_four_criteria_and_correct_task(self):
        writing = dict(self.attempt, skill='Writing', material={'title': 'Academic Writing Task 2'})
        valid = self.writing_result()
        session.validate(self.root, writing, valid)
        for change in ('response', 'criteria', 'target', 'complete', 'missing_sample'):
            result = copy.deepcopy(valid)
            if change == 'response':
                result['sample_text'] = 'TEST ONLY short paragraph'
            elif change == 'criteria':
                result['criteria'].pop('lexical_resource')
            elif change == 'target':
                result['band_target'] = 'task1'
            elif change == 'complete':
                result.pop('response_complete')
            else:
                result.pop('sample_text')
            with self.assertRaises(ValueError):
                session.validate(self.root, writing, result)
        valid['band_target'] = 'writing_skill'
        with self.assertRaises(ValueError):
            session.validate(self.root, writing, valid)

    def test_writing_task_band_summary_labels_task_not_skill_band(self):
        path = session.session_path(self.root, self.attempt['id'])
        writing = dict(self.attempt, skill='Writing', material={'title': 'Academic Writing Task 2'})
        path.write_text(json.dumps(writing))
        session.finalize(self.root, writing['id'], self.writing_result())
        self.assertIn('Task 2 estimasi AI 6.0', (self.root / 'PROGRESS.md').read_text())
        self.assertNotIn('Writing estimasi AI 6.0', (self.root / 'PROGRESS.md').read_text())

    def speaking_result(self):
        return dict(mode='ai_estimate', scope='full', band=6.0, input_type='audio',
                    speaking_parts=[1, 2, 3], audio_inspected=True,
                    audio_reference='chat:TEST-ONLY-parts-1-3-recording',
                    source_response={'input_type': 'audio',
                        'audio_reference': 'chat:TEST-ONLY-parts-1-3-recording', 'provenance': self.provenance()},
                    verification_method='TEST ONLY audio inspected',
                    criteria={'fluency_coherence': 6.0, 'lexical_resource': 6.0,
                              'grammatical_range_accuracy': 6.0, 'pronunciation': 6.0},
                    uncertainty='TEST ONLY AI estimate', feedback=self.result['feedback'])

    def test_speaking_full_band_needs_all_parts_audio_and_criteria(self):
        speaking = dict(self.attempt, skill='Speaking')
        valid = self.speaking_result()
        session.validate(self.root, speaking, valid)
        for change in ('partial', 'parts', 'criteria', 'audio', 'flags_only', 'transcript'):
            invalid = copy.deepcopy(valid)
            if change == 'partial':
                invalid['scope'] = 'sample'
            elif change == 'parts':
                invalid['speaking_parts'] = [2]
            elif change == 'criteria':
                invalid['criteria'].pop('lexical_resource')
            elif change == 'audio':
                invalid['audio_inspected'] = False
            elif change == 'flags_only':
                invalid['source_response'] = {'text': 'TEST ONLY transcript', 'provenance': self.provenance()}
            else:
                invalid['input_type'] = 'transcript'
                invalid['criteria']['pronunciation'] = None
            with self.assertRaises(ValueError):
                session.validate(self.root, speaking, invalid)
        valid.update(scope='sample', band=None, speaking_parts=[2])
        session.validate(self.root, speaking, valid)

    def test_legacy_completed_record_read_and_idempotent_without_new_requirements(self):
        legacy = copy.deepcopy(self.attempt)
        legacy.pop('phase')
        legacy.pop('response_revisions')
        old_result = copy.deepcopy(self.result)
        old_result.pop('source_response')
        old_result.pop('verification_method')
        legacy.update(status='completed', completed_at=session.now(), result=old_result)
        path = session.session_path(self.root, legacy['id'])
        path.write_text(json.dumps(legacy))
        before = path.read_bytes()
        self.assertEqual(session.load_sessions(self.root)[0]['result'], old_result)
        retry = session.finalize(self.root, legacy['id'], old_result)
        self.assertTrue(retry['already_completed'])
        self.assertEqual(before, path.read_bytes())

    def test_corrupt_legacy_completed_shape_rejected_before_summary_mutation(self):
        legacy = dict(self.attempt, status='completed', completed_at=session.now(), result=None)
        path = session.session_path(self.root, legacy['id'])
        path.write_text(json.dumps(legacy))
        progress_before = (self.root / 'PROGRESS.md').read_bytes()
        status_before = (self.root / 'STATUS.md').read_bytes()
        with self.assertRaises(ValueError):
            session.rebuild(self.root)
        with self.assertRaises(ValueError):
            session.start(self.root, 'test-task', 'Listening', 'pilot', 20)
        self.assertEqual(progress_before, (self.root / 'PROGRESS.md').read_bytes())
        self.assertEqual(status_before, (self.root / 'STATUS.md').read_bytes())

    def test_two_local_writers_cannot_mutate_same_attempt(self):
        with session.mutation_lock(self.root):
            with self.assertRaises(ValueError):
                session.checkpoint(self.root, self.attempt['id'], {'phase': 'awaiting_evidence'})
        self.assertEqual(session.load_sessions(self.root)[0]['response_revisions'], [])
        saved = session.checkpoint(self.root, self.attempt['id'], {'phase': 'awaiting_evidence'})
        self.assertTrue(saved['saved'])

    def test_checkpoint_cli_uses_same_record(self):
        payload = self.root / 'TEST-ONLY-input.json'
        payload.write_text(json.dumps({'text': 'TEST ONLY CLI response', 'provenance': self.provenance()}))
        process = subprocess.run([sys.executable, str(Path(__file__).parents[1] / 'scripts/session.py'),
                                  '--root', str(self.root), 'checkpoint', '--id', self.attempt['id'],
                                  '--input', str(payload)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 encoding='utf-8')
        self.assertEqual(process.returncode, 0, process.stderr + process.stdout)
        output = json.loads(process.stdout)
        self.assertTrue(output['saved'])
        self.assertEqual(output['session']['id'], self.attempt['id'])


if __name__ == '__main__':
    unittest.main()
