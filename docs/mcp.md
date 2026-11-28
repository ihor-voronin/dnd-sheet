# MCP: your characters in an AI assistant

`https://dnd.voronin.app/mcp` is a [Model Context Protocol](https://modelcontextprotocol.io)
server: Claude (or any MCP client) can list, create and run **your** characters with the
same rules as the site. Why it's built this way: [ADR 0005](adr/0005-mcp-server.md).

## Connecting

You need an account on the site first: sign in through Telegram once. The app can't create
one for you.

- **Claude (web, desktop, mobile)**: Settings → Connectors → add a custom connector with the
  URL `https://dnd.voronin.app/mcp`. Claude opens the site; sign in with Telegram if asked,
  check the app name and the return address, press «Дозволити».
- **Claude Code**:

  ```powershell
  claude mcp add --transport http dnd-sheet https://dnd.voronin.app/mcp
  ```

  then `/mcp` in Claude Code → dnd-sheet → authenticate.

Connected apps are listed on the home page («Підключені застосунки»); «Відключити» revokes
an app's access at once.

## What the assistant can do

| Tool | What it does |
| --- | --- |
| `list_characters` | your characters and an unfinished creation draft |
| `get_character` | the sheet: a summary (numbers, state, items, spells) or everything |
| `update_character` | hit points, damage and healing, spent slots and feature uses, death saves, exhaustion, inspiration, notes, equipped items; also `gender` and `avatar` |
| `start_character` → `get_creation_step` / `set_creation_step` → `finish_character` | the site's creation wizard, step by step, with only the options the rules allow |
| `manage_inventory` | add, change, remove items |
| `manage_spells` | learn or forget a spell, set the day's prepared spells; add and edit a custom spell (`custom: true`, class `"other"` for one outside any class) |
| `manage_custom_features` | add, change, remove a custom feature — a DM's boon, an item's ability, a house rule; with `uses` it gets a counter rests restore |
| `rest`, `spend_hit_dice` | short and long rests, hit dice |
| `level_up_options`, `level_up` | what the next level gives, and taking it |
| `set_class_choice`, `set_expertise` | fighting style, invocations, metamagic…; expertise |
| `set_avatar` | the character's portrait: without `avatar`, the current one and 24 suggestions for its species, class and gender (with image URLs); with `avatar` and/or `gender` (and `version`) changes them |
| `share_link` | the read-only link for the table or the DM |
| `export_pdf` | a PDF download link (5 minutes) |
| `search_compendium`, `get_compendium_entry` | the rules: spells, items, feats, species… |
| `delete_character` | delete a character for good — only with its exact name, after you confirm |

Custom features and spells are what the table has but the books don't: the assistant writes
them as the player says, the sheet marks them «власне» and computes nothing from them. The
sheet summary lists them (`custom_features`, and `custom: true` on spells) with their text
cut to 200 characters.

Also a resource, `character://<id>` (the sheet as Markdown), and three prompts: a character
from an idea, level-up advice, applying a session recap to the sheet.

Up to 50 characters per player, as on the site. Step-by-step instructions in Ukrainian are on
the site itself: [dnd.voronin.app/#/mcp](https://dnd.voronin.app/#/mcp).

## Security in short

- OAuth 2.1 with PKCE; the site is its own authorization server. Tokens work only for
  `/mcp` and only for your characters; the site's session cookie doesn't work there.
- Access tokens live an hour, refresh tokens 30 days and change on every use; a reused old
  refresh token revokes the app's access entirely.
- Only hashes of codes and tokens are stored.

## Running locally

With `DNDSHEET_AUTH=off` (single-player mode, as in the tests) `/mcp` works without
tokens, as the local player:

```powershell
claude mcp add --transport http dnd-local http://localhost:8000/mcp
```

With sign-in on, set `DNDSHEET_PUBLIC_URL` to the address the client uses (for example
`http://localhost:8000`): it's the token issuer, the resource the tokens are bound to and
the only allowed `Host`. Production sets it in `deploy/secrets/prod.env`.

Code: `backend/src/dndsheet/assistant/` (tools), `backend/src/dndsheet/identity/` (OAuth),
`frontend/src/features/oauth/` (consent screen and connected apps). Tests:
`backend/tests/assistant/`, `backend/tests/identity/test_oauth*.py`.
