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

```bash
python viper.py demo
python viper.py verify examples/claim-file-exists.json
```

For an editable CLI install:

```bash
python -m pip install -e .
hidden-viper demo
```

The shorter `viper` command remains as a compatibility alias.

Supported checks:
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

## Current proof

- deterministic local verifier
- 6 deterministic tests passing before publication of 0.1.2
- public demo receipts including a deliberately contradicted completion claim
- Ed25519-signed release and portfolio commitments
- CI configured for Python 3.11, 3.12, and 3.13

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
