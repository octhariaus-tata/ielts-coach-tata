#!/usr/bin/env python3
"""Sinkronisasi data coach yang aman; Python 3.8+, Git, tanpa paket tambahan."""

import argparse
from contextlib import contextmanager
import datetime
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlparse


TOP_LEVEL = frozenset({
    "AGENTS.md", "PROFILE.md", "PLAN.md", "PROGRESS.md", "AUDIT.md",
    "README.md", "STATUS.md", "TASK_BANK.md", "SETUP.md",
    "IMPLEMENTATION_REPORT.md", "SYSTEM.md", "ADAPTATION.md", "materials.json", ".gitignore", ".gitattributes",
})
DIRECTORIES = frozenset({"sessions", "evidence", "materials", "coach_refs", "feedback", "learning", "scripts", "tests"})
SKILL_FILES = frozenset({
    ".agents/skills/ielts-teacher/SKILL.md",
    ".agents/skills/ielts-teacher/agents/openai.yaml",
    ".agents/skills/ielts-coach/SKILL.md",
    ".agents/skills/ielts-coach/agents/openai.yaml",
    ".agents/skills/ielts-github-sync/SKILL.md",
    ".agents/skills/ielts-github-sync/agents/openai.yaml",
})
AUTHORIZED_REPOSITORY = "https://github.com/octhariaus-tata/ielts-coach-tata.git"
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".keystore")
SENSITIVE_NAMES = frozenset({
    "credentials", "credentials.json", "secrets.json", "token", "token.json",
    "id_rsa", "id_ed25519", "id_dsa", "id_ecdsa", "authorized_keys",
})
SECRET_PATTERNS = (
    re.compile(br"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    re.compile(br"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(br"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(br"\bAKIA[A-Z0-9]{16}\b"),
    re.compile(br"\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b"),
    re.compile(br"(?i)(?:password|api[_-]?key|access[_-]?token|client[_-]?secret)"
               br"\s*[=:]\s*[\"']?[^\s\"']{12,}"),
)
TIMEOUT = 30


class SyncError(Exception):
    def __init__(self, code, message, status="error"):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def allowed_path(path):
    """Whitelist, bukan glob Git; jangan ikuti symlink atau folder tersembunyi."""
    parts = PurePosixPath(path).parts
    if not parts or PurePosixPath(path).is_absolute() or ".." in parts:
        return False
    if path in TOP_LEVEL or path in SKILL_FILES:
        return True
    if parts[0] not in DIRECTORIES or len(parts) < 2:
        return False
    if any(p.startswith(".") and p != ".gitkeep" for p in parts[1:]):
        return False
    name = parts[-1].lower()
    return name not in SENSITIVE_NAMES and not name.endswith(SENSITIVE_SUFFIXES)


def contains_secret(data):
    return any(pattern.search(data) for pattern in SECRET_PATTERNS)


def safe_file(root, path):
    candidate = root / path
    if not allowed_path(path):
        raise SyncError("blocked_path", "Ada file di luar daftar data coaching.")
    for parent in [candidate] + list(candidate.parents):
        if parent == root:
            break
        if parent.is_symlink():
            raise SyncError("symlink_blocked", "Symlink tidak boleh dipublikasikan.")
    if candidate.exists() and candidate.is_file():
        # Scan juga binary: screenshot disimpan utuh, token yang jelas tetap diblokir.
        with candidate.open("rb") as handle:
            tail = b""
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                if contains_secret(tail + chunk):
                    raise SyncError("secret_blocked", "Pola credential ditemukan; sinkronisasi dihentikan.")
                tail = chunk[-512:]


class Git:
    def __init__(self, root):
        self.root = root

    def run(self, *args, check=True, binary=False):
        environment = os.environ.copy()
        environment["GIT_TERMINAL_PROMPT"] = "0"
        environment["GCM_INTERACTIVE"] = "never"
        environment["GIT_EDITOR"] = "true"
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root)] + list(args),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=environment, timeout=TIMEOUT,
            )
        except FileNotFoundError:
            raise SyncError("git_missing", "Git belum tersedia di laptop ini.", "local-only")
        except subprocess.TimeoutExpired:
            raise SyncError("git_timeout", "Git melewati batas waktu; data lokal tetap tersimpan.", "offline")
        if check and result.returncode:
            # stderr bisa berisi URL/token credential: jangan pernah keluarkan.
            raise SyncError("git_failed", "Operasi Git gagal; data lokal tetap tersimpan.")
        output = result.stdout if binary else result.stdout.decode("utf-8", "replace").strip()
        return result.returncode, output

    def revision(self, name):
        code, output = self.run("rev-parse", "--verify", name, check=False)
        return None if code else output


