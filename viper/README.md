# Hidden Viper

[![Hidden Viper CI](https://github.com/clarkandwebbV10/-hermes-nexus/actions/workflows/viper-ci.yml/badge.svg)](https://github.com/clarkandwebbV10/-hermes-nexus/actions/workflows/viper-ci.yml)

**Your AI says it finished. Hidden Viper checks.**

Hidden Viper is a local, provider-agnostic verification sidecar for AI agents and automated workflows. It turns completion claims into independently checkable receipts by comparing what an agent said happened with observable ground state.

## Why

A successful tool call is not the same thing as a successful outcome.

Examples:
- an agent says it created a file; Hidden Viper checks the filesystem;
- an agent says a service is live; Hidden Viper checks the port or HTTP endpoint;
- an agent says an artifact matches a requested hash; Hidden Viper recomputes it;
- an agent says text exists in a file; Hidden Viper checks the bytes.

Hidden Viper returns **VERIFIED**, **CONTRADICTED**, or **UNVERIFIED**.

## Quick start

From this directory:

```bash
python viper.py demo
python viper.py verify examples/claim-file-exists.json
```

For an editable CLI install:

```bash
python -m pip install -e .
hidden-viper demo
```

The legacy `viper` CLI alias remains available during the developer-preview transition.

Supported MVP checks:
- `file_exists`
- `file_sha256`
- `file_contains`
- `tcp_listen`
- `http_status`

The claim envelope is described in `claim.schema.json`.

Hidden Viper deliberately does **not** execute arbitrary shell commands in this public MVP.

## Design rule

> **Claim is not state.**

The agent channel may contain plans, tool calls, assertions and artifacts. Hidden Viper uses an independent observation path and records what it can actually verify.

## Formal verification track

The `formal/` directory uses Lean 4 to prove invariants about the verification model and Viability-Pool filtering logic. It is intentionally narrow: Lean can prove properties of the formal model, but it does not magically prove that a sensor, filesystem, network endpoint, or external agent told the truth.

## Current proof

- deterministic local verifier
- 6 local unit tests passing
- public demo receipts including a deliberately contradicted completion claim
- Ed25519-signed release and portfolio commitments
- Python CI configured for 3.11, 3.12, and 3.13
- Lean formal-model CI pinned to a specific Lean toolchain

## Provenance

This public snapshot is accompanied by an Ed25519-signed cryptographic commitment to a larger private development corpus, including the historical Hermes/Cyberneurova archive. The private signing key remains DPAPI-encrypted on the operator-controlled Windows machine and is never published.

See `provenance/PORTFOLIO_COMMITMENT.json`.

The signature proves integrity and possession of the committed bytes. It is not, by itself, a legal determination of ownership, inventorship, authorship, or patent priority.

## Status

**0.1.2 developer preview.**

The deeper private R&D layers are not published here. This repository intentionally exposes enough to test the product thesis without dumping the private research corpus.

## Contributing and security

See `CONTRIBUTING.md` and `SECURITY.md`.

## License

Copyright 2026 Clark Webb. All rights reserved. See `LICENSE.md`.
