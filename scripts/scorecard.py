"""Derived coaching evidence, never a grader or an end-to-end timing estimator."""
import hashlib
import datetime
import json
from pathlib import Path
import re

import adaptation
import lessons
import session

VERSION = 'scorecard-1'


def moment(value):
    if not isinstance(value, str):
        raise ValueError('Scorecard dates require an ISO timestamp.')
    parsed = datetime.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Scorecard dates require timezone provenance.')
    return parsed


def completion_at(record):
    transitions = record.get('transitions')
    if not isinstance(transitions, list):
        raise ValueError('Completed lesson transition evidence is invalid.')
    event = next((t for t in reversed(transitions) if isinstance(t, dict) and t.get('to') == 'completed'), None)
    if not event:
        raise ValueError('Completed lesson has no completion transition evidence.')
    moment(event.get('at'))
    return event['at']


def normalized(value):
    return re.sub(r'\s+', ' ', value).strip().casefold()


def location(root, name):
    target = Path(root) / 'learning' / 'scorecards' / name
    for p in (target,) + tuple(target.parents):
        if p == Path(root):
            break
        if p.is_symlink():
            raise ValueError('Scorecard paths cannot use symlinks.')
    return target


def main_completions(records, taught, root):
    """Linked task+lesson count once; short drills never advance main coverage."""
    linked = {r['official_attempt_id']: r for r in taught if r.get('official_attempt_id')}
    result = []
    for r in records:
        if r['status'] != 'completed' or r['kind'] in ('system_test', 'retake'):
            continue
        lesson = linked.get(r['id'])
        if lesson and lesson['status'] != 'completed':
            continue
        result.append({'id': 'session:' + r['id'], 'skill': r['skill'],
                       'completed_at': (completion_at(lesson) if lesson else r['completed_at']),
                       'session_id': r['id'], 'lesson_id': lesson['id'] if lesson else None})
    for r in taught:
        p = lessons.packet_for(root, r)
        if r['kind'] == 'system_test' or r['status'] != 'completed' or r.get('official_attempt_id') or p['practice_kind'] == 'short_drill':
            continue
        result.append({'id': 'lesson:' + r['id'], 'skill': r['main_skill'],
                       'completed_at': completion_at(r), 'session_id': None, 'lesson_id': r['id']})
    return sorted(result, key=lambda r: (moment(r['completed_at']), r['id']))


def initialize(root):
    """Pin the rollout boundary; historical completions remain learning evidence."""
    with session.mutation_lock(Path(root)):
        path = location(root, 'tracking.json')
        if path.exists():
            return json.loads(path.read_text())
        completed = main_completions(session.load_sessions(root), lessons.load(root), root)
        value = {'version': VERSION, 'started_at': session.now(),
                 'pre_tracking_completion_ids': [r['id'] for r in completed],
                 'provenance': {'method': 'coach_scorecard_rollout',
                                'reference': 'User approved lightweight tracking in the existing coach; prior completions excluded from new-workflow cadence.'}}
        session.json_write(path, value)
        return value


def teaching_process(taught):
    compliant, skipped, unknown = [], [], []
    for r in taught:
        if r['status'] != 'completed':
            continue
        if any(t.get('learner_requested_skip') for t in r['transitions']):
            skipped.append(r['id'])
            continue
        stages = [p['stage'] for p in r['presentations']]
        wanted = ['theory', 'example', 'guided', 'independent']
        if all(s in stages for s in wanted) and [stages.index(s) for s in wanted] == sorted(stages.index(s) for s in wanted):
            compliant.append(r['id'])
        else:
            unknown.append(r['id'])
    return {'documented_sequence': len(compliant), 'assessed_completed_lessons': len(compliant) + len(unknown),
            'explicit_skips': skipped, 'insufficient_delivery_evidence': unknown,
            'limit': 'Presentation records support documented delivery, not proof of learner comprehension.'}


