import copy
import importlib.util
import json
from pathlib import Path
import tempfile
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
            'evidence': [], 'conditions': {'duration_actual': None}
        }

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
        estimate = dict(mode='ai_estimate', scope='sample', input_type='transcript', band=6.0,
                        criteria={'pronunciation': 6.0}, uncertainty='TEST ONLY',
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
                        uncertainty='TEST ONLY', feedback=self.result['feedback'])
        with self.assertRaises(ValueError):
            session.validate(self.root, speaking, estimate)
        estimate['input_type'] = 'audio'
        with self.assertRaises(ValueError):
            session.validate(self.root, speaking, estimate)
        estimate.update(audio_inspected=True, audio_reference='TEST ONLY audio message')
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


if __name__ == '__main__':
    unittest.main()