def changes(git):
    _, output = git.run("-c", "status.renames=false", "status", "--porcelain=v1", "-z",
                        "--untracked-files=all", binary=True)
    result = []
    for entry in output.split(b"\0"):
        if not entry:
            continue
        state = entry[:2].decode("ascii", "replace")
        path = entry[3:].decode("utf-8", "surrogateescape")
        result.append({"path": path, "index": state[0], "worktree": state[1],
                       "allowed": allowed_path(path)})
    return result


def repository(git):
    code, top = git.run("rev-parse", "--show-toplevel", check=False)
    if code or Path(top).resolve() != git.root:
        raise SyncError("not_project_repository", "Folder ini belum menjadi clone repo coaching.", "local-only")
    code, branch = git.run("symbolic-ref", "--short", "HEAD", check=False)
    if code or branch != "main":
        raise SyncError("wrong_branch", "Buka branch main sebelum sinkronisasi.", "conflict")


def canonical_origin(value, allow_local=False):
    """Hanya GitHub HTTPS/SSH standar; URL dengan credential tidak diterima."""
    scp = re.fullmatch(r"git@github\.com:([^\s?#]+)", value, re.IGNORECASE)
    if scp:
        path = scp.group(1)
    else:
        parsed = urlparse(value)
        if parsed.scheme in ("https", "ssh") and parsed.hostname == "github.com":
            try:
                port = parsed.port
            except ValueError:
                return None
            if parsed.query or parsed.fragment or parsed.password:
                return None
            if parsed.scheme == "https" and (parsed.username or port not in (None, 443)):
                return None
            if parsed.scheme == "ssh" and (parsed.username != "git" or port not in (None, 22)):
                return None
            path = parsed.path.lstrip("/")
        elif allow_local and Path(value).is_absolute():
            return "local:" + str(Path(value).resolve())
        else:
            return None
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    if len(path.split("/")) != 2 or any(part in ("", ".", "..") for part in path.split("/")):
        return None
    return "github.com/" + path.lower()


def origin_configured(git, expected_origin=AUTHORIZED_REPOSITORY):
    code, urls = git.run("remote", "get-url", "--all", "origin", check=False)
    if code or not urls:
        return False
    _, push_urls = git.run("remote", "get-url", "--push", "--all", "origin", check=False)
    if urls != push_urls or len(urls.splitlines()) != 1:
        raise SyncError("different_push_remote", "Origin fetch/push berbeda; periksa konfigurasi tanpa mengubah data.")
    # Hanya API test boleh menentukan bare repo lokal; CLI selalu memakai tujuan resmi.
    allow_local = expected_origin != AUTHORIZED_REPOSITORY
    expected = canonical_origin(expected_origin, allow_local=allow_local)
    if not expected or canonical_origin(urls, allow_local=allow_local) != expected:
        raise SyncError("wrong_origin", "Origin bukan repo coaching yang diizinkan; periksa tujuan sebelum sinkronisasi.")
    _, refspecs = git.run("config", "--get-all", "remote.origin.fetch", check=False)
    accepted = {"+refs/heads/*:refs/remotes/origin/*", "refs/heads/*:refs/remotes/origin/*",
                "+refs/heads/main:refs/remotes/origin/main", "refs/heads/main:refs/remotes/origin/main"}
    if not accepted.intersection(refspecs.splitlines()):
        raise SyncError("unsupported_fetch", "Origin belum dikonfigurasi untuk memeriksa main.")
    return True


def fetch(git):
    try:
        code, _ = git.run("fetch", "--prune", "--no-tags", "origin", check=False)
    except SyncError as error:
        if error.code == "git_timeout":
            raise
        raise SyncError("fetch_failed", "Remote belum dapat diperiksa; data lokal tetap tersimpan.", "offline")
    if code:
        raise SyncError("fetch_failed", "Remote belum dapat diperiksa; periksa koneksi/akses GitHub.", "offline")


def snapshot(git, remote_verified=False):
    records = changes(git)
    local_head = git.revision("HEAD")
    remote_head = git.revision("refs/remotes/origin/main")
    ahead, behind = 0, 0
    if local_head and remote_head:
        _, counts = git.run("rev-list", "--left-right", "--count", "HEAD...refs/remotes/origin/main")
        ahead, behind = map(int, counts.split())
    elif local_head:
        ahead = int(git.run("rev-list", "--count", "HEAD")[1])
    allowed_changes = [item["path"] for item in records if item["allowed"]]
    staged_foreign = [item["path"] for item in records
                      if not item["allowed"] and item["index"] not in (" ", "?")]
    conflicts = [item["path"] for item in records
                 if "U" in (item["index"], item["worktree"])
                 or (item["index"] + item["worktree"]) in ("AA", "DD")]
    if conflicts or (ahead and behind):
        state = "conflict"
    elif not remote_head:
        state = "unpublished"
    elif behind:
        state = "behind"
    elif ahead:
        state = "ahead"
    elif allowed_changes or staged_foreign:
        state = "unpublished"
    elif remote_verified:
        state = "synced"
    else:
        state = "error"
    return {
        "status": state, "branch": "main", "remote_verified": remote_verified,
        "local_head": local_head, "remote_head": remote_head,
        "ahead": ahead, "behind": behind,
        "pending_files": allowed_changes,
        "foreign_files": [item["path"] for item in records if not item["allowed"]],
        "staged_foreign_files": staged_foreign, "conflicts": conflicts,
    }


