#!/usr/bin/env python3
"""Prepare one daily learning card without starting or grading an attempt.

Default is read-only JSON output. --save writes only .local/proactive/.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coach
import session

WEEK = {
    0: ('study', 'Listening', 20),
    1: ('study', 'Reading', 20),
    2: ('study', 'Speaking', 20),
    3: ('study', 'Writing', 20),
    4: ('weekly_recap', None, 20),
    5: ('rest', None, 0),
    6: ('rest', None, 0),
}
DAY_NAMES = ('Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu')
FOCUS = {
    'form_completion': 'Melengkapi formulir: menangkap detail dan mengikuti batas kata.',
    'short_answer_questions': 'Menjawab singkat dari audio dan mengikuti batas kata.',
    'true_false_not_given': 'Membedakan True, False, Not Given dengan bukti teks.',
    'matching_features': 'Mencocokkan informasi dengan tokoh atau kategori dalam teks.',
    'individual_long_turn': 'Part 2: mengembangkan jawaban tentang benda penting.',
    'introduction_interview': 'Part 1: menjawab tentang hometown dan accommodation.',
    'advantages_disadvantages_outweigh': 'Micro-task: posisi, outline, dan satu paragraf tentang tourism; tanpa band utuh.',
    'bar_chart': 'Micro-task: introduction dan overview grafik pendidikan; tanpa band utuh.',
}


def build(root, day):
    root = Path(root).resolve()
    records = session.load_sessions(root)
    report = coach.adaptation.analyze(root, records=records)
    active = [r for r in records if r['status'] == 'in_progress' and r['kind'] != 'system_test']
    completed = sorted([r for r in records if r['status'] == 'completed' and r['kind'] != 'system_test'],
                       key=lambda r: (r['completed_at'], r['id']))
    mode, planned_skill, planned_minutes = WEEK[day.weekday()]
    catalog = coach.catalog(root)
    lesson_state = coach.lessons.current(root, official=records)
    card = {'schema_version': 1, 'date': day.isoformat(), 'day': DAY_NAMES[day.weekday()],
            'generated_at': session.now(), 'timezone': 'Asia/Jakarta', 'target_available_time': '09:00',
            'planned_mode': mode, 'planned_skill': planned_skill,
            'input_session_ids': report['input_session_ids'],
            'input_feedback_ids': report['input_feedback_ids'],
            'rule_version': report['rule_version'], 'attempt_created': False,
            'source_limit': 'Local snapshot; coach rechecks source, readiness and sync when Tata says mulai.'}
    if lesson_state.get('waiting'):
        return dict(card, action='coach_attention', minutes=0, reason=lesson_state['next_action'])
    if lesson_state.get('current_lesson'):
        lesson = lesson_state['current_lesson']
        return dict(card, action='resume_lesson', lesson_id=lesson['id'], skill=lesson['main_skill'],
                    minutes=lesson['available_minutes'], phase=lesson['stage'], topic=lesson['objective'],
                    next_action=lesson_state['next_action'], learner_prompt=lesson['displayed_prompt'])
    if report['preferences']['effective'].get('teaching_sequence') == 'teach_first' and mode == 'study' and not active:
        prepared = coach.lessons.prepared(root, report['preferences']['effective'])
        return dict(card, action='prepare_lesson', minutes=report['preferences']['effective'].get('available_minutes', 40),
                    prepared_queue=prepared, next_action='Ketik mulai untuk materi → contoh → guided → independent → review.')
    if mode == 'rest':
        return dict(card, action='rest', minutes=0, topic='Akhir pekan: tidak ada tugas terjadwal.',
                    learner_instruction='Tidak ada tugas wajib atau utang tugas.')
    if len(active) > 1:
        return dict(card, action='coach_attention', minutes=0,
                    reason='Beberapa sesi aktif ditemukan; pertahankan semuanya dan rekonsiliasi.', task=None)
    if mode == 'weekly_recap':
        monday = day - dt.timedelta(days=day.weekday())
        recent = [r for r in completed if monday <= dt.date.fromisoformat(r['completed_at'][:10]) <= day]
        return dict(card, action='weekly_recap', minutes=planned_minutes,
                    topic='Recap: satu perbaikan dari hasil tiap skill yang tersedia, lalu satu prioritas minggu depan.',
                    review_session_ids=[r['id'] for r in recent],
                    pending_session_ids=[r['id'] for r in active],
                    learning_readiness=report['readiness']['status'],
                    learner_instruction='Ketik mulai untuk recap. Skill yang belum dilatih tetap ditandai belum ada bukti; tidak ada tes baru.')
    if active:
        record = active[0]
        task = record.get('material')
        return dict(card, action='resume', session_id=record['id'], skill=record['skill'],
                    phase=record.get('phase', 'working'), minutes=record['available_minutes'],
                    topic=task.get('title') if task else record['task_id'],
                    learner_instruction='Ketik lanjut; respons tersimpan dipulihkan. Jangan mengulang audio.',
                    task_id=record['task_id'])
    used = {r['task_id'] for r in completed}
    available = [t for t in catalog['tasks'] if t.get('skill') == planned_skill and
                 t.get('role') in ('primary', 'backup') and t['id'] not in used and
                 t.get('freshness', {}).get('eligible_for_new_attempt', True)]
    available.sort(key=lambda t: t.get('role') != 'primary')
    wanted = [t['id'] for t in available]
    queue = {'skill': planned_skill, 'next_task_id': wanted[0] if wanted else None,
             'backup_task_id': wanted[1] if len(wanted) > 1 else None}
    checks, selected = {}, None
    for tid in wanted:
        task = next((t for t in catalog['tasks'] if t['id'] == tid), None)
        if task is None:
            continue
        checks[tid] = coach.task_checks(root, task)
        if all(c['status'] == 'passed' for c in checks[tid].values()):
            selected = task
            break
    if selected is None:
        return dict(card, action='coach_attention', minutes=0, task=None,
                    reason='Coach perlu menyiapkan materi baru/valid; jangan memaksa materi lama menjadi pengukuran baru.',
                    queue=queue, checks=checks)
    budget = report['preferences']['effective'].get('available_minutes', planned_minutes)
    remaining = [t['id'] for t in catalog['tasks'] if t.get('skill') == selected['skill'] and
                 t.get('role') in ('primary', 'backup') and t['id'] not in used and
                 t.get('freshness', {}).get('eligible_for_new_attempt', True)]
    return dict(card, action='study', skill=selected['skill'], minutes=budget,
                task_id=selected['id'], topic=selected['title'],
                focus=FOCUS.get(selected.get('question_type'), selected.get('question_type')),
                question_numbers=selected.get('question_numbers', []),
                backup_task_id=queue['backup_task_id'] if selected['id'] == queue['next_task_id'] else None,
                material_checks=checks[selected['id']],
                sequence_adjusted=selected['skill'] != planned_skill,
                fresh_task_ids_for_skill=remaining, replenish_needed=len(remaining) < 2,
                learner_instruction='Ketik mulai. Coach membuka tepat satu tugas dan mencatat sesi; setelah menjawab, ketik done.',
                assessment_limit='Cuplikan/micro-task memberi feedback terbatas; bukan baseline penuh atau skor IELTS resmi.')


def save(root, card):
    folder = root / '.local' / 'proactive'
    for path in (root / '.local', folder):
        if path.is_symlink():
            raise ValueError('Folder output tidak boleh symlink.')
    serialized = json.dumps(card, ensure_ascii=False, indent=2) + '\n'
    session.atomic_write(folder / 'daily_card.json', serialized)
    session.atomic_write(folder / (card['date'] + '.json'), serialized)
    return hashlib.sha256(serialized.encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--date', type=dt.date.fromisoformat)
    parser.add_argument('--save', action='store_true')
    args = parser.parse_args()
    try:
        day = args.date or dt.datetime.now(session.JAKARTA).date()
        result = build(args.root, day)
        if args.save:
            result['local_card_sha256'] = save(args.root.resolve(), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
