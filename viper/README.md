# Viper

Your AI says it finished. Viper checks.

Viper is a local, provider-agnostic verification sidecar for AI agents and automated workflows. It turns completion claims into independently checkable receipts by comparing what an agent said happened with observable ground state.

## Why

A successful tool call is not the same thing as a successful outcome.

Examples:
- an agent says it created a file; Viper checks the filesystem;
- an agent says a service is live; Viper checks the port or HTTP endpoint;
- an agent says an artifact matches a requested hash; Viper recomputes it;
- an agent says text exists in a file; Viper checks the bytes.

Viper returns VERIFIED, CONTRADICTED, or UNVERIFIED.

## Quick start

Run: python viper.py demo

Then verify a claim file:
python viper.py verify examples/claim-file-exists.json

Supported MVP checks:
- file_exists
- file_sha256
- file_contains
- tcp_listen
- http_status

Viper deliberately does not execute arbitrary shell commands in this public MVP.

## Design rule

Claim is not state.

The agent channel may contain plans, tool calls, assertions and artifacts. Viper uses an independent observation path and records what it can actually verify.

## Provenance

This public snapshot is accompanied by an Ed25519-signed cryptographic commitment to a larger private development corpus, including the historical Hermes/Cyberneurova archive. The private signing key remains DPAPI-encrypted on the operator-controlled Windows machine and is never published.

See provenance/PORTFOLIO_COMMITMENT.json.

The signature proves integrity and possession of the committed bytes. It is not, by itself, a legal determination of ownership, inventorship, authorship or patent priority.

## Status

Public MVP / developer preview.

The deeper Great Ape AI, Hidden Viper, continuity, Sensorium and Subtractive Synthesis research layers are not all published here. This repository intentionally exposes only enough to demonstrate the product thesis without dumping the private R&D corpus.

## License

Copyright 2026 Clark Webb. All rights reserved. See LICENSE.md.