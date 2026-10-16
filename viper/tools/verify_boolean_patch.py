"""Re-run the public baseline, failing regressions, and corrected test suite.

Run from any directory in this checkout. Results are local evidence, not a
release or signature. --package additionally requires local setuptools/wheel.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parents[2]
BASELINE = "b186ce7bbdcaf15223271b2ceefb39fe7fc19c40"
REGRESSIONS = [
    "test_boolean_expectations.BooleanExpectationTests.test_file_exists_rejects_string_false_for_existing_file",
    "test_boolean_expectations.BooleanExpectationTests.test_tcp_listen_rejects_string_false_for_open_port",
    "test_version.HiddenViperVersionTests.test_package_metadata_matches_runtime",
    "test_version.HiddenViperVersionTests.test_readme_advertised_version_matches_runtime",
]


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "viper/receipts/boolean-validation")
    parser.add_argument("--package", action="store_true")
    args = parser.parse_args()
    output_dir = args.out.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt_path = output_dir / "receipt.json"
    # A failed rerun must not leave a previous success receipt at this path.
    receipt_path.unlink(missing_ok=True)
    results = []

    def run(name, command, cwd, expected=0):
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        log = output_dir / f"{name}.log"
        log.write_text(result.stdout, encoding="utf-8")
        results.append({
            "name": name, "command": command, "cwd": str(cwd),
            "returncode": result.returncode, "expectedReturncode": expected,
            "outputLog": log.name, "outputSha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        })
        print(f"{name}: exit {result.returncode} (expected {expected}); {log}", flush=True)
        if result.returncode != expected:
            raise RuntimeError(f"{name}: unexpected exit status; inspect {log}")
        return result.stdout

    with tempfile.TemporaryDirectory(prefix="hidden-viper-public-baseline-") as td:
        baseline = Path(td)
        for name in git("ls-tree", "-r", "--name-only", BASELINE, "--", "viper").splitlines():
            destination = baseline / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(subprocess.check_output(["git", "show", f"{BASELINE}:{name}"], cwd=REPO))
        original = run("baseline-tests", [sys.executable, "-m", "unittest", "discover", "-s", "viper/tests", "-v"], baseline)
        if "Ran 8 tests" not in original:
            raise RuntimeError("unexpected public baseline test count")
        for source in (REPO / "viper/tests").glob("test_*.py"):
            shutil.copy2(source, baseline / "viper/tests" / source.name)
        red = run("baseline-regressions", [sys.executable, "-m", "unittest", "-v", *REGRESSIONS], baseline / "viper/tests", expected=1)
        if "FAILED (failures=4)" not in red or "'VERIFIED' != 'UNVERIFIED'" not in red:
            raise RuntimeError("baseline did not reproduce the expected four regression failures")

    run("corrected-tests", [sys.executable, "-m", "unittest", "discover", "-s", "viper/tests", "-v"], REPO)
    run("diff-check", ["git", "diff", "--check"], REPO)
    if args.package:
        run("package-smoke", [sys.executable, str(REPO / "viper/tools/check_package.py")], REPO)

    source_paths = [REPO / "viper" / name for name in ("viper.py", "claim.schema.json", "pyproject.toml", "README.md", "CHANGELOG.md")]
    source_paths.extend(sorted((REPO / "viper/tests").glob("test_*.py")))
    source_paths.extend(sorted((REPO / "viper/tools").glob("*.py")))
    receipt = {
        "schema": "hidden-viper.patch-verification/v1",
        "observedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "baselineCommit": BASELINE, "checkoutHeadAtRun": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"), "python": sys.version,
        "sourceSha256": {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths},
        "results": results,
        "scope": "Local executable Python verification and optional packaging smoke; no release publication, signing, or claim of Lean-to-Python equivalence.",
    }
    encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    receipt["receiptSha256"] = hashlib.sha256(encoded).hexdigest()
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("PASS: baseline reproduced, corrected implementation verified; receipt.json written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
