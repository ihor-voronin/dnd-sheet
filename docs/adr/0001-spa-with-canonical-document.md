# ADR 0001 — SPA + canonical SheetDocument

Status: accepted.

## Context

More than one renderer is needed: the web sheet, a printable PDF, later PNG for Discord and JSON for VTTs.
The middle ground "server-rendered HTML as the contract" is ruled out: HTML is not a stable API, and every new renderer would have to parse markup.

## Decision

The source of truth is the domain artifact `SheetDocument` (versioned JSON). It is consumed by
the React app (web) and by server-side adapters behind the `SheetRenderer` port (PDF, Markdown, later PNG/VTT).

## Consequences

- `SheetDocument` lives in the `sheets` domain, not in the API layer.
- Every renderer must pass a conformance suite.
- The frontend is not a "thin client over endpoints" but a renderer of the document; it holds no business logic.
- The cost: two stacks, codegen, more infrastructure. Accepted deliberately.