def check_commits(git, base):
    """Periksa SEMUA commit yang akan dikirim, termasuk file yang kemudian dihapus."""
    target = (base + "..HEAD") if base else "HEAD"
    _, revisions = git.run("rev-list", target)
    for revision in revisions.splitlines():
        _, raw = git.run("diff-tree", "--root", "--no-commit-id", "-m", "-r", "--no-renames", "--name-only", "-z",
                         revision, binary=True)
        for encoded in raw.split(b"\0"):
            if not encoded:
                continue
            path = encoded.decode("utf-8", "surrogateescape")
            if not allowed_path(path):
                raise SyncError("foreign_commit", "Riwayat yang akan dikirim memuat file di luar data coaching.")
            _, tree_entry = git.run("ls-tree", revision, "--", path)
            if tree_entry.startswith("120000 ") or tree_entry.startswith("160000 "):
                raise SyncError("symlink_blocked", "Riwayat memuat symlink/submodule; push dihentikan.")
            if not tree_entry:
                continue  # Penghapusan: commit pembuat file diperiksa sendiri.
            code, data = git.run("show", revision + ":" + path, check=False, binary=True)
            if not code and contains_secret(data):
                raise SyncError("secret_blocked", "Riwayat memuat pola credential; push dihentikan.")


def save_status(root, result):
    """Cache lokal atomik; cache tidak termasuk whitelist dan tidak di-commit."""
    result["checked_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result["advisory"] = "Gunakan satu laptop aktif; pindah setelah status synced."
    local_dir = root / ".local"
    temporary = None
    try:
        if local_dir.is_symlink():
            raise OSError("Local cache directory is a symlink")
        local_dir.mkdir(exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(local_dir),
                                         prefix="sync-", suffix=".tmp", delete=False) as handle:
            temporary = handle.name
            json.dump(result, handle, ensure_ascii=True, indent=2)
            handle.write("\n")
        os.replace(temporary, str(local_dir / "sync.json"))
    except OSError:
        result["cache_saved"] = False
        if temporary:
            try:
                os.unlink(temporary)
            except OSError:
                pass
    else:
        result["cache_saved"] = True


@contextmanager
def sync_lock(root):
    """Serialize Git operations from coaching and hourly runs on this clone."""
    local = root / '.local'
    path = local / 'sync.lock'
    if local.is_symlink() or path.is_symlink():
        raise SyncError('unsafe_lock_path', 'Path lock Git tidak aman; sinkronisasi dihentikan.')
    local.mkdir(exist_ok=True)
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
                raise SyncError('sync_busy', 'Operasi Git lain sedang berjalan; coba pada jadwal berikutnya.', 'busy')
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
                raise SyncError('sync_busy', 'Operasi Git lain sedang berjalan; coba pada jadwal berikutnya.', 'busy')
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def synchronize(root, action, message, expected_origin=AUTHORIZED_REPOSITORY):
    root = Path(root).resolve()
    try:
        with sync_lock(root):
            return _synchronize(root, action, message, expected_origin)
    except SyncError as error:
        return {'action': action, 'status': error.status, 'error': error.code,
                'message': error.message, 'remote_verified': False}, 1
    except OSError:
        return {'action': action, 'status': 'error', 'error': 'sync_lock_io',
                'message': 'Lock Git tidak dapat disimpan; data lokal dipertahankan.', 'remote_verified': False}, 1


def _synchronize(root, action, message, expected_origin=AUTHORIZED_REPOSITORY):
    root = Path(root).resolve()
    git = Git(root)
    result = {"action": action, "status": "error", "remote_verified": False}
    try:
        repository(git)
        configured = origin_configured(git, expected_origin=expected_origin)
        result.update(snapshot(git))
        if action == "push" and result["staged_foreign_files"]:
            raise SyncError("staged_foreign", "Ada file asing yang sudah staged; coach tidak akan mengirimkannya.")
        if not configured:
            result.update(status="unpublished", message="Origin belum dipasang; data masih lokal.")
            return result, 0 if action == "status" else 1
        fetch(git)
        result.update(snapshot(git, remote_verified=True))
        if action == "status":
            return result, 0
        if result["conflicts"] or (result["ahead"] and result["behind"]):
            raise SyncError("diverged", "Riwayat berbeda; pertahankan kedua catatan dan selesaikan konflik dahulu.", "conflict")
        if action == "pull":
            if result["pending_files"] or result["staged_foreign_files"]:
                if result["behind"]:
                    message = ("Ada perubahan lokal dan remote lebih baru; pertahankan seluruh record/bukti "
                               "dan minta coach merekonsiliasi perubahan serta ringkasan sebelum sinkronisasi. "
                               "Jangan reset, force-push, atau mengulang push/pull untuk menimpa data.")
                else:
                    message = ("Ada perubahan lokal; simpan dan baca ulang catatan dahulu, lalu gunakan push "
                               "jika remote tetap sama. Jangan menghapus perubahan untuk membuat pull berhasil.")
                raise SyncError("dirty_worktree", message, result["status"])
            if not result["remote_head"]:
                raise SyncError("remote_main_missing", "Remote main belum ada; publish dengan push dahulu.", "unpublished")
            code, _ = git.run("merge", "--ff-only", "refs/remotes/origin/main", check=False)
            if code:
                raise SyncError("pull_blocked", "Fast-forward ditolak; perubahan lokal tetap dipertahankan.", "conflict")
        elif action == "push":
            if result["behind"]:
                if result["pending_files"] or result["staged_foreign_files"]:
                    message = ("Remote lebih baru dan ada perubahan lokal; pertahankan seluruh record/bukti "
                               "dan minta coach merekonsiliasi perubahan serta ringkasan. "
                               "Jangan mengulang push/pull, reset, atau force-push.")
                else:
                    message = "Remote lebih baru; gunakan pull fast-forward lalu periksa ulang status."
                raise SyncError("behind_remote", message, "behind")
            for path in result["pending_files"]:
                safe_file(root, path)
            check_commits(git, result["remote_head"])
            # Tidak memakai git add .; setiap path diverifikasi dan disebut eksplisit.
            for path in result["pending_files"]:
                git.run("add", "--", path)
            code, _ = git.run("diff", "--cached", "--quiet", check=False)
            if code == 1:
                code, _ = git.run("commit", "--message", message, check=False)
                if code:
                    raise SyncError("commit_failed", "Commit gagal; data dan staged files tetap ada. Periksa identitas Git.")
            elif code:
                raise SyncError("index_failed", "Index Git tidak dapat diperiksa; push dihentikan.")
            if not git.revision("HEAD"):
                raise SyncError("nothing_to_publish", "Belum ada commit coaching untuk dikirim.", "unpublished")
            check_commits(git, result["remote_head"])
            code, _ = git.run("push", "origin", "refs/heads/main:refs/heads/main", check=False)
            if code:
                raise SyncError("push_failed", "Push gagal; commit lokal tetap tersimpan dan belum tersinkron.", "offline")
            fetch(git)
        result.update(snapshot(git, remote_verified=True))
        result["message"] = "Data coaching sudah tersinkron." if result["status"] == "synced" else "Data lokal tetap tersimpan; lihat status."
        return result, 0
    except SyncError as error:
        # Baca ulang setelah kegagalan agar commit lokal/pending terbaru tercatat.
        try:
            result.update(snapshot(git, remote_verified=False))
        except (SyncError, ValueError):
            pass
        result.update(status=error.status, error=error.code, message=error.message,
                      remote_verified=False)
        return result, 1
    except (OSError, ValueError):
        result.update(status="error", error="local_io_error",
                      message="Data lokal tidak dapat diperiksa; tidak ada klaim sinkronisasi.", remote_verified=False)
        return result, 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "pull", "push"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="Folder clone coaching; default folder induk scripts/.")
    parser.add_argument("--message", default="Simpan data IELTS Coach Tata",
                        help="Pesan commit saat push.")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    if not root.is_dir():
        result, code = {"action": arguments.action, "status": "error", "error": "root_missing",
                        "message": "Folder coaching tidak tersedia.", "remote_verified": False}, 1
    else:
        import session
        try:
            with session.mutation_lock(root):
                result, code = synchronize(root, arguments.action, arguments.message)
        except (ValueError, OSError) as error:
            busy = isinstance(error, ValueError) and str(error).startswith('Pencatatan sedang digunakan chat lain')
            result, code = {'action': arguments.action, 'status': 'busy' if busy else 'error',
                            'error': 'session_busy' if busy else 'session_lock_io', 'remote_verified': False,
                            'message': 'Catatan sedang ditulis; coba setelah writer selesai.' if busy else
                                       'Lock pencatatan tidak dapat diperiksa; data lokal tetap tersimpan.'}, 1
        save_status(root, result)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return code


if __name__ == "__main__":
    sys.exit(main())
