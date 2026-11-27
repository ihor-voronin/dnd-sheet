# ADR 0002 — Only the server computes the rules

Status: accepted.

## Context

Hybrid automation (computed fields + manual overrides) tempts one to recompute on the client for instant feedback.

## Decision

There is a single engine — Python (`DerivedStatsCalculator`, `ModifierResolver`, `FormulaEvaluator`).
The SPA contains no 5e formulas. Every change → `PATCH /characters/{id}` with the current version → the server returns the recomputed sheet.
Wizard previews are computed on the server too, without saving.

## Consequences

- There are no two sources of truth for AC or HP.
- ~50–200 ms latency per change; mitigated by optimistic rendering of cosmetics only and by debouncing.
- Offline editing is not supported (not a requirement).
