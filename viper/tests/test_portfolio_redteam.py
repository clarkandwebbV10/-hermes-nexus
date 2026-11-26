import contextlib
import errno
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import viper


class PortfolioRedTeamRegression(unittest.TestCase):
    def test_empty_and_whitespace_are_not_success(self):
        self.assertEqual(viper.stream_verify([]), ([], 2))
        self.assertEqual(viper.stream_verify(["\n", "  \n"]), ([], 2))

    def test_inconclusive_tcp_is_unknown(self):
        for code in (errno.EHOSTUNREACH, errno.ETIMEDOUT, errno.ENETUNREACH):
            with self.subTest(code=code), patch("viper.socket.socket") as factory:
                factory.return_value.connect_ex.return_value = code
                for expected in (True, False):
                    result = viper.verify({"kind": "tcp_listen", "target": 12345, "expected": expected})
                    self.assertEqual(result["status"], "UNVERIFIED")

    def test_loopback_refusal_is_only_scoped_negative(self):
        with patch("viper.socket.socket") as factory:
            factory.return_value.connect_ex.return_value = errno.ECONNREFUSED
            result = viper.verify({"kind": "tcp_listen", "target": 12345, "expected": False})
            self.assertEqual(result["status"], "VERIFIED")
            result = viper.verify({"kind": "tcp_listen", "host": "192.0.2.1", "target": 12345, "expected": False})
            self.assertEqual(result["status"], "UNVERIFIED")

    def test_demo_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as folder:
            prior = Path.cwd()
            try:
                os.chdir(folder)
                existing = Path("hidden-viper-demo-output.txt")
                existing.write_bytes(b"synthetic existing user data")
                Path("definitely-not-created.txt").write_bytes(b"unrelated user data")
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(viper.run_demo(), 0)
                self.assertEqual(existing.read_bytes(), b"synthetic existing user data")
                self.assertEqual(Path("definitely-not-created.txt").read_bytes(), b"unrelated user data")
            finally:
                os.chdir(prior)


if __name__ == "__main__":
    unittest.main()
