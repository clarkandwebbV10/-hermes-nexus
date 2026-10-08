import hashlib
import json
import socket
import tempfile
import unittest
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
