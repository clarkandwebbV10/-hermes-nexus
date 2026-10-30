"""The patch harness's whitespace gate must not pass vacuously.

PR #3 review (P2): a bare `git diff --check` compares only the working tree with
the index, so whitespace errors that are already committed or staged pass. These
tests build disposable Git repositories and require the harness to report errors
wherever they sit: committed, staged, unstaged or untracked, and despite
repository settings that relax git's own check.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import verify_boolean_patch as harness


@unittest.skipUnless(shutil.which("git"), "git is required")
class WhitespaceGateTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="hidden-viper-whitespace-")
        self.repo = Path(self._td.name)
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Hidden Viper test")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.autocrlf", "false")
        self.write(".gitignore", "receipts/\n")
        self.write("viper/module.py", "value = 1\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "baseline")
        self.base = self.git("rev-parse", "HEAD")

    def tearDown(self):
        self._td.cleanup()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout.strip()

    def write(self, relative, text):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))

    def problems(self, **kwargs):
        return harness.whitespace_problems(self.repo, self.base, **kwargs)

    def test_clean_committed_change_passes(self):
        self.write("viper/module.py", "value = 2\n")
        self.git("commit", "-q", "-am", "clean")
        self.assertEqual(self.problems(), [])

    def test_committed_error_is_reported_where_bare_check_is_green(self):
        self.write("viper/module.py", "value = 2 \n")
        self.git("commit", "-q", "-am", "trailing space")
        bare = subprocess.run(["git", "diff", "--check"], cwd=self.repo, capture_output=True)
        self.assertEqual(bare.returncode, 0, "precondition: the old check is falsely green")
        self.assertEqual(self.problems(), ["viper/module.py:1: trailing whitespace"])

    def test_staged_error_is_reported(self):
        self.write("viper/module.py", "value = 1\nother = 2\t\n")
        self.git("add", "viper/module.py")
        self.assertEqual(self.problems(), ["viper/module.py:2: trailing whitespace"])

    def test_unstaged_error_is_reported(self):
        self.write("viper/module.py", "value = 1\n  \n")
        self.assertIn("viper/module.py:2: trailing whitespace", self.problems())

    def test_untracked_file_is_scanned(self):
        self.write("viper/new_tool.py", "ok = True\nbad = 1 \n")
        self.assertEqual(self.problems(), ["viper/new_tool.py:2: trailing whitespace"])

    def test_untracked_crlf_line_endings_are_not_errors(self):
        self.write("viper/windows.py", "ok = True\r\nalso = 1\r\n")
        self.assertEqual(self.problems(), [])

    def test_committed_crlf_is_reported_like_git(self):
        self.write("viper/module.py", "value = 2\r\n")
        self.git("commit", "-q", "-am", "crlf")
        self.assertEqual(self.problems(), ["viper/module.py:1: trailing whitespace"])

    def test_space_before_tab_in_indent_is_reported(self):
        self.write("viper/module.py", "if True:\n \tvalue = 1\n")
        self.git("commit", "-q", "-am", "indent")
        self.assertEqual(self.problems(), ["viper/module.py:2: space before tab in indent"])

    def test_new_blank_line_at_eof_is_reported(self):
        self.write("viper/module.py", "value = 1\n\n")
        self.git("commit", "-q", "-am", "blank at eof")
        self.assertEqual(self.problems(), ["viper/module.py:2: new blank line at EOF"])

    def test_repository_whitespace_config_cannot_relax_the_check(self):
        self.git("config", "core.whitespace", "-blank-at-eol,-space-before-tab,-blank-at-eof")
        self.write("viper/module.py", "value = 2 \n")
        self.git("commit", "-q", "-am", "relaxed config")
        self.assertEqual(self.problems(), ["viper/module.py:1: trailing whitespace"])

    def test_gitattributes_cannot_relax_the_check(self):
        self.write(".gitattributes", "* -whitespace\n")
        self.write("viper/module.py", "value = 2 \n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "attributes bypass")
        bypassed = subprocess.run(harness.whitespace_command(self.base), cwd=self.repo, capture_output=True)
        self.assertEqual(bypassed.returncode, 0, "precondition: git's own check obeys the attribute")
        self.assertEqual(self.problems(), ["viper/module.py:1: trailing whitespace"])

    def test_ignored_and_excluded_output_is_skipped(self):
        self.write("viper/receipts/run.log", "ok \n")
        self.write("viper/out/run.log", "ok \n")
        self.assertEqual(self.problems(exclude=[self.repo / "viper/out"]), [])

    def test_binary_files_are_skipped(self):
        (self.repo / "viper/blob.bin").write_bytes(b"\x00\x01 \n \t\n")
        self.assertEqual(self.problems(), [])

    def test_changes_outside_scope_are_ignored(self):
        self.write("docs/notes.md", "outside \n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "outside scope")
        self.assertEqual(self.problems(), [])

    def test_errors_already_in_the_baseline_are_not_new(self):
        self.write("viper/legacy.py", "old = 1 \n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "legacy")
        self.base = self.git("rev-parse", "HEAD")
        self.write("viper/legacy.py", "old = 1 \nnew = 2\n")
        self.assertEqual(self.problems(), [])

    def test_unknown_baseline_fails_closed(self):
        with self.assertRaises(RuntimeError):
            harness.whitespace_problems(self.repo, "0" * 40)


if __name__ == "__main__":
    unittest.main()
