import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))
import viper


class HiddenViperVersionTests(unittest.TestCase):
    def test_package_metadata_matches_runtime(self):
        with (PACKAGE_ROOT / "pyproject.toml").open("rb") as metadata_file:
            metadata = tomllib.load(metadata_file)
        self.assertEqual(metadata["project"]["version"], viper.VERSION)

    def test_readme_advertised_version_matches_runtime(self):
        readme = (PACKAGE_ROOT / "README.md").read_text(encoding="utf-8")
        advertised = re.findall(r"\*\*(\d+\.\d+\.\d+) developer preview\.\*\*", readme)
        self.assertEqual(advertised, [viper.VERSION])

    def test_source_cli_version_matches_runtime(self):
        with tempfile.TemporaryDirectory() as td:
            result = subprocess.run(
                [sys.executable, str(PACKAGE_ROOT / "viper.py"), "--version"],
                cwd=td,
                check=True,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.stdout.strip(), viper.VERSION)
        self.assertEqual(result.stderr, "")

    def test_receipt_version_matches_runtime(self):
        receipt = viper.verify({"kind": "unknown", "target": "unused"})
        self.assertEqual(receipt["hiddenViperVersion"], viper.VERSION)


if __name__ == "__main__":
    unittest.main()
