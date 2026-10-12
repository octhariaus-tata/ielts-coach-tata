#!/usr/bin/env python3
"""Durable coaching sessions. Python 3.8+, standard library only.

Checkpoint input is preserved before grading; the coach remains responsible for
reading the actual evidence and judging the response.
"""
import argparse
import copy
from contextlib import contextmanager
import datetime as dt
import json
import os
from pathlib import Path
import re
import sys
import uuid

JAKARTA = dt.timezone(dt.timedelta(hours=7))
SKILLS = ('Listening', 'Reading', 'Writing', 'Speaking')
KINDS = ('pilot', 'diagnostic', 'practice', 'retake', 'mock', 'system_test')
PHASES = ('working', 'awaiting_evidence', 'awaiting_review', 'completed')
MODES = ('answers_key', 'score_only', 'reported', 'unverified', 'ai_estimate')
BEGIN = '<!-- managed-sessions:start -->'
END = '<!-- managed-sessions:end -->'


def now():
    return dt.datetime.now(JAKARTA).isoformat(timespec='seconds')


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


@contextmanager
def mutation_lock(root):
    """OS lock prevents two local chats from creating or updating simultaneously.

    The OS releases it on interruption; no stale lock directory needs deletion.
    This is a local lock, not a cross-device GitHub lock.
    """
    path = root / '.local' / 'session.lock'
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError('Path lock pencatatan tidak aman; operasi dihentikan.')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            if handle.tell() == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise ValueError('Pencatatan sedang digunakan chat lain pada laptop ini. Coba lagi setelah selesai.')
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise ValueError('Pencatatan sedang digunakan chat lain pada laptop ini. Coba lagi setelah selesai.')
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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
    if not isinstance(sid, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', sid):
        raise ValueError('ID sesi tidak valid.')
    return root / 'sessions' / (sid + '.json')


def validate_score(score):
    if not isinstance(score, dict) or any(type(score.get(k)) is not int for k in ('correct', 'total')):
        raise ValueError('Skor harus bilangan bulat correct dan total.')
    if not 0 <= score['correct'] <= score['total'] or score['total'] <= 0:
        raise ValueError('Rentang skor tidak valid.')


def validate_provenance(provenance):
    if not isinstance(provenance, dict) or not all(nonempty(provenance.get(k)) for k in ('method', 'reference')):
        raise ValueError('Input memerlukan provenance dengan method dan reference yang jelas.')


def validate_evidence(root, evidence, check_files=True):
    if not isinstance(evidence, list) or any(not nonempty(path) for path in evidence):
        raise ValueError('Bukti harus berupa daftar path relatif di evidence/.')
    for path in evidence:
        p = Path(path)
        if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != 'evidence':
            raise ValueError('Bukti harus memakai path relatif di evidence/.')
        resolved = (root / p).resolve()
        try:
            # An evidence/ symlink pointing outside the project is also rejected.
            resolved.relative_to(root.resolve() / 'evidence')
        except ValueError:
            raise ValueError('Bukti keluar dari folder evidence/.')
        if check_files and not resolved.is_file():
            raise ValueError('File bukti tidak tersedia: ' + str(p))


def has_input(payload):
    return bool(nonempty(payload.get('text')) or payload.get('evidence') or
                payload.get('score') is not None or nonempty(payload.get('audio_reference')))


def validate_payload(root, payload, check_files=True):
    if not isinstance(payload, dict):
        raise ValueError('Checkpoint harus berupa objek JSON.')
    if 'text' in payload and not isinstance(payload['text'], str):
        raise ValueError('Respons text harus berupa teks.')
    if 'conditions' in payload and not isinstance(payload['conditions'], dict):
        raise ValueError('Kondisi harus berupa objek JSON.')
    if payload.get('purpose', 'attempt') not in ('attempt', 'review'):
        raise ValueError('Purpose harus attempt atau review.')
    if 'phase' in payload and payload['phase'] not in PHASES[:-1]:
        raise ValueError('Phase checkpoint tidak valid.')
    if payload.get('score') is not None:
        validate_score(payload['score'])
    evidence = payload.get('evidence', [])
    if not isinstance(evidence, list) or any(not nonempty(path) for path in evidence):
        raise ValueError('Bukti harus berupa daftar path.')
    validate_evidence(root, evidence, check_files=check_files)
    if has_input(payload):
        validate_provenance(payload.get('provenance'))
    if 'provenance' in payload and payload['provenance'] is not None:
        validate_provenance(payload['provenance'])


def load_sessions(root):
    """Validate the storage envelope, without regrading legacy results."""
    items = []
    for path in sorted((root / 'sessions').glob('*.json')):
        try:
            item = json.loads(path.read_text(encoding='utf-8'))
            if (not isinstance(item, dict) or item.get('schema_version') != 1 or
                    session_path(root, item.get('id')) != path or
                    item.get('status') not in ('in_progress', 'completed') or
                    item.get('skill') not in SKILLS or not nonempty(item.get('task_id')) or
                    item.get('kind') not in KINDS or not nonempty(item.get('started_at')) or
                    not isinstance(item.get('conditions', {}), dict) or
                    not isinstance(item.get('evidence', []), list) or
                    (item.get('material') is not None and not isinstance(item['material'], dict))):
                raise ValueError('Envelope tidak valid.')
            validate_evidence(root, item.get('evidence', []), check_files=False)
            phase = item.get('phase')
            if phase is not None and (phase not in PHASES or
                    (item['status'] == 'completed') != (phase == 'completed')):
                raise ValueError('Phase tidak cocok dengan status.')
            revisions = item.get('response_revisions', [])
            if not isinstance(revisions, list):
                raise ValueError('response_revisions bukan daftar.')
            revision_ids = set()
            for revision in revisions:
                if (not isinstance(revision, dict) or not nonempty(revision.get('revision_id')) or
                        revision['revision_id'] in revision_ids or not nonempty(revision.get('created_at'))):
                    raise ValueError('Revisi tidak valid.')
                revision_ids.add(revision['revision_id'])
                validate_payload(root, revision.get('payload'), check_files=False)
            if 'source_response' in item:
                validate_payload(root, item['source_response'], check_files=False)
            graded = item.get('graded_response_revision_id')
            if graded is not None and not any(r['revision_id'] == graded and
                    r['payload'].get('purpose', 'attempt') == 'attempt' for r in revisions):
                raise ValueError('Respons yang dinilai tidak ditemukan.')
            if item['status'] == 'completed':
                result = item.get('result')
                if (not nonempty(item.get('completed_at')) or not isinstance(result, dict) or
                        result.get('mode') not in MODES or not isinstance(result.get('feedback'), dict) or
                        not nonempty(result['feedback'].get('next_task'))):
                    raise ValueError('Hasil selesai tidak valid.')
                if result.get('score') is not None:
                    validate_score(result['score'])
            elif item.get('result') is not None:
                raise ValueError('Sesi aktif tidak boleh memiliki hasil selesai.')
        except (ValueError, TypeError, KeyError) as error:
            raise ValueError('Catatan sesi tidak valid: {} ({})'.format(path.name, error))
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


def _rebuild(root):
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
                 'Feedback AI terbatas' if result['mode'] == 'ai_estimate' else 'Belum dinilai')
        if result.get('band') is not None:
            if result['mode'] == 'ai_estimate':
                target = {'task1': 'Task 1', 'task2': 'Task 2'}.get(result.get('band_target'), s['skill'])
                label = '{} estimasi AI {}'.format(target, result['band'])
            else:
                label += ' — band perkiraan {}'.format(result['band'])
        lines.append('| {} | {} | {} | {} | {} |'.format(
            '[{}](sessions/{}.json)'.format(s['id'], s['id']), s['skill'], s['kind'],
            clean_cell(label), clean_cell(result['mode'])))
    if not completed:
        lines.append('| — | — | — | Belum ada latihan baru selesai | — |')
    managed_section(root / 'PROGRESS.md', '\n'.join(lines))
    state = ['## Keadaan sesi — dibaca dari sessions/', '',
             '- Sesi belajar aktif: ' + (', '.join(s['id'] for s in active) or 'tidak ada') + '.',
             '- Sesi belajar selesai: {}.'.format(len(completed)),
             '- Tes sistem tidak dihitung sebagai kemajuan Tata.']
    for s in active:
        state.append('- {}: {} ({} checkpoint tersimpan).'.format(
            s['id'], s.get('phase', 'working'), len(s.get('response_revisions', []))))
    if len(active) > 1:
        state.append('- Ada lebih dari satu sesi aktif; coach harus rekonsiliasi sebelum memulai sesi baru.')
    if completed:
        latest = max(completed, key=lambda s: s['completed_at'])
        state.append('- Tugas berikutnya: ' + latest['result']['feedback']['next_task'])
    managed_section(root / 'STATUS.md', '\n'.join(state))


