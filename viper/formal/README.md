# Hidden Viper formal verification

This directory uses Lean 4 to formalize a small set of invariants behind Hidden Viper.

## What is proved

### Claim is not state
The verification model distinguishes supporting evidence, contradictory evidence, and unknown evidence.

A successful tool call with unknown evidence remains unverified.
A successful tool call with contradictory evidence is contradicted.
Only supporting evidence maps to verified.

### Viability Pool safety
For a hard constraint that is proven sound with respect to the true-solution predicate, refining the Viability Pool cannot remove a true candidate.

Soft constraints are modeled as non-destructive. They do not remove candidates from the underlying pool.

## What is not proved

Lean proves properties of the formal definitions in this directory. It does not by itself prove that:
- a filesystem or network observation is correct;
- an external agent is honest;
- a sensor is complete;
- a cryptographic implementation is bug-free;
- every real-world verifier matches the formal model.

Those require implementation tests, independent observations, and additional verification.

## Build

The toolchain is pinned in `lean-toolchain`.

```bash
lake build
```
