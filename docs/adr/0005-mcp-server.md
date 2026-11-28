# ADR 0005 — An MCP server for managing characters, with our own OAuth

Status: proposed.

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
  the same services as the SPA, so it can't build a character the site would reject.
- Ownership is checked in the HTTP layer today (`characters/api/router.py`, `_guard`):
  services don't know who is asking.

Spec versions this ADR follows: MCP 2026-07-28 (authorization), Python SDK `mcp` 2.x.

## Decision

### 1. One process, one more route

The MCP server runs inside the existing FastAPI app, at `https://dnd.voronin.app/mcp`,
over Streamable HTTP in stateless mode (`MCPServer` from `mcp.server`,
`streamable_http_app(stateless_http=True, json_response=True)`, mounted before the SPA
fallback; `mcp.session_manager.run()` joins the app's lifespan).

- Tools call the application services directly (`SheetService`, `WizardService`,
  `LevelUpService`, the compendium service) — not the REST API. Same rules, same SQLite,
  same tests; no second deploy and no client to keep in sync with our own API.
- `TransportSecuritySettings(allowed_hosts=["dnd.voronin.app"], allowed_origins=[...])`:
  the SDK answers only localhost by default (421 otherwise).
- Stateless: no per-session memory between requests, so restarts and redeploys don't
  break a conversation, and Caddy needs no sticky sessions.
- stdio isn't offered: the data is on the server, and a local process would need the same
  OAuth anyway.

### 2. The site becomes its own OAuth 2.1 authorization server

The MCP endpoint is the resource server; the same app is the authorization server, and
the person behind a token is a Telegram user we already know.

| Endpoint | What it does |
| --- | --- |
| `GET /.well-known/oauth-protected-resource/mcp` | RFC 9728 metadata, added by the SDK: `resource`, `authorization_servers`, `scopes_supported` |
| `GET /.well-known/oauth-authorization-server` | RFC 8414 metadata: endpoints, `code_challenge_methods_supported: ["S256"]`, `client_id_metadata_document_supported: true`, `authorization_response_iss_parameter_supported: true`, `registration_endpoint` |
| `GET /oauth/authorize` | Validates the request, then hands over to the SPA screen `#/oauth/consent` |
| `POST /oauth/authorize` | The consent decision (needs the site session, CSRF-safe: SameSite cookie + a one-time `request_id`) → redirect with `code`, `state`, `iss` |
| `POST /oauth/token` | `authorization_code` (PKCE S256 required) and `refresh_token` (rotated every time) |
| `POST /oauth/register` | Dynamic Client Registration (RFC 7591) — deprecated by the spec, kept because existing clients still use it |
| `POST /oauth/revoke` | RFC 7009 |

The flow the player sees: Claude opens the site → if not signed in, the usual Telegram
login → a consent screen in Ukrainian: who asks (client name and the redirect **host**,
always shown; a warning for localhost-only clients), which scopes, "Allow" / "Deny".

Client identification, in the spec's order of preference:

1. **Client ID Metadata Documents**: `client_id` is an https URL; we fetch it (https only,
   no private or loopback addresses, 5 s timeout, 64 KB cap, cached by HTTP headers),
   check that its `client_id` equals the URL and take `client_name` and `redirect_uris`.
2. **DCR**: `/oauth/register` stores the client; open, but rate-limited and with clients
   that never completed an authorization purged after a day.

Rules for redirect URIs: https or `localhost` only, exact match against the registered list.

Tokens:

- Opaque random strings; only their SHA-256 is stored (like site sessions today).
- Access token: 1 hour. Refresh token: 30 days, rotated on every use; reuse of an old
  refresh token revokes the whole grant (theft detection).
- Every token is bound to its resource: the `resource` parameter (RFC 8707) must be
  `https://dnd.voronin.app/mcp`, and `TokenVerifier` rejects tokens issued for anything
  else. Tokens are never accepted by the REST API, and site sessions are never accepted
  by `/mcp`.
- Authorization codes: 60 seconds, single use, bound to `client_id`, `redirect_uri`,
  `code_challenge` and `resource`.

Storage: three new tables in the identity database — `oauth_clients`, `oauth_codes`,
`oauth_grants` (one row per user × client: scopes, refresh-token hash, access-token hash,
expiry, last use). A new "Connected apps" block on the profile lists the grants and
revokes them.

### 3. Scopes

| Scope | Allows |
| --- | --- |
| `characters:read` | list and read your characters, read the compendium |
| `characters:write` | everything in read, plus create, edit, rest, level up, share |

`write` implies `read`. A read-only token calling a write tool gets 403 with
`WWW-Authenticate: Bearer error="insufficient_scope", scope="characters:write", resource_metadata=…`,
so the client can ask for more (step-up). No `offline_access` in `scopes_supported`.

### 4. Tools

Grouped by what a player does, not mirroring the ~70 REST endpoints. Every tool takes the
user from the token; a character that isn't yours is "not found", exactly like the API.
Changing tools take the character's `version` and fail with a conflict if the sheet changed
since it was read — the SPA and the assistant can't overwrite each other.

| Tool | Scope | Annotations | Service |
| --- | --- | --- | --- |
| `list_characters` | read | read-only | store `ids_of` + summaries |
| `get_character` (`detail`: summary / full) | read | read-only | `SheetService.load` + sheet payload |
| `update_character` (HP and damage/healing, spell and pact slots, feature uses, death saves, exhaustion, inspiration, notes, equipped items) | write | idempotent | `SheetService.update` |
| `start_character` | write | — | `WizardService.start` |
| `get_creation_step` (options for a step, with keys and Ukrainian names) | read | read-only | wizard step options |
| `set_creation_step` | write | idempotent | `WizardService.apply` |
| `finish_character` | write | — | `WizardService.finish` |
| `manage_inventory` (`add` / `update` / `remove`) | write | destructive for `remove` | `add_item`, `update_item`, `remove_item` |
| `manage_spells` (`learn` / `forget` / `prepare`) | write | — | `add_spell`, `remove_spell`, `prepare_spells` |
| `rest` (`short` / `long`) | write | — | `SheetService.rest` |
| `spend_hit_dice` | write | — | `SheetService.spend_hit_die` |
| `level_up_options` | read | read-only | `LevelUpService.preview` |
| `level_up` | write | — | `LevelUpService.apply` |
| `set_class_choices` (fighting style, expertise, species feat…) | write | idempotent | `set_class_choice`, `set_expertise`, `set_species_feat` |
| `share_link` (`create` / `revoke`) | write | destructive for `revoke` | sharing |
| `export_pdf` | read | read-only | export + a 5-minute link token |
| `search_compendium` | read | read-only | compendium `entries` |
| `get_compendium_entry` | read | read-only | compendium entry |

There is no delete tool: the API has none, and losing a character to a misread sentence
is the worst failure this server could have.

Creation follows the wizard's own steps (species → class → abilities → background →
equipment → spells). `get_creation_step` returns only options the rules allow, and
`set_creation_step` validates on the server, so the assistant can't invent a subrace or
pick a spell the class doesn't have.