def rebuild(root):
    with mutation_lock(root):
        _rebuild(root)


def start(root, task_id, skill, kind, minutes):
    with mutation_lock(root):
        if skill not in SKILLS or kind not in KINDS:
            raise ValueError('Skill atau jenis sesi tidak valid.')
        if type(minutes) is not int or minutes <= 0:
            raise ValueError('Durasi harus positif; ini durasi tersedia, bukan durasi aktual.')
        sessions = load_sessions(root)
        existing = [s for s in sessions if s['status'] == 'in_progress' and
                    (s['kind'] == 'system_test') == (kind == 'system_test')]
        if len(existing) > 1:
            raise ValueError('Ada beberapa sesi aktif; rekonsiliasi dulu.')
        if existing:
            if existing[0]['task_id'] != task_id or existing[0]['skill'] != skill:
                raise ValueError('Sesi lain masih aktif. Gunakan lanjut dengan ID semula.')
            _rebuild(root)
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
                                        s['kind'] != 'system_test' for s in sessions):
                raise ValueError('Tugas ini sudah dikerjakan; pilih soal baru atau labeli retake.')
        stamp = now()
        sid = stamp[:10] + '-' + skill.lower() + '-' + uuid.uuid4().hex[:12]
        record = dict(schema_version=1, id=sid, status='in_progress', phase='working', started_at=stamp,
                      skill=skill, task_id=task_id, kind=kind, available_minutes=minutes,
                      material=material, conditions={}, evidence=[], response_revisions=[], result=None)
        json_write(session_path(root, sid), record)
        _rebuild(root)
        return {'created': True, 'session': record}


