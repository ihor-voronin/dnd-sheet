# ADR 0003 — Content is data, not code

Status: accepted.

## Context

The project started as a personal one and became a public site. Part of the content (SRD 5.1) is CC-BY; the rest is closed material that must not be published.

## Decision

All game information lives in the content corpus (`content/compendium/`, JSONL records) with a `license: "srd" | "proprietary"` field.
The code contains no rules texts, class names or spell names.
A public "SRD only" mode is a per-request switch, with no refactoring.

## Consequences

- An importer and content migrations are needed (`scripts/ingest`, `scripts/normalize`).
- Tests use fixtures as well as the real corpus.
- Switching to a public mode is cheap; the legal risk is localized in one place. In the public
  repository the proprietary corpus is stored only encrypted (git-crypt).
