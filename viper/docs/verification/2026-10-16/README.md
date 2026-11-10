# Public verifier correction — 2026-10-16

Development branch: `fix/viper-boolean-validation-20261016`.
Public baseline: `b186ce7bbdcaf15223271b2ceefb39fe7fc19c40`.

The public baseline verified an existing file and a listening loopback port
when a claim supplied the string `"false"`. Python's nonempty-string truthiness
changed the expectation to `True`. Its eight original tests passed despite
this behavior. Package metadata and README also advertised 0.1.2 while the
runtime and receipts reported 0.1.3.

The correction requires native JSON booleans for `file_exists` and `tcp_listen`,
before either observation. An omitted expectation still defaults to `true`.
Malformed expectations produce `UNVERIFIED`, preserving the original claim and
receipt hash format. Both true/false truth tables and omitted defaults are
covered using temporary files and real loopback sockets. The schema now
describes the same boolean constraint without adding a runtime dependency.

Related inspection found malformed envelopes and array/object claim kinds
could escape the direct API/CLI exception guard. These now produce
`UNVERIFIED` receipts. Existing `verify` exit 1 and JSONL exit precedence
(`UNVERIFIED` → 2, otherwise `CONTRADICTED` → 1) are retained.

Metadata and README now match the existing 0.1.3 runtime. This is an unreleased
development correction. Historical signed manifests, commitments, build logs,
and demo receipts retain their original bytes. They describe historical
artifacts and do not attest to this patch. No private prototype changes or
private test results are included or assumed.

## Reproduce

From the repository root, Python 3.11 or newer:

```bash
python -m unittest discover -s viper/tests -v
python viper/tools/verify_boolean_patch.py --out viper/receipts/boolean-validation
```

To include a local wheel build and clean installation, with the project's
setuptools build requirement and wheel installed locally:

```bash
python viper/tools/verify_boolean_patch.py --package --out viper/receipts/boolean-validation
```

The harness reconstructs the pinned public baseline in a temporary directory,
runs its eight original tests, overlays the regression tests, and requires
four specific failures: the two false verifications and the two version
mismatches. It then runs all 27 corrected tests. The optional package check
uses no package index and tests installed metadata, runtime, both CLI aliases,
and the boolean regression through both aliases. It does not publish a wheel.

## Evidence and inspection

- [Verification receipt](receipt.json): commands, exit statuses, source hashes,
  log hashes, interpreter, timestamp, baseline and checkout identity.
- [Original eight tests](baseline-tests.log): passed on the pinned public source.
- [Four failing regressions](baseline-regressions.log): failed for the original bugs.
- [Corrected suite](corrected-tests.log): all 27 tests passed on Python 3.12.14.
- [Installed package check](package-smoke.log): passed for both CLI aliases.
- [Offline spatial source inspector](index.html): source, baseline diff,
  relationships, hashes and execution receipts in one local file.

The receipt records the checkout HEAD at execution time; the candidate source
hashes identify the tested working-tree bytes before the patch commit exists.
These are local execution records, not cryptographic signatures or evidence
that Lean proves the Python implementation. CI separately tests Python 3.11,
3.12 and 3.13 when the pull request runs.

## Related paths and scope

The audit found exactly two `bool(expected)` conversions, both corrected.
Other adapters retain their prior `str`, `int` and `float` conversions; this
patch does not introduce general schema enforcement or change their contracts.
Malformed JSON syntax in the single-file CLI is outside this correction;
JSONL retains its existing malformed-JSON receipt behavior. The formal Lean
model and unrelated frontend are unchanged.

The JSON Schema conditional was inspected statically. A Draft 2020-12 validator
is not installed in this environment, so these execution logs do not claim
independent schema-validator coverage.