def find_session(root, sid):
    session_path(root, sid)
    item = next((s for s in load_sessions(root) if s['id'] == sid), None)
    if item is None:
        raise ValueError('ID sesi tidak ditemukan.')
    return item


def checkpoint(root, sid, payload):
    """Append input immediately. Identical retries do not create a revision."""
    with mutation_lock(root):
        item = find_session(root, sid)
        payload = copy.deepcopy(payload)
        validate_payload(root, payload)
        payload.setdefault('purpose', 'attempt')
        if item['status'] == 'completed' and payload['purpose'] != 'review':
            raise ValueError('Sesi selesai hanya menerima revisi review; respons attempt asli dipertahankan.')
        if not has_input(payload) and not payload.get('phase') and not payload.get('conditions'):
            raise ValueError('Checkpoint kosong; simpan input, kondisi, atau fase menunggu bukti.')
        revisions = item.setdefault('response_revisions', [])
        duplicate = next((r for r in revisions if r['payload'] == payload), None)
        if duplicate:
            _rebuild(root)
            return {'saved': False, 'duplicate': True, 'revision_id': duplicate['revision_id'], 'session': item}
        rid = uuid.uuid4().hex
        revisions.append({'revision_id': rid, 'created_at': now(), 'payload': payload})
        if item['status'] != 'completed':
            item['phase'] = payload.get('phase', 'awaiting_review' if has_input(payload) else item.get('phase', 'working'))
            item.setdefault('conditions', {}).update(payload.get('conditions', {}))
            item['evidence'] = list(dict.fromkeys(item.get('evidence', []) + payload.get('evidence', [])))
        json_write(session_path(root, sid), item)
        _rebuild(root)
        return {'saved': True, 'duplicate': False, 'revision_id': rid, 'session': item}


