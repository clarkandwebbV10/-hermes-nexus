"""The public demo must not modify the user's working directory."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import viper


class DemoIsolationTests(unittest.TestCase):
    def test_demo_preserves_preexisting_files_and_reports_expected_results(self):
        with tempfile.TemporaryDirectory() as directory:
            cwd = Path.cwd()
            try:
                os.chdir(directory)
                sentinel = Path("hidden-viper-demo-output.txt")
                contradiction = Path("definitely-not-created.txt")
                sentinel.write_bytes(b"USER FILE: do not overwrite or delete\n")
                contradiction.write_bytes(b"USER FILE: do not delete\n")
                before = {p.name: p.read_bytes() for p in (sentinel, contradiction)}
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    exit_code = viper.run_demo()
                receipts = json.loads(output.getvalue())
                self.assertEqual(exit_code, 0)
                self.assertEqual([r["status"] for r in receipts], ["VERIFIED", "VERIFIED", "CONTRADICTED"])
                self.assertEqual({p.name: p.read_bytes() for p in (sentinel, contradiction)}, before)
                self.assertEqual({p.name for p in Path(".").iterdir()}, set(before))
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
