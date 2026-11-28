# ADR 0005 — An MCP server for managing characters, with our own OAuth

Status: accepted (implemented). How to connect: [`docs/mcp.md`](../mcp.md).

## Context

Players want to manage their characters from an AI assistant: "make me a halfling bard who
used to be a smuggler", "we took a long rest", "add the +1 shortsword we found", "level up
Mira". The Model Context Protocol is the standard way to give an assistant such tools: one
server works in Claude (web, mobile, desktop, Claude Code) and in any other MCP client.

Constraints that shape the design:

- The only way to sign in is Telegram (`identity/`). An MCP client can't do a Telegram
  login itself, and the claude.ai apps — the ones that are at the table, on a phone — only
  connect to remote servers through OAuth.
- The rules live only on the server (ADR 0002). Whatever the assistant does must go through
  the same code as the SPA, so it can't build a character the site would reject.
- A lot of that code lives in the HTTP layer (`characters/api/router.py`): ownership
  (`_guard`), request validation, the enriched sheet payload, error codes.

Spec versions this ADR follows: MCP 2026-07-28 (authorization), Python SDK `mcp` 2.3.

## Decision

### 1. One process, one more route; tools call the site's own HTTP handlers

The MCP server (`dndsheet/assistant/`) runs inside the existing FastAPI app, at
`https://dnd.voronin.app/mcp`, over Streamable HTTP in stateless mode with JSON responses.
The SDK's Starlette app is attached by its exact paths before the SPA's `StaticFiles`, and
its session manager runs in the app's lifespan.

Each tool is a thin adapter: it calls the same HTTP handler the SPA calls, **in-process**
(`assistant/inprocess.py` builds an ASGI request and awaits the app — no network). The user
travels in `scope["state"]["user"]`, a key only the server can set, which `current_user`
reads. So the tools get ownership checks, validation, payloads and error codes for free,
and nothing about the rules is written twice.

This replaces the first idea — calling the application services directly and moving
`_guard` into a `CharacterAccess` service: that would have meant duplicating the router's
validation and payload code (most of `router.py`) for a second door.

- `TransportSecuritySettings`: the host and origin of `DNDSHEET_PUBLIC_URL` only.
- Stateless: restarts and redeploys don't break a conversation; Caddy needs nothing new.
- No stdio: the data is on the server.

### 2. The site is its own OAuth 2.1 authorization server — with the SDK's handlers

The SDK ships a complete authorization server (`auth_server_provider`): `/authorize`,
`/token`, `/register`, `/revoke`, PKCE S256, redirect matching, error formats. We implement
its provider interface (`identity/api/oauth_provider.py`) on top of our own service
(`identity/application/oauth.py`) and storage (`identity/infrastructure/sqlite_oauth.py`),
instead of writing the protocol ourselves.

| Endpoint | What it does |
| --- | --- |
| `GET /.well-known/oauth-protected-resource[/mcp]` | RFC 9728 — ours, not the SDK's (the SDK appends `/` to the issuer, and clients compare it literally) |
| `GET /.well-known/oauth-authorization-server` | RFC 8414 — ours, to add `client_id_metadata_document_supported` and the `none` auth method |
| `GET /authorize` | SDK: validates, then our provider stores the request and redirects to `/#/oauth/<id>` |
| `GET/POST /api/v1/oauth/requests/<id>` | The consent screen's data and the decision (JSON only, needs the site session) |
| `POST /token` | SDK: `authorization_code` (PKCE) and `refresh_token` (rotated) |
| `POST /register` | SDK: Dynamic Client Registration — deprecated by the spec, kept for existing clients; at most 30 per 10 minutes |
| `POST /revoke` | SDK: RFC 7009 |
| `GET/DELETE /api/v1/oauth/grants` | "Connected apps" on the home page |