def response_for_result(root, session, result):
    revisions = session.get('response_revisions', [])
    selected = result.get('response_revision_id')
    eligible = [r for r in revisions if r['payload'].get('purpose', 'attempt') == 'attempt' and has_input(r['payload'])]
    if selected is not None:
        revision = next((r for r in eligible if r['revision_id'] == selected), None)
        if revision is None:
            raise ValueError('response_revision_id harus menunjuk respons attempt asli yang tersimpan.')
    else:
        revision = eligible[-1] if eligible else None
    if revision:
        payload = revision['payload']
        validate_payload(root, payload)
        return payload, revision['revision_id']
    direct = result.get('source_response')
    if direct is None:
        direct = {'text': result.get('sample_text', ''), 'evidence': result.get('evidence', []),
                  'score': result.get('score'), 'provenance': result.get('provenance')}
    validate_payload(root, direct)
    if direct.get('purpose', 'attempt') != 'attempt':
        raise ValueError('Hasil attempt tidak boleh memakai respons review setelah feedback.')
    if not has_input(direct):
        raise ValueError('Hasil memerlukan respons atau skor dengan provenance yang tersimpan.')
    return direct, None


def criterion_present(criteria, key):
    value = criteria.get(key)
    return value is not None and value != '' and value != {} and value != [] and type(value) is not bool


def valid_band(value):
    return type(value) in (int, float) and 0 <= value <= 9 and value * 2 == int(value * 2)


