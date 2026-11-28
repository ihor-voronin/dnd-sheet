# dndsheet — D&D 5e (2014) character sheet in Ukrainian

[![CI](https://github.com/ihor-voronin/dnd-sheet/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ihor-voronin/dnd-sheet/actions/workflows/ci.yml)
[![Deploy](https://github.com/ihor-voronin/dnd-sheet/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/ihor-voronin/dnd-sheet/actions/workflows/deploy.yml)
[![dnd.voronin.app](https://img.shields.io/website?url=https%3A%2F%2Fdnd.voronin.app%2Fhealthz&label=dnd.voronin.app&up_message=rolling%20initiative&down_message=resting&logo=caddy)](https://dnd.voronin.app)
[![Backend coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fihor-voronin%2Fdnd-sheet%2Fbadges%2Fbackend-coverage.json)](docs/ci.md#coverage)
[![Frontend coverage](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fihor-voronin%2Fdnd-sheet%2Fbadges%2Ffrontend-coverage.json)](docs/ci.md#coverage)
[![Tests](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fihor-voronin%2Fdnd-sheet%2Fbadges%2Ftests.json)](docs/ci.md#coverage)
[![New code coverage](https://img.shields.io/badge/new%20code%20coverage-%E2%89%A5%2080%25-blue?logo=githubactions&logoColor=white)](docs/ci.md#coverage)

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](backend/pyproject.toml)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](backend/src/dndsheet)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)](frontend/package.json)
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6?logo=typescript&logoColor=white)](frontend/tsconfig.json)
[![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)](frontend/vite.config.ts)
[![SQLite](https://img.shields.io/badge/SQLite-WAL-003B57?logo=sqlite&logoColor=white)](docs/deploy.md)
[![Docker](https://img.shields.io/badge/Docker-multi--stage-2496ED?logo=docker&logoColor=white)](Dockerfile)
[![uv](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fastral-sh%2Fuv%2Fmain%2Fassets%2Fbadge%2Fv0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fastral-sh%2Fruff%2Fmain%2Fassets%2Fbadge%2Fv2.json)](ruff.toml)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-FAB040?logo=pre-commit&logoColor=white)](.pre-commit-config.yaml)
[![Terraform](https://img.shields.io/badge/Terraform-844FBA?logo=terraform&logoColor=white)](deploy/terraform)

[![D&D 5e](https://img.shields.io/badge/D%26D%205e-2014%20rules-ED1C24?logo=dungeonsanddragons&logoColor=white)](docs/books.md)
[![Compendium](https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2Fihor-voronin%2Fdnd-sheet%2Fbadges%2Frecords.json)](docs/books.md)
[![MCP](https://img.shields.io/badge/MCP-OAuth%202.1-D97757?logo=anthropic&logoColor=white)](docs/mcp.md)
[![Ukrainian](https://img.shields.io/badge/%D0%BC%D0%BE%D0%B2%D0%B0-%D1%83%D0%BA%D1%80%D0%B0%D1%97%D0%BD%D1%81%D1%8C%D0%BA%D0%B0-0057B7?labelColor=FFD700)](docs/translation-rules.md)
[![Telegram](https://img.shields.io/badge/Telegram-Mini%20App-26A5E4?logo=telegram&logoColor=white)](https://t.me/DnD_Sheet_VoroninAppBot)
[![Secrets](https://img.shields.io/badge/secrets-git--crypt%20%F0%9F%94%92-555)](deploy/README.md)
[![Natural 20](https://img.shields.io/badge/roll-natural%2020-gold?logo=dungeonsanddragons)](https://dnd.voronin.app)
[![Found a bug?](https://img.shields.io/badge/found%20a%20bug%3F-roll%20for%20a%20PR-8A2BE2)](https://dnd.voronin.app/#/bugs)

A website where a player builds a hero by the 2014 Player's Handbook rules, keeps
the sheet during play and prints it like a paper one. The site itself is in
Ukrainian, with the original English names next to every term.

- **Site:** https://dnd.voronin.app — sign-in with Telegram; the compendium is open without signing in.
- **Telegram:** [@DnD_Sheet_VoroninAppBot](https://t.me/DnD_Sheet_VoroninAppBot) — the same site
  as a Mini App, signed in automatically.

## Features

**Compendium** (no sign-in) — 13 classes and 123 subclasses, 69 species and 64
subraces, 94 backgrounds, 109 feats, 151 optional features, 519 spells and 1135
items from 89 sources. The home page lists what each book contributes, with prices
and links to D&D Beyond.

**Character creation** — a six-step wizard: species → class → ability scores →
background → equipment → spells. The server validates every step against the 2014
rules (species bonuses, no duplicate skills, standard array and point buy, class
and background starting equipment, cantrips and spells). The draft is stored on the
server, so it can be finished on another device.

**The sheet during play** — hit points, damage and healing, temporary HP, hit dice,
death saves, spell slots and Pact Magic, class resources, short and long rests by
the rules, weapon attacks, inventory from the compendium, spell preparation,
features with their rules text, notes with autosave. Any number can be overridden
by hand (and is marked as such). Two tabs or two devices can't overwrite each other:
the sheet is versioned and refreshes itself.

**Level-up and multiclassing** — a new level in any class with prerequisite checks,
hit points, subclass, ASI or feat, new spells; for multiclass characters — slots by
caster level, separate Pact Magic, spells grouped by class with their own DC and
attack bonus.

**Printing** — a PDF styled like a paper sheet (black and white, frames, room for a
pencil): main page, spells, equipment, adventure log and extra pages with the full
text of features and spells. Or the same page in the browser.

**Sharing** — a read-only link (`/#/s/<token>`): the sheet can be viewed and printed
without signing in, but not changed. A new link revokes the old one.

**Phone and Telegram** — mobile layout for the sheet and the wizard; the Telegram
Mini App uses Telegram's theme and Back button, lets Telegram download the PDF, and
`t.me/<bot>?startapp=s_<token>` opens a shared sheet right inside the app.

**AI assistant (MCP)** — `https://dnd.voronin.app/mcp`: connect Claude (or any MCP
client) and it can create a character through the same wizard, take rests, track hit
points and items, and level up — only your characters, only by the site's rules. Sign-in is
OAuth with a consent screen on the site; connected apps are listed on the home page and can
be disconnected. [`docs/mcp.md`](docs/mcp.md).

**Found a bug?** — `#/bugs`, linked from every page footer: two dozen common
complaints with sarcastic answers, each pointing to the folder in this repository
where the fix belongs (and a fork button).

## How it works

```
Browser / Telegram Mini App            Search engines, link previews
  React SPA (Vite, TanStack Query)       server-rendered /kb/… pages
        │  JSON API, session via cookie or Bearer (Mini App)
        ▼
FastAPI  ── DDD bounded contexts, boundaries enforced by import-linter
  ├─ compendium   compendium: JSONL book corpus + derived mechanics indexes
  ├─ characters   Character aggregate, wizard, sheet, level-up, multiclass
  │                 DerivedStatsCalculator → ComputedSheet (the server computes every number)
  ├─ sheets       SheetDocument — the canonical sheet document (JSON Schema in contract/)
  ├─ export       PDF (Jinja → HTML → WeasyPrint), Markdown — behind the SheetRenderer port
  ├─ identity     Telegram sign-in (Login Widget and Mini App), sessions
  ├─ site         public HTML pages: compendium /kb/…, glossary, guide, sitemaps (Jinja, no SPA)
  └─ shared       kernel: abilities, dice, armor, money, rules tables
        │
        ▼
SQLite (WAL) — versioned characters with owners, drafts, sessions, share links
```

Key decisions live in [`docs/adr/`](docs/adr/):

- **The server owns the rules** ([0002](docs/adr/0002-server-authoritative-rules.md)):
  the frontend computes nothing itself, it shows what the server returned.
- **Content is data** ([0003](docs/adr/0003-content-is-data.md)): classes, species,
  spells and items are corpus records, not code. Mechanics (hit dice, slots, bonuses)
  are derived from them into `content/index/`.
- **Glossary-driven translation** ([0004](docs/adr/0004-glossary-driven-translation.md)):
  Ukrainian names and texts live in `content/translations/`, the rules are in
  [`docs/translation-rules.md`](docs/translation-rules.md). Display format:
  "Ukrainian (English)".
- **One sheet document** ([0001](docs/adr/0001-spa-with-canonical-document.md)):
  the screen and the printout are built from the same `SheetDocument`.
- **One shared PostgreSQL** ([0006](docs/adr/0006-shared-postgresql.md)): a PostgreSQL 18
  instance serves every project on the VPS, with a database and least-privilege roles per
  project. Storage stays behind the ports, and SQLite remains the default until the cutover
  ([docs/database.md](docs/database.md)).

## Running locally

The simplest way is Docker: API, built SPA and corpus in one container, PDF works.

```powershell
docker compose up -d --build     # → http://127.0.0.1:8000
```

The Telegram widget doesn't work on `localhost`, so locally a **development sign-in
by name** is enabled (`DNDSHEET_DEV_LOGIN=1` in compose). Data lives in `./var`
(SQLite); rebuilding the image doesn't touch it.

Without Docker (faster development with reload):

```powershell
uv sync                                                        # .venv from uv.lock: backend + dev tools
$env:DNDSHEET_DEV_LOGIN = "1"
.venv\Scripts\python -m uvicorn dndsheet.main:app --reload     # API :8000

cd frontend; npm install; npm run dev                          # SPA :5173, proxies to the API
```

PDF without Docker needs WeasyPrint with GTK (a separate runtime on Windows);
otherwise PDF returns 503 and the PDF tests are skipped. Full details and
troubleshooting: **[RUN.md](RUN.md)**.

**The book corpus is encrypted** (see below): after cloning without the git-crypt
key the compendium is empty and part of the tests fail. Unlocking is described in
[`docs/deploy.md`](docs/deploy.md), section "First run on a new machine".

## Development

```
branch ──► commit (pre-commit) ──► PR into main ──► CI: pre-commit · backend · frontend · diff-coverage
                                                          │ green
                             https://dnd.voronin.app ◄── squash-merge → deploy.yml (+ badges)
```

- **Dependencies:** the backend is managed by [uv](https://docs.astral.sh/uv/) — one
  `uv.lock` for the repository (`pyproject.toml` at the root is a uv workspace with
  `backend/` as its member). Test tools are a dev group: the production image is
  built with `uv sync --frozen --no-dev` and has none of them. The frontend uses npm.
- **pre-commit** (`pre-commit install`, [RUN.md § 5.1](RUN.md)): ruff, prettier with
  import sorting, ESLint, tsc, shellcheck, terraform fmt, TruffleHog, gitlint, `uv lock`
  check and a check that secrets and the corpus go into git only encrypted.
- **Tests:** `uv run pytest backend --cov --cov-config=backend/pyproject.toml`
  (900+ tests: rules, reference characters, 20 levels of every class, multiclass, API,
  printing), `uv run lint-imports backend/pyproject.toml` (context boundaries),
  `cd frontend; npm run test:coverage` (vitest + Testing Library over the real screens,
  answering `fetch` from API responses recorded by `scripts/record_frontend_tape.py`).
- **Coverage:** at least 80% for the backend and the frontend, and at least 80% of the
  lines each PR adds or changes ([`docs/ci.md`](docs/ci.md#coverage)).
- **CI** ([`docs/ci.md`](docs/ci.md)) — GitHub Actions on every PR: the same hooks,
  the full backend suite in a Docker image with the corpus unlocked, the frontend tests
  and build, the coverage of new code. `main` accepts changes only through a PR with
  green checks, squash-merged.
- **Auto-deploy** — after CI on `main` is green.

## Production

A RackNerd VPS (Ubuntu 24.04), domain in Cloudflare. The server runs Docker: the
app behind Caddy (HTTPS from Let's Encrypt), SQLite in `/opt/dndsheet/var` with a
daily backup. Details, server access and database restore:
[`docs/deploy.md`](docs/deploy.md).

| What | With | When |
| --- | --- | --- |
| the app (image, compose, Caddy, `.env`) | `scripts/deploy_app.py` | CI after a merge into `main`; by hand — `deploy\terraform\deploy.ps1` |
| infrastructure (DNS, Docker, firewall, swap, backups, key-only SSH) | Terraform (`deploy/terraform`) | rarely, by hand: `deploy.ps1 -Infra` |

**Secrets and the corpus are in git, but encrypted with [git-crypt](https://github.com/AGWA/git-crypt):**
`deploy/secrets/` (tokens, SSH key, `.env`, Terraform state) and
`content/compendium`, `bestiary`, `index` (book texts). They are unlocked with the
owner's GPG key or with the `GIT_CRYPT_KEY` GitHub Actions secret.

## Repository layout

```
backend/src/dndsheet/   FastAPI app (contexts — see "How it works")
backend/tests/          tests: domain, rules, API, contracts, printing
frontend/src/           React SPA: features/{home,wizard,character,auth,bugs,mcp,oauth}, seo/, telegram.ts
contract/               sheet JSON Schema and corpus formats — the single source of types
content/                glossary, source registry, translations (plain);
                        compendium/, bestiary/, index/ (encrypted)
scripts/                corpus ingest and normalization, translations, deploy, icons, hooks
deploy/                 Terraform, server files, encrypted secrets
.github/                CI, deploy, rulesets for main
branding/               icon and bot avatar (generated by scripts/make_icons.py)
docs/                   plan, ADRs, per-area descriptions (below)
```

## Documentation

| Document | About |
| --- | --- |
| [RUN.md](RUN.md) | install, run, tests, pre-commit, troubleshooting |
| [docs/plan.md](docs/plan.md) | project plan and stages |
| [docs/adr/](docs/adr/) | architecture decisions |
| [docs/domain-character.md](docs/domain-character.md) | the character: aggregate, derived numbers, reference characters |
| [docs/wizard.md](docs/wizard.md) | the creation wizard |
| [docs/sheet.md](docs/sheet.md) | the sheet during play |
| [docs/level-up.md](docs/level-up.md) | level-up and multiclass |
| [docs/spells.md](docs/spells.md) | spells outside of level-up |
| [docs/export.md](docs/export.md) | printing and PDF |
| [docs/api-compendium.md](docs/api-compendium.md) | compendium API |
| [docs/mcp.md](docs/mcp.md) | MCP server for AI assistants, OAuth sign-in |
| [docs/seo.md](docs/seo.md) | SEO: analysis, server-rendered compendium pages, licensing policy, sitemaps, what's next |
| [docs/format.md](docs/format.md) | corpus record format |
| [docs/books.md](docs/books.md) | the 2014 book line and what each book provides |
| [docs/translation-rules.md](docs/translation-rules.md), [docs/translation.md](docs/translation.md) | translation rules and status |
| [docs/deploy.md](docs/deploy.md) | server, Terraform, secrets, Telegram, backups |
| [docs/database.md](docs/database.md) | shared PostgreSQL: setup, migrations, moving off SQLite, rollback, experiments |
| [docs/platform.md](docs/platform.md) | several projects on one VPS: moved to the [vps-infra](https://github.com/ihor-voronin/vps-infra/blob/main/docs/platform.md) repository |
| [docs/ci.md](docs/ci.md) | GitHub Actions, rules for `main`, auto-deploy |
| [docs/next-steps.md](docs/next-steps.md) | what's next |

Documentation, code comments in tooling and pipelines are in English; the site's
content (UI texts, translations, glossary) is in Ukrainian.

## Legal

- An unofficial **non-commercial** fan project: free, no ads, not affiliated with
  Wizards of the Coast or D&D Beyond. The Fan Content Policy notice is on the
  site's home page.
- Dungeons & Dragons, book and setting names, and the rules texts are property of
  Wizards of the Coast. The translation is amateur, made for convenience at the table.
- **Book texts are in this public repository only in encrypted form** (git-crypt).
  Code, the glossary and translations of names and texts (`content/translations/`)
  are in plain text.
- D&D Beyond is used only as a manual reference (name checks, book prices and links;
  covers are shown by linking to their site). There is no automated download of their
  content in the code.