def focused_checks(taught, root):
    samples, excluded = [], []
    known = {r['id']: r for r in taught}
    for lesson in taught:
        for review in lesson['reviews']:
            payload = review['payload']
            response = next(r for r in lesson['responses'] if r['id'] == payload['response_id'])
            c = response['payload'].get('conditions', {})
            check = c.get('check_type')
            if check not in ('transfer', 'retention'):
                continue
            source = known.get(c.get('source_lesson_id'))
            reason = None
            delay = None
            if response['stage'] != 'independent' or response['payload'].get('purpose', 'attempt') != 'attempt':
                reason = 'assisted_stage_or_revision'
            elif not source or source['status'] != 'completed' or source['packet_id'] == lesson['packet_id']:
                reason = 'missing_completed_source_or_reused_packet'
            elif source['objective'] != lesson['objective'] or source['main_skill'] != lesson['main_skill']:
                reason = 'objective_not_comparable'
            elif c.get('assisted') is not False or c.get('fresh_task') is not True or c.get('key_seen_before') is not False or c.get('hints_used') is True or c.get('transcript_seen') is True:
                reason = 'independence_or_freshness_unverified'
            elif lesson['official_attempt_id']:
                reason = 'official_results_are_reported_separately'
            else:
                delay = (moment(response['at']) - moment(completion_at(source))).total_seconds() / 86400
                if delay < 0:
                    reason = 'source_teaching_after_check'
                elif check == 'retention' and not 3 <= delay <= 7:
                    reason = 'retention_checkpoint_outside_3_to_7_days'
                packet = lessons.packet_for(root, lesson)
                checked_prompts = {normalized(i['prompt']) for i in packet['independent'] if i['id'] in payload['item_ids']}
                exposed = set()
                for previous in taught:
                    for display in previous['presentations']:
                        if previous['id'] == lesson['id'] or moment(display['at']) > moment(response['at']):
                            continue
                        content = display['content']
                        exposed.update(normalized(i['prompt']) for i in content.get('items', []))
                        if 'prompt' in content:
                            exposed.add(normalized(content['prompt']))
                if checked_prompts & exposed:
                    reason = 'previously_exposed_prompt'
            numeric = {k: v for k, v in payload.get('criteria', {}).items() if isinstance(v, dict) and 'correct' in v and 'total' in v}
            if reason or not numeric:
                excluded.append({'lesson_id': lesson['id'], 'response_id': response['id'], 'reason': reason or 'no_numeric_aspect_review'})
                continue
            for aspect, score in numeric.items():
                samples.append({'lesson_id': lesson['id'], 'response_id': response['id'],
                                'source_lesson_id': source['id'], 'check_type': check,
                                'objective': lesson['objective'], 'aspect': aspect,
                                'correct': score['correct'], 'assessed': score['total'],
                                'delay_days': round(delay, 2) if check == 'retention' else None,
                                'provenance': response['payload']['provenance']})
    return {'status': 'observations_available' if samples else 'insufficient_evidence',
            'samples': samples, 'excluded': excluded,
            'limit': 'Coach-verified conditions; aspect counts stay separate. No pooled accuracy, mastery, band or causal claim.'}


def build(root):
    root = Path(root)
    records, taught = session.load_sessions(root), lessons.load(root)
    taught = [r for r in taught if r['kind'] != 'system_test']
    analysis = adaptation.analyze(root, records=records)
    completed = [r for r in records if r['status'] == 'completed' and r['kind'] != 'system_test']
    excluded = dict(analysis['exclusion_reasons'])
    for r in completed:
        if r.get('conditions', {}).get('assisted') is not False:
            excluded[r['id']] = list(excluded.get(r['id'], [])) + ['unaided_conditions_unverified']
    path = location(root, 'tracking.json')
    tracking = json.loads(path.read_text()) if path.exists() else None
    if tracking and (tracking.get('version') != VERSION or not isinstance(tracking.get('pre_tracking_completion_ids'), list)):
        raise ValueError('Invalid scorecard rollout record.')
    mains = main_completions(records, taught, root)
    cohort = [r for r in mains if tracking and r['id'] not in tracking['pre_tracking_completion_ids']]
    per_skill = {}
    for skill in session.SKILLS:
        observed = sorted([r for r in completed if r['skill'] == skill], key=lambda r: r['completed_at'])
        eligible = [r for r in observed if r['id'] not in excluded]
        full = [e for e in analysis['readiness']['per_skill'][skill]['full_evidence'] if e['session_id'] not in excluded]
        enough = len({e['task_id'] for e in full}) >= 2
        if skill == 'Writing':
            enough = enough and all(len({e['task_id'] for e in full if e['band_target'] == target}) >= 2 for target in ('task1', 'task2'))
        def project(r):
            result = r['result']
            return {'session_id': r['id'], 'task_id': r['task_id'], 'scope': result['scope'],
                    'assessment_mode': result['mode'], 'source_label': (r.get('material') or {}).get('source_label'),
                    'score': result.get('score'), 'conditions': r.get('conditions', {}),
                    'source': 'sessions/' + r['id'] + '.json',
                    'excluded_reasons': excluded.get(r['id'], []),
                    'uncertainty': result.get('uncertainty')}
        per_skill[skill] = {'latest_observation': project(observed[-1]) if observed else None,
                            'latest_eligible_observation': project(eligible[-1]) if eligible else None,
                            'baseline_status': 'full_evidence_available_for_coach_review' if enough else 'insufficient',
                            'full_evidence': full}
    sources = ['sessions/' + r['id'] + '.json' for r in records] + ['learning/lessons/' + r['id'] + '.json' for r in taught]
    sources += ['feedback/' + fid + '.json' for fid in analysis['input_feedback_ids']]
    sources += ['feedback/resolutions/' + fid + '.json' for fid in analysis['input_resolution_ids']]
    sources += ['learning/packets/' + r['packet_id'] + '.json' for r in taught]
    sources += ['learning/experiments/' + fid + '.json' for fid in analysis['input_experiment_ids']]
    sources += ['learning/reviews/' + fid + '.json' for fid in analysis['input_review_ids']]
    if tracking:
        sources.append('learning/scorecards/tracking.json')
    pins = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in sorted(set(sources))}
    invalid = []
    for r in completed:
        try:
            session.validate(root, r, r['result'])
        except (ValueError, OSError, KeyError, TypeError) as error:
            invalid.append({'session_id': r['id'], 'reason': str(error)})
    effectiveness = ('comparable_outcomes_available_for_coach_review' if any(
        e['status'] == 'adopted' and e['assessment_citations_currently_usable'] for e in analysis['experiments'])
        else 'insufficient_evidence')
    return {'version': VERSION, 'derived': True, 'generated_at': session.now(), 'source_sha256': pins,
            'learning': {'target_overall': 6.5, 'per_skill': per_skill, 'effectiveness': effectiveness,
                         'experiments': analysis['experiments'], 'causal_claim': False},
            'focused_checks': focused_checks(taught, root),
            'teaching': teaching_process(taught),
            'practice': [{'lesson_id': r['id'], 'status': r['status'], **lessons.counts(r, lessons.packet_for(root, r))} for r in taught],
            'coverage': {'post_rollout_completed_main_lessons': len(cohort), 'latest_four': cohort[-4:],
                         'skills_in_latest_four': sorted({r['skill'] for r in cohort[-4:]}),
                         'missing_skills': sorted(set(session.SKILLS) - {r['skill'] for r in cohort[-4:]}),
                         'completed_four_lesson_blocks': len(cohort) // 4, 'historical_main_completions': len(mains) - len(cohort),
                         'limit': 'Task+linked lesson count once; short drills excluded. Coverage deviations require coach explanation, not automatic failure.'},
            'integrity': {'status': 'needs_action' if invalid else 'no_detected_record_validation_failure',
                          'assessment_validation_issues': invalid,
                          'unresolved_disputes': [{'feedback_id': d['feedback_id'], 'session_id': d.get('session_id'), 'state': d['state']} for d in analysis['unresolved_disputes']],
                          'zero_lost_responses_proven': False,
                          'limit': 'Validated records do not independently inventory every received chat response or prove grading correctness.'},
            'latency': {'status': 'not_measured', 'samples': 0, 'median_seconds': None, 'p90_seconds': None,
                        'reason': 'No verified complete-submission receipt and substantive-feedback display endpoints. Script-write times are not user waiting time.'},
            'thresholds': {'drill_accuracy': 'No universal threshold; report correct/assessed per objective and aspect.',
                           'latency': 'No verified baseline or service target yet; separate routine feedback and full reviews.'}}