def validate(root, session, result):
    if not isinstance(result, dict):
        raise ValueError('Hasil harus berupa objek JSON.')
    mode = result.get('mode')
    if mode not in MODES:
        raise ValueError('Mode bukti tidak valid.')
    if mode == 'unverified':
        raise ValueError('Respons belum terverifikasi tetap menunggu review; jangan tutup sebagai hasil selesai.')
    if not nonempty(result.get('verification_method')):
        raise ValueError('Metode verifikasi diperlukan untuk setiap hasil baru.')
    if not isinstance(result.get('conditions', {}), dict):
        raise ValueError('Kondisi harus berupa objek JSON.')
    validate_evidence(root, result.get('evidence', []))
    response, _ = response_for_result(root, session, result)
    feedback = result.get('feedback', {})
    if not isinstance(feedback, dict):
        raise ValueError('Feedback harus berupa objek JSON.')
    patterns = feedback.get('patterns', [])
    if not isinstance(patterns, list) or len(patterns) > 2 or any(not nonempty(p) for p in patterns):
        raise ValueError('Maksimal dua pola kesalahan berupa teks.')
    for field in ('strength', 'action', 'next_task'):
        if not nonempty(feedback.get(field)):
            raise ValueError('Feedback memerlukan ' + field)
    answers = result.get('answers', [])
    if not isinstance(answers, list):
        raise ValueError('Jawaban harus berupa daftar.')
    score = result.get('score')
    material = session.get('material') or {}
    known_numbers = set(str(q) for q in material.get('question_numbers', []))
    if result.get('scope') not in ('partial', 'snippet', 'full', 'sample'):
        raise ValueError('Scope hasil diperlukan: partial/snippet/full/sample.')
    if session['skill'] in ('Listening', 'Reading') and result['scope'] == 'full' and len(known_numbers) != 40:
        raise ValueError('Materi sesi ini belum terbukti tes lengkap /40.')
    if score is not None:
        validate_score(score)
        if known_numbers and score['total'] > len(known_numbers):
            raise ValueError('Total skor melebihi soal pada materi sesi ini.')
    if mode == 'answers_key':
        if not (nonempty(response.get('text')) or response.get('evidence')):
            raise ValueError('Skor total saja tidak membuktikan jawaban per soal.')
        if session['skill'] not in ('Listening', 'Reading') or not answers:
            raise ValueError('Koreksi objektif memerlukan jawaban yang terbaca.')
        if result.get('key_task_id') != session['task_id'] or result.get('key_version_verified') is not True:
            raise ValueError('Key harus diverifikasi untuk versi tugas yang sama.')
        if not nonempty(result.get('key_url')):
            raise ValueError('Sumber key diperlukan.')
        known_key = material.get('urls', {}).get('key')
        if known_key and result['key_url'] != known_key:
            raise ValueError('URL key tidak cocok dengan versi materi saat sesi dimulai.')
        numbers = set()
        for answer in answers:
            if not isinstance(answer, dict):
                raise ValueError('Jawaban per soal harus berupa objek.')
            number = str(answer.get('number', ''))
            if not number or number in numbers:
                raise ValueError('Nomor jawaban harus unik.')
            if known_numbers and number not in known_numbers:
                raise ValueError('Nomor soal tidak ada dalam materi sesi ini.')
            numbers.add(number)
            if type(answer.get('correct')) is not bool or 'given' not in answer or 'expected' not in answer:
                raise ValueError('Jawaban dan key per soal harus tersedia.')
            if not nonempty(answer.get('proof')):
                raise ValueError('Koreksi per soal memerlukan bukti teks/transcript.')
        if not score or score['total'] != len(answers) or score['correct'] != sum(a['correct'] for a in answers):
            raise ValueError('Skor harus cocok dengan bagian yang benar-benar diperiksa.')
    elif mode in ('score_only', 'reported', 'unverified'):
        if answers or patterns:
            raise ValueError('Bukti terbatas tidak mendukung koreksi atau pola per soal.')
        if mode in ('score_only', 'reported'):
            if score is None or response.get('score') != score:
                raise ValueError('Skor total memerlukan skor sumber yang sama dengan provenance tersimpan.')
        elif score is not None or result.get('band') is not None:
            raise ValueError('Input belum terverifikasi tidak mendukung skor atau band.')
        elif not (nonempty(response.get('text')) or response.get('evidence') or nonempty(response.get('audio_reference'))):
            raise ValueError('Input belum terverifikasi memerlukan respons asli, bukan hanya angka skor.')
    band = result.get('band')
    if band is not None:
        if not valid_band(band):
            raise ValueError('Band harus 0–9 dengan interval 0.5.')
        if mode != 'ai_estimate' and not (session['skill'] in ('Listening', 'Reading') and score and
                score['total'] == 40 and result['scope'] == 'full' and nonempty(result.get('band_source_url'))):
            raise ValueError('Cuplikan tidak boleh dikonversi menjadi band.')
    if mode == 'ai_estimate':
        if session['skill'] not in ('Writing', 'Speaking'):
            raise ValueError('Estimasi AI hanya untuk Writing/Speaking.')
        criteria = result.get('criteria')
        if not isinstance(criteria, dict) or not criteria or not nonempty(result.get('uncertainty')):
            raise ValueError('Estimasi AI memerlukan kriteria dan ketidakpastian.')
        if not (nonempty(response.get('text')) or response.get('evidence') or nonempty(response.get('audio_reference'))):
            raise ValueError('Feedback Writing/Speaking memerlukan sampel respons yang tersimpan.')
        if session['skill'] == 'Writing':
            if band is not None:
                target = result.get('band_target')
                if result['scope'] != 'full' or target not in ('task1', 'task2') or result.get('response_complete') is not True:
                    raise ValueError('Band Writing hanya untuk respons task1/task2 lengkap; micro-task bukan band keseluruhan.')
                snapshot = ' '.join(str(material.get(k, '')) for k in ('title', 'question_type', 'id'))
                task_matches = set(re.findall(r'task[ _-]?([12])', snapshot.lower()))
                if len(task_matches) != 1 or target != 'task' + next(iter(task_matches)):
                    raise ValueError('Band target harus cocok dengan jenis task pada snapshot materi.')
                task_criterion = 'task_achievement' if target == 'task1' else 'task_response'
                needed = (task_criterion, 'coherence_cohesion', 'lexical_resource', 'grammatical_range_accuracy')
                if not all(criterion_present(criteria, key) for key in needed):
                    raise ValueError('Band Writing memerlukan empat kriteria IELTS yang sesuai task.')
                # Conservative AI evidence policy, not an IELTS scoring cutoff.
                # Underlength responses may still receive limited criterion feedback.
                minimum = 150 if target == 'task1' else 250
                text = response.get('text')
                words = len(text.split()) if nonempty(text) else result.get('response_word_count')
                if type(words) is not int or words < minimum:
                    raise ValueError('Sampel Writing belum memadai untuk band per task; beri feedback terbatas.')
        else:
            if result.get('input_type') not in ('audio', 'transcript'):
                raise ValueError('Jenis input Speaking harus diketahui: audio atau transcript.')
            reference = result.get('audio_reference')
            audio_files = [p for p in response.get('evidence', []) if Path(p).suffix.lower() in
                           ('.wav', '.mp3', '.m4a', '.aac', '.ogg', '.webm', '.mp4')]
            durable_audio = bool(reference in audio_files or (response.get('input_type') == 'audio' and
                                nonempty(response.get('audio_reference')) and response['audio_reference'] == reference))
            inspected_audio = (result['input_type'] == 'audio' and result.get('audio_inspected') is True and
                               nonempty(reference) and durable_audio)
            if criteria.get('pronunciation') is not None and not inspected_audio:
                raise ValueError('Pronunciation memerlukan audio yang diperiksa dan bukti/reference sumber tersimpan.')
            if band is not None:
                needed = ('fluency_coherence', 'lexical_resource', 'grammatical_range_accuracy', 'pronunciation')
                if result['scope'] != 'full' or not inspected_audio or result.get('speaking_parts') != [1, 2, 3] or not all(criterion_present(criteria, key) for key in needed):
                    raise ValueError('Band Speaking memerlukan audio memadai Parts 1–3 dan empat kriteria; sampel parsial hanya feedback.')


