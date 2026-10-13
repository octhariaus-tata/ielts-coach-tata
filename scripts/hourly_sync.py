#!/usr/bin/env python3
"""One bounded scheduled backup run; Python 3.8+, no daemon or new credential."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import adaptation
import references
import session
import sync as git_sync


def save_run(root, result):
    result['checked_at'] = session.now()
    local = root / '.local'
    path = local / 'scheduled-sync.json'
    if not root.is_dir() or local.is_symlink() or path.is_symlink():
        result['run_log_saved'] = False
        return
    try:
        session.json_write(path, result)
    except (OSError, ValueError):
        result['run_log_saved'] = False
    else:
        result['run_log_saved'] = True


def run(root, message='Sinkronisasi otomatis IELTS Coach Tata'):
    root = Path(root).resolve()
    result = {'action': 'scheduled_sync', 'status': 'error', 'remote_verified': False,
              'synced': False, 'learning_readiness_changed': False}
    try:
        if not root.is_dir() or (root / '.local').is_symlink():
            raise ValueError('Folder project/cache tidak tersedia atau tidak aman.')
        if (root / '.local' / 'implementation-pending.json').exists():
            result.update(status='busy', deferred=True, error='implementation_validation_pending',
                          message='Implementation is awaiting validation; backup deferred without publishing intermediate changes.')
            save_run(root, result)
            return result, 0
        # Lock order: session -> Git, shared with coach.sync_action. Both locks
        # are nonblocking, so another writer defers rather than waiting forever.
        with session.mutation_lock(root):
            records = session.load_sessions(root)
            import lessons
            lessons.load(root)
            lessons.packets(root)
            import scorecard
            scorecard.validate_saved(root)
            adaptation.analyze(root, records=records)
            catalog = json.loads((root / 'materials.json').read_text(encoding='utf-8'))
            for task in catalog['tasks']:
                if task.get('role') in ('primary', 'backup') and task.get('skill') in ('Listening', 'Reading'):
                    checked = references.check_reference(root, task)
                    if checked['status'] != 'passed':
                        raise ValueError('Cache koreksi belum utuh: ' + task['id'])
            session._rebuild(root)  # Already holds the same OS mutation lock.
            action = 'push'
            try:
                git = git_sync.Git(root)
                git_sync.repository(git)
                view = git_sync.snapshot(git)
                if not view['pending_files'] and not view['ahead'] and not view['staged_foreign_files']:
                    action = 'pull'  # Fresh remote check + safe fast-forward; no empty push.
            except git_sync.SyncError:
                pass  # Main sync validation returns the specific repository error.
            synced, code = git_sync.synchronize(root, action, message)
            git_sync.save_status(root, synced)
            result.update(synced)
            result['synced'] = synced.get('status') == 'synced' and synced.get('remote_verified') is True
            result['saved_locally'] = True
            if synced.get('error') == 'sync_busy':
                result.update(status='busy', deferred=True)
                code = 0
    except ValueError as error:
        if str(error).startswith('Pencatatan sedang digunakan chat lain'):
            result.update(status='busy', deferred=True, message='Catatan sedang ditulis; sync ditunda ke jadwal berikutnya.')
            code = 0
        else:
            result.update(status='blocked', message=str(error), error='local_validation_failed')
            code = 1
    except (OSError, KeyError, TypeError) as error:
        result.update(status='blocked', message='Data lokal belum dapat diperiksa; tidak ada push atau penilaian ulang.',
                      error='local_validation_failed')
        code = 1
    save_run(root, result)
    return result, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--message', default='Sinkronisasi otomatis IELTS Coach Tata')
    args = parser.parse_args()
    result, code = run(args.root, args.message)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    sys.exit(main())
