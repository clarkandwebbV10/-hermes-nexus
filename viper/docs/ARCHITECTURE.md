# Viper architecture

Viper separates two channels:
1. Agent channel: plans, tool calls, claims and produced artifacts.
2. Observation channel: independently measured ground state.

A claim is promoted to VERIFIED only when an observation supports it. Tool success alone is not sufficient.

The public MVP intentionally keeps the observation set small and deterministic. Private R&D explores richer telemetry, provenance, continuity, reversible uncertainty handling and multi-sensor reconciliation.