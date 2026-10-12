"""Daily cards plan learning without mutating attempts or grading."""
import datetime as dt
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import daily_card
import test_coach as fixture


class DailyCardTests(unittest.TestCase):
    def setUp(self):
        self.env = fixture.CoachTests('test_offline_prepare_uses_verified_local_materials')
        self.env.setUp()
        self.addCleanup(self.env.doCleanups)
        self.root = self.env.root

    def test_weekdays_one_skill_friday_recap_weekends_off(self):
        expected = [('Listening', 'study'), ('Reading', 'study'), ('Speaking', 'study'),
                    ('Writing', 'study'), (None, 'weekly_recap'), (None, 'rest'), (None, 'rest')]
        before = (self.root / 'PROFILE.md').read_bytes()
        for offset, (skill, action) in enumerate(expected):
            card = daily_card.build(self.root, dt.date(2026, 10, 12) + dt.timedelta(days=offset))
            self.assertEqual(card.get('skill'), skill)
            self.assertEqual(card['action'], action)
            self.assertFalse(card['attempt_created'])
        self.assertEqual(list((self.root / 'sessions').glob('*.json')), [])
        self.assertEqual((self.root / 'PROFILE.md').read_bytes(), before)

    def test_tomorrow_reading_packet_has_no_answers_or_transcript(self):
        card = daily_card.build(self.root, dt.date(2026, 10, 13))
        self.assertEqual(card['task_id'], 'reading-marie-curie-tfng')
        self.assertEqual(card['minutes'], 20)
        self.assertNotIn('answers', card)
        self.assertNotIn('transcript', card)
        self.assertNotIn('band', card)

    def test_unfinished_attempt_is_resumed_not_replaced_by_calendar(self):
        record = self.env.prepare()
        path = self.root / 'sessions' / (record['id'] + '.json')
        before = path.read_bytes()
        card = daily_card.build(self.root, dt.date(2026, 10, 13))
        self.assertEqual(card['action'], 'resume')
        self.assertEqual(card['session_id'], record['id'])
        self.assertEqual(path.read_bytes(), before)

    def test_bad_primary_cache_uses_one_verified_backup(self):
        (self.root / 'coach_refs' / 'reading-marie-curie-tfng.json').unlink()
        card = daily_card.build(self.root, dt.date(2026, 10, 13))
        self.assertEqual(card['task_id'], 'reading-rockets-features')
        self.assertIsNone(card['backup_task_id'])

    def test_friday_preserves_pending_attempt_and_reports_no_fake_results(self):
        record = self.env.prepare()
        path = self.root / 'sessions' / (record['id'] + '.json')
        before = path.read_bytes()
        card = daily_card.build(self.root, dt.date(2026, 10, 16))
        self.assertEqual(card['action'], 'weekly_recap')
        self.assertEqual(card['pending_session_ids'], [record['id']])
        self.assertEqual(card['review_session_ids'], [])
        self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
