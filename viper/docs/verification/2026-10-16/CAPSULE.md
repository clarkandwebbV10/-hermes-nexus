# Discovery capsule — validate meaning before sensing

- Date: 2026-10-16.
- Context: public Hidden Viper boolean-expectation correction; baseline
  `b186ce7bbdcaf15223271b2ceefb39fe7fc19c40`.
- Principle: check the representation's type before interpreting an expectation
  or performing observation. Nonempty text is not evidence of a true intention.
- Rationale: `bool("false")` created false VERIFIED receipts; malformed claim
  envelopes also escaped the direct verification exception boundary.
- Implication: keep validation and receipt behavior consistent across adapters,
  direct API, single-file CLI, and JSONL. Match advertised schema and metadata.
- Implementation: strict booleans before file/TCP observation, guarded claim
  envelopes, schema/metadata alignment, executable baseline and correction tests.
- Status: verified locally on a development branch; no release published.
- Evidence: [receipt](receipt.json), [baseline failures](baseline-regressions.log),
  [corrected tests](corrected-tests.log), [installed package](package-smoke.log).
- Continuity: applies the standing U08/U12 shared-referent and provenance
  doctrines; no private-prototype result is substituted for public-source proof.
