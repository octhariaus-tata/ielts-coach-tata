#!/usr/bin/env python3
"""Durable coaching sessions. Python 3.8+, standard library only."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import uuid

JAKARTA = dt.timezone(dt.timedelta(hours=7))
SKILLS = ('Listening', 'Reading', 'Writing', 'Speaking')
BEGIN = '<!-- managed-sessions:start -->'
END = '<!-- managed-sessions:end -->'


def now():
    return dt.datetime.now(JAKARTA).isoformat(timespec='seconds')


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(content, encoding='utf-8')
        os.replace(str(temporary), str(path))
        if path.read_text(encoding='utf-8') != content:
            raise ValueError('Penyimpanan tidak lolos pembacaan ulang.')
    finally:
        if temporary.exists():
            temporary.unlink()


def json_write(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def session_path(root, sid):
    if not re.fullmatch(r'[A-Za-z0-9_-]+', sid):
        raise ValueError('ID sesi tidak valid.')
    return root / 'sessions' / (sid + '.json')


def load_sessions(root):
    items = []
    for path in sorted((root / 'sessions').glob('*.json')):
        item = json.loads(path.read_text(encoding='utf-8'))
        if (item.get('schema_version') != 1 or not item.get('id') or
                session_path(root, item['id']) != path or
                item.get('status') not in ('in_progress', 'completed') or
                item.get('skill') not in SKILLS or not item.get('task_id') or
                item.get('kind') not in ('pilot', 'diagnostic', 'practice', 'retake', 'mock', 'system_test')):
            raise ValueError('Catatan sesi tidak valid: ' + path.name)
        items.append(item)
    return items


def managed_section(path, section):
    text = path.read_text(encoding='utf-8') if path.exists() else '# Catatan\n'
    block = BEGIN + '\n' + section.rstrip() + '\n' + END
    if BEGIN in text or END in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
            raise ValueError('Marker ringkasan tidak valid: ' + path.name)
        text = text[:text.index(BEGIN)] + block + text[text.index(END) + len(END):]
    else:
        text = text.rstrip() + '\n\n' + block + '\n'
    atomic_write(path, text)


def clean_cell(value):
    return str(value).replace('|', '/').replace('\n', ' ')


def rebuild(root):
    items = load_sessions(root)
    real = [s for s in items if s['kind'] != 'system_test']
    active = [s for s in real if s['status'] == 'in_progress']
    completed = [s for s in real if s['status'] == 'completed']
    lines = ['## Sesi baru — ringkasan dari sessions/', '',
             '| ID | Skill | Jenis | Hasil | Status bukti |', '| --- | --- | --- | --- | --- |']
    for s in completed:
        result = s['result']
        score = result.get('score')
        label = ('{}/{}'.format(score['correct'], score['total']) if score else
                 'Estimasi AI' if result['mode'] == 'ai_estimate' else 'Belum dinilai')
        lines.append('| {} | {} | {} | {} | {} |'.format(
            '[{}](sessions/{}.json)'.format(s['id'], s['id']), s['skill'], s['kind'],
            label, clean_cell(result['mode'])))
    if not completed:
        lines.append('| — | — | — | Belum ada latihan baru selesai | — |')
    managed_section(root / 'PROGRESS.md', '\n'.join(lines))
    state = ['## Keadaan sesi — dibaca dari sessions/', '',
             '- Sesi belajar aktif: ' + (', '.join(s['id'] for s in active) or 'tidak ada') + '.',
             '- Sesi belajar selesai: {}.'.format(len(completed)),
             '- Tes sistem tidak dihitung sebagai kemajuan Tata.']
    if len(active) > 1:
        state.append('- Ada lebih dari satu sesi aktif; coach harus rekonsiliasi sebelum memulai sesi baru.')
    if completed:
        latest = max(completed, key=lambda s: s['completed_at'])
        state.append('- Tugas berikutnya: ' + latest['result']['feedback']['next_task'])
    managed_section(root / 'STATUS.md', '\n'.join(state))


def start(root, task_id, skill, kind, minutes):
    if skill not in SKILLS or kind not in ('pilot', 'diagnostic', 'practice', 'retake', 'mock', 'system_test'):
        raise ValueError('Skill atau jenis sesi tidak valid.')
    if minutes <= 0:
        raise ValueError('Durasi harus positif; ini durasi tersedia, bukan durasi aktual.')
    existing = [s for s in load_sessions(root) if s['status'] == 'in_progress' and
                (s['kind'] == 'system_test') == (kind == 'system_test')]
    if len(existing) > 1:
        raise ValueError('Ada beberapa sesi aktif; rekonsiliasi dulu.')
    if existing:
        if existing[0]['task_id'] != task_id or existing[0]['skill'] != skill:
            raise ValueError('Sesi lain masih aktif. Gunakan lanjut dengan ID semula.')
        rebuild(root)
        return {'created': False, 'session': existing[0]}
    material = None
    catalog_path = root / 'materials.json'
    if kind != 'system_test':
        if not catalog_path.is_file():
            raise ValueError('Katalog materi belum tersedia.')
        catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
        material = next((t for t in catalog['tasks'] if t['id'] == task_id), None)
        if material is None or material['skill'] != skill:
            raise ValueError('Tugas/skill tidak cocok dengan katalog materi.')
        if not material.get('freshness', {}).get('eligible_for_new_attempt', True) and kind != 'retake':
            raise ValueError('Materi sudah terekspos; gunakan jenis retake untuk review.')
        if kind != 'retake' and any(s['task_id'] == task_id and s['status'] == 'completed' and
                                    s['kind'] != 'system_test' for s in load_sessions(root)):
            raise ValueError('Tugas ini sudah dikerjakan; pilih soal baru atau labeli retake.')
    stamp = now()
    sid = stamp[:10] + '-' + skill.lower() + '-' + uuid.uuid4().hex[:12]
    record = dict(schema_version=1, id=sid, status='in_progress', started_at=stamp,
                  skill=skill, task_id=task_id, kind=kind, available_minutes=minutes,
                  material=material, conditions={}, evidence=[], result=None)
    json_write(session_path(root, sid), record)
    rebuild(root)
    return {'created': True, 'session': record}


def validate(root, session, result):
    mode = result.get('mode')
    if mode not in ('answers_key', 'score_only', 'reported', 'unverified', 'ai_estimate'):
        raise ValueError('Mode bukti tidak valid.')
    feedback = result.get('feedback', {})
    patterns = feedback.get('patterns', [])
    if not isinstance(patterns, list) or len(patterns) > 2:
        raise ValueError('Maksimal dua pola kesalahan.')
    for field in ('strength', 'action', 'next_task'):
        if not isinstance(feedback.get(field), str) or not feedback[field].strip():
            raise ValueError('Feedback memerlukan ' + field)
    answers = result.get('answers', [])
    score = result.get('score')
    material = session.get('material') or {}
    known_numbers = set(str(q) for q in material.get('question_numbers', []))
    if result.get('scope') not in ('partial', 'snippet', 'full', 'sample'):
        raise ValueError('Scope hasil diperlukan: partial/snippet/full/sample.')
    if session['skill'] in ('Listening', 'Reading') and result['scope'] == 'full' and len(known_numbers) != 40:
        raise ValueError('Materi sesi ini belum terbukti tes lengkap /40.')
    if score is not None:
        if any(type(score.get(k)) is not int for k in ('correct', 'total')):
            raise ValueError('Skor harus bilangan bulat.')
        if not 0 <= score['correct'] <= score['total'] or score['total'] <= 0:
            raise ValueError('Rentang skor tidak valid.')
        if known_numbers and score['total'] > len(known_numbers):
            raise ValueError('Total skor melebihi soal pada materi sesi ini.')
    if mode == 'answers_key':
        if session['skill'] not in ('Listening', 'Reading') or not answers:
            raise ValueError('Koreksi objektif memerlukan jawaban yang terbaca.')
        if result.get('key_task_id') != session['task_id'] or result.get('key_version_verified') is not True:
            raise ValueError('Key harus diverifikasi untuk versi tugas yang sama.')
        if not result.get('key_url') or not result.get('verification_method'):
            raise ValueError('Sumber key dan metode verifikasi diperlukan.')
        known_key = (session.get('material') or {}).get('urls', {}).get('key')
        if known_key and result['key_url'] != known_key:
            raise ValueError('URL key tidak cocok dengan versi materi saat sesi dimulai.')
        numbers = set()
        for answer in answers:
            number = str(answer.get('number', ''))
            if not number or number in numbers:
                raise ValueError('Nomor jawaban harus unik.')
            if known_numbers and number not in known_numbers:
                raise ValueError('Nomor soal tidak ada dalam materi sesi ini.')
            numbers.add(number)
            if type(answer.get('correct')) is not bool or 'given' not in answer or 'expected' not in answer:
                raise ValueError('Jawaban dan key per soal harus tersedia.')
            if not answer.get('proof'):
                raise ValueError('Koreksi per soal memerlukan bukti teks/transcript.')
        if not score or score['total'] != len(answers) or score['correct'] != sum(a['correct'] for a in answers):
            raise ValueError('Skor harus cocok dengan bagian yang benar-benar diperiksa.')
    elif mode in ('score_only', 'reported', 'unverified'):
        if answers or patterns:
            raise ValueError('Bukti terbatas tidak mendukung koreksi atau pola per soal.')
    if result.get('band') is not None:
        if mode == 'ai_estimate':
            if session['skill'] not in ('Writing', 'Speaking') or not result.get('criteria') or not result.get('uncertainty'):
                raise ValueError('Estimasi AI memerlukan kriteria dan ketidakpastian.')
        elif not (session['skill'] in ('Listening', 'Reading') and score and
                  score['total'] == 40 and result.get('scope') == 'full' and result.get('band_source_url')):
            raise ValueError('Cuplikan tidak boleh dikonversi menjadi band.')
    if mode == 'ai_estimate':
        if session['skill'] not in ('Writing', 'Speaking'):
            raise ValueError('Estimasi AI hanya untuk Writing/Speaking.')
        if not result.get('criteria') or not result.get('uncertainty'):
            raise ValueError('Estimasi AI memerlukan kriteria dan ketidakpastian.')
        if session['skill'] == 'Speaking':
            if result.get('input_type') not in ('audio', 'transcript'):
                raise ValueError('Jenis input Speaking harus diketahui: audio atau transcript.')
            if result.get('criteria', {}).get('pronunciation') is not None and not (
                    result['input_type'] == 'audio' and result.get('audio_inspected') is True and result.get('audio_reference')):
                raise ValueError('Pronunciation memerlukan audio yang benar-benar diperiksa dan referensi buktinya.')
    for path in result.get('evidence', []):
        p = Path(path)
        if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != 'evidence':
            raise ValueError('Bukti harus memakai path relatif di evidence/.')
        resolved = (root / p).resolve()
        try:
            resolved.relative_to((root / 'evidence').resolve())
        except ValueError:
            raise ValueError('Bukti keluar dari folder evidence/.')
        if not resolved.is_file():
            raise ValueError('File bukti tidak tersedia: ' + str(p))


def finalize(root, sid, result):
    path = session_path(root, sid)
    session = next((s for s in load_sessions(root) if s['id'] == sid), None)
    if session is None:
        raise ValueError('ID sesi tidak ditemukan.')
    validate(root, session, result)
    if session['status'] == 'completed':
        if session['result'] != result:
            raise ValueError('Sesi sudah selesai dengan hasil berbeda. Catat koreksi beralasan, jangan menimpa.')
        rebuild(root)
        return {'saved': False, 'already_completed': True, 'session': session}
    session.update(status='completed', completed_at=now(), result=result,
                   conditions=result.get('conditions', {}), evidence=result.get('evidence', []))
    json_write(path, session)
    rebuild(root)
    return {'saved': True, 'already_completed': False, 'session': session}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('start')
    p.add_argument('--task', required=True)
    p.add_argument('--skill', required=True, choices=SKILLS)
    p.add_argument('--kind', default='practice')
    p.add_argument('--minutes', type=int, default=20)
    p = sub.add_parser('finalize')
    p.add_argument('--id', required=True)
    p.add_argument('--result', type=Path, required=True, help='JSON hasil coach; simpan input sementara di .local/.')
    sub.add_parser('status')
    sub.add_parser('rebuild')
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.command == 'start':
            output = start(root, args.task, args.skill, args.kind, args.minutes)
        elif args.command == 'finalize':
            output = finalize(root, args.id, json.loads(args.result.read_text(encoding='utf-8')))
        elif args.command == 'rebuild':
            rebuild(root)
            output = {'rebuilt': True}
        else:
            sessions = load_sessions(root)
            output = {'active': [s for s in sessions if s['status'] == 'in_progress' and s['kind'] != 'system_test'],
                      'completed_learning_count': sum(s['status'] == 'completed' and s['kind'] != 'system_test' for s in sessions)}
        print(json.dumps(output, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
