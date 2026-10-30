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
# git's default whitespace rules, passed on the command line so a repository or
# user `core.whitespace` setting cannot silently relax the check.
WHITESPACE_RULES = "blank-at-eol,space-before-tab,blank-at-eof"
CHECK_SCOPE = "viper"
_TRAILING = " \t\r\f\v"


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO, text=True).strip()


def whitespace_command(base: str, scope: str = CHECK_SCOPE) -> list[str]:
    return ["git", "-c", f"core.whitespace={WHITESPACE_RULES}", "diff", "--check", "--no-ext-diff", base, "--", scope]


def _git_bytes(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed ({result.returncode}): {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def _line_problem(line: str) -> str | None:
    if line != line.rstrip(_TRAILING):
        return "trailing whitespace"
    indent = line[: len(line) - len(line.lstrip(" \t"))]
    if " \t" in indent:
        return "space before tab in indent"
    return None


def _first_trailing_blank_line(text: str) -> int | None:
    """1-based number of the first blank line at the end of `text`, if any."""
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    first = None
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip(_TRAILING):
            break
        first = index + 1
    return first


def whitespace_problems(repo: Path, base: str, scope: str = CHECK_SCOPE, exclude=()) -> list[str]:
    """Whitespace errors introduced since `base` under `scope`, as "path:line: message".

    A bare `git diff --check` compares only the working tree with the index, so a
    patch that is already committed or staged passes vacuously. This covers
    committed, staged, unstaged and untracked (not ignored) files relative to the
    baseline commit. git's own check runs with explicit rules; an independent scan
    of the added lines catches `.gitattributes` overrides (`-whitespace`) that
    git's check obeys, and untracked files, which `git diff` never sees.
    """
    repo = Path(repo)
    excluded = [Path(path).resolve() for path in exclude]
    found: dict[tuple[str, int, str], None] = {}

    check = subprocess.run(whitespace_command(base, scope), cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if check.returncode not in (0, 2):
        raise RuntimeError(f"git diff --check failed ({check.returncode}): {check.stderr.decode(errors='replace').strip()}")
    for raw in check.stdout.decode("utf-8", errors="replace").splitlines():
        path, sep, rest = raw.partition(":")
        number, sep2, message = rest.partition(": ")
        if sep and sep2 and number.isdigit():
            found[(path, int(number), message.rstrip("."))] = None

    changed = _git_bytes(repo, "diff", "--name-only", "-z", "--no-renames", base, "--", scope)
    for path in filter(None, changed.decode("utf-8", errors="surrogateescape").split("\0")):
        if not (repo / path).is_file():
            continue  # deleted since the baseline
        diff = _git_bytes(repo, "diff", "-U0", "--no-color", "--no-ext-diff", "--no-renames", base, "--", path)
        new_line, in_hunk = 0, False
        for line in diff.decode("utf-8", errors="replace").split("\n"):
            if line.startswith("@@"):
                new_line, in_hunk = int(line.split("+", 1)[1].split(" ", 1)[0].split(",", 1)[0]), True
            elif in_hunk and line.startswith("+"):
                problem = _line_problem(line[1:])
                if problem:
                    found[(path, new_line, problem)] = None
                new_line += 1
        current = (repo / path).read_bytes()
        if b"\0" not in current[:8000]:
            blank = _first_trailing_blank_line(current.decode("utf-8", errors="replace"))
            in_base = subprocess.run(["git", "cat-file", "-e", f"{base}:{path}"], cwd=repo, capture_output=True).returncode == 0
            base_blank = in_base and _first_trailing_blank_line(_git_bytes(repo, "show", f"{base}:{path}").decode("utf-8", errors="replace"))
            if blank and not base_blank:
                found[(path, blank, "new blank line at EOF")] = None

    untracked = _git_bytes(repo, "ls-files", "--others", "--exclude-standard", "-z", "--", scope)
    for path in filter(None, untracked.decode("utf-8", errors="surrogateescape").split("\0")):
        absolute = (repo / path).resolve()
        if any(absolute == root or root in absolute.parents for root in excluded):
            continue
        data = absolute.read_bytes()
        if b"\0" in data[:8000]:
            continue  # binary
        text = data.decode("utf-8", errors="replace")
        for number, line in enumerate(text.split("\n")[: text.count("\n") + (0 if text.endswith("\n") else 1)], start=1):
            # Not yet added, so git's CRLF normalization has not run: accept CRLF endings.
            problem = _line_problem(line[:-1] if line.endswith("\r") else line)
            if problem:
                found[(path, number, problem)] = None
        blank = _first_trailing_blank_line(text.replace("\r\n", "\n"))
        if blank:
            found[(path, blank, "new blank line at EOF")] = None

    return [f"{path}:{number}: {message}" for path, number, message in sorted(found)]


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

    def record(name, command, cwd, returncode, output, expected=0, **extra):
        log = output_dir / f"{name}.log"
        log.write_text(output, encoding="utf-8")
        results.append({
            "name": name, "command": command, "cwd": str(cwd),
            "returncode": returncode, "expectedReturncode": expected,
            "outputLog": log.name, "outputSha256": hashlib.sha256(log.read_bytes()).hexdigest(),
            **extra,
        })
        print(f"{name}: exit {returncode} (expected {expected}); {log}", flush=True)
        if returncode != expected:
            raise RuntimeError(f"{name}: unexpected exit status; inspect {log}")
        return output

    def run(name, command, cwd, expected=0):
        result = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=False)
        return record(name, command, cwd, result.returncode, result.stdout, expected)

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
    problems = whitespace_problems(REPO, BASELINE, exclude=[output_dir])
    record(
        "diff-check", whitespace_command(BASELINE), REPO, 1 if problems else 0, "".join(f"{p}\n" for p in problems),
        scope=f"committed, staged, unstaged and untracked changes under {CHECK_SCOPE}/ since {BASELINE}, "
              "plus an added-line scan independent of git whitespace configuration and attributes",
    )
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
