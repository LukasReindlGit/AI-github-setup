import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
BOOTSTRAP = KIT / "bootstrap.py"


def run(*args, cwd):
    return subprocess.run([sys.executable, str(BOOTSTRAP), *args], cwd=cwd, capture_output=True, text=True)


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        (self.repo / "CLAUDE.md").write_text("# Mine\n")
        (self.repo / "package.json").write_text('{"scripts": {"test": "true"}}')

    def tearDown(self):
        self.tmp.cleanup()

    def install(self, *extra):
        out = run("--target", ".", "--backlog", "5", "--repo", "o/r", *extra, cwd=self.repo)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_install_is_complete_and_has_no_unrendered_tokens(self):
        self.install()
        for rel in (".claude/workflow.json", ".claude/settings.json", "scripts/batch.py", "scripts/check.sh"):
            self.assertTrue((self.repo / rel).exists(), rel)
        cfg = json.loads((self.repo / ".claude/workflow.json").read_text())
        self.assertEqual((cfg["backlog_issue"], cfg["base_branch"]), (5, "main"))
        for path in self.repo.rglob("*"):
            if path.is_file() and ".git" not in path.parts and path.suffix != ".yml":
                self.assertNotIn("{{", path.read_text(), path)

    def test_idempotent_and_keeps_project_files(self):
        self.install()
        (self.repo / "docs/GIT_WORKFLOW.md").write_text("mine")
        before = (self.repo / "CLAUDE.md").read_text()
        out = run("--target", ".", cwd=self.repo)
        self.assertEqual((self.repo / "docs/GIT_WORKFLOW.md").read_text(), "mine")
        self.assertEqual((self.repo / "CLAUDE.md").read_text(), before)
        self.assertIn("keep", out.stdout)

    def test_settings_merge_keeps_existing_and_denies_push(self):
        (self.repo / ".claude").mkdir()
        (self.repo / ".claude/settings.json").write_text(
            json.dumps({"permissions": {"allow": ["Bash(make *)"]}, "model": "opus"})
        )
        self.install()
        data = json.loads((self.repo / ".claude/settings.json").read_text())
        self.assertIn("Bash(make *)", data["permissions"]["allow"])
        self.assertIn("Bash(git push *)", data["permissions"]["deny"])
        self.assertEqual(data["model"], "opus")

    def test_guard_selftest_passes_in_target(self):
        self.install()
        out = subprocess.run([sys.executable, ".claude/hooks/test_guard_git.py"], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout)

    def test_dry_run_writes_nothing(self):
        out = run("--target", ".", "--dry-run", cwd=self.repo)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertFalse((self.repo / ".claude").exists())

    def test_integration_must_use_prefix(self):
        out = run("--target", ".", "--integration", "agent", cwd=self.repo)
        self.assertNotEqual(out.returncode, 0)


if __name__ == "__main__":
    unittest.main()
