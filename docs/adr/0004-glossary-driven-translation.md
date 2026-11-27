# ADR 0004 — Glossary as data, translation with provenance

Status: accepted.

## Context

The content's source language is English. An official Ukrainian translation exists as a PDF available for reference.
The text volume is ~1.5–2 million characters. Without a single glossary the terms would drift apart within two weeks.

## Decision

- `content/glossary.uk.yml` holds the terms (term_en, term_uk, source, citation, status) and the forbidden spellings.
- UI strings are code; game terms come only from the glossary.
- Every localized string carries `provenance: official | own_human | own_mt_draft` + `citation`.
- A glossary check in CI (`backend/tests/api/test_terminology.py`): if code or translations use a forbidden spelling, the build fails.
- Machine translation is allowed only as a draft (`own_mt_draft`) until a human confirms it.

## Consequences

- Translation becomes a managed process rather than a side job.
- A UI/CLI is needed to review and insert official terms with a citation (book + page).
- Strings with no official counterpart are marked explicitly — it's visible where they may diverge from the official Ukrainian edition.
