# Search engines and link previews

## Analysis (November 2026)

**State before this work.** The site wasn't indexed (no results for `site:dnd.voronin.app`).
The SPA is one HTML page with hash routes (`#/kb/…`), so to a crawler the whole site was
`/`: an empty `<div id="root">`, a `<noscript>` paragraph, and a one-URL sitemap. All the
compendium content lived behind JavaScript and `#` URLs, which search engines treat as one
page.

**Demand.** Ukrainian D&D players search for the same things as everyone else: a spell or
class by name ("вогняна куля днд", "паладин 5е"), lists ("закляття 1 рівня", "раси днд"),
rules terms ("рятівний кидок що це", "кість хітів"), and "how to make a character". No
keyword-volume tool is connected, so volumes are qualitative: the long tail of entry names
is the bulk of it, and Russian-language sites answer most of these queries today.

**Competitors.**

| Site | What | Strength | Gap we fill |
| --- | --- | --- | --- |
| [1d20.com.ua](https://1d20.com.ua/) | Ukrainian knowledge base: ~14,000 pages (spells, monsters, items, classes), 2014 and 2024 rules, a character builder; real URLs (`/classes/wizard-xphb/`) | the strongest Ukrainian competitor, already indexed | our sheet computes every number and prints a PDF; one canonical page per 2014 entry with the English name in the title |
| [5esrd.kyiv.ua](https://5esrd.kyiv.ua/) | SRD 5.1 translation (community ІНРІУМ): static HTML, `/spells/fireball.html` ("Вогнекуля [Fireball]") | clean static pages, a sitemap | SRD only: no PHB/XGE/TCE spells, subclasses, feats or backgrounds |
| wiki.dnd.in.ua | terminology wiki | — | returned HTTP 500 when checked |
| dnd.su, ttg.club | Russian | dominate Cyrillic results | Ukrainian-language queries |
| D&D Beyond, aidedd.org | English | dominate English results | Ukrainian |

So the niche isn't empty, but no Ukrainian site combines a full 2014 compendium with a
character sheet. Our assets are thousands of Ukrainian entries with both names
("Вогняна куля (Fireball)"), a glossary, and the wizard.

**What to build, in order of impact.**

1. Server-rendered compendium pages with real URLs: about 2,200 indexable pages.
   **Done.**
2. Sitemaps and internal links (sections, related entries, class ↔ spells,
   subclasses). **Done.**
3. A glossary of terms ("що таке рятівний кидок"): informational queries with no
   Ukrainian answer. **Done.**
4. A "how to create a character" guide that leads into the wizard: the main conversion
   page. **Done.**
5. Getting the pages indexed: Search Console and links from communities. **Owner's
   step** (see below).
6. Splitting the SPA bundle: it doesn't affect the compendium pages (they don't load it),
   only the home page. **Later.**

## What's built

| What | Where |
| --- | --- |
| Compendium pages: `/kb`, `/kb/<section>`, `/kb/<section>/<slug>`, `/kb/classes/<class>/<subclass>` | `backend/src/dndsheet/site/` (`api/router.py`, `api/pages.py`, templates) |
| One page per name: duplicates across books are merged, other slugs redirect (301) | `site/application/catalog.py` (`_rank`, `alias`) |
| Glossary `/kb/glossary`: the player glossary plus the UA–EN terminology table | `frontend/src/glossary.ts`, `content/glossary.uk.yml` |
| Guide `/guides/create-character` | `site/api/templates/guide_create_character.html.jinja` |
| Sitemap index `/sitemap.xml` → `/sitemaps/{pages,species,classes,…}.xml` | `site/api/router.py` |
| `/llms.txt` for AI search | `site/api/router.py` |
| `robots.txt` (OAuth, MCP, sign-in and shared sheets closed) | `backend/src/dndsheet/api/app.py`, `_configure_crawlers` |
| Real paths for SPA pages: `/bugs`, `/mcp` (a browser gets the SPA, an MCP client gets the protocol) | `api/app.py` (`SPA_PATHS`, `_BrowserOrMcp`), `frontend/src/App.tsx` (`PATH_ROUTES`) |
| title, description, canonical, Open Graph, JSON-LD `WebApplication` for the home page | `frontend/index.html` |
| the preview image, 1200×630 | `frontend/public/og-image.png`, drawn by `scripts/make_og_image.py` |
| a year of caching for hashed `/assets/*`, gzip/zstd, HSTS | `deploy/terraform/files/Caddyfile.tftpl` |

Every entry page has a unique `<title>` ("Вогняна куля (Fireball) — закляття D&D 5e
українською"), a meta description from the Ukrainian text, a canonical URL, one H1 with
both names, breadcrumbs with `BreadcrumbList` JSON-LD, facts (level, school, range…; hit
die, saving throws…), the full text, links to related entries, the source book with its D&D
Beyond link, and a call to action into the wizard. Terms in the facts link to the glossary.
SRD pages carry the CC BY 4.0 attribution the SRD requires.

**The pages don't load the SPA.** They are plain HTML with inline CSS and the site's
Alegreya fonts from the SPA build (`/assets/*.woff2`, found by name at runtime), plus about
40 lines of inline JS (theme toggle, filtering a section's list). A spell page is about
16 KB before gzip and renders in a few milliseconds once the catalog is in memory (the first
request builds it in about 2 s). So the 700 KB bundle doesn't affect their Core Web Vitals.

**The SPA links to these pages.** The in-app compendium (`features/knowledge`) was removed:
"Довідник" and the home page's contents are plain links to `/kb/…`, and old `#/kb/<section>/<key>`
links are sent to the matching page (`frontend/src/seo/kbLinks.ts`; the server redirects
slugs from other books). One URL per entry, readable without JavaScript.

**Where the Ukrainian comes from.** The pages use the same data as the wizard: species,
classes and backgrounds from `characters.api.knowledge` and the wizard's class and subclass
endpoints; spells, feats, options and items from the compendium plus `content/translations/`.
The SPA's dictionaries (species, class and item names, skill and ability labels, the player
glossary) live in `frontend/src`, so `npm run build` exports them to
`dist/kb-labels.json` (`frontend/scripts/export-kb-labels.mjs`) and the backend reads that
file. Without it the pages still work, with English names for species and classes.

## Licensing policy

The owner's decision (November 2026): **every entry, whatever its license, is published in
full and indexed**, and `free` (free WotC PDFs) is treated like SRD. The risk is known: the
texts of paid books belong to Wizards of the Coast, and a takedown request is possible.
1d20.com.ua publishes the same way.

So the policy can be changed without a code change, through `DNDSHEET_KB_PROPRIETARY` (for
`proprietary` and `third_party` entries; SRD and `free` are always full):

| Value | Book text | Indexed | In the sitemap |
| --- | --- | --- | --- |
| `full` (default) | yes | yes | yes |
| `summary` | no: name, facts, source book with a link, "the full text is in the app" | yes | yes |
| `noindex` | yes | no (`noindex` meta + `X-Robots-Tag`) | no |

A page with no Ukrainian at all (no name, no text) is `noindex` under any policy: it would
be a copy of English sites. The rules are in `site/domain/publication.py` and are tested in
`backend/tests/site/`.

## Owner's steps after deploy

1. Add `https://dnd.voronin.app` to [Google Search Console](https://search.google.com/search-console)
   (DNS TXT record) and submit `https://dnd.voronin.app/sitemap.xml`. Each section is its own
   sitemap, so coverage shows per section.
2. The same in [Bing Webmaster Tools](https://www.bing.com/webmasters) (it also feeds
   ChatGPT search and DuckDuckGo).
3. Links: the ІНРІУМ Telegram (@dnd_ua) and Discord, Ukrainian D&D chats and groups,
   the GitHub README. A few links from Ukrainian D&D communities matter more than anything
   on the page.

## Not done yet

- **`lastmod` in the sitemaps.** The corpus has `fetched_at`, but translations change
  later and their dates aren't recorded, so a `lastmod` would be wrong. Google ignores
  inaccurate `lastmod`, so it's left out until translation files carry dates.
- **Monsters** (`content/bestiary/`): a separate corpus with no Ukrainian translation yet.
  Pages without Ukrainian wouldn't be indexed (see above).
- **Rules** (`category: rule`, 636 entries): English only for now.
- **Splitting the 700 KB bundle** (wizard and sheet on demand): only the SPA's home page
  would gain.
- **Telegram Mini App**: the compendium pages open as plain pages inside Telegram; the
  Telegram back button is the app's, not the page's.
- **Item descriptions**: 235 of 1,135 items have Ukrainian text; the rest show the
  English text under a Ukrainian name.

Regenerate the preview image after changing the sheet preview or the name:

```powershell
.venv\Scripts\python.exe scripts\make_og_image.py
```
