#!/usr/bin/env python3
"""Thin local coaching workflow. Python 3.8+, no third-party packages.

The coach chooses tasks and reviews evidence; this tool preserves state and
reports limits. It never plays audio, submits an attempt, or invents a grade.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import session
import sync as git_sync
import references
import adaptation
import lessons
import scorecard

CAPABILITIES = ('audio_playback', 'screenshot_capture', 'speaking_audio')
STATES = ('passed', 'failed', 'not_tested')
ROTATION = ('Listening', 'Reading', 'Speaking', 'Writing')
REHEARSAL = 'system-rehearsal'


def device_id(root):
    return hashlib.sha256((platform.node() + '|' + str(root.resolve())).encode()).hexdigest()[:16]


def read_json(path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def sync_action(root, action, message='Simpan IELTS Coach Tata'):
    try:
        with session.mutation_lock(root):
            result, code = git_sync.synchronize(root, action, message)
    except ValueError as error:
        busy = str(error).startswith('Pencatatan sedang digunakan chat lain')
        result, code = {'action': action, 'status': 'busy' if busy else 'error', 'remote_verified': False,
                        'error': 'session_busy' if busy else 'unsafe_session_lock',
                        'message': 'Pencatatan lain sedang berjalan; sync ditunda.' if busy else 'Lock pencatatan tidak aman; sync dihentikan.'}, 1
    except OSError:
        result, code = {'action': action, 'status': 'error', 'remote_verified': False,
                        'error': 'session_lock_io', 'message': 'Lock pencatatan tidak dapat diperiksa; data lokal tetap tersimpan.'}, 1
    git_sync.save_status(root, result)
    return dict(result, exit_code=code)


def local_sync(root):
    """Cached network results are historical, never proof of current remote."""
    cache = read_json(root / '.local' / 'sync.json', {})
    result = {'status': 'not_verified', 'remote_verified': False,
              'checked_at': None, 'last_network_check': cache,
              'message': 'Remote belum diperiksa pada operasi ini.'}
    try:
        git = git_sync.Git(root)
        git_sync.repository(git)
        result.update(git_sync.snapshot(git, remote_verified=False))
        if result['status'] == 'error':
            result['status'] = 'not_verified'
    except git_sync.SyncError as error:
        result.update(status=error.status, error=error.code, message=error.message)
    return result


def observe(root, value):
    if not isinstance(value, dict) or value.get('capability') not in CAPABILITIES or value.get('status') not in STATES:
        raise ValueError('Observation memerlukan capability dan status passed/failed/not_tested.')
    session.validate_provenance(value.get('provenance'))
    evidence = value.get('evidence', [])
    session.validate_evidence(root, evidence)
    if value['status'] == 'passed':
        suffixes = {Path(path).suffix.lower() for path in evidence}
        if value['capability'] == 'screenshot_capture' and not suffixes.intersection({'.png', '.jpg', '.jpeg', '.webp'}):
            raise ValueError('Screenshot lulus memerlukan gambar asli yang tersimpan dan diperiksa coach.')
        if value['capability'] == 'speaking_audio' and not suffixes.intersection({'.wav', '.mp3', '.m4a', '.ogg', '.aac', '.webm', '.mp4'}):
            raise ValueError('Speaking lulus memerlukan rekaman asli yang tersimpan dan diperiksa coach.')
        if value['capability'] == 'audio_playback':
            ref = Path(value['provenance']['reference'])
            if (ref.is_absolute() or '..' in ref.parts or not ref.parts or
                    ref.parts[0] not in ('materials', 'tests') or
                    ref.suffix.lower() not in ('.mp3', '.wav', '.m4a', '.ogg', '.aac', '.webm') or
                    file_check(root, str(ref))['status'] != 'passed'):
                raise ValueError('Playback lulus harus mengacu pada asset lokal yang dimainkan pengguna.')
    path = root / '.local' / 'readiness.json'
    store = read_json(path, {})
    if store.get('device_id') != device_id(root):
        store = {'device_id': device_id(root), 'root': str(root.resolve()), 'observations': {}}
    artifacts = list(evidence)
    if value['status'] == 'passed' and value['capability'] == 'audio_playback':
        artifacts.append(value['provenance']['reference'])
    item = dict(value, checked_at=session.now(), artifact_sha256={
        path: hashlib.sha256((root / path).read_bytes()).hexdigest() for path in artifacts})
    store['observations'][value['capability']] = item
    session.json_write(path, store)
    return item


def file_check(root, path, expected_sha=None):
    try:
        relative = Path(path)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Path asset harus relatif.')
        asset = root / relative
        if any(p.is_symlink() for p in (asset,) + tuple(asset.parents) if p != root and root in p.parents) or not asset.is_file():
            raise ValueError('Asset tidak tersedia atau symlink.')
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        if expected_sha and digest != expected_sha:
            raise ValueError('Checksum asset berubah.')
        return {'status': 'passed', 'checked_at': session.now(), 'path': path,
                'sha256': digest, 'method': 'local file read; checksum if declared'}
    except (OSError, ValueError, TypeError) as error:
        return {'status': 'failed', 'checked_at': session.now(), 'path': path, 'reason': str(error)}


def catalog(root):
    data = read_json(root / 'materials.json')
    if not isinstance(data, dict) or not isinstance(data.get('tasks'), list):
        raise ValueError('Katalog materi belum tersedia.')
    return data


def queue(root, records):
    data = catalog(root)
    completed = [s for s in records if s['status'] == 'completed' and s['kind'] != 'system_test']
    used = {s['task_id'] for s in completed}
    skill = ROTATION[(ROTATION.index(max(completed, key=lambda s: s['completed_at'])['skill']) + 1) % 4] if completed else 'Listening'
    available = [t for t in data['tasks'] if t.get('skill') == skill and
                 t.get('role') in ('primary', 'backup') and
                 t.get('freshness', {}).get('eligible_for_new_attempt', True) and t['id'] not in used]
    available.sort(key=lambda t: t.get('role') != 'primary')
    return {'skill': skill, 'next_task_id': available[0]['id'] if available else None,
            'backup_task_id': available[1]['id'] if len(available) > 1 else None,
            'needs_new_material': not bool(available),
            'basis': 'Rotasi sementara L–R–S–W; coach boleh menyesuaikan berdasarkan bukti.'}


def coaching_brief(root, records=None, skill=None, minutes=None):
    """Recommendations from traceable records, never a new grade or promise."""
    report = adaptation.analyze(root, records=records)
    hypotheses = report['recurring_hypotheses']
    if skill:
        hypotheses = [h for h in hypotheses if h.get('skill') == skill]
    lesson_state = lessons.current(root, official=records)
    prepared = lessons.prepared(root, report['preferences']['effective'])
    return {'rule_version': report['rule_version'],
            'input_session_ids': report['input_session_ids'],
            'input_feedback_ids': report['input_feedback_ids'],
            'input_resolution_ids': report['input_resolution_ids'],
            'input_experiment_ids': report['input_experiment_ids'],
            'input_review_ids': report['input_review_ids'],
            'preferences': report['preferences'], 'coverage': report['coverage'],
            'recurring_hypotheses': hypotheses[:2],
            'assessment_warnings': [
                {'session_id': sid, 'status': 'disputed_or_excluded',
                 'reason': report['exclusion_reasons'].get(sid),
                 'instruction': 'Skor lama tetap arsip, dikeluarkan dari analisis kemampuan hingga sumber diperiksa.'}
                for sid in report['excluded_assessment_ids']],
            'access_issues': report['access_issues'],
            'improvement_decisions': report['experiments'],
            'learning_readiness': report['readiness'], 'time_budget_minutes': minutes,
            'current_lesson': lesson_state.get('current_lesson'), 'prepared_queue': prepared,
            'waiting': lesson_state.get('waiting'),
            'next_action': lesson_state.get('next_action') or ('Prepare the primary Teacher lesson.' if prepared else 'Prepare an IELTS-led Teacher packet and one backup.'),
            'action': lesson_state.get('next_action') or 'Teach material and worked example before guided and independent practice; preserve evidence.'}


def task_checks(root, task):
    local = task.get('local', {})
    checks = {'prompt': file_check(root, local.get('prompt'), local.get('prompt_sha256'))}
    if task['skill'] == 'Listening':
        # Original acquisition checksum is retained independently of a playback report.
        provenance = read_json(root / 'materials' / 'PROVENANCE.json', {})
        audio_record = provenance.get('outputs', {}).get(task['id'] + '-audio', {})
        checks['audio_file'] = file_check(root, local.get('audio'), audio_record.get('sha256'))
        if (audio_record.get('file') != local.get('audio') or audio_record.get('url') != task.get('urls', {}).get('audio') or
                not isinstance(audio_record.get('sha256'), str) or len(audio_record['sha256']) != 64):
            checks['audio_file'].update(status='failed', reason='Provenance audio tidak cocok dengan asset/sumber tugas.')
    if task['skill'] in ('Listening', 'Reading'):
        checks['correction_cache'] = references.check_reference(root, task)
    return checks


def readiness(root, task=None, sync_result=None):
    checked = session.now()
    checks = {}
    probe = root / '.local' / 'readiness-probe.txt'
    try:
        session.atomic_write(probe, 'IELTS system read/write probe\n')
        probe.unlink()
        session.load_sessions(root)
        checks['storage'] = {'status': 'passed', 'checked_at': checked, 'method': 'write/readback + session envelope read'}
    except (ValueError, OSError) as error:
        checks['storage'] = {'status': 'failed', 'checked_at': checked, 'reason': str(error)}
    store = read_json(root / '.local' / 'readiness.json', {})
    observations = store.get('observations', {}) if store.get('device_id') == device_id(root) else {}
    for capability in CAPABILITIES:
        item = observations.get(capability, {'status': 'not_tested', 'checked_at': None})
        # A deleted original invalidates a previous successful observation.
        if item.get('status') == 'passed':
            try:
                session.validate_evidence(root, item.get('evidence', []))
                expected = set(item.get('evidence', []))
                if capability == 'audio_playback':
                    expected.add(item.get('provenance', {}).get('reference', ''))
                hashes = item.get('artifact_sha256')
                if not isinstance(hashes, dict) or not expected or not expected.issubset(hashes):
                    raise ValueError('Observation lama belum mempunyai checksum bukti; perlu diperiksa ulang.')
                for path, digest in hashes.items():
                    if file_check(root, path, digest)['status'] != 'passed':
                        raise ValueError('Asset/bukti berubah sejak observation; periksa ulang.')
                if capability == 'audio_playback':
                    ref = item.get('provenance', {}).get('reference', '')
                    if not ref or not (root / ref).is_file():
                        raise ValueError('Asset playback yang diperiksa sudah tidak tersedia.')
            except ValueError as error:
                item = dict(item, status='failed', reason=str(error))
        checks[capability] = item
    if task:
        checks.update(task_checks(root, task))
    sync_result = sync_result or local_sync(root)
    safe_switch = (sync_result.get('status') == 'synced' and sync_result.get('remote_verified') is True and
                   not sync_result.get('pending_files') and not sync_result.get('foreign_files') and
                   not sync_result.get('ahead') and not sync_result.get('behind'))
    listening = bool(task and task['skill'] == 'Listening' and all(
        checks[k]['status'] == 'passed' for k in
        ('storage', 'prompt', 'audio_file', 'correction_cache', 'audio_playback', 'screenshot_capture')) and
        checks['audio_playback'].get('provenance', {}).get('reference') == task.get('local', {}).get('audio'))
    return {'device_id': device_id(root), 'root': str(root.resolve()), 'checked_at': checked,
            'checks': checks, 'ready_local_listening': listening,
            'player_controls_verified': checks['audio_playback']['status'] == 'passed',
            'speaking_verified': checks['speaking_audio']['status'] == 'passed',
            'safe_switch_laptop': bool(safe_switch),
            'limits': 'Playback report applies only to its named asset; file integrity does not prove audibility. Speaking capability does not establish an IELTS band.'}


def prepare(root, task_id=None, minutes=None, kind='practice'):
    root = Path(root).resolve()
    if kind not in ('practice', 'pilot', 'system_test'):
        raise ValueError('Prepare kind harus practice/pilot/system_test.')
    sync_result = sync_action(root, 'pull')
    records = session.load_sessions(root)
    adaptation_report = adaptation.analyze(root, records=records)
    # Only structured, explicitly attributed learner preferences may adjust the
    # default. A caller's current time budget takes precedence.
    if minutes is None:
        minutes = (adaptation_report['preferences']['effective'].get('available_minutes', 20)
                   if kind != 'system_test' else 20)
    if type(minutes) is not int or minutes <= 0:
        raise ValueError('Durasi tersedia harus bilangan bulat positif.')
    active = [s for s in records if s['status'] == 'in_progress' and
              (s['kind'] == 'system_test') == (kind == 'system_test')]
    if len(active) > 1:
        raise ValueError('Ada beberapa sesi aktif; coach perlu rekonsiliasi.')
    if active:
        item = active[0]
        work = lessons.current(root, official=records)
        if work.get('waiting'):
            return dict(work, created=False, sync=sync_result)
        task = item.get('material')
        return {'created': False, 'resumed': True, 'session': item, 'sync': sync_result,
                'packet': references.learner_packet(task) if task else None,
                'readiness': readiness(root, task, sync_result), 'queue': queue(root, records),
                'coaching_brief': coaching_brief(root, records, item['skill'], minutes)}
    if kind != 'system_test':
        work = lessons.current(root, official=records)
        if work.get('waiting'):
            return dict(work, created=False, sync=sync_result)
        current_lesson = work.get('current_lesson')
        if current_lesson:
            record = lessons.find(root, current_lesson['id'])
            lp = lessons.packet_for(root, record)
            # A verified official attempt is created only at independent stage.
            if record['stage'] == 'independent' and lp.get('official_task_id'):
                if record.get('official_attempt_id') and session.find_session(root, record['official_attempt_id'])['status'] == 'completed':
                    return {'created': False, 'resumed': True, 'lesson': current_lesson, 'sync': sync_result,
                            'coaching_brief': coaching_brief(root, records, record['main_skill'], record['available_minutes'])}
                if task_id and task_id != lp['official_task_id']:
                    raise ValueError('Resume the lesson task; do not silently switch official tasks.')
                task_id = lp['official_task_id']
            else:
                return {'created': False, 'resumed': True, 'lesson': current_lesson, 'sync': sync_result,
                        'coaching_brief': coaching_brief(root, records, record['main_skill'], record['available_minutes'])}
        elif adaptation_report['preferences']['effective'].get('teaching_sequence') == 'teach_first':
            if sync_result.get('behind') or sync_result.get('conflicts') or sync_result.get('status') == 'conflict':
                return {'created': False, 'waiting': 'reconciliation', 'sync': sync_result}
            result = lessons.start(root, adaptation_report['preferences']['effective'], minutes=minutes)
            result.update(sync=sync_result, coaching_brief=coaching_brief(root, records))
            return result
    if sync_result.get('behind') or sync_result.get('conflicts') or sync_result.get('status') == 'conflict':
        return {'created': False, 'waiting': 'reconciliation', 'sync': sync_result}
    if kind == 'system_test':
        if task_id not in (None, REHEARSAL):
            raise ValueError('Wrapper system_test hanya memakai fixture rehearsal; jangan membuka soal baru Tata.')
        created = session.start(root, REHEARSAL, 'Listening', kind, minutes)
        return dict(created, sync=sync_result, packet={
            'id': REHEARSAL, 'title': 'Tes sistem — suara sintetis dan respons contoh',
            'local': {'audio': 'tests/fixtures/rehearsal-tone.wav', 'prompt': 'tests/fixtures/rehearsal.html'},
            'instruction': 'Bukan latihan IELTS. Pengguna menekan Play sendiri.'})
    planned = queue(root, records)
    task_id = task_id or planned['next_task_id']
    task = next((t for t in catalog(root)['tasks'] if t['id'] == task_id), None)
    if not task or task.get('role') not in ('primary', 'backup'):
        raise ValueError('Tugas baru belum siap atau hanya arsip; coach perlu memilih materi terverifikasi.')
    checks = task_checks(root, task)
    if any(c['status'] != 'passed' for c in checks.values()):
        return {'created': False, 'waiting': 'materials', 'checks': checks, 'sync': sync_result,
                'backup_task_id': planned['backup_task_id']}
    created = session.start(root, task['id'], task['skill'], kind, minutes)
    if kind != 'system_test' and work.get('current_lesson'):
        lessons.link(root, work['current_lesson']['id'], created['session']['id'])
    # Starting a session modifies tracked files after pull; it is no longer clean.
    current_sync = local_sync(root)
    packet = references.learner_packet(task)
    packet['minutes'] = minutes
    return dict(created, sync=sync_result, packet=packet,
                readiness=readiness(root, task, current_sync), queue=planned,
                coaching_brief=coaching_brief(root, skill=task['skill'], minutes=minutes))


def feedback(root, payload):
    root = Path(root).resolve()
    outcome = adaptation.record_feedback(root, payload)
    outcome['saved'] = True  # A duplicate event has already been read back.
    outcome['coaching_brief'] = coaching_brief(root)
    sync_result = sync_action(root, 'push', 'Simpan feedback IELTS ' + outcome['record']['id'])
    outcome.update(sync=sync_result, synced=sync_result.get('status') == 'synced' and
                   sync_result.get('remote_verified') is True)
    return outcome


def checkpoint(root, sid, payload):
    root = Path(root).resolve()
    if not isinstance(payload, dict):
        raise ValueError('Checkpoint harus berupa objek JSON.')
    try:
        result = session.checkpoint(root, sid, payload)
    except (OSError, ValueError):
        item = session.find_session(root, sid)
        normalized = dict(payload, purpose=payload.get('purpose', 'attempt'))
        revision = next((r for r in item.get('response_revisions', []) if r['payload'] == normalized), None)
        if revision is None:
            raise
        return {'saved': True, 'synced': False, 'summaries_saved': False, 'session': item,
                'revision_id': revision['revision_id'], 'message': 'Respons tersimpan; retry checkpoint untuk memulihkan ringkasan dan sinkronisasi.'}
    result['saved'] = True  # Identical retry is already durably stored.
    sync_result = sync_action(root, 'push', 'Simpan respons IELTS ' + sid)
    result['sync'] = sync_result
    result['synced'] = sync_result.get('status') == 'synced' and sync_result.get('remote_verified') is True
    return result


def complete(root, sid, result=None):
    root = Path(root).resolve()
    if result is not None and not isinstance(result, dict):
        raise ValueError('Hasil harus berupa objek JSON.')
    item = session.find_session(root, sid)
    already = item['status'] == 'completed'
    if already:
        if result is not None and result != item['result']:
            raise ValueError('Sesi selesai dengan hasil berbeda; jangan menimpa atau menilai ulang.')
        outcome = {'saved': True, 'already_completed': True, 'session': item}
    else:
        if result is not None:
            direct = result.get('source_response')
            if direct is None and result.get('provenance'):
                direct = {k: result[k] for k in ('score', 'evidence', 'provenance') if k in result}
                direct['text'] = result.get('sample_text', '')
            if direct is not None and not isinstance(direct, dict):
                raise ValueError('source_response harus berupa objek JSON.')
            if direct is not None and session.has_input(direct):
                # Direct API callers get the same preserve-before-grade behavior
                # as chat checkpoint callers, even if the assessment is rejected.
                session.validate_payload(root, direct)
                if direct.get('purpose', 'attempt') != 'attempt':
                    raise ValueError('Input penilaian harus respons attempt asli.')
                try:
                    session.checkpoint(root, sid, direct)
                except (OSError, ValueError):
                    persisted = session.find_session(root, sid)
                    normalized = dict(direct, purpose=direct.get('purpose', 'attempt'))
                    if not any(r['payload'] == normalized for r in persisted.get('response_revisions', [])):
                        raise
                    return {'saved': False, 'response_saved': True, 'summaries_saved': False,
                            'synced': False, 'waiting': 'summary_recovery', 'session': persisted,
                            'message': 'Respons tersimpan sebelum penilaian; ulangi complete dengan result setelah ringkasan pulih.'}
                item = session.find_session(root, sid)
        if result is None:
            waiting = session.checkpoint(root, sid, {'phase': 'awaiting_evidence'})
            return {'saved': False, 'waiting': 'evidence', 'session': waiting['session'],
                    'message': 'Respons/skor dengan asalnya diperlukan; sesi tetap aktif.'}
        if result.get('mode') == 'unverified':
            waiting = session.checkpoint(root, sid, {'phase': 'awaiting_review'})
            return {'saved': False, 'waiting': 'review', 'session': waiting['session'],
                    'message': 'Input tersimpan belum terverifikasi; attempt menunggu review.'}
        task = item.get('material')
        if result.get('mode') == 'answers_key' and task:
            ref_check = references.check_reference(root, task)
            if ref_check['status'] != 'passed':
                waiting = session.checkpoint(root, sid, {'phase': 'awaiting_review'})
                return {'saved': False, 'waiting': 'correction_cache', 'session': waiting['session'], 'check': ref_check}
        try:
            outcome = session.finalize(root, sid, result)
        except (ValueError, OSError) as error:
            persisted = session.find_session(root, sid)
            if persisted['status'] == 'completed':
                return {'saved': True, 'summaries_saved': False, 'synced': False,
                        'session': persisted, 'message': 'Hasil tersimpan; ringkasan belum pulih. Retry complete tanpa result; jangan menilai ulang.'}
            waiting = session.checkpoint(root, sid, {'phase': 'awaiting_evidence'})
            return {'saved': False, 'waiting': 'evidence_or_review', 'session': waiting['session'], 'message': str(error)}
        outcome['saved'] = True  # Read-back validated; repeated done remains durably saved.
    # A completed record may survive an interrupted summary write. Recover it
    # without repeating assessment; never publish stale derived summaries.
    try:
        session.rebuild(root)
    except (ValueError, OSError):
        return dict(outcome, summaries_saved=False, synced=False,
                    message='Hasil tersimpan; ringkasan belum pulih. Retry complete tanpa result.')
    outcome['scorecard_update'] = scorecard.safely_refresh(root)
    sync_result = sync_action(root, 'push', 'Simpan sesi IELTS ' + sid)
    outcome.update(summaries_saved=True, sync=sync_result, synced=sync_result.get('status') == 'synced' and
                   sync_result.get('remote_verified') is True, retry_sync_only=already,
                   queue=queue(root, session.load_sessions(root)), coaching_brief=coaching_brief(root))
    return outcome


def status(root, observation=None, verify_sync=False):
    root = Path(root).resolve()
    if observation is not None:
        observe(root, observation)
    records = session.load_sessions(root)
    planned = queue(root, records)
    active = [s for s in records if s['status'] == 'in_progress' and s['kind'] != 'system_test']
    next_task = next((t for t in catalog(root)['tasks'] if t['id'] == planned['next_task_id']), None)
    task = active[0].get('material') if active else next_task
    report = scorecard.safely_refresh(root)
    sync_result = sync_action(root, 'status') if verify_sync else local_sync(root)
    return {'active': active, 'system_tests': [s for s in records if s['kind'] == 'system_test'],
            'completed_learning_count': sum(s['status'] == 'completed' and s['kind'] != 'system_test' for s in records),
            'queue': planned, 'sync': sync_result, 'readiness': readiness(root, task, sync_result),
            'coaching_brief': coaching_brief(root, records, task.get('skill') if task else None),
            'scorecard_update': report}


def lesson(root, action, lid=None, payload=None, minutes=None, defer_sync=False):
    """Teacher packet/lesson API. Returned lesson views exclude coach-only answers."""
    root = Path(root).resolve()
    preferences = adaptation.analyze(root)['preferences']['effective']
    if action == 'inspect':
        return {'lesson': lessons.summary(root, lessons.find(root, lid)) if lid else lessons.current(root),
                'coaching_brief': coaching_brief(root)}
    if action == 'teacher-brief':
        payload = payload or {}
        return lessons.teacher_brief(root, preferences, payload.get('main_skill'),
                                     payload.get('ielts_task_type'), payload.get('objective'))
    payload = payload or {}
    if action == 'packet':
        result = lessons.store_packet(root, payload)
    elif action == 'retire-packet':
        result = lessons.retire(root, lid, payload)
    elif action == 'prepare':
        pulled = sync_action(root, 'pull')
        preferences = adaptation.analyze(root)['preferences']['effective']
        work = lessons.current(root)
        if (pulled.get('behind') or pulled.get('conflicts') or pulled.get('status') == 'conflict') and not work.get('current_lesson'):
            return {'waiting': 'reconciliation', 'sync': pulled}
        result = lessons.start(root, preferences, packet_id=payload.get('packet_id'), minutes=minutes)
        result['sync'] = pulled
    elif action == 'migrate':
        result = lessons.start(root, preferences, packet_id=payload['packet_id'], migration=payload)
    elif action == 'checkpoint':
        result = lessons.checkpoint(root, lid, payload)
    elif action == 'present':
        record = lessons.find(root, lid)
        packet = lessons.packet_for(root, record)
        if packet.get('official_task_id'):
            task = next(t for t in catalog(root)['tasks'] if t['id'] == packet['official_task_id'])
            checks = task_checks(root, task)
            if any(c['status'] != 'passed' for c in checks.values()):
                return {'waiting': 'materials', 'checks': checks}
            if record['stage'] == 'independent' and not record.get('official_attempt_id'):
                created = session.start(root, task['id'], task['skill'], 'practice',
                                        record['available_minutes'] or preferences.get('available_minutes', 40))
                lessons.link(root, lid, created['session']['id'])
        result = lessons.present(root, lid, payload)
    elif action == 'review':
        result = lessons.review(root, lid, payload)
    elif action in ('advance', 'complete'):
        if action == 'complete':
            payload = dict(payload, stage='completed')
        result = lessons.advance(root, lid, payload)
    else:
        raise ValueError('Unknown lesson operation.')
    result['coaching_brief'] = coaching_brief(root)
    if result.get('waiting'):
        return result
    if action in ('complete', 'advance') and result.get('lesson', {}).get('status') == 'completed':
        result['scorecard_update'] = scorecard.safely_refresh(root)
    if defer_sync:
        result.update(synced=False, sync_pending=True)
    else:
        sync_result = sync_action(root, 'push', 'Simpan teaching lesson ' + (lid or result.get('packet_id', '')))
        result.update(sync=sync_result, synced=sync_result.get('status') == 'synced' and sync_result.get('remote_verified') is True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--task')
    p.add_argument('--minutes', type=int, help='Waktu saat ini; mengalahkan preferensi, default 20 menit jika belum ada preferensi pelajar.')
    p.add_argument('--kind', choices=('practice', 'pilot', 'system_test'), default='practice')
    p = commands.add_parser('checkpoint')
    p.add_argument('--id', required=True)
    p.add_argument('--input', type=Path, required=True)
    p = commands.add_parser('complete')
    p.add_argument('--id', required=True)
    p.add_argument('--result', type=Path)
    p = commands.add_parser('status')
    p.add_argument('--observe', type=Path)
    p.add_argument('--verify-sync', action='store_true')
    p = commands.add_parser('feedback')
    p.add_argument('--input', type=Path, required=True)
    commands.add_parser('scorecard', help='Save a local derived evidence report; never grade or estimate response latency.')
    p = commands.add_parser('lesson')
    p.add_argument('action', choices=('teacher-brief', 'packet', 'retire-packet', 'prepare', 'migrate', 'inspect',
                                      'present', 'checkpoint', 'review', 'advance', 'complete'))
    p.add_argument('--id')
    p.add_argument('--input', type=Path)
    p.add_argument('--minutes', type=int)
    p.add_argument('--defer-sync', action='store_true', help='Local checkpoint/readback first; sync at the same lesson milestone.')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            output = prepare(args.root, args.task, args.minutes, args.kind)
        elif args.command == 'checkpoint':
            output = checkpoint(args.root, args.id, read_json(args.input))
        elif args.command == 'complete':
            output = complete(args.root, args.id, read_json(args.result) if args.result else None)
        elif args.command == 'feedback':
            output = feedback(args.root, read_json(args.input))
        elif args.command == 'scorecard':
            output = scorecard.refresh(args.root)
        elif args.command == 'lesson':
            output = lesson(args.root, args.action, args.id, read_json(args.input) if args.input else None,
                            args.minutes, args.defer_sync)
        else:
            output = status(args.root, read_json(args.observe) if args.observe else None, args.verify_sync)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1 if output.get('waiting') else 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == '__main__':
    sys.exit(main())
