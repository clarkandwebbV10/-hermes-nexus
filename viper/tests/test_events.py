import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
import viper
from viper_events import MAX_LINE, verify_events


class EventStreamTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory()
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name)
        self.artifact = self.root / "viper.py"
        self.artifact.write_bytes((PROJECT / "viper.py").read_bytes())
        self.manifest = self.root / "manifest.json"
        self.entries = {"checked": {"kind": "file_sha256", "target": "viper.py",
                                   "expected": viper.sha256_file(self.artifact)}}
        self.manifest.write_text(json.dumps(self.entries), encoding="utf-8")

    def event(self, event_type="outcome.claimed", **fields):
        data = {"source": "agent", "id": "event-1", "type": event_type, "claim": "checked", **fields}
        return (json.dumps(data) + "\n").encode()

    def inspect(self, data):
        out = io.StringIO()
        code = verify_events(io.BytesIO(data), out, self.manifest)
        receipts = [json.loads(row) for row in out.getvalue().splitlines()]
        for receipt in receipts:
            claimed = receipt.pop("receiptSha256")
            self.assertEqual(viper.canonical_hash(receipt), claimed)
        return code, receipts

    def test_observe_then_observe_changed_bytes(self):
        raw = self.event()
        code, rows = self.inspect(raw)
        self.assertEqual((code, rows[0]["status"]), (0, "VERIFIED"))
        source = rows[0]["provenance"]
        self.assertEqual((source["source"], source["id"], source["claim"]), ("agent", "event-1", "checked"))
        self.assertEqual(source["inputSha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(source["manifestSha256"], viper.sha256_file(self.manifest))
        self.artifact.write_text("changed by test", encoding="utf-8")
        code, rows = self.inspect(raw)
        self.assertEqual((code, rows[0]["status"]), (1, "CONTRADICTED"))

    def test_success_without_an_outcome_and_unknown_claim(self):
        raw = self.event("tool.completed", status="success") + self.event(claim="missing")
        code, rows = self.inspect(raw)
        self.assertEqual(code, 2)
        self.assertEqual([r["status"] for r in rows], ["UNVERIFIED"] * 2)
        self.assertEqual([r["provenance"]["line"] for r in rows], [1, 2])

    def test_event_cannot_replace_the_operator_verifier(self):
        code, rows = self.inspect(self.event(target="elsewhere.txt", kind="http_status", expected="different"))
        self.assertEqual(code, 0)
        self.assertTrue(self.artifact.samefile(rows[0]["claim"]["target"]))

    def test_bad_lines_do_not_hide_later_receipts(self):
        raw = b"[]\n" + b"{" + b"x" * MAX_LINE + b"\n" + self.event()
        code, rows = self.inspect(raw)
        self.assertEqual(code, 2)
        self.assertEqual([r["status"] for r in rows], ["UNVERIFIED", "UNVERIFIED", "VERIFIED"])
        self.assertEqual(rows[1]["provenance"]["inputSha256"], hashlib.sha256(raw.splitlines(keepends=True)[1]).hexdigest())
        self.assertEqual(self.inspect(b" \n"), (2, []))

    def test_invalid_claim_shapes_and_duplicate_source(self):
        for entry in ({"kind":"file_exists", "target":"../viper.py", "expected":True},
                      {"kind":"file_exists", "target":"viper.py", "expected":1},
                      {"kind":"tcp_listen", "target":"80", "expected":True}):
            self.manifest.write_text(json.dumps({"checked":entry}), encoding="utf-8")
            code, rows = self.inspect(self.event())
            self.assertEqual((code, rows[0]["status"]), (2, "UNVERIFIED"))
        code, rows = self.inspect(b'{"id":"x","id":"y","source":"s","type":"outcome.claimed","claim":"checked"}\n')
        self.assertEqual((code, rows[0]["status"]), (2, "UNVERIFIED"))

    def test_cli_streams_and_returns_the_verdict(self):
        run = subprocess.run([sys.executable, str(PROJECT/"viper.py"), "events", "--manifest", str(self.manifest)],
                             input=self.event(), capture_output=True, cwd=self.root, check=False)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["status"], "VERIFIED")

