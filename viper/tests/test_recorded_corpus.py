import importlib.util
import json
import unittest
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

