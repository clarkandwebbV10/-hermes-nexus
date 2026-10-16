import json
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import viper


INVALID_EXPECTATIONS = ("false", "true", "", "0", "1", 0, 1, 0.0, 1.0, None, [], [False], {}, {"value": False})


class BooleanExpectationTests(unittest.TestCase):
    def assert_invalid_receipt(self, claim):
        receipt = viper.verify(claim)
        self.assertEqual(receipt["status"], "UNVERIFIED")
        self.assertIn("expected must be a JSON boolean", receipt["observation"]["error"])
        self.assertEqual(receipt["claim"], claim)
        unhashed = dict(receipt)
        digest = unhashed.pop("receiptSha256")
        self.assertEqual(digest, viper.canonical_hash(unhashed))

    def test_file_exists_rejects_string_false_for_existing_file(self):
        # Baseline bool("false") incorrectly produces a VERIFIED receipt here.
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "present"
            path.touch()
            self.assert_invalid_receipt({"kind": "file_exists", "target": str(path), "expected": "false"})

    def test_file_exists_rejects_non_booleans_in_both_states(self):
        with tempfile.TemporaryDirectory() as td:
            present = Path(td) / "present"
            present.touch()
            for target in (present, Path(td) / "absent"):
                for expected in INVALID_EXPECTATIONS:
                    with self.subTest(target=target.name, expected=expected):
                        self.assert_invalid_receipt({"kind": "file_exists", "target": str(target), "expected": expected})

    def test_file_exists_preserves_boolean_truth_table_and_default(self):
        with tempfile.TemporaryDirectory() as td:
            present = Path(td) / "present"
            present.touch()
            for target, actual in ((present, True), (Path(td) / "absent", False)):
                for expected in (True, False):
                    with self.subTest(actual=actual, expected=expected):
                        receipt = viper.verify({"kind": "file_exists", "target": str(target), "expected": expected})
                        self.assertEqual(receipt["status"], "VERIFIED" if actual == expected else "CONTRADICTED")
                        self.assertIs(receipt["observation"]["exists"], actual)
                receipt = viper.verify({"kind": "file_exists", "target": str(target)})
                self.assertEqual(receipt["status"], "VERIFIED" if actual else "CONTRADICTED")

    def test_tcp_listen_rejects_string_false_for_open_port(self):
        # Use a real loopback listener to reproduce the original false verification.
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(64)
            self.assert_invalid_receipt({"kind": "tcp_listen", "target": listener.getsockname()[1], "expected": "false"})

    def test_tcp_listen_rejects_non_booleans_in_both_states(self):
        for listening in (True, False):
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                if listening:
                    sock.listen(64)
                for expected in INVALID_EXPECTATIONS:
                    with self.subTest(listening=listening, expected=expected):
                        self.assert_invalid_receipt({"kind": "tcp_listen", "target": sock.getsockname()[1], "expected": expected})

    def test_tcp_listen_preserves_boolean_truth_table_and_default(self):
        for listening in (True, False):
            # Keep the non-listening port bound so another process cannot take it.
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                if listening:
                    sock.listen(16)
                claim = {"kind": "tcp_listen", "target": sock.getsockname()[1], "timeoutSeconds": 0.2}
                for expected in (True, False):
                    with self.subTest(listening=listening, expected=expected):
                        receipt = viper.verify({**claim, "expected": expected})
                        self.assertEqual(receipt["status"], "VERIFIED" if listening == expected else "CONTRADICTED")
                        self.assertIs(receipt["observation"]["listening"], listening)
                receipt = viper.verify(claim)
                self.assertEqual(receipt["status"], "VERIFIED" if listening else "CONTRADICTED")

    def test_direct_file_check_rejects_invalid_expected_before_observation(self):
        with patch.object(viper, "Path") as path:
            with self.assertRaisesRegex(ValueError, "expected must be a JSON boolean"):
                viper.check_file_exists({"target": "unused", "expected": "false"})
            path.assert_not_called()

    def test_direct_tcp_check_rejects_invalid_expected_before_connection(self):
        with patch.object(viper.socket, "socket") as socket_factory:
            with self.assertRaisesRegex(ValueError, "expected must be a JSON boolean"):
                viper.check_tcp_listen({"target": 12345, "expected": "false"})
            socket_factory.assert_not_called()

    def test_stream_preserves_invalid_claim_and_exit_precedence(self):
        with tempfile.TemporaryDirectory() as td:
            target = str(Path(td) / "absent")
            claims = [
                {"kind": "file_exists", "target": target, "expected": False},
                {"kind": "file_exists", "target": target, "expected": "false"},
                {"kind": "file_exists", "target": target, "expected": True},
            ]
            receipts, code = viper.stream_verify(map(json.dumps, claims))
            self.assertEqual([r["status"] for r in receipts], ["VERIFIED", "UNVERIFIED", "CONTRADICTED"])
            self.assertEqual(receipts[1]["claim"], claims[1])
            self.assertEqual(code, 2)

    def test_verify_cli_rejects_string_false(self):
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "present"
            target.touch()
            claim_file = Path(td) / "claim.json"
            claim_file.write_text(json.dumps({"kind": "file_exists", "target": str(target), "expected": "false"}), encoding="utf-8")
            result = subprocess.run([sys.executable, viper.__file__, "verify", str(claim_file)], capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)["status"], "UNVERIFIED")

    def test_stream_cli_rejects_string_false_and_continues(self):
        with tempfile.TemporaryDirectory() as td:
            target = str(Path(td) / "absent")
            claims = [
                {"kind": "file_exists", "target": target, "expected": "false"},
                {"kind": "file_exists", "target": target, "expected": False},
            ]
            result = subprocess.run([sys.executable, viper.__file__, "stream"], input="\n".join(map(json.dumps, claims)), capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertEqual([json.loads(line)["status"] for line in result.stdout.splitlines()], ["UNVERIFIED", "VERIFIED"])


if __name__ == "__main__":
    unittest.main()