**Only existing accounts.** The consent screen signs in with Telegram as usual, but with
`?existing_only=1`: a Telegram account that has never been on the site is refused ("sign in
on the site first"). Apps never create players.

The player sees who asks (client name, and the redirect **host**, always), what for, a
warning for localhost-only clients and for self-registered (not URL-verified) ones, and
"Allow" / "Deny". The redirect carries `code`, `state` and `iss`.

Client identification, in the spec's order of preference:

1. **Client ID Metadata Documents**: `client_id` is an https URL; we fetch it (https on
   443 only, with a path, no credentials; every resolved address must be public; no
   redirects; 5 s; 64 KB), check that its `client_id` equals the URL, take `client_name` and
   `redirect_uris`, and keep it for an hour.
2. **DCR**: `/register` stores the client; registrations that never got a token are purged
   after a day.

Redirect URIs: https or `localhost`/`127.0.0.1` only, exact match.

Tokens: opaque random strings, only SHA-256 stored. Access 1 hour; refresh 30 days,
rotated on every use; reuse of an old refresh token revokes the whole grant (theft
detection). Codes: 60 s, single use, bound to the client, redirect, PKCE and resource. Every
token is bound to the resource `…/mcp` (`validate_token_resource`); an `/authorize` request
for another resource gets `invalid_target`. Site sessions don't work on `/mcp`, MCP tokens
don't work on the REST API.

### 3. One scope

`characters` — see and change your characters. A read-only split (`characters:read` /
`:write`) was planned, but step-up for a write tool needs an HTTP-level 403 while tools
run inside one JSON-RPC endpoint; it adds risk without a player asking for it. The
"Connected apps" block revokes everything at once.

### 4. Tools

Grouped by what a player does (20 tools), not mirroring the ~70 REST endpoints. Changing
tools take the sheet's `version`, so the SPA and the assistant can't overwrite each other.
Answers are short: a sheet summary (numbers and state, a few KB instead of ~20 KB), wizard
options with prose cut to 160 characters.

| Tool | Annotations |
| --- | --- |
| `list_characters`, `get_character` (summary / full) | read-only |
| `update_character` (HP, damage/healing, slots, feature uses, death saves, exhaustion, inspiration, notes, equipped) | idempotent |
| `start_character`, `get_creation_step`, `set_creation_step`, `finish_character` | — / read-only / idempotent / — |
| `manage_inventory` (`add` / `update` / `remove`) | destructive |
| `manage_spells` (`learn` / `forget` / `prepare`) | — |
| `rest`, `spend_hit_dice` | — |
| `level_up_options`, `level_up` | read-only / — |
| `set_class_choice`, `set_expertise` | idempotent |
| `share_link` (`status` / `create` / `revoke`) | destructive |
| `export_pdf` (a 5-minute link) | read-only |
| `search_compendium`, `get_compendium_entry` | read-only |
| `delete_character` (needs the exact name) | destructive |

Deleting was left out at first — the API had none, and losing a character to a misread
sentence is the worst failure this server could have. When the site got deletion, the tool
followed with a guard: besides the id it takes the character's **name**, which must match
(case aside), so a wrong id can't delete another character; the destructive annotation
makes clients ask the player first.

A player has at most 50 characters (`CHARACTER_LIMIT` in the router, the same for the SPA
and MCP): starting or finishing a character beyond it is a 409 with an explanation, and
`list_characters` shows the `limit`.

### 5. Resources and prompts

- Resource `character://{id}` — the sheet as the site's Markdown export.
- Prompts: "a character from an idea", "level-up advice", "apply a session recap".

### 6. Language

Tool names and descriptions in English (models choose tools better that way); data and
errors stay Ukrainian, as on the site; options carry their keys.

## Consequences

- Players can create and run characters from Claude, signing in with the same Telegram
  account; the site stays the single source of truth.
- We run an authorization server. Its tests: PKCE, code reuse, redirect mismatch, wrong
  resource, refresh rotation and reuse detection, revocation and disconnect, session ≠ token,
  other players' characters, CIMD limits (SSRF), the registration limit.
- `DNDSHEET_AUTH=off` (tests, local runs): `/mcp` without tokens, as the local player.
- `DNDSHEET_PUBLIC_URL` is required in production (the deploy script sets it from the domain).
- New dependency: `mcp` 2.x.
- Known SDK quirks: `/revoke` wants a `client_secret` field even from public clients (empty
  works); DCR client secrets are stored as the SDK compares them (plain), unlike our tokens.
- Not yet: a log of MCP calls and per-grant rate limits; a `compendium://` resource;
  notifications, sampling, elicitation.
