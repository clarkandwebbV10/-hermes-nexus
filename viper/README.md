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

For `file_exists` and `tcp_listen`, `expected` must be a JSON boolean
(`true` or `false`). Omitting it defaults to `true`. Strings such as `"false"`,
numbers, `null`, arrays, and objects produce an **UNVERIFIED** receipt with a
validation error, before the filesystem or network is probed. For example,
`{"kind":"file_exists","target":"retired.txt","expected":false}` checks
that a file is absent. Producers relying on truthiness coercion must send
native JSON booleans instead.

`tcp_listen` reports an accepted connection as `listening: true`. It reports
`listening: false` only for an explicit refusal from a loopback address, where
the probe and the target share a vantage point. A timeout, an unreachable
network, a permission error, or a refusal from a remote host (which a firewall
or middlebox can produce) is **UNVERIFIED**, because it does not establish that
no listener exists. Observed outcomes include `connectionResult`
(`"connected"` or `"refused"`).

Invalid claim objects and unsupported claim kinds also produce **UNVERIFIED**
receipts. The `verify` command exits `1` for any non-verified receipt; JSONL
`stream` exits `2` if any input is unverified, ahead of contradiction exit `1`.

Hidden Viper deliberately does **not** execute arbitrary shell commands in this public MVP.

## Agent event streams

Run `hidden-viper events --manifest checks.json` and send one UTF-8 JSON event per line to stdin. A manifest is supplied by the operator from a stable directory containing the artifacts. It maps an identifier to a filesystem check. For example, this manifest checks a file already present in the project directory.

```json
{"project-readme":{"kind":"file_exists","target":"README.md","expected":true}}
```

An event can request that check with this envelope.

```json
{"type":"outcome.claimed","source":"agent","id":"event-1","claim":"project-readme"}
```

The receipt binds the verifier result, source, event ID, line number and SHA-256 digests of the raw line and manifest. Source and ID are labels reported by the producer. The artifact bytes provide the independent observation. A tool-completion event, an unfamiliar event, a missing registered claim or a malformed line yields `UNVERIFIED`. The exit code is 0 for verified outcomes, 1 for contradictions and 2 for unverified or empty input.

Supported manifest checks are `file_exists` with a JSON boolean, `file_sha256` with a 64-digit hexadecimal digest and `file_contains` with a bounded text value. Paths use forward slashes relative to the manifest. Use a stable, operator-controlled directory during verification. The adapter supports regular files and absent paths. Event-provided commands, URLs and target overrides have no effect. Stream records are limited to 64 KiB.

Public recorded examples and their replay commands are in `corpus/README.md`.

## Design rule

> **Claim is not state.**

The agent channel may contain plans, tool calls, assertions and artifacts. Hidden Viper uses an independent observation path and records what it can actually verify.

## Formal verification track

The `formal/` directory uses Lean 4 to prove invariants about the verification model and Viability-Pool filtering logic. It is intentionally narrow: Lean can prove properties of the formal model, but it does not magically prove that a sensor, filesystem, network endpoint, or external agent told the truth.

## Current proof

- deterministic local verifier
- local unit tests: `python -m unittest discover -s tests -v`
- public demo receipts including a deliberately contradicted completion claim
- Ed25519-signed release and portfolio commitments
- Python CI configured for 3.11, 3.12, and 3.13
- Lean formal-model CI pinned to a specific Lean toolchain

## Provenance

This public snapshot is accompanied by an Ed25519-signed cryptographic commitment to a larger private development corpus, including the historical Hermes/Cyberneurova archive. The private signing key remains DPAPI-encrypted on the operator-controlled Windows machine and is never published.

See `provenance/PORTFOLIO_COMMITMENT.json`.

The signature proves integrity and possession of the committed bytes. It is not, by itself, a legal determination of ownership, inventorship, authorship, or patent priority.

## Status

**0.1.3 developer preview.**

The deeper private R&D layers are not published here. This repository intentionally exposes enough to test the product thesis without dumping the private research corpus.

## Contributing and security

See `CONTRIBUTING.md` and `SECURITY.md`.

## License

Copyright 2026 Clark Webb. All rights reserved. See `LICENSE.md`.
