# Visuals: portraits, emblems, backgrounds

What pictures the site has, where they come from, how they are served and what they cost.
The rule behind every choice: **no Wizards of the Coast or D&D Beyond art, nothing scraped,
only our own drawings or openly licensed sets with attribution**, and **no slowdown**.

## What is where

| Where | Picture | Source |
| --- | --- | --- |
| Sheet header, home cards, shared sheet | the character's portrait (hexagon, 64–96 px) | own, drawn in code |
| Sheet → click the portrait | the portrait picker: 24 recommendations + the whole catalogue | own |
| Printed sheet / PDF | a light "paper" version of the portrait in the name banner | own |
| Wizard, species step | a sample portrait on every species card | own |
| Wizard, class step | the class emblem on every class card | game-icons.net |
| Wizard, background | a faint "summoning circle" (circles, hexagram, d20) | own |
| `/kb` home | an emblem per section | game-icons.net |
| `/kb/classes`, class and subclass pages | the class emblem; four portraits of the class | game-icons.net + own |
| `/kb/spells`, spell pages | the school-of-magic emblem | game-icons.net |
| species pages | four portraits of the species | own |
| other entry pages | the section emblem | game-icons.net |
| `/kb/credits` | every icon, its author and licence | — |

## Portraits (own art)

`backend/src/dndsheet/visuals/` — a bounded context of its own (import-linter: `api → application → domain`).

- **Catalogue** (`domain/catalog.py`): a portrait is *species group × gender × class × variant*.
  43 groups (human, elf, drow, dwarf, dragonborn, tabaxi, kenku, warforged, …) cover every
  species in the corpus by name (`species_group("Mountain Dwarf") == "dwarf"`); gendered groups
  have female and male portraits, the others (birds, constructs, dragonborn…) one kind (`x`).
  13 classes, 1–3 variants: **1248 portraits**. Ids are stable (`elf-f-wizard-1`): the sheet
  stores them, so the scheme can only change together with a migration of saved sheets.
- **Drawing** (`application/portraits.py`): flat shapes in the site's palette — a bust
  (class outfit: robe, armour, furs, cloak, apron…), the head of the species (humanoid with
  ears, horns, tusks, halo, fins…; or a dragon, cat, bird, tortle, warforged, bull, elephant
  head), hair and beard, class headgear (wizard hat, hood, helm, circlet, goggles, antlers…).
  Variants differ by skin, hair and headgear, chosen by a stable hash of the id, so an id
  always draws the same picture. Each file is a self-contained SVG with its own dark
  background: it reads the same in the dark and the light theme, like a token on the table.
  `render(..., paper=True)` gives the print version (white hexagon, thin frame).
- **Recommendations** (`catalog.recommend`): own species + own gender, own class first, then
  the other classes of the species, then the same class of other species — 24 by default
  (the owner asked for 20–30 out of up to 2000).
- **Default portrait**: until the player picks one, the sheet shows one of the
  recommendations for its species, class and gender, chosen by the character's id (two elf
  wizards in one party are not twins). `portrait.chosen` says which case it is.

### Gender

The character had no gender. It now has an **optional** `gender` (`female` / `male` / none),
asked on the wizard's species step next to the name and editable in the portrait picker. It
affects nothing but the portrait recommendations (no rules use it); "not set" shows both.
The picker also filters the catalogue by the portrait's look (female / male / no gender
cues) independently of the character's field.

### Stored data

Two new optional keys in the character JSON record (`characters/infrastructure/character_json.py`)
and one in the draft record; old records read as "not set":

| Record | Key | Value |
| --- | --- | --- |
| character | `gender` | `"female"`, `"male"` or `null` |
| character | `avatar` | a portrait id (`elf-f-wizard-1`) or `null` (default portrait) |
| wizard draft | `gender` | as above, copied to the character on finish |

No new table or column: the database move (SQLite → Postgres) only carries the JSON along.

### API

| Request | What |
| --- | --- |
| `PATCH /api/v1/characters/{id}` with `avatar` and/or `gender` | change them; versioned like every sheet change (`version`, 409 on a stale one); an unknown portrait id → 422 |
| `GET /api/v1/characters/{id}` | `character.gender`, `character.avatar`, `character.portrait {id, url, label, chosen}` (also in the roster and the shared sheet) |
| `GET /api/v1/avatars` | the catalogue: `base` URL, groups, classes, `items` as `[id, group, f/m/x, class]` (61 KB, 8 KB gzip, cached an hour) |
| `GET /api/v1/avatars/recommended?species=&class=&gender=` | recommendations with `url` and `label` |
| `GET /assets/avatars/<version>/<id>.svg` | one portrait (no sign-in) |
| `GET /assets/emblems/<version>/<name>.svg` | one emblem, for the SPA's CSS masks |

