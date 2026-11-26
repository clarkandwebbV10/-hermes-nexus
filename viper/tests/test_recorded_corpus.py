import importlib.util
import json
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "corpus"
spec = importlib.util.spec_from_file_location("recorded_replay", ROOT / "replay.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class RecordedActionsTests(unittest.TestCase):
    def test_recorded_verdicts_and_control(self):
        records = json.loads((ROOT/"ruflo-runs.json").read_bytes())
        actual = {r["runId"]:runner.replay(r)["status"] for r in records}
        self.assertEqual(actual, {44559314121:"CONTRADICTED", 44582410370:"CONTRADICTED", 44583377147:"VERIFIED"})

    def test_incomplete_observations_stay_unverified(self):
        record = json.loads((ROOT/"ruflo-runs.json").read_bytes())[0]
        record["jobs"] = [j for j in record["jobs"] if "Performance" not in j["name"]]
        self.assertEqual(runner.replay(record)["status"], "UNVERIFIED")

    def test_replay_lf_bytes_despite_windows_text_translation(self):
        # Force Windows-style text translation on every platform. Only the
        # byte-preserving replay implementation can pass this negative case.
        records = json.loads((ROOT/"ruflo-runs.json").read_bytes())
        control = next(r for r in records if r["runId"] == 44583377147)
        original_write_text = Path.write_text
        original_verify = runner.verify_events
        observed = []

        def windows_text_writer(path, data, *args, **kwargs):
            if path.name == "observation.txt":
                return path.write_bytes(data.replace("\n", "\r\n").encode("utf-8"))
            return original_write_text(path, data, *args, **kwargs)

        def observe_bytes(stream, output, manifest_path):
            observed.append((manifest_path.parent/"observation.txt").read_bytes())
            return original_verify(stream, output, manifest_path)

        with mock.patch.object(Path, "write_text", new=windows_text_writer), \
             mock.patch.object(runner, "verify_events", side_effect=observe_bytes):
            receipt = runner.replay(control)
        self.assertEqual(receipt["status"], "VERIFIED")
        self.assertEqual(observed, [b"integration outcome = FAILURE\n"])

    def test_fresh_download_run_binding_rejects_null_or_missing_metadata(self):
        # Recorded public observation, with deliberately malformed API fields.
        record = json.loads((ROOT/"ruflo-runs.json").read_bytes())[0]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = root / str(record["runId"])
            folder.mkdir()
            jobs = [dict(j, run_id=record["runId"]) for j in record["jobs"]]
            artifacts = [dict(a, workflow_run={"id": record["runId"]})
                         for a in record["artifacts"]]
            (folder/"report.log").write_bytes(("\n".join(record["reportOutput"]) + "\n").encode("utf-8"))

            def save_api_responses():
                (folder/"jobs.json").write_bytes(json.dumps({"jobs": jobs}).encode("utf-8"))
                (folder/"artifacts.json").write_bytes(json.dumps({"artifacts": artifacts}).encode("utf-8"))

            jobs[0].pop("run_id")
            save_api_responses()
            with self.assertRaisesRegex(ValueError, "job belongs to a different run"):
                runner.read_downloads(root, record)
            jobs[0]["run_id"] = record["runId"]

            for malformed in (None, {}, {"id": record["runId"] + 1}):
                with self.subTest(workflow_run=malformed):
                    artifacts[0]["workflow_run"] = malformed
                    save_api_responses()
                    with self.assertRaisesRegex(ValueError, "artifact belongs to a different run"):
                        runner.read_downloads(root, record)

            artifacts[0]["workflow_run"] = {"id": record["runId"]}
            save_api_responses()
            checked = runner.read_downloads(root, record)
            self.assertEqual(checked["runId"], record["runId"])
            self.assertEqual(len(checked["jobs"]), len(record["jobs"]))
            self.assertEqual(len(checked["artifacts"]), len(record["artifacts"]))