### 5. Resources and prompts

- Resources: `character://{id}` (the sheet as Markdown — the existing renderer) and
  `compendium://{entry_id}`.
- Prompts: "a character from an idea", "level-up advice", "apply a session recap to the
  sheet" (HP, spell slots, hit dice, items found).

### 6. Language

Tool names, descriptions and parameter docs are in English (models choose tools better
that way). Data and errors stay Ukrainian, as on the site; every option carries its key,
so the assistant never has to translate back.

### 7. Ownership moves into the application layer

The `_guard` check moves from the router into a small application service
(`CharacterAccess.require(user, character_id)` / `require_draft`), used by both the REST
router and the MCP tools. One check, two doors.

## Consequences

- Players can create and run characters from Claude on a phone, signing in with the same
  Telegram account; the site stays the single source of truth.
- We now run an authorization server. It's the riskiest code in the project and gets its
  own tests: PKCE, code reuse, redirect mismatch, refresh rotation and reuse detection,
  audience mismatch, CIMD fetch limits, scope step-up, revocation.
- `DNDSHEET_AUTH=off` (tests, local runs) skips OAuth: `/mcp` works as the local player.
- New dependency: `mcp` 2.x (Python ≥ 3.11 — we run 3.12).
- Every MCP call is logged (user, client, tool, character, result — no arguments with free
  text), and each grant is rate-limited.
- Not now: server-initiated notifications, sampling, elicitation; a stdio transport;
  MCP access to other players' shared characters.

## Plan

1. `CharacterAccess` in the application layer; the router uses it (no behaviour change).
2. OAuth authorization server: tables, endpoints, consent screen, "Connected apps".
3. `/mcp`: `TokenVerifier`, read tools, then write tools, resources, prompts.
4. Tests against an in-process client, and a manual run with Claude (custom connector).
5. `docs/mcp.md`: how to connect, what each tool does.