def refresh(root):
    root = Path(root)
    initialize(root)
    with session.mutation_lock(root):
        report = build(root)
        session.json_write(location(root, 'current.json'), report)
        blocks = report['coverage']['completed_four_lesson_blocks']
        records = main_completions(session.load_sessions(root), lessons.load(root), root)
        baseline = json.loads(location(root, 'tracking.json').read_text())['pre_tracking_completion_ids']
        cohort = [r for r in records if r['id'] not in baseline]
        new = False
        # Capture each block exactly once, even if a previous report write crashed.
        for block in range(1, blocks + 1):
            target = location(root, 'four-main-%04d.json' % block)
            if not target.exists():
                snapshot = dict(report, four_lesson_block=block,
                                four_lesson_window=cohort[(block - 1) * 4:block * 4],
                                limit='Evidence summary as of report generation; the named coverage window is fixed, not a reconstructed historical ability assessment.')
                session.json_write(target, snapshot)
                new = True
        return {'saved': True, 'scorecard': report, 'new_four_lesson_review': new,
                'path': 'learning/scorecards/current.json'}


def safely_refresh(root):
    try:
        return refresh(root)
    except (ValueError, OSError, KeyError, TypeError, IndexError, AttributeError) as error:
        return {'saved': False, 'status': 'needs_action', 'message': str(error),
                'limit': 'Learner attempt remains saved; scorecard retry must not regrade.'}


def validate_saved(root):
    """Backup checks cached report envelopes; source drift requires regeneration."""
    directory = location(root, 'current.json').parent
    for path in directory.glob('*.json'):
        location(root, path.name)
        value = json.loads(path.read_text())
        if value.get('version') != VERSION:
            raise ValueError('Scorecard cache version invalid: ' + path.name)
        if path.name == 'tracking.json':
            if not isinstance(value.get('pre_tracking_completion_ids'), list):
                raise ValueError('Scorecard tracking boundary invalid.')
            moment(value.get('started_at'))
        elif (value.get('derived') is not True or not isinstance(value.get('source_sha256'), dict)
              or value.get('latency', {}).get('status') != 'not_measured'
              or value.get('learning', {}).get('causal_claim') is not False
              or value.get('integrity', {}).get('zero_lost_responses_proven') is not False):
            raise ValueError('Scorecard cache claims or envelope invalid: ' + path.name)
