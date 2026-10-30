# Changelog

## Unreleased
- require JSON boolean expectations for file-existence and TCP checks; malformed
  expectations produce UNVERIFIED before observation instead of truthiness coercion
- constrain boolean expectations in the claim schema and document compatibility
- return UNVERIFIED receipts for malformed claim envelopes in the direct API and CLI
- align package metadata and README with the existing 0.1.3 source version
- add regression coverage for boolean validation, receipts, CLI/JSONL, and versions
- preserve historical release manifests and signatures; no new release is published
- scope the patch harness's whitespace gate to every change since the public baseline
  (committed, staged, unstaged and untracked), with an added-line scan that repository
  `core.whitespace` settings and `.gitattributes` cannot relax; a bare `git diff --check`
  passed vacuously once the patch was committed (PR #3 review, P2)

## 0.1.3 - 2026-10-08
- added provider-agnostic JSONL stdin adapter
- added deterministic stream exit semantics
- added malformed-input handling as UNVERIFIED rather than guessed
- expanded test suite from 6 to 8 tests

## 0.1.2 - 2026-10-08
- corrected canonical public product name to Hidden Viper
- added `hidden-viper` canonical CLI while retaining `viper` as a compatibility alias
- updated schemas, docs, provenance, release identity, and issue names

## 0.1.1 - 2026-10-08
- added packaging metadata and CLI entry point
- expanded deterministic tests
- added claim JSON schema
- added security and contribution guidance
- added CI workflow
- preserved signed public provenance commitment

## 0.1.0 - 2026-10-08
- initial public developer preview
