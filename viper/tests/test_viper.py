import errno
import hashlib
import json
import socket
import tempfile
import unittest
from unittest.mock import patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import viper


class HiddenViperTests(unittest.TestCase):
    def test_file_exists_verified(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.txt"
            path.write_text("hello")
            receipt = viper.verify({"kind": "file_exists", "target": str(path), "expected": True})
            self.assertEqual(receipt["status"], "VERIFIED")

    def test_missing_file_contradicted(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "missing.txt"
            receipt = viper.verify({"kind": "file_exists", "target": str(path), "expected": True})
            self.assertEqual(receipt["status"], "CONTRADICTED")

    def test_sha256(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.txt"
            path.write_bytes(b"abc")
            expected = hashlib.sha256(b"abc").hexdigest()
            receipt = viper.verify({"kind": "file_sha256", "target": str(path), "expected": expected})
            self.assertEqual(receipt["status"], "VERIFIED")

    def test_file_contains_verified(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "x.txt"
            path.write_text("deployment-state=ready\n", encoding="utf-8")
            receipt = viper.verify({"kind": "file_contains", "target": str(path), "expected": "deployment-state=ready"})
            self.assertEqual(receipt["status"], "VERIFIED")

    def test_tcp_listen_verified(self):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        try:
            port = sock.getsockname()[1]
            receipt = viper.verify({"kind": "tcp_listen", "target": port, "host": "127.0.0.1", "expected": True})
            self.assertEqual(receipt["status"], "VERIFIED")
        finally:
            sock.close()

    def test_tcp_inconclusive_is_unverified_for_either_expectation(self):
        for code in (errno.ETIMEDOUT, errno.ENETUNREACH, errno.EHOSTUNREACH, errno.EACCES):
            for expected in (True, False):
                with self.subTest(code=code, expected=expected), patch.object(viper.socket, "socket") as factory:
                    factory.return_value.connect_ex.return_value = code
                    claim = {"kind": "tcp_listen", "target": 12345, "expected": expected}
                    receipts, exit_code = viper.stream_verify([json.dumps(claim)])
                    self.assertEqual(receipts[0]["status"], "UNVERIFIED")
                    self.assertNotIn("listening", receipts[0]["observation"])
                    self.assertEqual(exit_code, 2)
                    factory.return_value.close.assert_called_once()

    def test_tcp_explicit_refusal_preserves_observed_negative(self):
        for code in {errno.ECONNREFUSED, getattr(errno, "WSAECONNREFUSED", errno.ECONNREFUSED)}:
            for expected, status in ((False, "VERIFIED"), (True, "CONTRADICTED")):
                with self.subTest(code=code, expected=expected), patch.object(viper.socket, "socket") as factory:
                    factory.return_value.connect_ex.return_value = code
                    receipt = viper.verify({"kind": "tcp_listen", "target": 12345, "expected": expected})
                    self.assertEqual(receipt["status"], status)
                    self.assertEqual(receipt["observation"]["connectionResult"], "refused")

    def test_unsupported_is_unverified(self):
        receipt = viper.verify({"kind": "unknown", "target": "x"})
        self.assertEqual(receipt["status"], "UNVERIFIED")

    def test_jsonl_stream_preserves_contradiction(self):
        with tempfile.TemporaryDirectory() as td:
            existing = Path(td) / "exists.txt"
            existing.write_text("ok")
            lines = [
                json.dumps({"kind": "file_exists", "target": str(existing), "expected": True}),
                json.dumps({"kind": "file_exists", "target": str(Path(td) / "missing.txt"), "expected": True}),
            ]
            receipts, code = viper.stream_verify(lines)
            self.assertEqual([r["status"] for r in receipts], ["VERIFIED", "CONTRADICTED"])
            self.assertEqual(code, 1)

    def test_jsonl_stream_marks_bad_json_unverified(self):
        receipts, code = viper.stream_verify(["not-json"])
        self.assertEqual(receipts[0]["status"], "UNVERIFIED")
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
