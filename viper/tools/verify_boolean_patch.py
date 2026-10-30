"""Re-run the public baseline, failing regressions, and corrected test suite.

Run from any directory in this checkout. Results are local evidence, not a
release or signature. --package additionally requires local setuptools/wheel.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
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
    return ["git", "-c", f"core.whitespace={WHITESPACE_RULES}", "diff", "--check", "-M", "--no-ext-diff", base, "--", scope]


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


def _lines_and_trailing_blanks(text: str) -> tuple[int, int]:
    """Number of lines in `text` and how many of them are blank lines at the end."""
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    blanks = 0
    for line in reversed(lines):
        if line.strip(_TRAILING):
            break
        blanks += 1
    return len(lines), blanks


def _regular_text(path: Path) -> str | None:
    """Text of a regular, non-binary file; None for symlinks, missing or binary files."""
    if path.is_symlink() or not path.is_file():
        return None
    data = path.read_bytes()
    return None if b"\0" in data[:8000] else data.decode("utf-8", errors="replace")


def whitespace_problems(repo: Path, base: str, scope: str = CHECK_SCOPE, exclude=()) -> list[str]:
    """Whitespace errors introduced since `base` under `scope`, as "path:line: message".

    A bare `git diff --check` compares only the working tree with the index, so a
    patch that is already committed or staged passes vacuously. This covers
    committed, staged, unstaged and untracked (not ignored) files relative to the
    baseline commit. git's own check runs with explicit rules; an independent scan
    of the added lines, forced to text, catches `.gitattributes` overrides
    (`-whitespace`, `-diff`) and untracked files, which `git diff` never sees.
    Renames are followed, so moving a file does not count its old lines as new.
    Symbolic links are not followed. Paths under `exclude` are skipped.
    Known limit: a file moved without `git mv` and not yet added is untracked, so
    all of its lines count as new.
    """
    repo = Path(repo)
    roots = [Path(os.path.abspath(path)) for path in exclude]

    def excluded(path: str) -> bool:
        absolute = Path(os.path.abspath(repo / path))
        return any(absolute == root or root in absolute.parents for root in roots)

    found: dict[tuple[str, int, str], None] = {}

    def add(path: str, number: int, message: str) -> None:
        if not excluded(path):
            found[(path, number, message)] = None

    check = subprocess.run(whitespace_command(base, scope), cwd=repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if check.returncode not in (0, 2):
        raise RuntimeError(f"git diff --check failed ({check.returncode}): {check.stderr.decode(errors='replace').strip()}")
    for raw in check.stdout.decode("utf-8", errors="replace").splitlines():
        path, sep, rest = raw.partition(":")
        number, sep2, message = rest.partition(": ")
        if sep and sep2 and number.isdigit():
            add(path, int(number), message.rstrip("."))

    status = _git_bytes(repo, "diff", "--name-status", "-z", "-M", "--no-ext-diff", base, "--", scope)
    fields = status.decode("utf-8", errors="surrogateescape").split("\0")
    index = 0
    while index < len(fields) and fields[index]:
        code = fields[index]
        if code[0] in "RC":
            old, path = fields[index + 1], fields[index + 2]
            index += 3
        else:
            old = path = fields[index + 1]
            index += 2
        if code[0] == "D" or excluded(path):
            continue
        current = _regular_text(repo / path)
        if current is None:
            continue
        pathspec = [old, path] if old != path else [path]
        diff = _git_bytes(repo, "diff", "-U0", "-a", "-M", "--no-color", "--no-ext-diff", "--no-textconv", base, "--", *pathspec)
        new_line, in_hunk = 0, False
        for line in diff.decode("utf-8", errors="replace").split("\n"):
            if line.startswith("@@"):
                new_line, in_hunk = int(line.split("+", 1)[1].split(" ", 1)[0].split(",", 1)[0]), True
            elif in_hunk and line.startswith("+"):
                problem = _line_problem(line[1:])
                if problem:
                    add(path, new_line, problem)
                new_line += 1
        count, blanks = _lines_and_trailing_blanks(current)
        in_base = subprocess.run(["git", "cat-file", "-e", f"{base}:{old}"], cwd=repo, capture_output=True).returncode == 0
        base_blanks = _lines_and_trailing_blanks(_git_bytes(repo, "show", f"{base}:{old}").decode("utf-8", errors="replace"))[1] if in_base else 0
        if blanks > base_blanks:
            add(path, count - blanks + base_blanks + 1, "new blank line at EOF")

    untracked = _git_bytes(repo, "ls-files", "--others", "--exclude-standard", "-z", "--", scope)
    for path in filter(None, untracked.decode("utf-8", errors="surrogateescape").split("\0")):
        if excluded(path):
            continue
        text = _regular_text(repo / path)
        if text is None:
            continue
        pieces = text.split("\n")
        terminated = text.count("\n")
        for number, line in enumerate(pieces, start=1):
            if number > terminated and line == "":
                break
            # Not yet added, so git's CRLF normalization has not run: a CR before LF
            # is a line ending; a final CR with no LF after it is trailing whitespace.
            if number <= terminated and line.endswith("\r"):
                line = line[:-1]
            problem = _line_problem(line)
            if problem:
                add(path, number, problem)
        count, blanks = _lines_and_trailing_blanks(text)
        if blanks:
            add(path, count - blanks + 1, "new blank line at EOF")

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