def finalize(root, sid, result):
    with mutation_lock(root):
        item = find_session(root, sid)
        # Legacy records remain readable/idempotent without applying v1.1 rules retroactively.
        if item['status'] == 'completed':
            if item['result'] != result:
                raise ValueError('Sesi sudah selesai dengan hasil berbeda. Catat koreksi beralasan, jangan menimpa.')
            _rebuild(root)
            return {'saved': False, 'already_completed': True, 'session': item}
        validate(root, item, result)
        response, rid = response_for_result(root, item, result)
        stored_result = copy.deepcopy(result)
        if rid:
            item['graded_response_revision_id'] = rid
        else:
            # Direct legacy-style completion still preserves a raw source response.
            item['source_response'] = copy.deepcopy(response)
        conditions = dict(item.get('conditions', {}))
        conditions.update(response.get('conditions', {}))
        conditions.update(result.get('conditions', {}))
        evidence = list(dict.fromkeys(item.get('evidence', []) + response.get('evidence', []) + result.get('evidence', [])))
        item.update(status='completed', phase='completed', completed_at=now(), result=stored_result,
                    conditions=conditions, evidence=evidence)
        json_write(session_path(root, sid), item)
        _rebuild(root)
        return {'saved': True, 'already_completed': False, 'session': item}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('start')
    p.add_argument('--task', required=True)
    p.add_argument('--skill', required=True, choices=SKILLS)
    p.add_argument('--kind', default='practice')
    p.add_argument('--minutes', type=int, default=20)
    p = sub.add_parser('checkpoint')
    p.add_argument('--id', required=True)
    p.add_argument('--input', type=Path, required=True, help='JSON respons/kondisi/provenance; input sementara di .local/.')
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
        elif args.command == 'checkpoint':
            output = checkpoint(root, args.id, json.loads(args.input.read_text(encoding='utf-8')))
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
