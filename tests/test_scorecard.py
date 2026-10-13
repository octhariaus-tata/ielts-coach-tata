"""Evidence reporting regressions in isolated TEST fixtures, never learner data."""
import copy
import datetime
import json
import unittest
from unittest import mock

import test_lessons as fixture
import scorecard
import lessons


class ScorecardTests(unittest.TestCase):
    def setUp(self):
        self.env = fixture.LessonTests('test_startup_resumes_same_banking_prompt_without_official_attempt')
        self.env.setUp()
        self.addCleanup(self.env.doCleanups)
        self.root, self.coach = self.env.root, self.env.coach
        scorecard.initialize(self.root)

    def complete_session(self):
        value = self.coach.session.start(self.root, self.env.env.task_id, 'Listening', 'practice', 20)
        sid = value['session']['id']
        self.coach.checkpoint(self.root, sid, self.env.env.input())
        out = self.coach.complete(self.root, sid, self.env.env.result())
        return sid, out

    def complete_drill(self, n=12, main=False, pid='TEST-primary'):
        p = self.env.packet(pid=pid)
        if main:
            p['practice_kind'] = 'task'
        with mock.patch.object(self.env, 'packet', return_value=p):
            self.env.independent()
        ids = ['q' + str(i) for i in range(1, n + 1)]
        self.env.present(ids)
        out = self.env.submit({i: 'TEST ONLY response' for i in ids})
        self.env.grade(out['response_id'], ids)
        self.env.advance('review')
        return self.env.advance('completed')

    def test_four_main_completion_reports_once_and_keeps_grades_unchanged(self):
        for _ in range(4):
            out = self.complete_drill(1, main=True, pid='TEST-main-' + str(_))
        self.assertTrue(out['scorecard_update']['new_four_lesson_review'])
        before = lessons.path(self.root, 'lessons', self.env.lid).read_bytes()
        retry = self.env.advance('completed')
        self.assertFalse(retry['scorecard_update']['new_four_lesson_review'])
        self.assertEqual(before, lessons.path(self.root, 'lessons', self.env.lid).read_bytes())
        reports = list((self.root / 'learning' / 'scorecards').glob('four-main-*.json'))
        self.assertEqual(len(reports), 1)
        coverage = retry['scorecard_update']['scorecard']['coverage']
        self.assertEqual(coverage['post_rollout_completed_main_lessons'], 4)
        self.assertEqual(coverage['skills_in_latest_four'], ['Speaking'])
        self.assertEqual(len(coverage['missing_skills']), 3)

    def test_pool_is_not_completed_work_and_supplementary_does_not_count_main(self):
        out = self.complete_drill()
        report = out['scorecard_update']['scorecard']
        self.assertEqual(report['practice'][0]['prepared'], 30)
        self.assertEqual(report['practice'][0]['submitted'], 12)
        self.assertEqual(report['practice'][0]['reviewed'], 12)
        self.assertEqual(report['practice'][0]['homework_debt'], 0)
        self.assertEqual(report['coverage']['post_rollout_completed_main_lessons'], 0)
        self.assertEqual(report['teaching']['documented_sequence'], 1)
        self.assertEqual(report['focused_checks']['status'], 'insufficient_evidence')

    def test_unknown_latency_and_score_only_do_not_become_learning_benefit(self):
        self.complete_session()
        report = scorecard.build(self.root)
        self.assertEqual(report['latency']['status'], 'not_measured')
        self.assertIsNone(report['latency']['median_seconds'])
        self.assertFalse(report['integrity']['zero_lost_responses_proven'])
        self.assertEqual(report['learning']['effectiveness'], 'insufficient_evidence')
        self.assertIsNone(report['learning']['per_skill']['Listening']['latest_eligible_observation'])
        self.assertEqual(report['learning']['per_skill']['Listening']['latest_observation']['assessment_mode'], 'score_only')
        self.assertNotIn('PRIVATE TEST ANSWER', json.dumps(report))

    def test_rollout_preserves_but_excludes_historical_completions(self):
        scorecard.location(self.root, 'tracking.json').unlink()
        self.complete_session()  # Initial refresh pins the pre-tracking record.
        report = scorecard.build(self.root)
        self.assertEqual(report['coverage']['historical_main_completions'], 1)
        self.assertEqual(report['coverage']['post_rollout_completed_main_lessons'], 0)
        self.assertIsNotNone(report['learning']['per_skill']['Listening']['latest_observation'])

    def test_ordinary_answer_does_not_refresh_scorecard(self):
        self.env.independent(); self.env.present(['q1'])
        with mock.patch.object(scorecard, 'safely_refresh', side_effect=AssertionError('Not per answer')):
            out = self.env.submit({'q1': 'TEST ONLY response'})
            self.env.grade(out['response_id'], ['q1'])

    def test_reporting_failure_keeps_completed_attempt_and_retry_never_regrades(self):
        with mock.patch.object(scorecard, 'build', side_effect=ValueError('TEST corrupt source')):
            sid, out = self.complete_session()
        self.assertFalse(out['scorecard_update']['saved'])
        self.assertEqual(self.coach.session.find_session(self.root, sid)['status'], 'completed')
        self.assertTrue(self.coach.complete(self.root, sid)['scorecard_update']['saved'])

    def test_linked_attempt_and_lesson_count_once_after_both_complete(self):
        self.env.official_independent(); self.env.present(['1', '2'])
        record = lessons.find(self.root, self.env.lid); sid = record['official_attempt_id']
        self.coach.checkpoint(self.root, sid, self.env.env.input())
        self.coach.complete(self.root, sid, self.env.env.result())
        self.assertEqual(scorecard.build(self.root)['coverage']['post_rollout_completed_main_lessons'], 0)
        out = self.env.submit({'1': 'TEST ONLY answer', '2': 'TEST ONLY answer'})
        payload = {'response_id': out['response_id'], 'item_ids': ['1', '2'], 'official_result_reference': sid,
                   'provenance': self.env.prov, 'feedback': {'strength': 'TEST ONLY', 'patterns': [], 'action': 'Check', 'next_task': 'Next'}}
        self.coach.lesson(self.root, 'review', self.env.lid, payload, defer_sync=True)
        self.env.advance('review'); self.env.advance('completed')
        self.assertEqual(scorecard.build(self.root)['coverage']['post_rollout_completed_main_lessons'], 1)

    def test_transfer_excludes_guidance_revisions_and_unknown_conditions(self):
        self.complete_drill(1)
        source = lessons.find(self.root, self.env.lid)
        second = copy.deepcopy(self.env.packet(pid='TEST-transfer'))
        second['independent'][0]['prompt'] = 'TEST ONLY new transfer context'
        self.coach.lesson(self.root, 'packet', payload=second, defer_sync=True)
        self.env.lid = self.coach.lesson(self.root, 'prepare', defer_sync=True)['lesson']['id']
        self.coach.lesson(self.root, 'advance', self.env.lid,
                          {'stage': 'independent', 'learner_requested_skip': True, 'actor': 'learner', 'provenance': self.env.prov}, defer_sync=True)
        self.env.present(['q1'])
        conditions = {'check_type': 'transfer', 'source_lesson_id': source['id'], 'fresh_task': True,
                      'assisted': False, 'key_seen_before': False}
        out = self.env.submit({'q1': 'TEST ONLY new answer'}, conditions=conditions)
        payload = {'response_id': out['response_id'], 'item_ids': ['q1'], 'provenance': self.env.prov,
                   'criteria': {'grammar': {'correct': 1, 'total': 1}},
                   'feedback': {'strength': 'Observed', 'patterns': [], 'action': 'Check', 'next_task': 'Next'}}
        self.coach.lesson(self.root, 'review', self.env.lid, payload, defer_sync=True)
        report = scorecard.build(self.root)
        self.assertEqual(report['focused_checks']['samples'][0]['assessed'], 1)
        self.assertNotIn('band', report['focused_checks']['samples'][0])
        # Different packet ID cannot make a previously displayed prompt fresh.
        target = lessons.packet_for(self.root, lessons.find(self.root, self.env.lid))
        target['independent'][0]['prompt'] = self.env.packet()['independent'][0]['prompt']
        lessons.path(self.root, 'packets', target['id']).write_text(json.dumps(target))
        # Keep display and pinned packet consistent to test semantic reuse.
        record = json.loads(lessons.path(self.root, 'lessons', self.env.lid).read_text())
        record['packet_sha256'] = lessons.digest(target)
        for p in record['presentations']:
            if p['stage'] == 'independent':
                p['content'] = lessons.stage_content(target, 'independent', p['item_ids'])
        lessons.save(self.root, record)
        self.assertEqual(scorecard.build(self.root)['focused_checks']['excluded'][0]['reason'], 'previously_exposed_prompt')
        target['independent'][0]['prompt'] = 'TEST ONLY new transfer context'
        lessons.path(self.root, 'packets', target['id']).write_text(json.dumps(target))
        record['packet_sha256'] = lessons.digest(target)
        for p in record['presentations']:
            if p['stage'] == 'independent':
                p['content'] = lessons.stage_content(target, 'independent', p['item_ids'])
        lessons.save(self.root, record)
        # Source completion in the future cannot support transfer.
        source['transitions'][-1]['at'] = '2099-01-01T00:00:00+07:00'
        lessons.save(self.root, source)
        self.assertEqual(scorecard.build(self.root)['focused_checks']['excluded'][0]['reason'], 'source_teaching_after_check')
        source['transitions'][-1]['at'] = '2020-01-01T00:00:00+07:00'
        lessons.save(self.root, source)
        record = lessons.find(self.root, self.env.lid)
        record['responses'][-1]['payload']['conditions']['check_type'] = 'retention'
        lessons.save(self.root, record)
        self.assertEqual(scorecard.build(self.root)['focused_checks']['excluded'][0]['reason'], 'retention_checkpoint_outside_3_to_7_days')
        when = scorecard.moment(record['responses'][-1]['at']) - datetime.timedelta(days=4)
        source['transitions'][-1]['at'] = when.isoformat()
        lessons.save(self.root, source)
        self.assertEqual(scorecard.build(self.root)['focused_checks']['samples'][0]['delay_days'], 4)
        record['responses'][-1]['payload']['conditions']['assisted'] = True
        lessons.save(self.root, record)
        self.assertEqual(scorecard.build(self.root)['focused_checks']['samples'], [])

    def test_malformed_completion_and_timestamp_return_action_without_crashing(self):
        self.complete_drill(1, main=True)
        record = lessons.find(self.root, self.env.lid)
        record['transitions'] = []
        lessons.path(self.root, 'lessons', record['id']).write_text(json.dumps(record))
        self.assertEqual(scorecard.safely_refresh(self.root)['status'], 'needs_action')
        record['transitions'] = [{'to': 'completed', 'at': None}]
        lessons.path(self.root, 'lessons', record['id']).write_text(json.dumps(record))
        self.assertEqual(scorecard.safely_refresh(self.root)['status'], 'needs_action')

    def test_cache_refresh_after_source_change_and_safe_symlink_rejection(self):
        self.env.start()
        first = scorecard.refresh(self.root)['scorecard']
        self.env.present()
        second = scorecard.refresh(self.root)['scorecard']
        self.assertNotEqual(first['source_sha256'], second['source_sha256'])
        cache = scorecard.location(self.root, 'current.json'); cache.unlink()
        cache.symlink_to(self.root / 'STATUS.md')
        self.assertFalse(scorecard.safely_refresh(self.root)['saved'])

    def test_backup_rejects_cache_claims_and_does_not_modify_source(self):
        self.env.start()
        scorecard.refresh(self.root)
        scorecard.validate_saved(self.root)
        cache = scorecard.location(self.root, 'current.json')
        report = json.loads(cache.read_text())
        report['latency']['status'] = 'measured'
        cache.write_text(json.dumps(report))
        with self.assertRaises(ValueError):
            scorecard.validate_saved(self.root)


if __name__ == '__main__':
    unittest.main()
