"""Replay public GitHub Actions reports against their independently recorded job outcomes."""
import argparse
import hashlib
import io
import json
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from viper_events import verify_events

PRODUCERS = ("Agent Coordination Tests", "Memory Sharing Integration",
             "Fault Tolerance Tests", "Performance Integration Tests")


def job_named(jobs, suffix):
    matches = [job for job in jobs if job["name"].endswith(suffix)]
    return matches[0] if len(matches) == 1 else None


def observe_failure(record):
    jobs = record["jobs"]
    setup = job_named(jobs, "Integration Test Setup")
    producers = [job_named(jobs, suffix) for suffix in PRODUCERS]
    names = [item["name"] for item in record["artifacts"]]
    if (setup and setup["conclusion"] == "failure" and all(job and job["conclusion"] == "skipped" for job in producers)
            and names == ["integration-test-final-report-"]):
        return "FAILURE"
    return None


def replay(record):
    job = job_named(record["jobs"], "Integration Test Report")
    if not job or job["id"] != record["reportJobId"]:
        raise ValueError("report job does not match the recorded run")
    summaries = [m.group(1) for line in record["reportOutput"]
                 if (m := re.fullmatch(r"\S+Z Overall status: (SUCCESS|FAILURE)", line))]
    if len(summaries) != 1:
        raise ValueError("expected one recorded overall status")
    observed = observe_failure(record)
    event = {"source":"github-actions", "id":f"run-{record['runId']}/job-{job['id']}",
             "type":"outcome.claimed", "claim":"overall", "reportOutput":record["reportOutput"],
             "observationsSha256":hashlib.sha256(json.dumps({"jobs":record["jobs"],"artifacts":record["artifacts"]},
                                sort_keys=True, separators=(",",":"),ensure_ascii=False).encode()).hexdigest()}
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        # An incomplete source snapshot has no registered outcome to verify.
        manifest = {"overall" if observed else "unknown": {"kind":"file_contains", "target":"observation.txt",
                     "expected":"integration outcome = " + summaries[0] + "\n"}}
        (root/"checks.json").write_text(json.dumps(manifest), encoding="utf-8")
        if observed:
            (root/"observation.txt").write_bytes(("integration outcome = " + observed + "\n").encode("utf-8"))
        out = io.StringIO()
        verify_events(io.BytesIO((json.dumps(event) + "\n").encode()), out, root/"checks.json")
        return json.loads(out.getvalue())


def read_downloads(root, record):
    folder = root/str(record["runId"])
    jobs = json.loads((folder/"jobs.json").read_bytes())["jobs"]
    if any(not isinstance(j, dict) or j.get("run_id") != record["runId"] for j in jobs):
        raise ValueError("a job belongs to a different run")
    artifacts = json.loads((folder/"artifacts.json").read_bytes())["artifacts"]
    if any(not isinstance(a, dict) or not isinstance(a.get("workflow_run"), dict)
           or a["workflow_run"].get("id") != record["runId"] for a in artifacts):
        raise ValueError("an artifact belongs to a different run")
    report_lines = (folder/"report.log").read_text(encoding="utf-8-sig").splitlines()
    return {**record, "reportOutput":[line for line in report_lines if re.fullmatch(r"\S+Z (Overall status: (SUCCESS|FAILURE)|Tests passed: \d+/\d+)",line)],
            "jobs":[{k:j[k] for k in ("id","name","conclusion")} for j in jobs],
            "artifacts":[{k:a[k] for k in ("id","name")} for a in artifacts]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--downloads", type=Path, help="use fresh public source responses from run-specific folders")
    args = parser.parse_args()
    records = json.loads((HERE/"ruflo-runs.json").read_bytes())
    for record in records:
        source = read_downloads(args.downloads, record) if args.downloads else record
        receipt = replay(source)
        print(json.dumps({"runId":record["runId"], "status":receipt["status"],
                          "report":record["publicRun"] + "/job/" + str(record["reportJobId"]),
                          "receipt":receipt}, ensure_ascii=True))


if __name__ == "__main__":
    main()

