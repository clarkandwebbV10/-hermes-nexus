import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import viper


class ClaimValidationTests(unittest.TestCase):
    def test_non_object_claims_are_unverified(self):
        for claim in (None, False, True, 0, 1.5, "file_exists", [], ["file_exists"]):
            with self.subTest(claim=claim):
                receipt = viper.verify(claim)
                self.assertEqual(receipt["status"], "UNVERIFIED")
                self.assertIn("claim must be a JSON object", receipt["observation"]["error"])
                self.assertEqual(receipt["claim"], claim)
                unhashed = dict(receipt)
                digest = unhashed.pop("receiptSha256")
                self.assertEqual(digest, viper.canonical_hash(unhashed))

    def test_non_string_kinds_are_unverified(self):
        for kind in ([], {}, None, False, 1):
            with self.subTest(kind=kind):
                receipt = viper.verify({"kind": kind, "target": "unused"})
                self.assertEqual(receipt["status"], "UNVERIFIED")
                self.assertIn("unsupported claim kind", receipt["observation"]["error"])

    def test_verify_cli_emits_receipt_for_malformed_envelopes(self):
        with tempfile.TemporaryDirectory() as td:
            claim_file = Path(td) / "claim.json"
            for claim in (None, [], {"kind": [], "target": "unused"}):
                with self.subTest(claim=claim):
                    claim_file.write_text(json.dumps(claim), encoding="utf-8")
                    result = subprocess.run([sys.executable, viper.__file__, "verify", str(claim_file)], capture_output=True, text=True, check=False)
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(json.loads(result.stdout)["status"], "UNVERIFIED")

    def test_stream_continues_after_invalid_kind(self):
        receipts, code = viper.stream_verify([json.dumps({"kind": [], "target": "unused"}), json.dumps({"kind": "unknown"})])
        self.assertEqual([r["status"] for r in receipts], ["UNVERIFIED", "UNVERIFIED"])
        self.assertEqual(receipts[0]["claim"], {"kind": [], "target": "unused"})
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
