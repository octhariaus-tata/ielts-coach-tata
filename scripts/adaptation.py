#!/usr/bin/env python3
"""Evidence-scoped coaching adaptation. Python 3.8+, standard library only.

Events preserve feedback and coach decisions. Analysis produces hypotheses and
review prompts; it never rewrites scores, targets, keys, prompts or policy.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import session

RULE_VERSION = 'adaptation-1.3'
CATEGORIES = ('preference', 'access', 'difficulty', 'scoring_dispute')
METRICS = ('response_capture', 'completion', 'transfer_accuracy', 'feedback_usefulness')
ROTATION = ('Listening', 'Reading', 'Speaking', 'Writing')


def stamp():
    return dt.datetime.now(session.JAKARTA).isoformat(timespec='microseconds')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise ValueError('Event ID harus identifier relatif yang aman (1–128 karakter).')
    return value


def fields(payload, allowed, required):
    if not isinstance(payload, dict) or set(payload) - set(allowed):
        raise ValueError('Payload bukan objek atau memuat field di luar lingkup feedback/workflow.')
    if any(key not in payload for key in required):
        raise ValueError('Field wajib belum tersedia: ' + ', '.join(required))


def text(value, label):
    if not session.nonempty(value):
        raise ValueError(label + ' harus berupa teks yang tersedia.')
    return value


def stream(value):
    if value not in ('learner', 'system_test'):
        raise ValueError('Kind harus learner atau system_test.')
    return value


def records_for(root, supplied=None):
    current = session.load_sessions(root)
    if supplied is None:
        return current
    if not isinstance(supplied, list):
        raise ValueError('Records harus berupa daftar record sesi yang tersimpan.')
    live = {r['id']: r for r in current}
    seen = set()
    for record in supplied:
        if (not isinstance(record, dict) or record.get('id') in seen or
                record.get('id') not in live or record != live[record['id']]):
            raise ValueError('Input sesi tidak tersedia, duplikat, atau sudah tertinggal; baca ulang record tersimpan.')
        seen.add(record['id'])
    return supplied


def cite_sessions(root, ids, kind):
    if not isinstance(ids, list) or any(not isinstance(s, str) for s in ids) or len(ids) != len(set(ids)):
        raise ValueError('Citation sesi harus daftar ID unik.')
    known = {r['id']: r for r in records_for(root)}
    cited = []
    for sid in ids:
        identifier(sid)
        if sid not in known:
            raise ValueError('Sesi citation tidak tersedia: ' + sid)
        record = known[sid]
        if (record['kind'] == 'system_test') != (kind == 'system_test'):
            raise ValueError('Citation learner dan tes sistem harus terpisah.')
        cited.append(record)
    return cited


def event_path(root, directory, eid):
    path = root / directory / (identifier(eid) + '.json')
    for parent in (path,) + tuple(path.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError('Event tidak boleh tersimpan melalui symlink.')
    return path


def existing_event(root, directory, eid, payload):
    path = event_path(root, directory, eid)
    if not path.exists():
        return None
    old = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(old, dict) or old.get('schema_version') != 1 or old.get('id') != eid or old.get('payload') != payload or
            old.get('payload_sha256', digest(payload)) != digest(payload)):
        raise ValueError('Event ID sudah digunakan dengan isi berbeda; riwayat tidak ditimpa.')
    return {'saved': False, 'duplicate': True, 'record': old}


def save_event(root, directory, eid, payload, **metadata):
    duplicate = existing_event(root, directory, eid, payload)
    if duplicate:
        return duplicate
    path = event_path(root, directory, eid)
    record = dict(schema_version=1, id=eid, created_at=stamp(), payload=copy.deepcopy(payload),
                  payload_sha256=digest(payload), **metadata)
    session.json_write(path, record)
    return {'saved': True, 'duplicate': False, 'record': record}


def events(root, directory):
    result = []
    for path in sorted((root / directory).glob('*.json')):
        value = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(value, dict) or value.get('schema_version') != 1 or
                event_path(root, directory, value.get('id')) != path or
                not isinstance(value.get('payload'), dict) or not session.nonempty(value.get('created_at'))):
            raise ValueError('Event tersimpan tidak valid: ' + path.name)
        payload = value['payload']
        if directory == 'feedback':
            normalized = normalize_feedback(payload)
            cite_sessions(root, [normalized['session_id']] if normalized.get('session_id') else [], normalized['kind'])
        elif directory == 'feedback/resolutions':
            identifier(value.get('feedback_id'))
            normalized = normalize_resolution(root, value['feedback_id'], payload, check_files=False)
            source = next((r for r in events(root, 'feedback') if r['id'] == value['feedback_id']), None)
            if source is None or source['payload']['category'] != 'scoring_dispute' or value.get('kind') != source['payload']['kind']:
                raise ValueError('Resolution tidak cocok dengan feedback asal.')
        elif directory == 'learning/experiments':
            normalized = normalize_experiment(root, payload, check_files=False)
            cite_sessions(root, normalized['baseline_session_ids'], normalized['kind'])
        elif directory == 'learning/reviews':
            identifier(value.get('experiment_id'))
            normalized = normalize_review(root, value['experiment_id'], payload, check_files=False)
            experiment = next((r for r in events(root, 'learning/experiments') if r['id'] == value['experiment_id']), None)
            if experiment is None or value.get('kind') != experiment['payload']['kind']:
                raise ValueError('Review tidak cocok dengan experiment asal.')
            cite_sessions(root, payload['session_ids'], value['kind'])
        else:
            raise ValueError('Direktori event tidak didukung.')
        if (normalized != payload or value['id'] != payload['event_id'] or
                value.get('payload_sha256', digest(payload)) != digest(payload)):
            raise ValueError('Payload event tersimpan tidak kanonik: ' + path.name)
        result.append(value)
    return sorted(result, key=lambda r: (r['created_at'], r['id']))


def normalize_feedback(payload):
    fields(payload, ('event_id', 'kind', 'actor', 'text', 'category', 'session_id', 'lesson_id', 'scope', 'signals', 'provenance'),
           ('event_id', 'text', 'category', 'provenance'))
    value = copy.deepcopy(payload)
    eid = identifier(value['event_id'])
    value['kind'] = stream(value.get('kind', 'learner'))
    value.setdefault('actor', 'unspecified')
    if value['actor'] not in ('learner', 'owner', 'unspecified') or value['category'] not in CATEGORIES:
        raise ValueError('Actor atau kategori feedback tidak valid.')
    text(value['text'], 'Feedback')
    session.validate_provenance(value['provenance'])
    sid = value.get('session_id')
    value.setdefault('scope', 'session' if sid else 'global')
    if value['scope'] not in ('global', 'session', 'lesson') or (value['scope'] == 'session' and not sid):
        raise ValueError('Feedback sesi memerlukan session_id.')
    if value['scope'] == 'lesson':
        identifier(value.get('lesson_id'))
    elif value.get('lesson_id'):
        raise ValueError('lesson_id requires lesson scope.')
    if value['category'] == 'scoring_dispute' and (not sid or value['scope'] != 'session'):
        raise ValueError('Scoring dispute harus menunjuk session_id dengan scope session; feedback umum tetap kategori preference.')
    signals = value.setdefault('signals', {})
    if not isinstance(signals, dict) or set(signals) - {'preferred_feedback_style', 'available_minutes', 'difficulty',
            'lesson_language', 'teaching_sequence', 'practice_volume', 'completion_mode', 'short_drill_items'}:
        raise ValueError('Signals hanya boleh memuat preferensi yang eksplisit.')
    for key, allowed in {'lesson_language': ('en', 'id'), 'teaching_sequence': ('teach_first',),
                         'practice_volume': ('adaptive',), 'completion_mode': ('natural', 'explicit_done')}.items():
        if key in signals and signals[key] not in allowed:
            raise ValueError('Invalid explicit teaching preference: ' + key)
    if 'short_drill_items' in signals and signals['short_drill_items'] != [20, 30]:
        raise ValueError('Short drill prepared range is [20, 30], not a universal task size.')
    if 'preferred_feedback_style' in signals and signals['preferred_feedback_style'] not in ('concise', 'detailed'):
        raise ValueError('Gaya feedback harus concise atau detailed.')
    if 'available_minutes' in signals and (type(signals['available_minutes']) is not int or not 1 <= signals['available_minutes'] <= 180):
        raise ValueError('Waktu tersedia harus 1–180 menit; bukan durasi aktual.')
    if 'difficulty' in signals and signals['difficulty'] not in ('too_easy', 'too_hard', 'appropriate'):
        raise ValueError('Kesulitan subjektif tidak valid.')
    return value


def record_feedback(root, payload):
    root = Path(root).resolve()
    value = normalize_feedback(payload)
    eid = value['event_id']
    sid = value.get('session_id')
    with session.mutation_lock(root):
        if value['scope'] == 'lesson':
            import lessons
            lesson = lessons.find(root, value['lesson_id'])
            if lesson['kind'] != value['kind']:
                raise ValueError('Learner/system-test lesson scopes must remain separate.')
        duplicate = existing_event(root, 'feedback', eid, value)
        if duplicate:
            return duplicate
        cited = cite_sessions(root, [sid] if sid else [], value['kind'])
        return save_event(root, 'feedback', eid, value,
                          session_snapshots={r['id']: digest(r) for r in cited}, rule_version=RULE_VERSION)


def normalize_resolution(root, feedback_id, payload, check_files=True):
    fields(payload, ('event_id', 'resolution', 'rationale', 'provenance', 'evidence'),
           ('resolution', 'rationale', 'provenance'))
    value = copy.deepcopy(payload)
    text(value['rationale'], 'Alasan review')
    session.validate_provenance(value['provenance'])
    if value['resolution'] not in ('confirmed_original', 'correction_required'):
        raise ValueError('Resolution harus confirmed_original atau correction_required.')
    identifier(feedback_id)
    value.setdefault('evidence', [])
    session.validate_evidence(root, value['evidence'], check_files=check_files)
    value.setdefault('event_id', 'resolution-' + digest(dict(feedback_id=feedback_id, payload=value))[:24])
    eid = identifier(value['event_id'])
    return value


def resolve_feedback(root, feedback_id, payload):
    root = Path(root).resolve()
    value = normalize_resolution(root, feedback_id, payload)
    eid = value['event_id']
    with session.mutation_lock(root):
        duplicate = existing_event(root, 'feedback/resolutions', eid, value)
        if duplicate:
            if duplicate['record'].get('feedback_id') != feedback_id:
                raise ValueError('Resolution ID sudah terkait feedback lain.')
            return duplicate
        feedback = next((e for e in events(root, 'feedback') if e['id'] == feedback_id), None)
        if feedback is None or feedback['payload']['category'] != 'scoring_dispute':
            raise ValueError('Resolution memerlukan event scoring_dispute yang tersedia.')
        original = feedback['payload']
        cited = cite_sessions(root, [original['session_id']] if original.get('session_id') else [], original['kind'])
        source_hash = result_hash = None
        pinned = list(value['evidence'])
        if value['resolution'] == 'confirmed_original':
            if cited:
                record = cited[0]
                if record['status'] != 'completed':
                    raise ValueError('Hasil asli belum selesai; belum dapat dikonfirmasi.')
                session.validate(root, record, record['result'])
                source, _ = session.response_for_result(root, record, record['result'])
                source_hash, result_hash = digest(source), digest(record['result'])
                pinned += source.get('evidence', []) + record['result'].get('evidence', [])
                session.validate_evidence(root, pinned)
            elif not value['evidence']:
                raise ValueError('Resolution global memerlukan bukti review yang tersimpan.')
        return save_event(root, 'feedback/resolutions', eid, value, feedback_id=feedback_id,
                          kind=original['kind'], original_source_sha256=source_hash,
                          original_result_sha256=result_hash,
                          evidence_sha256={p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in pinned},
                          rule_version=RULE_VERSION)


def quarantine(root, feedback, resolutions, records):
    known = {r['id']: r for r in records}
    open_disputes, reasons = [], {}
    latest = {r['feedback_id']: r for r in resolutions}
    for event in feedback:
        value = event['payload']
        if value['kind'] != 'learner' or value['category'] != 'scoring_dispute':
            continue
        resolution = latest.get(event['id'])
        state = 'unresolved'
        if resolution:
            state = resolution['payload']['resolution']
            if state == 'confirmed_original':
                try:
                    session.validate_evidence(root, resolution['payload'].get('evidence', []))
                    for path, expected in resolution.get('evidence_sha256', {}).items():
                        if hashlib.sha256((root / path).read_bytes()).hexdigest() != expected:
                            raise ValueError('Bukti resolution berubah.')
                    if value.get('session_id'):
                        record = known.get(value['session_id'])
                        if record is None or digest(record.get('result')) != resolution['original_result_sha256']:
                            raise ValueError('Hasil yang direview berubah.')
                        source, _ = session.response_for_result(root, record, record['result'])
                        required = set(source.get('evidence', []) + record['result'].get('evidence', []))
                        if not required.issubset(resolution.get('evidence_sha256', {})):
                            raise ValueError('Pin original source bytes belum lengkap.')
                        if digest(source) != resolution['original_source_sha256']:
                            raise ValueError('Sumber hasil yang direview berubah.')
                except (ValueError, OSError, KeyError, TypeError):
                    state = 'stale_resolution'
        if state != 'confirmed_original':
            item = {'feedback_id': event['id'], 'session_id': value.get('session_id'), 'state': state,
                    'text': value['text'], 'provenance': value['provenance']}
            open_disputes.append(item)
            if value.get('session_id'):
                reasons.setdefault(value['session_id'], []).append('scoring_dispute:' + state)
    return open_disputes, reasons


def assessment_reason(root, record, quarantined):
    if record['id'] in quarantined:
        return 'scoring_dispute'
    if record['status'] != 'completed' or record['kind'] in ('retake', 'system_test'):
        return 'not_new_completed_learner_assessment'
    conditions = record.get('conditions', {})
    plays = conditions.get('audio_plays')
    if plays is not None and (type(plays) is not int or plays < 1):
        return 'invalid_audio_condition'
    if (conditions.get('assisted') is True or conditions.get('transcript_seen') is True or
            conditions.get('hints_used') is True or conditions.get('key_seen_before') is True or
            record['skill'] == 'Listening' and type(plays) is int and plays > 1):
        return 'known_assisted_or_key_exposed'
    if conditions.get('key_seen_before') is not False or record['skill'] == 'Listening' and (type(plays) is not int or plays != 1):
        return 'freshness_conditions_unverified'
    try:
        session.validate(root, record, record['result'])
    except (ValueError, OSError, KeyError, TypeError):
        return 'insufficient_validated_source'
    return None


def comparison_key(record):
    conditions = record.get('conditions', {})
    if type(conditions.get('timed')) is not bool or conditions.get('key_seen_before') is not False:
        return None
    plays = conditions.get('audio_plays') if record['skill'] == 'Listening' else None
    if record['skill'] == 'Listening' and (type(plays) is not int or plays != 1):
        return None
    question_type = (record.get('material') or {}).get('question_type')
    if not session.nonempty(question_type):
        return None
    return (record['skill'], question_type, record['result'].get('scope'), conditions['timed'], False, plays)


def source_evidence_hashes(root, records):
    """Pin available original source bytes; None records unavailable bytes honestly."""
    hashes = {}
    for record in records:
        result = record.get('result') or {}
        try:
            source, _ = session.response_for_result(root, record, result)
        except (ValueError, OSError, KeyError, TypeError):
            rid = record.get('graded_response_revision_id') or result.get('response_revision_id')
            source = next((r['payload'] for r in record.get('response_revisions', []) if r['revision_id'] == rid), None)
            source = source or record.get('source_response') or result.get('source_response') or {}
        paths = (source.get('evidence', []) if isinstance(source, dict) else []) + result.get('evidence', [])
        session.validate_evidence(root, paths, check_files=False)
        for path in paths:
            artifact = root / path
            hashes[path] = hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact.is_file() else None
    return hashes


def source_hashes_current(root, hashes):
    try:
        if not isinstance(hashes, dict) or any(not isinstance(h, str) or not re.fullmatch(r'[a-f0-9]{64}', h) for h in hashes.values()):
            return False
        session.validate_evidence(root, list(hashes))
        return all(hashlib.sha256((root / path).read_bytes()).hexdigest() == expected for path, expected in hashes.items())
    except (ValueError, OSError, TypeError):
        return False


def source_pins_current(root, records, pins):
    required = source_evidence_hashes(root, records)
    return isinstance(pins, dict) and set(required).issubset(pins) and source_hashes_current(root, pins)


def normalize_experiment(root, payload, check_files=True):
    fields(payload, ('event_id', 'kind', 'hypothesis', 'proposed_change', 'change_scope', 'metric',
                     'baseline_session_ids', 'evidence', 'provenance'),
           ('event_id', 'hypothesis', 'proposed_change', 'metric', 'provenance'))
    value = copy.deepcopy(payload)
    eid = identifier(value['event_id'])
    value['kind'] = stream(value.get('kind', 'learner'))
    value.setdefault('change_scope', 'workflow')
    value.setdefault('baseline_session_ids', [])
    value.setdefault('evidence', [])
    if value['change_scope'] not in ('workflow', 'presentation') or value['metric'] not in METRICS:
        raise ValueError('Experiment hanya boleh mengusulkan presentasi/workflow dan metric yang dikenal.')
    text(value['hypothesis'], 'Hipotesis')
    text(value['proposed_change'], 'Usulan perubahan')
    session.validate_provenance(value['provenance'])
    session.validate_evidence(root, value['evidence'], check_files=check_files)
    return value


def record_experiment(root, payload):
    root = Path(root).resolve()
    value = normalize_experiment(root, payload)
    eid = value['event_id']
    with session.mutation_lock(root):
        duplicate = existing_event(root, 'learning/experiments', eid, value)
        if duplicate:
            return duplicate
        cited = cite_sessions(root, value['baseline_session_ids'], value['kind'])
        return save_event(root, 'learning/experiments', eid, value, status='pending',
                          baseline_available=bool(cited or value['evidence']),
                          session_snapshots={r['id']: digest(r) for r in cited},
                          source_evidence_sha256=source_evidence_hashes(root, cited), rule_version=RULE_VERSION)


def normalize_review(root, experiment_id, payload, check_files=True):
    fields(payload, ('event_id', 'decision', 'rationale', 'session_ids', 'provenance', 'evidence'),
           ('decision', 'rationale', 'session_ids', 'provenance'))
    value = copy.deepcopy(payload)
    text(value['rationale'], 'Alasan keputusan')
    session.validate_provenance(value['provenance'])
    if value['decision'] not in ('adopted', 'rejected', 'inconclusive'):
        raise ValueError('Keputusan review tidak valid.')
    value.setdefault('evidence', [])
    session.validate_evidence(root, value['evidence'], check_files=check_files)
    value.setdefault('event_id', 'review-' + digest(dict(experiment_id=experiment_id, payload=value))[:24])
    eid = identifier(value['event_id'])
    return value


def review_experiment(root, experiment_id, payload):
    root = Path(root).resolve()
    value = normalize_review(root, experiment_id, payload)
    eid = value['event_id']
    with session.mutation_lock(root):
        duplicate = existing_event(root, 'learning/reviews', eid, value)
        if duplicate:
            if duplicate['record'].get('experiment_id') != experiment_id:
                raise ValueError('Review ID sudah terkait experiment lain.')
            return duplicate
        experiment = next((e for e in events(root, 'learning/experiments') if e['id'] == identifier(experiment_id)), None)
        if experiment is None:
            raise ValueError('Experiment tidak tersedia.')
        kind = experiment['payload']['kind']
        cited = cite_sessions(root, value['session_ids'], kind)
        baseline = cite_sessions(root, experiment['payload']['baseline_session_ids'], kind)
        if value['decision'] == 'adopted':
            if not cited:
                raise ValueError('Adopsi memerlukan citation hasil yang tersedia.')
            if kind == 'learner':
                feedback, resolutions = events(root, 'feedback'), events(root, 'feedback/resolutions')
                _, disputed = quarantine(root, feedback, resolutions, records_for(root))
                if (any(experiment.get('session_snapshots', {}).get(r['id']) != digest(r) for r in baseline) or
                        not source_pins_current(root, baseline, experiment.get('source_evidence_sha256', {}))):
                    raise ValueError('Baseline berubah atau sumber bytes belum tersedia sejak proposal; buat proposal review baru.')
                if len({r['task_id'] for r in cited}) < 2 or not baseline:
                    raise ValueError('Adopsi learner memerlukan baseline dan dua tugas baru yang independen.')
                if any(assessment_reason(root, r, disputed) for r in baseline + cited):
                    raise ValueError('Bukti disputed, assisted, retake atau belum terverifikasi tidak boleh mendukung adopsi.')
                if {r['task_id'] for r in baseline}.intersection(r['task_id'] for r in cited):
                    raise ValueError('Outcome harus soal baru, bukan retake baseline.')
                keys = {comparison_key(r) for r in baseline + cited}
                if None in keys or len(keys) != 1:
                    raise ValueError('Bukti experiment belum sebanding menurut skill, jenis soal dan kondisi tercatat.')
        return save_event(root, 'learning/reviews', eid, value, experiment_id=experiment_id, kind=kind,
                          session_snapshots={r['id']: digest(r) for r in cited},
                          source_evidence_sha256=source_evidence_hashes(root, cited), rule_version=RULE_VERSION,
                          causal_claim=False, automatic_policy_change=False)


def analyze(root, records=None):
    root = Path(root).resolve()
    records = records_for(root, records)
    feedback, resolutions = events(root, 'feedback'), events(root, 'feedback/resolutions')
    disputes, quarantine_reasons = quarantine(root, feedback, resolutions, records)
    learner_feedback = [e for e in feedback if e['payload']['kind'] == 'learner']
    active = [r for r in records if r['status'] == 'in_progress' and r['kind'] != 'system_test']
    globals_, scoped, lesson_scoped, sources = {}, {}, {}, {}
    for event in learner_feedback:
        value = event['payload']
        if value.get('actor', 'unspecified') != 'learner':
            continue
        if value['scope'] == 'global':
            globals_.update(value.get('signals', {}))
            sources.update({k: event['id'] for k in value.get('signals', {})})
        elif value.get('session_id') in {r['id'] for r in active}:
            scoped.setdefault(value['session_id'], {}).update(value.get('signals', {}))
            sources.update({value['session_id'] + ':' + k: event['id'] for k in value.get('signals', {})})
        elif value['scope'] == 'lesson':
            lesson_scoped.setdefault(value['lesson_id'], {}).update(value.get('signals', {}))
            sources.update({value['lesson_id'] + ':' + k: event['id'] for k in value.get('signals', {})})
    effective = dict(globals_)
    if len(active) == 1:
        effective.update(scoped.get(active[0]['id'], {}))
    # Read only the lesson envelope here: lessons validates the full packet, and
    # calling it here would recursively enter preference analysis.
    active_lessons = []
    for file in (root / 'learning' / 'lessons').glob('*.json'):
        item = json.loads(file.read_text(encoding='utf-8'))
        if item.get('kind') == 'learner' and item.get('status') != 'completed':
            active_lessons.append(item)
    if len(active_lessons) == 1:
        effective.update(lesson_scoped.get(active_lessons[0]['id'], {}))
    learning = sorted([r for r in records if r['status'] == 'completed' and r['kind'] != 'system_test'],
                      key=lambda r: (r['completed_at'], r['id']))
    exclusions = dict(quarantine_reasons)
    hypotheses, full = {}, {skill: [] for skill in session.SKILLS}
    for record in records:
        reason = assessment_reason(root, record, quarantine_reasons)
        if reason:
            if record['kind'] != 'system_test' and record['status'] == 'completed':
                exclusions.setdefault(record['id'], []).append(reason)
            continue
        result = record['result']
        if result['mode'] == 'answers_key':
            observations = [dict(number=a['number'], given=a['given'], expected=a['expected'], proof=a['proof'])
                            for a in result['answers'] if a['correct'] is False]
            label = 'objective_answer_proof'
        elif result['mode'] == 'ai_estimate':
            source, revision = session.response_for_result(root, record, result)
            observations = [dict(response_revision_id=revision, source_sha256=digest(source),
                                 criteria=result['criteria'], uncertainty=result['uncertainty'])]
            label = 'AI_observed_sample_hypothesis'
        else:
            observations = []
            label = 'not_pattern_evidence'
        if observations:
            for pattern in result['feedback'].get('patterns', []):
                normalized = re.sub(r'\s+', ' ', pattern).strip().casefold()
                hypotheses.setdefault((record['skill'], normalized), []).append({
                    'session_id': record['id'], 'task_id': record['task_id'], 'wording': pattern,
                    'evidence_type': label, 'observations': observations, 'conditions': record.get('conditions', {})})
        conditions = record.get('conditions', {})
        timed_fresh = conditions.get('timed') is True and conditions.get('key_seen_before') is False
        if record['skill'] == 'Listening':
            timed_fresh = timed_fresh and type(conditions.get('audio_plays')) is int and conditions.get('audio_plays') == 1
        if timed_fresh and result.get('scope') == 'full' and (
                result['mode'] == 'answers_key' and result.get('score', {}).get('total') == 40 or
                result['mode'] == 'ai_estimate' and result.get('band') is not None):
            full[record['skill']].append({'session_id': record['id'], 'task_id': record['task_id'],
                                        'band_target': result.get('band_target'), 'status': 'local_evidence_for_coach_review'})
    recurring = [{'skill': skill, 'pattern': pattern, 'status': 'recurring_hypothesis_not_stable_weakness',
                  'support': evidence, 'session_ids': sorted({e['session_id'] for e in evidence}),
                  'task_ids': sorted({e['task_id'] for e in evidence}), 'rule_version': RULE_VERSION}
                 for (skill, pattern), evidence in sorted(hypotheses.items())
                 if len({e['task_id'] for e in evidence}) >= 2]
    per_skill = {}
    sufficient = not disputes
    for skill, evidence in full.items():
        enough = len({e['task_id'] for e in evidence}) >= 2
        if skill == 'Writing':
            enough = enough and all(len({e['task_id'] for e in evidence if e['band_target'] == target}) >= 2
                                    for target in ('task1', 'task2'))
        sufficient = sufficient and enough
        per_skill[skill] = {'full_evidence': evidence, 'two_fresh_samples_available': enough}
    experiments, reviews = events(root, 'learning/experiments'), events(root, 'learning/reviews')
    known = {r['id']: r for r in records}
    ledger = []
    for experiment in experiments:
        history = [r for r in reviews if r['experiment_id'] == experiment['id']]
        latest = history[-1] if history else None
        cited_ids = experiment['payload']['baseline_session_ids'] + (latest['payload']['session_ids'] if latest else [])
        snapshots = dict(experiment.get('session_snapshots', {}))
        snapshots.update(latest.get('session_snapshots', {}) if latest else {})
        pinned = dict(experiment.get('source_evidence_sha256', {}))
        pinned.update(latest.get('source_evidence_sha256', {}) if latest else {})
        usable = (all(sid in known for sid in cited_ids) and
                  source_pins_current(root, [known[sid] for sid in cited_ids], pinned)) and bool(cited_ids) and experiment['payload']['kind'] == 'learner' and all(
            sid in known and snapshots.get(sid) == digest(known[sid]) and
            not assessment_reason(root, known[sid], quarantine_reasons) for sid in cited_ids)
        ledger.append({'id': experiment['id'], 'kind': experiment['payload']['kind'],
                       'status': latest['payload']['decision'] if latest else 'pending',
                       'metric': experiment['payload']['metric'], 'review_ids': [r['id'] for r in history],
                       'assessment_citations_currently_usable': usable,
                       'causal_claim': False, 'automatic_policy_change': False})
    recent = learning[-8:]
    return {'rule_version': RULE_VERSION, 'input_session_ids': sorted(r['id'] for r in records),
            'input_feedback_ids': [e['id'] for e in feedback], 'input_resolution_ids': [e['id'] for e in resolutions],
            'input_experiment_ids': [e['id'] for e in experiments], 'input_review_ids': [e['id'] for e in reviews],
            'experiments': ledger,
            'feedback_counts': {category: sum(e['payload']['category'] == category for e in learner_feedback) for category in CATEGORIES},
            'system_test_feedback_count': sum(e['payload']['kind'] == 'system_test' for e in feedback),
            'preferences': {'global': globals_, 'by_session': scoped, 'by_lesson': lesson_scoped,
                            'effective': effective, 'source_event_ids': sources},
            'unresolved_disputes': disputes,
            'access_issues': [{'feedback_id': e['id'], 'session_id': e['payload'].get('session_id'),
                               'text': e['payload']['text'], 'provenance': e['payload']['provenance']}
                              for e in learner_feedback if e['payload']['category'] == 'access'],
            'recurring_hypotheses': recurring, 'excluded_assessment_ids': sorted(exclusions),
            'exclusion_reasons': exclusions,
            'coverage': {'recent_sessions': [{'id': r['id'], 'task_id': r['task_id'], 'skill': r['skill'],
                                               'kind': r['kind'], 'assessment_usable': r['id'] not in exclusions}
                                              for r in recent],
                         'counts': {skill: sum(r['skill'] == skill for r in recent) for skill in session.SKILLS}},
            'next_skill': ROTATION[(ROTATION.index(learning[-1]['skill']) + 1) % 4] if learning else 'Listening',
            'readiness': {'status': 'coach_review_required' if sufficient else 'insufficient',
                          'per_skill': per_skill, 'ready_for_review': bool(sufficient), 'official_readiness': False,
                          'target_overall': 6.5, 'target_each_skill': 6.0,
                          'target_each_skill_status': 'temporary_unverified_requirement',
                          'policy': 'Conservative local coach review trigger, not an IELTS prediction or admission rule.'}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('record-feedback', 'experiment'):
        commands.add_parser(name).add_argument('--input', type=Path, required=True)
    for name in ('resolve-feedback', 'review-experiment'):
        child = commands.add_parser(name)
        child.add_argument('--id', required=True)
        child.add_argument('--input', type=Path, required=True)
    commands.add_parser('analyze')
    args = parser.parse_args()
    try:
        payload = json.loads(args.input.read_text(encoding='utf-8')) if hasattr(args, 'input') else None
        if args.command == 'record-feedback':
            result = record_feedback(args.root, payload)
        elif args.command == 'experiment':
            result = record_experiment(args.root, payload)
        elif args.command == 'resolve-feedback':
            result = resolve_feedback(args.root, args.id, payload)
        elif args.command == 'review-experiment':
            result = review_experiment(args.root, args.id, payload)
        else:
            result = analyze(args.root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    sys.exit(main())
