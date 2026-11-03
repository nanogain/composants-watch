import json
import subprocess
import tempfile
import unittest
from unittest import mock
from datetime import timedelta
from pathlib import Path

from composants_watch.publish import build_payload, git_push, write_json
from tests.helpers import NOW

SCORED = {"watchlist": [], "opportunities": [], "unclassified": [],
          "stats": {"listings_seen": 0, "models_with_reference": 0}}


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


class PayloadTest(unittest.TestCase):
    def test_payload_schema_and_status(self):
        health = {"dealabs": {"consecutive_failures": 0, "last_ok": "x", "items": 12},
                  "reddit": {"consecutive_failures": 5, "last_ok": None, "items": 0},
                  "ebay": {"disabled": True}}
        p = build_payload(SCORED, health, NOW)
        self.assertEqual(set(p), {"generated_at", "version", "sources", "watchlist",
                                  "opportunities", "unclassified", "stats"})
        self.assertEqual(p["version"], 1)
        self.assertEqual(p["generated_at"], "2026-11-03T12:00:00Z")
        self.assertEqual(p["sources"]["dealabs"], {"status": "ok", "items": 12, "last_ok": "x"})
        self.assertEqual(p["sources"]["reddit"]["status"], "down")
        self.assertEqual(p["sources"]["ebay"]["status"], "disabled")

    def test_status_ok_below_threshold(self):
        p = build_payload(SCORED, {"reddit": {"consecutive_failures": 4, "last_ok": None, "items": 0}}, NOW)
        self.assertEqual(p["sources"]["reddit"]["status"], "ok")

    def test_last_ok_change_alone_is_not_a_change(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "deals.json"
            h = lambda t: {"dealabs": {"consecutive_failures": 0, "last_ok": t, "items": 3}}
            self.assertTrue(write_json(build_payload(SCORED, h("a"), NOW), path))
            self.assertFalse(write_json(build_payload(SCORED, h("b"), NOW), path))
            down = {"dealabs": {"consecutive_failures": 5, "last_ok": "a", "items": 0}}
            self.assertTrue(write_json(build_payload(SCORED, down, NOW), path))

    def test_write_json_unchanged_returns_false(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "data" / "deals.json"
            self.assertTrue(write_json(build_payload(SCORED, {}, NOW), path))
            self.assertFalse(write_json(build_payload(SCORED, {}, NOW + timedelta(minutes=30)), path))
            self.assertEqual(json.loads(path.read_text())["generated_at"], "2026-11-03T12:00:00Z")
            changed = dict(SCORED, stats={"listings_seen": 3, "models_with_reference": 0})
            self.assertTrue(write_json(build_payload(changed, {}, NOW), path))


class GitPushTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.remote = root / "remote.git"
        self.repo = root / "repo"
        git(root, "init", "-q", "--bare", "-b", "main", str(self.remote))
        git(root, "init", "-q", "-b", "main", str(self.repo))
        git(self.repo, "config", "user.name", "t")
        git(self.repo, "config", "user.email", "t@t")
        (self.repo / "README").write_text("x")
        git(self.repo, "add", "README")
        git(self.repo, "commit", "-qm", "init")
        git(self.repo, "remote", "add", "origin", str(self.remote))
        git(self.repo, "push", "-q", "origin", "main")
        self.rel = "docs/data/deals.json"
        (self.repo / "docs" / "data").mkdir(parents=True)
        (self.repo / self.rel).write_text("{}")
        self.token = root / "token"

    def tearDown(self):
        self.tmp.cleanup()

    def test_git_push_commits_and_pushes_to_local_remote(self):
        ok, msg = git_push(self.repo, self.rel, self.token, NOW)
        self.assertTrue(ok, msg)
        log = git(self.remote, "log", "-1", "--format=%s", "main")
        self.assertTrue(log.startswith("data: mise à jour"))

    def test_nothing_to_commit_still_ok(self):
        git_push(self.repo, self.rel, self.token, NOW)
        ok, msg = git_push(self.repo, self.rel, self.token, NOW)
        self.assertTrue(ok, msg)

    def test_unpushed_commit_pushed_next_time(self):
        git(self.repo, "add", self.rel)
        git(self.repo, "commit", "-qm", "data: mise à jour précédente")
        ok, _ = git_push(self.repo, self.rel, self.token, NOW)
        self.assertTrue(ok)
        self.assertIn("précédente", git(self.remote, "log", "--format=%s", "main"))

    def test_git_push_missing_token_fails_cleanly(self):
        git(self.repo, "remote", "set-url", "origin", "https://github.com/x/y.git")
        ok, msg = git_push(self.repo, self.rel, self.token, NOW)
        self.assertFalse(ok)
        self.assertEqual(msg, "token absent")
        self.assertTrue(git(self.repo, "log", "-1", "--format=%s").startswith("data: mise à jour"))

    def test_token_not_written_to_git_config(self):
        git(self.repo, "remote", "set-url", "origin", "https://127.0.0.1:9/x/y.git")
        self.token.write_text("SECRET-TOKEN-123\n")
        ok, msg = git_push(self.repo, self.rel, self.token, NOW)
        self.assertFalse(ok)
        self.assertNotIn("SECRET-TOKEN-123", (self.repo / ".git" / "config").read_text())
        self.assertNotIn("SECRET-TOKEN-123", msg)


if __name__ == "__main__":
    unittest.main()


class GitPushSafetyTest(GitPushTest):
    def test_token_never_in_argv(self):
        import composants_watch.publish as pub
        git(self.repo, "remote", "set-url", "origin", "https://127.0.0.1:9/x/y.git")
        self.token.write_text("SECRET-TOKEN-123")
        import base64
        b64 = base64.b64encode(b"x-access-token:SECRET-TOKEN-123").decode()
        real = subprocess.run
        seen = []

        def spy(args, **kw):
            seen.append(" ".join(args))
            return real(args, **kw)
        with mock.patch.object(pub.subprocess, "run", side_effect=spy):
            git_push(self.repo, self.rel, self.token, NOW)
        self.assertTrue(seen)
        for a in seen:
            self.assertNotIn("SECRET-TOKEN-123", a)
            self.assertNotIn(b64, a)

    def test_timeout_returns_false_without_secret(self):
        import composants_watch.publish as pub
        git(self.repo, "remote", "set-url", "origin", "https://github.com/x/y.git")
        self.token.write_text("SECRET-TOKEN-123")
        real = subprocess.run

        def slow(args, **kw):
            if "push" in args:
                raise subprocess.TimeoutExpired(args, 120)
            return real(args, **kw)
        with mock.patch.object(pub.subprocess, "run", side_effect=slow):
            ok, msg = git_push(self.repo, self.rel, self.token, NOW)
        self.assertFalse(ok)
        self.assertIn("délai", msg)
        self.assertNotIn("SECRET", msg)

    def test_pushes_to_main_from_other_branch(self):
        git(self.repo, "checkout", "-q", "-b", "feat/x")
        ok, msg = git_push(self.repo, self.rel, self.token, NOW)
        self.assertTrue(ok, msg)
        self.assertTrue(git(self.remote, "log", "-1", "--format=%s", "main").startswith("data: mise à jour"))

    def test_only_deals_json_committed(self):
        (self.repo / "secret.txt").write_text("perso")
        git(self.repo, "add", "secret.txt")
        git_push(self.repo, self.rel, self.token, NOW)
        files = git(self.remote, "show", "--name-only", "--format=", "main").split()
        self.assertEqual(files, [self.rel])


class RepoIgnoreTest(unittest.TestCase):
    def test_deals_json_not_ignored_but_db_is(self):
        root = Path(__file__).resolve().parent.parent
        r = subprocess.run(["git", "check-ignore", "-q", "docs/data/deals.json"], cwd=root)
        self.assertEqual(r.returncode, 1, "docs/data/deals.json est ignoré par .gitignore")
        r = subprocess.run(["git", "check-ignore", "-q", "data/watch.db"], cwd=root)
        self.assertEqual(r.returncode, 0)
