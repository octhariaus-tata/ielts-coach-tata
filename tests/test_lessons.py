"""Teacher workflow rehearsals in isolated TEST fixtures, no learner/network writes."""
import copy
import json
from pathlib import Path
import unittest
from unittest import mock

import test_coach as fixture
import lessons


class LessonTests(unittest.TestCase):
    def setUp(self):
        self.env = fixture.CoachTests('test_offline_prepare_uses_verified_local_materials')
        self.env.setUp()
        self.addCleanup(self.env.doCleanups)
        self.root, self.coach = self.env.root, self.env.coach if hasattr(self.env, 'coach') else fixture.coach
        self.prov = {'method': 'TEST ONLY fixture', 'reference': 'Not Tata; isolated lesson rehearsal'}
        self.preferences = {'available_minutes': 40, 'lesson_language': 'en', 'teaching_sequence': 'teach_first',
                            'practice_volume': 'adaptive', 'short_drill_items': [20, 30], 'completion_mode': 'natural'}
        self.coach.feedback(self.root, self.event('TEST-global', self.preferences))

    def event(self, eid, signals, **fields):
        return dict(event_id=eid, kind='learner', actor='learner', category='preference', scope='global',
                    text='TEST ONLY explicit teaching preferences', signals=signals, provenance=self.prov, **fields)

    def packet(self, pid='TEST-primary', role='primary', n=30):
        return {'schema_version': 1, 'id': pid, 'version': '1', 'role': role, 'main_skill': 'Speaking',
                'ielts_task_type': 'part1_short_answers', 'objective': 'TEST ONLY short answers',
                'source_label': 'coach_created', 'practice_kind': 'short_drill',
                'theory': 'Use do/does to match the subject.', 'strategy': 'Find the subject first.',
                'worked_example': {'prompt': 'Does the fictional baker work?', 'answer': 'Yes, she does.',
                                   'reasoning': 'She takes does.'},
                'guided': [{'id': 'g1', 'prompt': 'Do you use your phone for banking?', 'hint': 'Reply I.'}],
                'independent': [{'id': 'q' + str(i), 'prompt': 'TEST ONLY fictional person %s: give a short answer.' % i,
                                 'optional': i > 12} for i in range(1, n + 1)],
                'coach_only': {'answers': {'q' + str(i): 'PRIVATE TEST ANSWER %s' % i for i in range(1, n + 1)}},
                'basis': {'preferences_sha256': lessons.digest(self.preferences), 'files': {}}, 'provenance': self.prov}

    def start(self, n=30):
        self.coach.lesson(self.root, 'packet', payload=self.packet(n=n), defer_sync=True)
        out = self.coach.lesson(self.root, 'prepare', defer_sync=True)
        self.lid = out['lesson']['id']
        return out

    def present(self, ids=None):
        value = dict(provenance=self.prov)
        if ids is not None:
            value['item_ids'] = ids
        return self.coach.lesson(self.root, 'present', self.lid, value, defer_sync=True)

    def advance(self, stage):
        return self.coach.lesson(self.root, 'advance', self.lid, {'stage': stage, 'provenance': self.prov}, defer_sync=True)

    def submit(self, answers, submission='complete', **extra):
        payload = dict(text='TEST ONLY complete answers' if submission == 'complete' else 'TEST ONLY still answering',
                       answers=answers, submission=submission, provenance=self.prov, **extra)
        return self.coach.lesson(self.root, 'checkpoint', self.lid, payload, defer_sync=True)

    def grade(self, rid, ids):
        payload = {'response_id': rid, 'item_ids': ids, 'provenance': self.prov,
                   'feedback': {'strength': 'TEST ONLY observed response', 'patterns': [],
                                'action': 'Check spelling.', 'next_task': 'Use a new context.'},
                   'criteria': {'grammar': 'TEST ONLY limited drill feedback'}}
        return self.coach.lesson(self.root, 'review', self.lid, payload, defer_sync=True), payload

    def independent(self):
        self.start()
        self.present()
        self.advance('example')
        self.present()
        self.advance('guided')
        self.present()
        out = self.submit({'g1': 'Yes, I do.'})
        self.grade(out['response_id'], ['g1'])
        self.advance('independent')

    def test_startup_resumes_same_banking_prompt_without_official_attempt(self):
        self.start()
        self.present(); self.advance('example'); self.present(); self.advance('guided'); self.present()
        resumed = self.coach.prepare(self.root, minutes=15)
        self.assertTrue(resumed['resumed'])
        self.assertEqual(resumed['lesson']['id'], self.lid)
        self.assertEqual(resumed['lesson']['available_minutes'], 40)
        self.assertEqual(resumed['lesson']['displayed_prompt']['items'][0]['prompt'], 'Do you use your phone for banking?')
        self.assertEqual(list((self.root / 'sessions').glob('*.json')), [])
        self.assertEqual(resumed['coaching_brief']['preferences']['effective']['lesson_language'], 'en')

    def test_complete_without_done_is_checkpointed_and_reviewed_once(self):
        self.independent(); self.present(['q1'])
        first = self.submit({'q1': 'TEST ONLY wrong but complete'})
        self.assertEqual(first['lesson']['status'], 'awaiting_review')
        out, payload = self.grade(first['response_id'], ['q1'])
        self.assertFalse(out['duplicate'])
        again = self.coach.lesson(self.root, 'review', self.lid, payload, defer_sync=True)
        self.assertTrue(again['duplicate'])
        self.assertEqual(len(lessons.find(self.root, self.lid)['reviews']), 2)  # guided plus independent

    def test_partial_pause_and_crash_recover_without_grading_or_answers(self):
        self.independent(); self.present(['q1', 'q2'])
        partial = self.submit({'q1': 'TEST ONLY partial'}, submission='partial')
        with self.assertRaises(ValueError): self.grade(partial['response_id'], ['q1'])
        paused = self.submit({}, submission='paused')
        self.assertEqual(paused['lesson']['status'], 'paused')
        resumed = self.coach.prepare(self.root)
        self.assertEqual(resumed['lesson']['id'], self.lid)
        self.assertNotIn('PRIVATE TEST ANSWER', json.dumps(resumed))
        complete = self.submit({'q1': 'one', 'q2': 'two'})
        restored = self.coach.lesson(self.root, 'inspect', self.lid)
        self.assertEqual(restored['lesson']['status'], 'awaiting_review')
        self.assertEqual(restored['lesson']['responses'][-1]['id'], complete['response_id'])

    def test_first_answers_and_post_feedback_revisions_are_separate(self):
        self.independent(); self.present(['q1'])
        first = self.submit({'q1': 'first'})
        self.grade(first['response_id'], ['q1']); self.advance('review')
        self.submit({'q1': 'corrected'}, purpose='review')
        record = lessons.find(self.root, self.lid)
        self.assertEqual(record['responses'][-2]['payload']['answers']['q1'], 'first')
        self.assertEqual(record['responses'][-1]['payload']['purpose'], 'review')
        self.assertEqual(lessons.counts(record, lessons.packet_for(self.root, record))['submitted'], 1)

    def test_thirty_prepared_twelve_submitted_no_debt_or_rotation_change(self):
        before = self.coach.queue(self.root, [])
        self.independent(); self.present(['q' + str(i) for i in range(1, 13)])
        out = self.submit({'q' + str(i): 'TEST ONLY answer' for i in range(1, 13)})
        self.grade(out['response_id'], ['q' + str(i) for i in range(1, 13)])
        self.advance('review'); self.advance('completed')
        record = lessons.find(self.root, self.lid)
        self.assertEqual(lessons.counts(record, lessons.packet_for(self.root, record)),
                         {'prepared': 30, 'presented': 12, 'submitted': 12, 'reviewed': 12, 'homework_debt': 0})
        self.assertEqual(self.coach.queue(self.root, []), before)

    def test_learner_view_excludes_coach_only_answers_at_every_stage(self):
        self.independent()
        for out in (self.present(), self.coach.status(self.root), self.coach.lesson(self.root, 'inspect', self.lid)):
            serialized = json.dumps(out)
            self.assertNotIn('PRIVATE TEST ANSWER', serialized)
            self.assertNotIn('coach_only', serialized)

    def test_malformed_and_leaking_packets_rejected_before_registration(self):
        for change in ('url', 'field', 'hint', 'same_data', 'range'):
            packet = self.packet()
            if change == 'url': packet['theory'] += ' coach_refs/secret.json'
            elif change == 'field': packet['independent'][0]['answer'] = 'PRIVATE'
            elif change == 'hint': packet['independent'][0]['hint'] = 'PRIVATE'
            elif change == 'same_data': packet['independent'][0]['prompt'] = packet['worked_example']['prompt']
            else: packet['independent'] = packet['independent'][:12]
            with self.assertRaises(ValueError): self.coach.lesson(self.root, 'packet', payload=packet, defer_sync=True)
        self.assertEqual(lessons.packets(self.root), [])

    def test_owner_unknown_and_completed_lesson_preferences_do_not_leak(self):
        for actor in ('owner', 'unspecified'):
            event = self.event('TEST-' + actor, {'lesson_language': 'id'}); event['actor'] = actor
            self.coach.feedback(self.root, event)
        self.assertEqual(self.coach.status(self.root)['coaching_brief']['preferences']['effective']['lesson_language'], 'en')
        self.independent()
        event = self.event('TEST-scoped', {'lesson_language': 'id'});event.update(scope='lesson', lesson_id=self.lid)
        self.coach.feedback(self.root, event)
        self.assertEqual(self.coach.status(self.root)['coaching_brief']['preferences']['effective']['lesson_language'], 'id')
        self.present(['q1']);out=self.submit({'q1': 'TEST ONLY answer'});self.grade(out['response_id'], ['q1'])
        self.advance('review');self.advance('completed')
        self.assertEqual(self.coach.status(self.root)['coaching_brief']['preferences']['effective']['lesson_language'], 'en')

    def test_source_and_preference_changes_stale_prepared_packets(self):
        asset = self.root / 'evidence' / 'TEST-source.txt'; asset.parent.mkdir(exist_ok=True);asset.write_text('TEST ONLY original')
        packet = self.packet();packet['basis']['files'] = {'evidence/TEST-source.txt': lessons.reference(self.root, 'evidence/TEST-source.txt')}
        self.coach.lesson(self.root, 'packet', payload=packet, defer_sync=True)
        asset.write_text('TEST ONLY replacement')
        out = self.coach.lesson(self.root, 'prepare', payload={'packet_id': packet['id']}, defer_sync=True)
        self.assertEqual(out['waiting'], 'stale_packet')
        self.coach.lesson(self.root, 'retire-packet', packet['id'], {'reason': 'TEST ONLY source changed', 'provenance': self.prov}, defer_sync=True)
        changed = copy.deepcopy(self.preferences); changed['available_minutes']=60
        self.assertIn('preferences_changed', lessons.stale_reasons(self.root, self.packet(), changed))

    def test_stage_skip_requires_explicit_learner_and_cannot_create_band(self):
        self.start()
        with self.assertRaises(ValueError): self.advance('independent')
        self.coach.lesson(self.root, 'advance', self.lid, {'stage':'independent','learner_requested_skip':True,
                          'actor':'learner','provenance':self.prov}, defer_sync=True)
        self.present(['q1']);out=self.submit({'q1':'TEST ONLY answer'})
        payload={'response_id':out['response_id'],'item_ids':['q1'],'band':8,'provenance':self.prov}
        with self.assertRaises(ValueError): self.coach.lesson(self.root,'review',self.lid,payload,defer_sync=True)

    def test_conflicting_active_work_is_preserved(self):
        self.start()
        attempt = self.coach.session.start(self.root, self.env.task_id, 'Listening', 'practice', 20)
        before=lessons.find(self.root,self.lid)
        out=self.coach.prepare(self.root)
        self.assertEqual(out['waiting'],'reconciliation')
        self.assertEqual(lessons.find(self.root,self.lid),before)
        self.assertEqual(self.coach.session.find_session(self.root,attempt['session']['id'])['status'],'in_progress')

    def test_offline_retry_and_summary_failure_preserve_checkpoint(self):
        self.independent();self.present(['q1'])
        payload={'text':'TEST ONLY raw answer','answers':{'q1':'raw'},'submission':'complete','provenance':self.prov}
        with mock.patch.object(self.coach.session,'_rebuild',side_effect=OSError('TEST ONLY interrupted summary')):
            with self.assertRaises(OSError): self.coach.lesson(self.root,'checkpoint',self.lid,payload,defer_sync=True)
        self.env.synchronize.side_effect=self.env.offline
        out=self.coach.lesson(self.root,'checkpoint',self.lid,payload)
        self.assertTrue(out['duplicate']);self.assertFalse(out['synced'])
        self.assertEqual(sum(r['payload']==payload for r in lessons.find(self.root,self.lid)['responses']),1)

    def test_legacy_budget_unknown_and_saved_prompt_stay_unknown_on_resume(self):
        self.coach.lesson(self.root,'packet',payload=self.packet(),defer_sync=True)
        source=self.root/'evidence'/'TEST-history.json';source.parent.mkdir(exist_ok=True);source.write_text('{}')
        migration={'packet_id':'TEST-primary','stage':'guided','references':['evidence/TEST-history.json'],'provenance':self.prov}
        out=self.coach.lesson(self.root,'migrate',payload=migration,defer_sync=True)
        self.lid=out['lesson']['id'];self.assertIsNone(out['lesson']['available_minutes'])
        resumed=self.coach.prepare(self.root,minutes=40)
        self.assertIsNone(resumed['lesson']['available_minutes'])
        self.assertEqual(resumed['lesson']['displayed_prompt']['items'][0]['prompt'],'Do you use your phone for banking?')

    def test_status_and_brief_share_one_current_action(self):
        self.start();self.present();self.advance('example');self.present();self.advance('guided');self.present()
        action=self.coach.status(self.root)['coaching_brief']['next_action']
        self.assertIn('- Tugas berikutnya: '+action,(self.root/'STATUS.md').read_text())
        self.assertEqual((self.root/'STATUS.md').read_text().count('- Tugas berikutnya:'),1)

    def test_completed_correction_review_keeps_record_completed(self):
        self.independent();self.present(['q1']);out=self.submit({'q1':'first'})
        self.grade(out['response_id'],['q1']);self.advance('review');self.advance('completed')
        out=self.submit({'q1':'corrected'},purpose='review')
        self.grade(out['response_id'],['q1'])
        record=lessons.find(self.root,self.lid)
        self.assertEqual((record['stage'],record['status']),('completed','completed'))
        self.coach.status(self.root)

    def test_presentation_retry_after_review_is_a_true_noop(self):
        self.independent();self.present(['q1']);out=self.submit({'q1':'first'})
        self.grade(out['response_id'],['q1'])
        before=lessons.find(self.root,self.lid)
        retry=self.present(['q1'])
        self.assertTrue(retry['duplicate']);self.assertEqual(lessons.find(self.root,self.lid),before)
        self.advance('review')

    def test_same_text_in_different_stages_is_preserved_twice(self):
        self.start();self.present();self.advance('example');self.present();self.advance('guided');self.present()
        payload={'text':'TEST ONLY identical short answer','submission':'complete','provenance':self.prov}
        a=self.coach.lesson(self.root,'checkpoint',self.lid,payload,defer_sync=True)
        self.grade(a['response_id'],[]);self.advance('independent');self.present(['q1'])
        b=self.coach.lesson(self.root,'checkpoint',self.lid,payload,defer_sync=True)
        self.assertNotEqual(a['response_id'],b['response_id']);self.assertFalse(b['duplicate'])
        self.assertEqual(b['lesson']['status'],'awaiting_review')

    def official_independent(self):
        task=next(t for t in self.env.catalog['tasks'] if t['id']==self.env.task_id)
        p=self.packet();p.update(source_label='official',practice_kind='task',official_task_id=task['id'],main_skill=task['skill'])
        p['independent']=[{'id':n,'prompt':'TEST ONLY official question '+n} for n in task['question_numbers']]
        p['coach_only']={}
        name=task['local']['prompt'];p['basis']['files']={name:lessons.reference(self.root,name)}
        self.coach.lesson(self.root,'packet',payload=p,defer_sync=True)
        self.lid=self.coach.lesson(self.root,'prepare',defer_sync=True)['lesson']['id']
        self.present();self.advance('example');self.present();self.advance('guided');self.present()
        out=self.submit({'g1':'TEST ONLY guided'});self.grade(out['response_id'],['g1']);self.advance('independent')

    def test_official_delivery_links_attempt_and_cannot_use_drill_review(self):
        self.official_independent()
        with self.assertRaises(ValueError): lessons.present(self.root,self.lid,{'provenance':self.prov})
        self.present(['1','2'])
        record=lessons.find(self.root,self.lid);sid=record['official_attempt_id']
        self.assertIsNotNone(sid)
        out=self.submit({'1':'TEST ONLY learner','2':'TEST ONLY learner'})
        with self.assertRaises(ValueError): self.grade(out['response_id'],['1','2'])
        self.assertEqual(self.coach.session.find_session(self.root,sid)['status'],'in_progress')

    def test_restart_after_official_complete_resumes_lesson_without_retake(self):
        self.official_independent();self.present(['1','2'])
        record=lessons.find(self.root,self.lid);sid=record['official_attempt_id']
        self.coach.checkpoint(self.root,sid,self.env.input())
        self.coach.complete(self.root,sid,self.env.result())
        before=self.coach.session.find_session(self.root,sid)
        resumed=self.coach.prepare(self.root)
        self.assertTrue(resumed['resumed']);self.assertEqual(resumed['lesson']['id'],self.lid)
        self.assertIn('completed official attempt',resumed['lesson']['next_action'])
        self.assertEqual(self.coach.session.find_session(self.root,sid),before)
        self.assertEqual(len(self.coach.session.load_sessions(self.root)),1)

    def test_teacher_brief_never_contains_upcoming_correction_data(self):
        out=self.coach.lesson(self.root,'teacher-brief',payload={'main_skill':'Listening','ielts_task_type':'form_completion','objective':'TEST ONLY preparation'})
        serialized=json.dumps(out)
        self.assertNotIn('coach_refs/',serialized);self.assertNotIn('key_url',serialized)
        self.assertIn('learning_context',out)

    def test_fresh_pool_items_remain_answerable_after_first_batch_review(self):
        self.independent();self.present(['q1']);first=self.submit({'q1':'first'})
        self.grade(first['response_id'],['q1']);self.present(['q2'])
        second=self.submit({'q2':'second'})
        self.grade(second['response_id'],['q2'])
        count=lessons.counts(lessons.find(self.root,self.lid),lessons.packet_for(self.root,lessons.find(self.root,self.lid)))
        self.assertEqual((count['submitted'],count['reviewed']),(2,2))
        with self.assertRaises(ValueError):self.submit({'q1':'changed after feedback'})
        self.advance('review')

    def test_criteria_cannot_smuggle_nested_band_estimates(self):
        self.independent();self.present(['q1']);out=self.submit({'q1':'first'})
        payload={'response_id':out['response_id'],'item_ids':['q1'],'provenance':self.prov,
                 'criteria':{'grammar':{'band':8}},'feedback':{'strength':'Observed','patterns':[],
                 'action':'Check','next_task':'New context'}}
        with self.assertRaises(ValueError):self.coach.lesson(self.root,'review',self.lid,payload,defer_sync=True)

    def test_new_prompt_does_not_replace_an_unanswered_prompt(self):
        self.independent();self.present(['q1'])
        with self.assertRaises(ValueError):self.present(['q2'])
        self.assertEqual(lessons.summary(self.root,lessons.find(self.root,self.lid))['displayed_prompt']['items'][0]['id'],'q1')

    def test_completed_lesson_uses_prepared_queue_not_stale_historical_next_task(self):
        self.independent();self.present(['q1']);out=self.submit({'q1':'first'});self.grade(out['response_id'],['q1'])
        self.advance('review');self.advance('completed')
        packet=self.packet(pid='TEST-next')
        self.coach.lesson(self.root,'packet',payload=packet,defer_sync=True)
        self.coach.session.rebuild(self.root)
        brief=self.coach.status(self.root)['coaching_brief']
        self.assertEqual(brief['next_action'],'Start theory from prepared Teacher packet: TEST-next')
        self.assertIn('- Tugas berikutnya: '+brief['next_action'],(self.root/'STATUS.md').read_text())
        self.assertIn('TEST-global',lessons.find(self.root,self.lid)['preference_source_event_ids'].values())


if __name__ == '__main__':
    unittest.main()
