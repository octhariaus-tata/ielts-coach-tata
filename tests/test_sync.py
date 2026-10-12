"""Integration tests: repo sementara, dua laptop simulasi, tanpa GitHub/network."""

import json
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sync.py"
MODULE_SPEC = importlib.util.spec_from_file_location("ielts_sync", SCRIPT)
SYNC = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(SYNC)


@unittest.skipUnless(shutil.which("git"), "Git diperlukan")
class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ielts-sync-test-")
        self.base = Path(self.temporary.name)
        self.remote = self.base / "remote.git"
        self.a = self.base / "laptop-a"
        self.b = self.base / "laptop-b"
        self.git(self.base, "init", "--bare", "--initial-branch=main", str(self.remote))
        self.git(self.base, "clone", str(self.remote), str(self.a))
        self.configure(self.a)
        self.write(self.a, ".gitignore", ".local/\n__pycache__/\n")
        self.write(self.a, "PROFILE.md", "Profil simulasi, bukan data Tata.\n")
        self.write(self.a, "PROGRESS.md", "TES SISTEM\n")
        self.git(self.a, "add", "--", ".gitignore", "PROFILE.md", "PROGRESS.md")
        self.git(self.a, "commit", "-m", "Initial simulation")
        self.git(self.a, "push", "-u", "origin", "main")
        self.git(self.base, "clone", str(self.remote), str(self.b))
        self.configure(self.b)

    def tearDown(self):
        self.temporary.cleanup()

    def git(self, root, *arguments, check=True):
        result = subprocess.run(["git", "-C", str(root)] + list(arguments),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=30)
        if check and result.returncode:
            self.fail("Git fixture failed: " + result.stderr)
        return result.stdout.strip()

    def configure(self, root):
        self.git(root, "config", "user.name", "System Test")
        self.git(root, "config", "user.email", "test@example.invalid")

    def write(self, root, filename, contents):
        target = root / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contents, bytes):
            target.write_bytes(contents)
        else:
            target.write_text(contents, encoding="utf-8")

    def sync(self, root, action, expected=0):
        # Production CLI does not allow an origin override; fixtures inject it only through API.
        data, code = SYNC.synchronize(root, action, "Simpan tes sistem", expected_origin=str(self.remote))
        SYNC.save_status(root, data)
        self.assertEqual(code, expected, json.dumps(data))
        return data

    def head(self, root):
        return self.git(root, "rev-parse", "HEAD")

    def test_two_copies_roundtrip_binary_and_repeated_push(self):
        image = b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 4
        prompt = b"%PDF-1.7\nPrompt-only official material simulation\n%%EOF\n"
        audio = b"ID3\x04\x00\x00\x00\x00\x00\x00" + bytes(range(256)) * 8
        self.write(self.a, "sessions/2026-10-12-system-test.json", '{"kind":"system-test"}\n')
        self.write(self.a, "evidence/system-test/screenshot.png", image)
        self.write(self.a, "materials/system-test/prompt.pdf", prompt)
        self.write(self.a, "materials/system-test/audio.mp3", audio)
        result = self.sync(self.a, "push")
        self.assertEqual(result["status"], "synced")
        self.assertTrue(result["remote_verified"])
        published_head = self.head(self.a)
        self.assertEqual(self.sync(self.a, "push")["status"], "synced")
        self.assertEqual(self.head(self.a), published_head, "Repeated done/push must not add a commit")
        self.assertEqual(self.sync(self.b, "status")["status"], "behind")
        self.assertEqual(self.sync(self.b, "pull")["status"], "synced")
        self.assertEqual((self.b / "evidence/system-test/screenshot.png").read_bytes(), image)
        self.assertEqual((self.b / "materials/system-test/prompt.pdf").read_bytes(), prompt)
        self.assertEqual((self.b / "materials/system-test/audio.mp3").read_bytes(), audio)
        self.assertEqual(self.head(self.b), published_head)
        self.assertNotIn(".local/", self.git(self.a, "ls-files"))

    def test_dirty_local_is_preserved_on_pull(self):
        self.write(self.a, "PLAN.md", "New simulated plan\n")
        self.sync(self.a, "push")
        self.write(self.b, "PROGRESS.md", "Pending simulated session\n")
        before = self.head(self.b)
        result = self.sync(self.b, "pull", expected=1)
        self.assertEqual(result["error"], "dirty_worktree")
        self.assertEqual(self.head(self.b), before)
        self.assertEqual((self.b / "PROGRESS.md").read_text(), "Pending simulated session\n")

    def test_divergent_histories_not_reset_or_merged(self):
        self.write(self.a, "PLAN.md", "Laptop A\n")
        self.sync(self.a, "push")
        self.write(self.b, "STATUS.md", "Laptop B pending\n")
        self.git(self.b, "add", "--", "STATUS.md")
        self.git(self.b, "commit", "-m", "Unsynced B")
        before = self.head(self.b)
        for action in ("pull", "push"):
            result = self.sync(self.b, action, expected=1)
            self.assertEqual(result["status"], "conflict")
            self.assertEqual(result["error"], "diverged")
            self.assertEqual(self.head(self.b), before)
        self.assertTrue((self.b / "STATUS.md").exists())

    def test_unknown_unstaged_is_preserved_but_not_published(self):
        self.write(self.a, "private-notes.txt", "private information\n")
        self.write(self.a, ".env", "PRIVATE_CONFIGURATION=yes\n")
        self.write(self.a, "sessions/new-session.md", "TES SISTEM\n")
        result = self.sync(self.a, "push")
        self.assertEqual(result["status"], "synced")
        self.assertIn("private-notes.txt", result["foreign_files"])
        self.sync(self.b, "pull")
        self.assertFalse((self.b / "private-notes.txt").exists())
        self.assertFalse((self.b / ".env").exists())
        self.assertTrue((self.a / "private-notes.txt").exists())

    def test_staged_foreign_refused_without_unstaging(self):
        self.write(self.a, "private-notes.txt", "do not publish\n")
        self.git(self.a, "add", "--", "private-notes.txt")
        self.write(self.a, "sessions/new-session.md", "TES SISTEM\n")
        before = self.head(self.a)
        result = self.sync(self.a, "push", expected=1)
        self.assertEqual(result["error"], "staged_foreign")
        self.assertEqual(self.head(self.a), before)
        self.assertIn("private-notes.txt", self.git(self.a, "diff", "--cached", "--name-only"))
        self.sync(self.b, "pull")
        self.assertFalse((self.b / "private-notes.txt").exists())

    def test_foreign_file_committed_then_deleted_cannot_leak_in_history(self):
        self.write(self.a, "private-notes.txt", "must stay local\n")
        self.git(self.a, "add", "--", "private-notes.txt")
        self.git(self.a, "commit", "-m", "Mistaken local commit")
        self.git(self.a, "rm", "--", "private-notes.txt")
        self.git(self.a, "commit", "-m", "Delete file")
        result = self.sync(self.a, "push", expected=1)
        self.assertEqual(result["error"], "foreign_commit")
        self.assertNotEqual(self.head(self.a), self.head(self.b))

    def test_offline_push_keeps_pending_and_does_not_claim_synced(self):
        unreachable = self.base / "temporarily-unreachable.git"
        self.remote.rename(unreachable)
        self.write(self.a, "sessions/pending.md", "TES SISTEM\n")
        for action in ("status", "push"):
            result = self.sync(self.a, action, expected=1)
            self.assertEqual(result["status"], "offline")
            self.assertFalse(result["remote_verified"])
            self.assertIn("sessions/pending.md", result["pending_files"])
        self.assertTrue((self.a / "sessions/pending.md").exists())
        cached = json.loads((self.a / ".local/sync.json").read_text())
        self.assertEqual(cached["status"], "offline")
        unreachable.rename(self.remote)
        self.assertEqual(self.sync(self.a, "push")["status"], "synced")

    def test_remote_rejected_push_keeps_local_commit_for_retry(self):
        # Receive config works on Windows too; no executable hook needed.
        self.git(self.remote, "config", "receive.denyNonFastForwards", "true")
        self.git(self.remote, "config", "receive.denyCurrentBranch", "refuse")
        self.git(self.remote, "config", "core.bare", "false")
        self.write(self.a, "sessions/pending.md", "TES SISTEM\n")
        before = self.head(self.a)
        result = self.sync(self.a, "push", expected=1)
        self.assertEqual(result["error"], "push_failed")
        self.assertEqual(result["status"], "offline")
        self.assertNotEqual(self.head(self.a), before)
        retained = self.head(self.a)
        self.assertEqual(result["ahead"], 1)
        self.git(self.remote, "config", "core.bare", "true")
        self.assertEqual(self.sync(self.a, "push")["status"], "synced")
        self.assertEqual(self.head(self.a), retained)

    def test_secret_and_symlink_are_refused(self):
        secret = "gh" + "p_" + "a" * 36
        self.write(self.a, "sessions/accidental-token.md", secret + "\n")
        result = self.sync(self.a, "push", expected=1)
        self.assertEqual(result["error"], "secret_blocked")
        self.assertNotIn(secret, json.dumps(result))
        (self.a / "sessions/accidental-token.md").unlink()
        target = self.a / "evidence/link.txt"
        target.parent.mkdir(exist_ok=True)
        try:
            target.symlink_to(self.a / "PROFILE.md")
        except OSError:
            self.skipTest("Symlink creation not available")
        result = self.sync(self.a, "push", expected=1)
        self.assertEqual(result["error"], "symlink_blocked")

    def test_no_repo_and_no_origin_are_local_only(self):
        outside = self.base / "ordinary-folder"
        outside.mkdir()
        result = self.sync(outside, "status", expected=1)
        self.assertEqual(result["status"], "local-only")
        self.git(self.a, "remote", "remove", "origin")
        result = self.sync(self.a, "status")
        self.assertEqual(result["status"], "unpublished")
        self.assertFalse(result["remote_verified"])

    def test_ancestor_repo_is_not_mistaken_for_project_repo(self):
        nested = self.a / "subfolder"
        nested.mkdir()
        result = self.sync(nested, "push", expected=1)
        self.assertEqual(result["error"], "not_project_repository")

    def test_wrong_branch_and_different_push_url_refused(self):
        self.git(self.a, "checkout", "-b", "other")
        result = self.sync(self.a, "status", expected=1)
        self.assertEqual(result["error"], "wrong_branch")
        self.git(self.a, "checkout", "main")
        self.git(self.a, "remote", "set-url", "--push", "origin", str(self.base / "different.git"))
        result = self.sync(self.a, "push", expected=1)
        self.assertEqual(result["error"], "different_push_remote")

    def test_cli_refuses_unapproved_origin_without_fetch_or_stage(self):
        self.write(self.a, "sessions/pending.md", "TES SISTEM\n")
        before = self.head(self.a)
        result = subprocess.run([sys.executable, str(SCRIPT), "push", "--root", str(self.a)],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=45)
        self.assertEqual(result.returncode, 1)
        data = json.loads(result.stdout)
        self.assertEqual(data["error"], "wrong_origin")
        self.assertFalse(data["remote_verified"])
        self.assertEqual(self.head(self.a), before)
        self.assertEqual(self.git(self.a, "diff", "--cached", "--name-only"), "")
        self.assertEqual(result.stderr, "")

    def test_exact_github_destination_https_and_ssh(self):
        expected = "github.com/octhariaus-tata/ielts-coach-tata"
        for url in ("https://github.com/octhariaus-tata/ielts-coach-tata.git",
                    "git@github.com:octhariaus-tata/ielts-coach-tata.git",
                    "ssh://git@github.com/octhariaus-tata/ielts-coach-tata.git"):
            self.assertEqual(SYNC.canonical_origin(url), expected)
        for url in ("https://github.com/someone-else/ielts-coach-tata.git",
                    "https://github.com/octhariaus-tata/other-repo.git"):
            self.git(self.a, "remote", "set-url", "origin", url)
            data, code = SYNC.synchronize(self.a, "push", "Must not send")
            self.assertEqual(code, 1)
            self.assertEqual(data["error"], "wrong_origin")
        self.assertIsNone(SYNC.canonical_origin("https://user:password@github.com/octhariaus-tata/ielts-coach-tata.git"))
        self.assertIsNone(SYNC.canonical_origin("https://github.com.example.com/octhariaus-tata/ielts-coach-tata.git"))


if __name__ == "__main__":
    unittest.main()