`<version>` is a hash of the drawing code (portraits) or of `emblems.json` (emblems): a file
under the current version never changes, so it is served `immutable` for a year (and Caddy
adds the same for `/assets/*`); a stale version still works but is cached 5 minutes only.
The server renders a portrait in well under a millisecond and keeps 4096 in memory.

MCP: `set_avatar` (without `avatar` it lists the current portrait and 24 suggestions with
URLs; with `avatar`/`gender` and `version` it changes them), `update_character` accepts the
same two fields, the species step takes `gender`. See [mcp.md](mcp.md).

## Emblems (game-icons.net, CC BY 3.0)

30 icons from [game-icons.net](https://game-icons.net) (by Lorc and Delapouite), licence
[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Only the shape is used, recoloured
to the theme (`currentColor` / CSS mask). Every icon, its author and its page are listed on
`/kb/credits` and in [CREDITS.md](../CREDITS.md); the compendium footer links there.

`scripts/make_emblems.py <game-icons checkout>` picks the icons (the `CHOSEN` table: 13
classes, 8 schools, 9 sections), rounds the path data to one decimal (a third fewer bytes)
and writes `backend/src/dndsheet/visuals/application/emblems.json` with author and URL. To
add one: add a line to `CHOSEN`, run the script, add a label in `site/api/router.py`
(`_EMBLEM_LABELS`) and use it.

- **Compendium pages** (server-rendered, no SPA bundle): the template calls `emblem(name)`;
  `Sprite` collects the names and `base.html.jinja` inserts only those shapes as `<symbol>`s
  in one hidden `<svg>` at the end of `<body>`. No extra request, no layout shift (the size
  is in the inlined CSS), `aria-hidden` (an emblem sits next to the name it illustrates).
- **SPA**: class cards use `/assets/emblems/…/class-*.svg` as a CSS mask painted in
  `--brass`, so it follows the theme.

## Wizard background

A "summoning circle" — circles with tick marks, a hexagram and a d20 in the middle — drawn by
us, as a 2 KB SVG data URI in `theme.css` used as a CSS **mask** on a fixed `::before` of
`.wizard`, painted in `--brass` at 8–10 % opacity: it takes the theme's colour, never covers
text, costs no request, is hidden in print and shrinks to one circle on phones.

## Accessibility

- The sheet portrait is a button «Змінити портрет (зараз: …)» with `aria-expanded`; its image
  is `alt=""` (the button names it). On the shared sheet the image has a descriptive `alt`.
- Home cards: `alt=""` — the card already says who the hero is; a second label would be noise.
- Picker tiles are buttons with the portrait's description as `aria-label`, `aria-pressed` for
  the current one, marked by a crimson ring **and** a ✓ (not colour alone). Keyboard focus
  draws a hexagonal ring in the text colour (a plain `outline` would be clipped by `clip-path`).
- Species/compendium portraits have descriptive `alt`; emblems are `aria-hidden`.

## Cost (measured)

Local build and server, before → after this change.

| What | Before | After |
| --- | --- | --- |
| SPA main JS | 711.9 KB (217.4 KB gzip) | 715.6 KB (219.0 KB gzip) |
| SPA CSS | 117.2 KB (19.0 KB gzip) | 123.9 KB (20.7 KB gzip) |
| Portrait picker | — | lazy chunk 4.8 KB (1.9 KB gzip), loaded on first open |
| One portrait SVG | — | 4.3 KB average, 1.2 KB gzip; lazy `<img>` with `width`/`height` |
| `/kb` HTML | 17.4 KB (5.3 gzip) | 30.6 KB (10.7 gzip) |
| `/kb/classes` | 27.1 KB (7.4 gzip) | 43.3 KB (14.1 gzip) |
| `/kb/classes/wizard` | 74.8 KB (16.8 gzip) | 78.3 KB (18.5 gzip) + 4 lazy portraits |
| `/kb/spells` | 124.1 KB (24.7 gzip) | 177.8 KB (29.7 gzip) |
| `/kb/spells/fireball` | 19.4 KB (6.0 gzip) | 21.9 KB (6.9 gzip) |
| `/kb/species/elf` | 67.8 KB (16.5 gzip) | 71.3 KB (17.7 gzip) + 4 lazy portraits |
| CLS (sheet, compendium) | 0 | 0 |
| LCP element | text (`h1.sheet-name`, first paragraph) | the same text |

Compendium pages still load no script bundle and make no extra requests for emblems; the
LCP element is still text, so pictures can't delay it. Local LCP timings in the dev browser
were too noisy (±1 s between identical reloads) to compare; the structural checks above are
what the numbers rest on. To re-measure: `logs/measure_pages.py`-style fetch of the pages
(HTML size raw/gzip) and the `PerformanceObserver` snippet for LCP/CLS in a real browser.

## Ideas not done

- Per-subclass emblems (today a subclass shows its class's emblem).
- A light "paper" theme for portraits on screen; uploads of the player's own portrait.
- More variants per group (the catalogue can grow to ~2000 without UI changes: ids only add).
