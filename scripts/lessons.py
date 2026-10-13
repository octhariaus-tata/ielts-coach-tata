"""Resumable teaching packets; the coach, not this module, teaches and grades."""
import copy
import hashlib
import json
from pathlib import Path
import re
import uuid

import session

STAGES = ('theory', 'example', 'guided', 'independent', 'review', 'completed')
STATUSES = ('active', 'awaiting_response', 'awaiting_review', 'paused', 'completed')
PACKET_FIELDS = {'schema_version', 'id', 'version', 'role', 'main_skill', 'ielts_task_type',
                 'objective', 'source_label', 'practice_kind', 'theory', 'strategy',
                 'worked_example', 'guided', 'independent', 'coach_only', 'basis',
                 'official_task_id', 'provenance'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        raise ValueError('Lesson/packet ID must be a safe relative identifier.')
    return value


def path(root, directory, name):
    candidate = Path(root) / 'learning' / directory / (identifier(name) + '.json')
    for parent in (candidate,) + tuple(candidate.parents):
        if parent == Path(root):
            break
        if parent.is_symlink():
            raise ValueError('Lesson paths must not use symlinks.')
    return candidate


def reference(root, value):
    session.validate_evidence(root, [value])
    return hashlib.sha256((Path(root) / value).read_bytes()).hexdigest()


def require_text(value, label):
    if not session.nonempty(value):
        raise ValueError(label + ' must contain text.')


def validate_packet(root, packet):
    if not isinstance(packet, dict) or set(packet) - PACKET_FIELDS:
        raise ValueError('Unknown Teacher packet fields; keep coach-only answers separate.')
    if packet.get('schema_version') != 1:
        raise ValueError('Unsupported Teacher packet schema.')
    identifier(packet.get('id'))
    if packet.get('role') not in ('primary', 'backup') or packet.get('main_skill') not in session.SKILLS:
        raise ValueError('Packet needs a role and main IELTS skill.')
    if packet.get('source_label') not in ('coach_created', 'official'):
        raise ValueError('Label packet source explicitly.')
    if packet.get('practice_kind') not in ('short_drill', 'task'):
        raise ValueError('Packet practice_kind must be short_drill or task.')
    for key in ('version', 'ielts_task_type', 'objective', 'theory', 'strategy'):
        require_text(packet.get(key), key)
    session.validate_provenance(packet.get('provenance'))
    example = packet.get('worked_example')
    if not isinstance(example, dict) or set(example) != {'prompt', 'answer', 'reasoning'}:
        raise ValueError('Worked example needs prompt, answer and reasoning.')
    for key in example:
        require_text(example[key], 'worked example ' + key)
    seen = set()
    for stage in ('guided', 'independent'):
        items = packet.get(stage)
        if not isinstance(items, list) or not items:
            raise ValueError(stage + ' needs at least one item.')
        for item in items:
            if not isinstance(item, dict) or set(item) - {'id', 'prompt', 'hint', 'optional'}:
                raise ValueError('Learner items contain only ID, prompt, optional hint and optional flag.')
            iid = identifier(item.get('id'))
            if iid in seen:
                raise ValueError('Packet item IDs must be unique across stages.')
            seen.add(iid)
            require_text(item.get('prompt'), 'item prompt')
            if 'optional' in item and type(item['optional']) is not bool:
                raise ValueError('optional must be boolean.')
            if stage == 'independent' and 'hint' in item:
                raise ValueError('Independent items must not carry answer hints.')
            if 'hint' in item:
                require_text(item['hint'], 'guided hint')
    if packet['practice_kind'] == 'short_drill' and not 20 <= len(packet['independent']) <= 30:
        raise ValueError('Short drills prepare 20–30 items; completion is not mandatory.')
    canonical = lambda text: re.sub(r'\s+', ' ', text).strip().casefold()
    independent = {canonical(i['prompt']) for i in packet['independent']}
    if canonical(example['prompt']) in independent or any(canonical(i['prompt']) in independent for i in packet['guided']):
        raise ValueError('Worked/guided examples must use different independent data.')
    private = packet.get('coach_only', {})
    if not isinstance(private, dict) or set(private) - {'answers', 'rubric'}:
        raise ValueError('Coach-only packet section needs answers/rubric only.')
    answers = private.get('answers', {})
    if not isinstance(answers, dict) or set(answers) - seen:
        raise ValueError('Coach-only answers must reference known item IDs.')
    basis = packet.get('basis')
    if not isinstance(basis, dict) or set(basis) != {'preferences_sha256', 'files'}:
        raise ValueError('Teacher packet needs a pinned preference/file basis.')
    if not re.fullmatch(r'[a-f0-9]{64}', str(basis['preferences_sha256'])) or not isinstance(basis['files'], dict):
        raise ValueError('Invalid packet basis.')
    for name, expected in basis['files'].items():
        if name.startswith('coach_refs/'):
            raise ValueError('Teacher input must not include upcoming official correction caches.')
        if not re.fullmatch(r'[a-f0-9]{64}', str(expected)):
            raise ValueError('Invalid source checksum.')
        # Changed sources make a packet stale, not invalid history.
        session.validate_evidence(root, [name], check_files=False)
    task_id = packet.get('official_task_id')
    if packet['source_label'] == 'official' and not task_id:
        raise ValueError('Official packets must reference a verified catalog task.')
    if task_id:
        catalog = json.loads((Path(root) / 'materials.json').read_text())
        task = next((t for t in catalog['tasks'] if t['id'] == task_id), None)
        if not task or task['skill'] != packet['main_skill']:
            raise ValueError('Official task/skill must match the catalog.')
        if answers:
            raise ValueError('Upcoming official answers remain in correction caches, not Teacher packets.')
        if task['local']['prompt'] not in basis['files']:
            raise ValueError('Pin the exact official learner prompt.')
    # Structural projection protects private sections; coach reviews semantic leaks.
    learner = {k: packet[k] for k in ('theory', 'strategy', 'worked_example', 'guided', 'independent')}
    serialized = json.dumps(learner).casefold()
    if any(token in serialized for token in ('coach_refs/', 'answer_key', 'answer-key', 'transcript.pdf', 'transcript.json')):
        raise ValueError('Correction references must not enter learner-visible material.')
    return packet


def packets(root):
    result = []
    for file in sorted((Path(root) / 'learning' / 'packets').glob('*.json')):
        value = json.loads(file.read_text())
        validate_packet(root, value)
        if path(root, 'packets', value['id']) != file:
            raise ValueError('Packet filename/ID mismatch.')
        result.append(value)
    return result


def stale_reasons(root, packet, preferences):
    reasons = []
    if packet['basis']['preferences_sha256'] != digest(preferences):
        reasons.append('preferences_changed')
    for name, expected in packet['basis']['files'].items():
        try:
            if reference(root, name) != expected:
                reasons.append('source_changed:' + name)
        except (OSError, ValueError):
            reasons.append('source_unavailable:' + name)
    return reasons


def store_packet(root, packet):
    validate_packet(root, packet)
    with session.mutation_lock(root):
        target = path(root, 'packets', packet['id'])
        if target.exists():
            if json.loads(target.read_text()) != packet:
                raise ValueError('Packet IDs are immutable; use a new version/ID.')
            return {'saved': True, 'duplicate': True, 'packet_id': packet['id']}
        available = [p for p in packets(root) if p['id'] not in {r['packet_id'] for r in load(root)}]
        if any(p['role'] == packet['role'] for p in available):
            raise ValueError('Only one prepared primary and one backup; consume or explicitly retire the old packet.')
        session.json_write(target, packet)
        return {'saved': True, 'duplicate': False, 'packet_id': packet['id']}


def validate(root, record):
    if not isinstance(record, dict) or record.get('schema_version') != 1:
        raise ValueError('Unsupported lesson record.')
    identifier(record.get('id'))
    identifier(record.get('packet_id'))
    if record.get('kind') not in ('learner', 'system_test') or record.get('main_skill') not in session.SKILLS:
        raise ValueError('Lesson kind/skill invalid.')
    if record.get('stage') not in STAGES or record.get('status') not in STATUSES:
        raise ValueError('Lesson stage/status invalid.')
    if (record['stage'] == 'completed') != (record['status'] == 'completed'):
        raise ValueError('Completed lesson stage/status must agree.')
    budget = record.get('available_minutes')
    if budget is None:
        if not record.get('legacy_resume'):
            raise ValueError('Only migrated lessons may have unknown original budget.')
    elif type(budget) is not int or not 1 <= budget <= 180:
        raise ValueError('Lesson budget must be 1–180 minutes.')
    for key in ('objective', 'ielts_task_type', 'started_at'):
        require_text(record.get(key), key)
    session.validate_provenance(record.get('provenance'))
    revisions = record.get('responses')
    reviews = record.get('reviews')
    presentations = record.get('presentations')
    if not all(isinstance(v, list) for v in (revisions, reviews, presentations)):
        raise ValueError('Lesson needs presentation, response and review histories.')
    packet_file = path(root, 'packets', record['packet_id'])
    packet = json.loads(packet_file.read_text())
    validate_packet(root, packet)
    if record.get('packet_sha256') != digest(packet):
        raise ValueError('Lesson packet changed since the lesson started.')
    known_items = {i['id'] for s in ('guided', 'independent') for i in packet[s]}
    ids = set()
    for revision in revisions:
        rid = identifier(revision.get('id'))
        if rid in ids:
            raise ValueError('Duplicate lesson response ID.')
        ids.add(rid)
        payload = revision.get('payload')
        validate_response(root, packet, payload)
        if revision.get('stage') not in ('guided', 'independent', 'review'):
            raise ValueError('Response stage invalid.')
    for review in reviews:
        payload = review.get('payload', {})
        response = next((r for r in revisions if r['id'] == payload.get('response_id')), None)
        if not response or response['payload']['submission'] != 'complete':
            raise ValueError('Review must reference a complete checkpoint.')
        validate_review(root, record, payload)
    for display in presentations:
        if display.get('stage') not in STAGES[:-1] or not isinstance(display.get('content'), dict):
            raise ValueError('Invalid displayed prompt history.')
        if set(display.get('item_ids', [])) - known_items:
            raise ValueError('Displayed IDs do not match the packet.')
        if display['content'] != stage_content(packet, display['stage'], display.get('item_ids', [])):
            raise ValueError('Display snapshot must match learner-only projection.')
    official = record.get('official_attempt_id')
    if official:
        attempt = session.find_session(root, official)
        if attempt['task_id'] != packet.get('official_task_id'):
            raise ValueError('Linked attempt does not match official packet task.')
    for name in record.get('legacy_references', []):
        session.validate_evidence(root, [name])
    return record


def load(root):
    records = []
    for file in sorted((Path(root) / 'learning' / 'lessons').glob('*.json')):
        value = json.loads(file.read_text())
        validate(root, value)
        if path(root, 'lessons', value['id']) != file:
            raise ValueError('Lesson filename/ID mismatch.')
        records.append(value)
    return records


def find(root, lid):
    return next((r for r in load(root) if r['id'] == identifier(lid)), None) or _missing()


def _missing():
    raise ValueError('Lesson ID not found.')


def packet_for(root, record):
    return json.loads(path(root, 'packets', record['packet_id']).read_text())


def stage_content(packet, stage, ids=None):
    if stage == 'theory':
        return {'material': packet['theory'], 'strategy': packet['strategy']}
    if stage == 'example':
        return copy.deepcopy(packet['worked_example'])
    if stage in ('guided', 'independent'):
        items = packet[stage]
        if ids is not None:
            if len(ids) != len(set(ids)) or set(ids) - {i['id'] for i in items}:
                raise ValueError('Displayed items must belong to this stage.')
            items = [i for i in items if i['id'] in ids]
        return {'items': copy.deepcopy(items), 'source_label': packet['source_label']}
    return {'instruction': 'Review saved learner responses; no automatic band or mastery claim.'}


def counts(record, packet):
    ids = {i['id'] for i in packet['independent']}
    presented = {i for p in record['presentations'] if p['stage'] == 'independent' for i in p['item_ids']}
    submitted = {i for r in record['responses'] if r['stage'] == 'independent' and r['payload'].get('purpose', 'attempt') == 'attempt'
                 for i in r['payload'].get('answers', {})}
    reviewed = {i for r in record['reviews'] for i in r['payload']['item_ids'] if i in ids}
    return {'prepared': len(ids), 'presented': len(presented), 'submitted': len(submitted),
            'reviewed': len(reviewed), 'homework_debt': 0}


def summary(root, record):
    packet = packet_for(root, record)
    displays = [p for p in record['presentations'] if p['stage'] == record['stage']]
    content = displays[-1]['content'] if displays else stage_content(packet, record['stage'])
    return {'id': record['id'], 'packet_id': record['packet_id'], 'main_skill': record['main_skill'],
            'objective': record['objective'], 'stage': record['stage'], 'status': record['status'],
            'available_minutes': record['available_minutes'], 'official_attempt_id': record.get('official_attempt_id'),
            'displayed_prompt': copy.deepcopy(content), 'counts': counts(record, packet),
            'responses': copy.deepcopy(record['responses']), 'next_action': next_action(record)}


def next_action(record):
    if record['status'] == 'completed':
        return 'Prepare the next IELTS-led lesson and one backup.'
    if record['status'] == 'paused':
        return 'Wait for the learner to continue; preserve partial answers.'
    if record['status'] == 'awaiting_review':
        return 'Review the saved complete response once, then advance the lesson.'
    if record['stage'] in ('guided', 'independent') and record['status'] == 'awaiting_response':
        return 'Continue the displayed ' + record['stage'] + ' prompt; wait for the learner response.'
    return 'Deliver ' + record['stage'] + ' for: ' + record['objective']


def current(root, official=None):
    active = [r for r in load(root) if r['kind'] != 'system_test' and r['status'] != 'completed']
    official = official if official is not None else session.load_sessions(root)
    attempts = [r for r in official if r['kind'] != 'system_test' and r['status'] == 'in_progress']
    conflict = len(active) > 1 or len(attempts) > 1 or bool(active and attempts and active[0].get('official_attempt_id') != attempts[0]['id'])
    if conflict:
        return {'waiting': 'reconciliation', 'lesson_ids': [r['id'] for r in active],
                'attempt_ids': [r['id'] for r in attempts], 'next_action': 'Reconcile active work without discarding any record.'}
    lesson = summary(root, active[0]) if active else None
    action = 'Continue official attempt ' + attempts[0]['id'] if attempts else lesson['next_action'] if lesson else None
    return {'current_lesson': lesson, 'next_action': action}


def prepared(root, preferences):
    used = {r['packet_id'] for r in load(root)}
    return [{'id': p['id'], 'role': p['role'], 'main_skill': p['main_skill'], 'objective': p['objective'],
             'stale_reasons': stale_reasons(root, p, preferences)} for p in packets(root) if p['id'] not in used]


def start(root, preferences, packet_id=None, minutes=None, migration=None):
    with session.mutation_lock(root):
        state = current(root)
        if state.get('waiting'):
            return state
        if state.get('current_lesson'):
            return {'created': False, 'resumed': True, 'lesson': state['current_lesson']}
        if any(r['status'] == 'in_progress' and r['kind'] != 'system_test' for r in session.load_sessions(root)):
            return {'waiting': 'official_attempt', 'next_action': state['next_action']}
        candidates = prepared(root, preferences)
        selected = next((p for p in candidates if p['id'] == packet_id), None) if packet_id else next((p for p in candidates if p['role'] == 'primary' and not p['stale_reasons']), None)
        if not selected:
            return {'waiting': 'teacher_packet', 'prepared_queue': candidates}
        if selected['stale_reasons']:
            return {'waiting': 'stale_packet', 'stale_reasons': selected['stale_reasons']}
        packet = next(p for p in packets(root) if p['id'] == selected['id'])
        budget = minutes if minutes is not None else preferences.get('available_minutes', 40)
        if type(budget) is not int or not 1 <= budget <= 180:
            raise ValueError('New lesson budget must be 1–180 minutes.')
        stamp = session.now()
        lid = stamp[:10] + '-lesson-' + uuid.uuid4().hex[:12]
        record = {'schema_version': 1, 'id': lid, 'kind': 'learner', 'packet_id': packet['id'],
                  'packet_sha256': digest(packet), 'main_skill': packet['main_skill'],
                  'objective': packet['objective'], 'ielts_task_type': packet['ielts_task_type'],
                  'available_minutes': budget, 'started_at': stamp, 'stage': 'theory', 'status': 'active',
                  'responses': [], 'reviews': [], 'presentations': [], 'transitions': [],
                  'preferences': copy.deepcopy(preferences), 'official_attempt_id': None,
                  'provenance': {'method': 'coach_lesson_prepare', 'reference': 'Teacher packet ' + packet['id']}}
        if migration:
            session.validate_provenance(migration.get('provenance'))
            record.update(legacy_resume=True, available_minutes=None, stage=migration['stage'],
                          status='awaiting_response', provenance=migration['provenance'],
                          legacy_references=migration['references'])
            for stage in STAGES[:STAGES.index(record['stage']) + 1]:
                ids = [i['id'] for i in packet.get(stage, [])] if stage in ('guided', 'independent') else []
                record['presentations'].append({'stage': stage, 'item_ids': ids,
                                               'content': stage_content(packet, stage, ids), 'at': stamp,
                                               'provenance': migration['provenance']})
        validate(root, record)
        session.json_write(path(root, 'lessons', lid), record)
        session._rebuild(root)
        return {'created': True, 'resumed': False, 'lesson': summary(root, find(root, lid))}


def validate_response(root, packet, payload):
    if not isinstance(payload, dict) or set(payload) - {'text', 'answers', 'evidence', 'submission', 'purpose', 'provenance', 'conditions'}:
        raise ValueError('Response fields invalid.')
    session.validate_provenance(payload.get('provenance'))
    if payload.get('submission') not in ('partial', 'complete', 'paused') or payload.get('purpose', 'attempt') not in ('attempt', 'review'):
        raise ValueError('Coach must explicitly mark submission partial/complete/paused and purpose.')
    if 'text' in payload and not isinstance(payload['text'], str):
        raise ValueError('Response text must be a string.')
    answers = payload.get('answers', {})
    if not isinstance(answers, dict) or set(answers) - {i['id'] for s in ('guided', 'independent') for i in packet[s]}:
        raise ValueError('Answers must refer to known item IDs.')
    if any(not isinstance(v, str) for v in answers.values()):
        raise ValueError('Answers are strings, including intentionally blank answers.')
    session.validate_evidence(root, payload.get('evidence', []))
    if not (payload.get('text') or answers or payload.get('evidence') or payload['submission'] == 'paused'):
        raise ValueError('Checkpoint needs input or an explicit pause.')
    if 'conditions' in payload and not isinstance(payload['conditions'], dict):
        raise ValueError('Response conditions must be an object.')


def checkpoint(root, lid, payload):
    with session.mutation_lock(root):
        record = find(root, lid)
        packet = packet_for(root, record)
        validate_response(root, packet, payload)
        existing = next((r for r in record['responses'] if r['payload'] == payload), None)
        if existing:
            session._rebuild(root)
            return {'saved': True, 'duplicate': True, 'response_id': existing['id'], 'lesson': summary(root, record)}
        if record['stage'] not in ('guided', 'independent', 'review', 'completed'):
            raise ValueError('Deliver the material and example before collecting exercises.')
        if record['stage'] in ('review', 'completed') and payload.get('purpose') != 'review':
            raise ValueError('Post-feedback responses are separate review revisions.')
        stage = 'review' if payload.get('purpose') == 'review' else record['stage']
        displayed = {i for p in record['presentations'] if p['stage'] == stage for i in p['item_ids']}
        if stage != 'review' and set(payload.get('answers', {})) - displayed:
            raise ValueError('Cannot submit items that were not presented.')
        rid = uuid.uuid4().hex
        record['responses'].append({'id': rid, 'at': session.now(), 'stage': stage, 'payload': copy.deepcopy(payload)})
        if record['status'] != 'completed' and stage != 'review':
            record['status'] = {'partial': 'awaiting_response', 'complete': 'awaiting_review', 'paused': 'paused'}[payload['submission']]
        session.json_write(path(root, 'lessons', lid), record)
        session._rebuild(root)
        return {'saved': True, 'duplicate': False, 'response_id': rid, 'lesson': summary(root, find(root, lid))}


def validate_review(root, record, payload):
    if not isinstance(payload, dict) or set(payload) - {'response_id', 'item_ids', 'feedback', 'criteria', 'official_result_reference', 'provenance'}:
        raise ValueError('Review fields invalid; bands and mastery claims are not lesson results.')
    session.validate_provenance(payload.get('provenance'))
    response = next((r for r in record['responses'] if r['id'] == payload.get('response_id')), None)
    if not response or response['payload']['submission'] != 'complete':
        raise ValueError('Checkpoint a complete submission before reviewing.')
    ids = payload.get('item_ids')
    if not isinstance(ids, list) or len(ids) != len(set(ids)) or set(ids) - set(response['payload'].get('answers', {})):
        raise ValueError('Review only submitted items in the selected checkpoint.')
    feedback = payload.get('feedback', {})
    if not isinstance(feedback, dict) or any(not session.nonempty(feedback.get(k)) for k in ('strength', 'action', 'next_task')):
        raise ValueError('Review needs strength, action and next task.')
    patterns = feedback.get('patterns', [])
    if not isinstance(patterns, list) or len(patterns) > 2 or any(not session.nonempty(p) for p in patterns):
        raise ValueError('At most two error patterns.')
    criteria = payload.get('criteria', {})
    if not isinstance(criteria, dict) or set(criteria) - {'grammar', 'spelling', 'punctuation', 'task_fulfilment'}:
        raise ValueError('Keep drill criteria separate from IELTS band assessment.')
    if payload.get('official_result_reference'):
        if payload['official_result_reference'] != record.get('official_attempt_id'):
            raise ValueError('Official result reference must be the linked attempt.')
        if session.find_session(root, record['official_attempt_id'])['status'] != 'completed':
            raise ValueError('Official assessment must be completed through existing validated workflow.')


def review(root, lid, payload):
    with session.mutation_lock(root):
        record = find(root, lid)
        validate_review(root, record, payload)
        old = next((r for r in record['reviews'] if r['payload']['response_id'] == payload['response_id']), None)
        if old:
            if old['payload'] != payload:
                raise ValueError('Do not overwrite a reviewed response; preserve corrections separately.')
            session._rebuild(root)
            return {'saved': True, 'duplicate': True, 'lesson': summary(root, record)}
        if record['status'] in ('paused', 'awaiting_response'):
            raise ValueError('Do not review while the learner is paused or still answering.')
        record['reviews'].append({'at': session.now(), 'payload': copy.deepcopy(payload)})
        record['status'] = 'active'
        session.json_write(path(root, 'lessons', lid), record)
        session._rebuild(root)
        return {'saved': True, 'duplicate': False, 'lesson': summary(root, find(root, lid))}


def present(root, lid, payload):
    with session.mutation_lock(root):
        record = find(root, lid)
        if record['status'] in ('completed', 'paused', 'awaiting_review'):
            raise ValueError('Resume/review saved work before presenting another prompt.')
        packet = packet_for(root, record)
        ids = payload.get('item_ids')
        if ids is None:
            ids = [i['id'] for i in packet.get(record['stage'], [])] if record['stage'] in ('guided', 'independent') else []
        content = stage_content(packet, record['stage'], ids)
        if record['stage'] in ('guided', 'independent') and not ids:
            raise ValueError('Present at least one exercise item.')
        session.validate_provenance(payload.get('provenance'))
        display = {'stage': record['stage'], 'item_ids': ids, 'content': content, 'provenance': payload['provenance']}
        duplicate = next((p for p in record['presentations'] if all(p.get(k) == v for k, v in display.items())), None)
        if not duplicate:
            record['presentations'].append(dict(display, at=session.now()))
        if record['stage'] in ('guided', 'independent'):
            record['status'] = 'awaiting_response'
        session.json_write(path(root, 'lessons', lid), record)
        session._rebuild(root)
        return {'saved': True, 'duplicate': bool(duplicate), 'lesson': summary(root, find(root, lid))}


def advance(root, lid, payload):
    with session.mutation_lock(root):
        record = find(root, lid)
        target = payload.get('stage')
        if target not in STAGES:
            raise ValueError('Unknown target lesson stage.')
        session.validate_provenance(payload.get('provenance'))
        if record['stage'] == target:
            session._rebuild(root)
            return {'saved': True, 'duplicate': True, 'lesson': summary(root, record)}
        if record['status'] != 'active':
            raise ValueError('Wait for complete submission and review before advancing.')
        source = record['stage']
        skipping = payload.get('learner_requested_skip') is True
        if STAGES.index(target) != STAGES.index(source) + 1 and not skipping:
            raise ValueError('Teach theory, example, guided, independent and review in order.')
        if STAGES.index(target) <= STAGES.index(source):
            raise ValueError('Use review revisions, not backward stage changes.')
        if skipping and payload.get('actor') != 'learner':
            raise ValueError('Only an explicit learner request can skip teaching stages.')
        if not skipping:
            if not any(p['stage'] == source for p in record['presentations']) and source not in ('review',):
                raise ValueError('Record the actually displayed material before advancing.')
            if source in ('guided', 'independent') and not any(
                    any(r['id'] == v['payload']['response_id'] and r['stage'] == source for r in record['responses']) for v in record['reviews']):
                raise ValueError('Review the complete exercise response before advancing.')
        if target == 'completed':
            if record.get('official_attempt_id') and session.find_session(root, record['official_attempt_id'])['status'] != 'completed':
                raise ValueError('Finish linked official attempt before completing lesson.')
            if not record['reviews']:
                raise ValueError('A lesson needs reviewed evidence before completion.')
        record['transitions'].append({'from': source, 'to': target, 'at': session.now(),
                                      'learner_requested_skip': skipping, 'provenance': payload['provenance']})
        record.update(stage=target, status='completed' if target == 'completed' else 'active')
        session.json_write(path(root, 'lessons', lid), record)
        session._rebuild(root)
        return {'saved': True, 'lesson': summary(root, find(root, lid))}


def link(root, lid, attempt_id):
    with session.mutation_lock(root):
        record = find(root, lid)
        if record['stage'] != 'independent':
            raise ValueError('Official attempt begins at independent stage only.')
        record['official_attempt_id'] = attempt_id
        validate(root, record)
        session.json_write(path(root, 'lessons', lid), record)
        session._rebuild(root)


def teacher_brief(root, preferences, skill, task_type, objective):
    require_text(objective, 'objective')
    require_text(task_type, 'IELTS task type')
    if skill not in session.SKILLS:
        raise ValueError('Teacher brief requires one main IELTS skill.')
    return {'main_skill': skill, 'ielts_task_type': task_type, 'objective': objective,
            'preferences': copy.deepcopy(preferences), 'prepared_short_items': [20, 30],
            'planning_minutes': {'theory': 5, 'example': 5, 'guided': 8, 'independent': 17, 'review': 5},
            'basis': {'preferences_sha256': digest(preferences), 'files': {}},
            'delegation': 'One bounded read-only Teacher prepares a packet. Main coach validates, delivers, grades and writes.',
            'output_schema': 'scripts/lessons.py validate_packet; separate learner stages and coach_only.',
            'limits': 'No upcoming official key/transcript, no account operations, no grading or learner-data mutations. Label AI examples.'}
