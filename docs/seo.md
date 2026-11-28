# Search engines and link previews

The SPA is one HTML page with hash routes (`#/kb/…`), so to a crawler the whole site is
`/`. What it gets there:

| What | Where |
| --- | --- |
| title, description, canonical, Open Graph, Twitter card, JSON-LD `WebApplication` | `frontend/index.html` |
| a `<noscript>` summary for crawlers without JavaScript (AI crawlers, link unfurlers) | `frontend/index.html` |
| the preview image, 1200×630 | `frontend/public/og-image.png`, drawn by `scripts/make_og_image.py` (site fonts, the real printed sheet) |
| `robots.txt` (OAuth, MCP, sign-in and shared sheets closed; the compendium API open — rendering reads it) and `sitemap.xml` | `backend/src/dndsheet/api/app.py`, `_configure_crawlers`, from `DNDSHEET_PUBLIC_URL` |
| a tab title per page, the character's name on its sheet | `frontend/src/App.tsx` (`pageTitle`), `CharacterView` |
| a year of caching for hashed `/assets/*`, HSTS, `nosniff`, referrer policy | `deploy/terraform/files/Caddyfile.tftpl` |

Regenerate the preview image after changing the sheet preview or the name:

```powershell
.venv\Scripts\python.exe scripts\make_og_image.py
```

## Not done yet

- **Real URLs and server-rendered pages for the compendium** (`/kb/spells/fireball`): the
  biggest gain — thousands of Ukrainian pages no other site has. Needs a licensing
  decision first: SRD and free entries can be indexed in full; entries from paid books
  should get a name, metadata and a short summary (full text only in the app, `noindex`).
- Real URLs for `/mcp` and `/bugs` instead of `#/…`.
- A glossary page from `content/glossary.uk.yml`, guides ("how to create a character").
- Splitting the 700 KB bundle (compendium and wizard loaded on demand).
- `llms.txt` once there are pages worth pointing to.
