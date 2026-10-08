# Verifying Hidden Viper provenance

This public directory contains:
- `PORTFOLIO_COMMITMENT.json`
- `PORTFOLIO_COMMITMENT.provenance.json`
- `OPERATOR_PUBLIC_KEY.pem`
- `verify_signature.py`

The public commitment publishes hashes and counts, not private Hermes conversation content. The Ed25519 private key remains DPAPI-encrypted on the operator-controlled Windows machine and is not in this repository.

## Verify the signature and artifact hash

Install the verification dependency:

```bash
python -m pip install cryptography
```

Then run:

```bash
python provenance/verify_signature.py provenance/PORTFOLIO_COMMITMENT.provenance.json --artifact provenance/PORTFOLIO_COMMITMENT.json
```

A successful result reports `signatureValid: true` and `artifactHashMatches: true`.

## Evidence boundary

A valid signature proves that the corresponding private key signed the exact payload and that the supplied artifact still matches its committed SHA-256 hash.

It does not by itself determine legal ownership, inventorship, authorship, trade-secret status, or patent priority.
