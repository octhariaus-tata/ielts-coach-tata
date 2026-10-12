#!/usr/bin/env python3
"""Offline integrity checks for coach-only correction excerpts. Python 3.8+.

These checks establish cache availability, provenance and task alignment. They do
not establish learner answers, playback, browser access or an IELTS band. No
correction content is returned by check_reference or learner_packet.
"""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re

JAKARTA = dt.timezone(dt.timedelta(hours=7))
SHA256 = re.compile(r'^[a-f0-9]{64}$')


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def project_file(root, relative, directory):
    """Reject absolute paths, traversal and symlinks escaping the project."""
    root = Path(root).resolve()
    if not isinstance(relative, str) or not relative:
        raise ValueError('Path referensi belum tersedia.')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or path.parts[0] != directory:
        raise ValueError('Path referensi harus berada dalam ' + directory + '/.')
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root / directory)
    except ValueError:
        raise ValueError('Path referensi keluar dari project.')
    return resolved


def parse_key_page(text, page):
    """Preserve the official printed alternatives and order-independent groups.

    This deliberately does not expand optional bracketed words, round numbers or
    guess equivalent answers. Coach applies the printed key after the attempt.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError('Teks key kosong.')
    entries = []
    current = None
    policy = []
    in_policy = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r'^Page\s+\d+\s+of\s+\d+$', line) or line == 'IELTS.org':
            continue
        if line.startswith('Words in brackets'):
            in_policy = True
        if in_policy:
            policy.append(line)
            continue
        match = re.match(r'^(\d+(?:\s*&\s*\d+)?)\s+(.+)$', line)
        if match:
            numbers = [number.strip() for number in match.group(1).split('&')]
            rest = match.group(2).strip()
            grouped = len(numbers) > 1
            if grouped and not re.fullmatch(r'in either order', rest, re.I):
                raise ValueError('Kelompok key tidak memiliki aturan urutan yang jelas.')
            current = {'question_numbers': numbers, 'source_page': page,
                       'order': 'any' if grouped else 'fixed',
                       'answer_lines': [] if grouped else [rest]}
            entries.append(current)
        elif current is not None:
            current['answer_lines'].append(line)
    for item in entries:
        if not item['answer_lines']:
            raise ValueError('Key tidak memuat jawaban untuk semua nomor.')
        if item['order'] == 'any' and len(item['answer_lines']) != len(item['question_numbers']):
            raise ValueError('Jumlah jawaban kelompok key tidak cocok.')
    return entries, ' '.join(policy)


def check_reference(root, task):
    """Return a content-free check report for an exact catalog task dictionary."""
    result = {'status': 'not_tested', 'reasons': [],
              'checked_at': dt.datetime.now(JAKARTA).isoformat(timespec='seconds'),
              'task_id': task.get('id') if isinstance(task, dict) else None}
    if not isinstance(task, dict):
        result.update(status='failed', reasons=['Metadata tugas tidak valid.'])
        return result
    metadata = task.get('coach_reference')
    if task.get('skill') not in ('Listening', 'Reading'):
        result['reasons'] = ['Tugas ini memakai kriteria Writing/Speaking, bukan key objektif lokal.']
        return result
    if not metadata:
        result.update(status='failed', reasons=['Cache koreksi lokal belum tersedia; menunggu referensi versi yang sama.'])
        return result
    try:
        if not isinstance(metadata, dict) or metadata.get('schema_version') != 1:
            raise ValueError('Metadata cache koreksi tidak valid.')
        if metadata.get('visibility') != 'coach_only_after_done':
            raise ValueError('Kebijakan pemisahan referensi coach belum jelas.')
        cache_path = project_file(root, metadata.get('path'), 'coach_refs')
        if not cache_path.is_file():
            raise ValueError('File cache koreksi tidak tersedia; menunggu referensi versi yang sama.')
        expected_sha = metadata.get('sha256')
        if not isinstance(expected_sha, str) or not SHA256.fullmatch(expected_sha):
            raise ValueError('Checksum cache koreksi tidak valid.')
        actual_sha = sha256(cache_path)
        if actual_sha != expected_sha:
            raise ValueError('Checksum cache koreksi berubah; jangan memakai key yang belum diverifikasi ulang.')
        cache = json.loads(cache_path.read_text(encoding='utf-8'))
        if not isinstance(cache, dict) or cache.get('schema_version') != 1:
            raise ValueError('Format cache koreksi tidak didukung.')
        if cache.get('visibility') != 'coach_only_after_done':
            raise ValueError('Cache tidak memiliki kebijakan hanya coach setelah done.')
        if cache.get('task_id') != task.get('id') or cache.get('skill') != task.get('skill'):
            raise ValueError('Cache koreksi milik tugas/skill lain.')
        numbers = task.get('question_numbers')
        if (not isinstance(numbers, list) or not numbers or
                len(numbers) != len(set(numbers)) or
                not all(isinstance(n, str) and n.isdigit() for n in numbers) or
                cache.get('question_numbers') != numbers):
            raise ValueError('Rentang nomor key tidak cocok dengan materi.')
        if cache.get('source_version') != task.get('source_version'):
            raise ValueError('Versi cache koreksi tidak cocok dengan materi.')
        source = cache.get('source', {})
        provenance = json.loads((Path(root) / 'materials/PROVENANCE.json').read_text(encoding='utf-8'))
        declared_source = provenance.get('sources', {}).get(task['skill'].lower(), {})
        if (source.get('url') != task.get('urls', {}).get('source') or
                source.get('url') != declared_source.get('url') or
                source.get('sha256') != declared_source.get('sha256') or
                not isinstance(source.get('sha256'), str) or not SHA256.fullmatch(source['sha256']) or
                source.get('pages') != declared_source.get('pages')):
            raise ValueError('Provenance sumber key tidak cocok dengan PDF resmi versi materi.')
        if (cache.get('verification', {}).get('status') != 'verified_from_official_source' or
                not cache.get('verified_date') or not cache.get('verification', {}).get('method')):
            raise ValueError('Cache belum memiliki bukti pemeriksaan sumber resmi.')
        prompt = task.get('local', {})
        mapping = cache.get('prompt', {})
        if (mapping.get('path') != prompt.get('prompt') or
                mapping.get('sha256') != prompt.get('prompt_sha256') or
                mapping.get('source_pages') != task.get('source_pages')):
            raise ValueError('Pemetaan prompt/key tidak cocok dengan versi tugas.')
        prompt_path = project_file(root, prompt.get('prompt'), 'materials')
        if not prompt_path.is_file() or sha256(prompt_path) != mapping.get('sha256'):
            raise ValueError('File prompt tidak tersedia atau checksum berubah.')
        output = provenance.get('outputs', {}).get(task['id'], {})
        if (output.get('file') != mapping.get('path') or output.get('sha256') != mapping.get('sha256') or
                output.get('pages') != mapping.get('source_pages')):
            raise ValueError('Prompt tidak cocok dengan provenance ekstraksi asli.')
        key = cache.get('key', {})
        key_pages = task.get('key_pages')
        if (key.get('url') != task.get('urls', {}).get('key') or
                key.get('source_pages') != key_pages or not isinstance(key_pages, list) or not key_pages):
            raise ValueError('Halaman/URL key tidak cocok dengan katalog.')
        raw_pages = key.get('page_texts', [])
        if not isinstance(raw_pages, list) or [p.get('page') for p in raw_pages if isinstance(p, dict)] != key_pages:
            raise ValueError('Cuplikan halaman key tidak lengkap.')
        parsed_entries = []
        policies = []
        for item in raw_pages:
            entries, policy = parse_key_page(item.get('text'), item['page'])
            parsed_entries.extend(entries)
            if policy:
                policies.append(policy)
        covered = [q for item in parsed_entries for q in item['question_numbers']]
        if covered != numbers or key.get('entries') != parsed_entries:
            raise ValueError('Isi key/rentang nomor tidak sesuai cuplikan sumber.')
        if key.get('optional_words_and_alternatives_policy') != ' '.join(policies):
            raise ValueError('Aturan alternatif jawaban tidak cocok dengan key sumber.')
        if task['skill'] == 'Listening':
            instruction = cache.get('answer_instruction', {})
            if (instruction.get('source_page') not in task.get('source_pages', []) or
                    instruction.get('max_words') != 3 or instruction.get('allow_number') is not True or
                    instruction.get('text') != 'Write NO MORE THAN THREE WORDS AND/OR A NUMBER for each answer.'):
                raise ValueError('Batas kata Listening dari prompt belum tersimpan dengan benar.')
            transcript = cache.get('transcript', {})
            if (transcript.get('url') != task.get('urls', {}).get('transcript') or
                    transcript.get('source_pages') != task.get('transcript_pages') or
                    not transcript.get('source_pages')):
                raise ValueError('Versi/halaman transcript tidak cocok dengan materi.')
            pages = transcript.get('page_texts', [])
            if ([p.get('page') for p in pages if isinstance(p, dict)] != transcript['source_pages'] or
                    not all(isinstance(p.get('text'), str) and p['text'].strip() for p in pages) or
                    transcript.get('timestamps_available') is not False):
                raise ValueError('Transcript lokal tidak lengkap atau timestamp belum terbukti.')
        else:
            if cache.get('transcript') is not None:
                raise ValueError('Reading tidak memerlukan transcript Listening.')
            passage = cache.get('reading_text', {})
            if (passage.get('source_pages') != task.get('source_pages') or
                    [p.get('page') for p in passage.get('page_texts', []) if isinstance(p, dict)] != task.get('source_pages') or
                    not all(isinstance(p.get('text'), str) and p['text'].strip() for p in passage.get('page_texts', []))):
                raise ValueError('Teks bukti Reading lokal tidak lengkap.')
        result.update(status='passed', path=metadata['path'], cache_sha256=actual_sha,
                      source_sha256=source['sha256'], question_numbers=numbers,
                      verified_date=cache['verified_date'],
                      reasons=['Cache lokal sesuai source version, prompt, rentang soal dan provenance resmi.'])
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result.update(status='failed', reasons=[str(exc)])
    return result


def learner_packet(task):
    """Whitelist learner material; never return cache paths, keys or transcripts."""
    local = task.get('local', {})
    assets = {}
    for key in ('prompt', 'audio'):
        relative = local.get(key)
        if relative is not None:
            path = Path(relative)
            suffixes = ('.pdf',) if key == 'prompt' else ('.mp3', '.wav', '.m4a', '.ogg', '.webm')
            if (path.is_absolute() or '..' in path.parts or not path.parts or
                    path.parts[0] != 'materials' or path.suffix.lower() not in suffixes):
                raise ValueError('Paket Tata hanya boleh memuat asset learner dalam materials/.')
        assets[key] = relative
    packet = {key: task[key] for key in ('id', 'skill', 'title', 'question_type',
                                       'question_numbers', 'provider', 'source_label',
                                       'source_version') if key in task}
    packet['local'] = assets
    packet['minutes'] = task.get('suggested_session', {}).get('minutes', 20)
    packet['result_collection'] = {
        key: task.get('result_collection', {}).get(key) for key in ('primary', 'fallback')}
    packet['instruction'] = ('Kerjakan prompt lokal; Tata menekan Play sendiri bila ada audio. '
                             'Kirim respons awal/screenshot, lalu done untuk review.')
    return packet


def main():
    parser = argparse.ArgumentParser(description='Periksa cache koreksi tanpa menampilkan jawaban.')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--task', help='ID tugas; kosong untuk semua tugas Listening/Reading.')
    args = parser.parse_args()
    catalog = json.loads((args.root / 'materials.json').read_text(encoding='utf-8'))
    tasks = [t for t in catalog['tasks'] if t.get('skill') in ('Listening', 'Reading')]
    if args.task:
        tasks = [t for t in tasks if t['id'] == args.task]
        if not tasks:
            parser.error('Tugas Listening/Reading tidak ditemukan.')
    results = [check_reference(args.root, task) for task in tasks]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0 if all(r['status'] == 'passed' for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
