import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

PROJECT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('reference_module', PROJECT / 'scripts/references.py')
references = importlib.util.module_from_spec(spec)
spec.loader.exec_module(references)


class ReferenceTests(unittest.TestCase):
    """Use actual verified excerpts, including their ranges and source policies."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copytree(PROJECT / 'coach_refs', self.root / 'coach_refs')
        shutil.copytree(PROJECT / 'materials', self.root / 'materials')
        self.catalog = json.loads((PROJECT / 'materials.json').read_text(encoding='utf-8'))
        self.tasks = [t for t in self.catalog['tasks'] if t['skill'] in ('Listening', 'Reading')]
        self.task = copy.deepcopy(next(t for t in self.tasks if t['id'] == 'listening-packham-form'))
        self.cache_path = self.root / self.task['coach_reference']['path']
        self.cache = json.loads(self.cache_path.read_text(encoding='utf-8'))

    def rewrite_cache(self):
        self.cache_path.write_text(json.dumps(self.cache, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.task['coach_reference']['sha256'] = references.sha256(self.cache_path)

    def check_failed(self):
        checked = references.check_reference(self.root, self.task)
        self.assertEqual(checked['status'], 'failed')
        self.assertTrue(checked['reasons'])

    def test_actual_four_caches_work_offline_and_report_only_metadata(self):
        self.assertEqual(len(self.tasks), 4)
        for task in self.tasks:
            checked = references.check_reference(self.root, task)
            self.assertEqual(checked['status'], 'passed')
            self.assertEqual(checked['question_numbers'], task['question_numbers'])
            self.assertNotIn('key', checked)
            self.assertNotIn('entries', checked)
            self.assertNotIn('transcript', checked)
            self.assertNotIn('answer_lines', checked)

    def test_real_key_entries_cover_exact_source_ranges_not_just_checksums(self):
        for task in self.tasks:
            cache = json.loads((self.root / task['coach_reference']['path']).read_text(encoding='utf-8'))
            entries = []
            for page in cache['key']['page_texts']:
                parsed, _ = references.parse_key_page(page['text'], page['page'])
                entries.extend(parsed)
            self.assertEqual(entries, cache['key']['entries'])
            self.assertEqual([n for entry in entries for n in entry['question_numbers']], task['question_numbers'])
            self.assertTrue(all(entry['answer_lines'] for entry in entries))
            self.assertTrue(all(entry['source_page'] in task['key_pages'] for entry in entries))

    def test_real_listening_word_limits_optional_variants_and_group_rules_preserved(self):
        for task in [t for t in self.tasks if t['skill'] == 'Listening']:
            cache = json.loads((self.root / task['coach_reference']['path']).read_text(encoding='utf-8'))
            self.assertEqual(cache['answer_instruction']['max_words'], 3)
            self.assertTrue(cache['answer_instruction']['allow_number'])
            self.assertIn('Words in brackets are optional', cache['key']['optional_words_and_alternatives_policy'])
            self.assertIn('separated by a slash', cache['key']['optional_words_and_alternatives_policy'])
            groups = [e for e in cache['key']['entries'] if e['order'] == 'any']
            expected = [['6', '7']] if task['id'] == 'listening-packham-form' else [['11', '12'], ['13', '14'], ['15', '16']]
            self.assertEqual([g['question_numbers'] for g in groups], expected)
            self.assertTrue(all(len(g['answer_lines']) == 2 for g in groups))
            self.assertFalse(cache['transcript']['timestamps_available'])
            self.assertEqual([p['page'] for p in cache['transcript']['page_texts']], task['transcript_pages'])

    def test_learner_packet_omits_all_correction_content_and_original_urls(self):
        for task in self.catalog['tasks']:
            packet = references.learner_packet(task)
            self.assertEqual(packet['local']['prompt'], task['local']['prompt'])
            serialized = json.dumps(packet)
            for forbidden in ('coach_refs/', 'coach_reference', 'key_pages', 'answer_lines', 'page_texts', 'timestamps_available', '"urls"'):
                self.assertNotIn(forbidden, serialized)

    def test_learner_packet_rejects_cache_path_and_path_traversal(self):
        for forbidden in ('coach_refs/listening-packham-form.json', '../coach_refs/key.json', '/tmp/key.json', 'materials/../coach_refs/key.json', 'materials/TEST-ONLY-key.json'):
            bad = copy.deepcopy(self.task)
            bad['local']['prompt'] = forbidden
            with self.assertRaises(ValueError):
                references.learner_packet(bad)

    def test_missing_cache_fails_without_network_or_fabricated_key(self):
        self.cache_path.unlink()
        self.check_failed()

    def test_missing_metadata_is_not_ready(self):
        del self.task['coach_reference']
        self.check_failed()

    def test_changed_cache_checksum_fails(self):
        self.cache_path.write_text(self.cache_path.read_text() + ' ')
        self.check_failed()

    def test_corrupt_json_with_new_checksum_still_fails(self):
        self.cache_path.write_text('{invalid TEST ONLY')
        self.task['coach_reference']['sha256'] = references.sha256(self.cache_path)
        self.check_failed()

    def test_wrong_version_fails_even_if_cache_hash_matches(self):
        self.cache['source_version'] = 'TEST ONLY wrong version'
        self.rewrite_cache()
        self.check_failed()

    def test_wrong_prompt_hash_fails(self):
        prompt = self.root / self.task['local']['prompt']
        prompt.write_bytes(prompt.read_bytes() + b'\nTEST ONLY modification')
        self.check_failed()

    def test_wrong_source_provenance_fails(self):
        self.cache['source']['sha256'] = 'a' * 64
        self.rewrite_cache()
        self.check_failed()

    def test_wrong_question_range_fails(self):
        self.cache['question_numbers'] = ['1', '2']
        self.rewrite_cache()
        self.check_failed()

    def test_incomplete_or_changed_structured_key_fails_even_with_new_checksum(self):
        self.cache['key']['entries'].pop()
        self.rewrite_cache()
        self.check_failed()

    def test_duplicate_question_in_source_key_fails(self):
        self.cache['key']['page_texts'][0]['text'] += '\n1 TEST ONLY duplicate\n'
        self.rewrite_cache()
        self.check_failed()

    def test_missing_transcript_and_changed_page_range_fail(self):
        original = copy.deepcopy(self.cache)
        self.cache['transcript']['page_texts'].pop()
        self.rewrite_cache()
        self.check_failed()
        self.cache = original
        self.cache['transcript']['source_pages'] = [4, 5]
        self.rewrite_cache()
        self.check_failed()

    def test_word_limit_policy_must_match_verified_prompt(self):
        self.cache['answer_instruction']['max_words'] = 5
        self.rewrite_cache()
        self.check_failed()

    def test_empty_reading_text_fails(self):
        self.task = copy.deepcopy(next(t for t in self.tasks if t['skill'] == 'Reading'))
        self.cache_path = self.root / self.task['coach_reference']['path']
        self.cache = json.loads(self.cache_path.read_text(encoding='utf-8'))
        self.cache['reading_text']['page_texts'][0]['text'] = ''
        self.rewrite_cache()
        self.check_failed()

    def test_cache_and_prompt_paths_cannot_escape_project(self):
        self.task['coach_reference']['path'] = '../coach_refs/test.json'
        self.check_failed()
        outside = self.root.parent / (self.root.name + '-TEST-ONLY-outside.json')
        outside.write_text('{}')
        self.addCleanup(lambda: outside.unlink() if outside.exists() else None)
        link = self.root / 'coach_refs' / 'TEST-ONLY-link.json'
        link.symlink_to(outside)
        self.task['coach_reference']['path'] = 'coach_refs/TEST-ONLY-link.json'
        self.check_failed()

    def test_writing_speaking_are_not_objective_key_checks(self):
        for task in [t for t in self.catalog['tasks'] if t['skill'] in ('Writing', 'Speaking')]:
            self.assertEqual(references.check_reference(self.root, task)['status'], 'not_tested')

    def test_historical_exposed_tasks_are_archived_and_not_selectable(self):
        for task in self.catalog['review_only']:
            self.assertEqual(task['readiness'], 'archive_not_selectable')
            self.assertFalse(task['selectable'])
            self.assertFalse(task['freshness']['eligible_for_new_attempt'])


if __name__ == '__main__':
    unittest.main()
