"""Offline bounded legacy stream and durable output regressions."""
import io
import json
from pathlib import Path
from queue import Empty, Queue
import subprocess
import sys
import tempfile
from threading import Thread
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import viper
from viper_events import MAX_LINE


class LegacyStreamSecurity(unittest.TestCase):
    def test_receipt_flushes_before_stdin_closes(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact = Path(folder) / "test.txt"
            artifact.write_bytes(b"fixture")
            mirror = Path(folder) / "receipts.jsonl"
            proc = subprocess.Popen([sys.executable, str(ROOT / "viper.py"),
                                     "stream", "--out", str(mirror)],
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            rows = Queue()
            def reader():
                rows.put(proc.stdout.readline())
            worker = Thread(target=reader, daemon=True)
            try:
                worker.start()
                proc.stdin.write((json.dumps({"kind":"file_exists","target":str(artifact)})+"\n").encode())
                proc.stdin.flush()
                row = rows.get(timeout=8)
                self.assertEqual(json.loads(row)["status"],"VERIFIED")
                self.assertEqual(mirror.read_bytes(),row)
                self.assertIsNone(proc.poll())
                proc.stdin.close()
                self.assertEqual(proc.wait(timeout=8),0)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
                worker.join(timeout=2)
                for pipe in (proc.stdin,proc.stdout,proc.stderr):
                    if pipe and not pipe.closed:
                        pipe.close()

    def test_bad_lines_do_not_stop_valid_observations(self):
        with tempfile.TemporaryDirectory() as folder:
            artifact = Path(folder) / "ok"
            artifact.touch()
            valid = json.dumps({"kind":"file_exists","target":str(artifact)}).encode()
            data = (b"x" * (MAX_LINE+1) + b"\n" + b'{"kind":"file_exists","kind":"unknown"}\n'
                    + b'{"kind":"unknown","target":NaN}\n' + b'{"kind":"unknown","target":"\\ud800"}\n'
                    + b'\xff\n' + valid + b"\n")
            output = io.StringIO()
            self.assertEqual(viper.write_stream(io.BytesIO(data),output),2)
            rows = [json.loads(line) for line in output.getvalue().splitlines()]
            self.assertEqual([r["status"] for r in rows],["UNVERIFIED"]*5+["VERIFIED"])
            for row in rows:
                recorded = row.pop("receiptSha256")
                self.assertEqual(viper.canonical_hash(row),recorded)

    def test_existing_mirror_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            mirror = Path(folder)/"preserve.jsonl"
            mirror.write_bytes(b"existing evidence")
            result = subprocess.run([sys.executable,str(ROOT/"viper.py"),"stream","--out",str(mirror)],
                                    input=b"",capture_output=True,timeout=8)
            self.assertEqual(result.returncode,2)
            self.assertEqual(mirror.read_bytes(),b"existing evidence")


if __name__ == "__main__":
    unittest.main()
