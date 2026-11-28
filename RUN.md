# Running dndsheet

Step by step: first install, daily run, tests, pre-commit, troubleshooting.
Production (server, Terraform, secrets) is in [docs/deploy.md](docs/deploy.md);
CI and auto-deploy in [docs/ci.md](docs/ci.md).

**Requirements:** Python ≥ 3.11, Node ≥ 20, Git, Docker Desktop (recommended).
Checked on Windows 11 / PowerShell 7 with Python 3.12–3.13 and Node 22–24.

---

## 0. Where to run commands

All commands below run from the repository root unless stated otherwise.

**After cloning**, unlock the encrypted files (book corpus and deploy secrets) —
without that the compendium is empty and part of the tests fail:

```powershell
git config gpg.program "C:/Program Files/GnuPG/bin/gpg.exe"
git-crypt unlock
```

Details and who can unlock: [docs/deploy.md](docs/deploy.md), section "First run on a new machine".

---

## 1. First install (once)

### 1.1 Python environment

Backend dependencies are managed by [uv](https://docs.astral.sh/uv/)
(`winget install --id astral-sh.uv -e`). The versions are pinned in `uv.lock`:

```powershell
uv sync
```

Creates `.venv` (Python 3.11+; the image uses 3.12) with the backend installed
editable, FastAPI, Pydantic, Jinja2, uvicorn and the dev group: pytest, pytest-cov,
jsonschema, httpx2, import-linter, pyyaml. `uv run <command>` runs anything in it;
`.\.venv\Scripts\python.exe` works too.

If `.venv` also holds tools uv doesn't know about (OCR and ingest scripts), add
`--inexact`: plain `uv sync` removes packages that aren't in the lock.

After changing dependencies in `backend/pyproject.toml`: `uv lock` (the pre-commit
hook fails if the lock is stale), and commit `uv.lock`.

Check:

```powershell
uv run pytest backend -q
```

Expected: all tests pass; 2 are skipped on Windows without GTK (PDF, see section 6).

### 1.2 Frontend

```powershell
cd frontend
npm install
npm run contract      # generates TypeScript types from contract/sheet-document.schema.json
```

> Re-run `npm run contract` **every time** `contract/sheet-document.schema.json` changes.
> `src/contract/sheetDocument.ts` is generated — don't edit it by hand.

### 1.3 (Optional) PDF rendering

```powershell
uv sync --extra pdf
```

On Windows this is **not enough**: WeasyPrint needs GTK (Pango). See section 6.

---

## 2. Daily run (development mode)

Two terminals.

**Terminal 1 — API:**

```powershell
$env:DNDSHEET_DEV_LOGIN = "1"     # sign in by name; Telegram doesn't work on localhost
.\.venv\Scripts\python.exe -m uvicorn dndsheet.main:app --reload
```

**Terminal 2 — SPA with hot reload:**

```powershell
cd frontend
npm run dev
```

Open **http://127.0.0.1:5173**. Vite proxies `/api` and `/healthz` to
`http://127.0.0.1:8000` (see `frontend/vite.config.ts`), so no CORS is needed.

---

## 3. Single server (like production)

FastAPI serves the built frontend from the same origin.

```powershell
cd frontend
npm run build
cd ..
.\.venv\Scripts\python.exe -m uvicorn dndsheet.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**.

Data (SQLite: characters, wizard drafts, users, sessions) lives in `var/`, which is
not in git. To use another folder:

```powershell
$env:DNDSHEET_DATA_DIR = "C:\dndsheet-data"
```

---

## 3.1 Docker: everything in a container (recommended)

Only Docker Desktop is needed — no local Python or Node.

```powershell
docker compose up -d --build        # build the image and start
docker compose ps                   # status and port
docker compose logs -f app          # logs
docker compose down                 # stop
```

Open **http://127.0.0.1:8000** (the port is bound to this machine only: `127.0.0.1:8000:8000`).

What's in the image (`Dockerfile`):

- stage `web` (node:22-alpine) builds the SPA — `tsc --noEmit && vite build`; Node doesn't reach the final image;
- stage `deps` installs the backend with the `pdf` extra into a separate prefix, without `.pyc` and sources;
- stage `runtime` (python:3.12-slim) gets the installed packages, the Pango/HarfBuzz libraries
  and a Cyrillic font for WeasyPrint, `content/sources.yml`, `content/compendium`,
  `content/bestiary`, `content/index` and translations (not `content/raw` — only ingest needs it);
- `.dockerignore` excludes `content/raw`, `var/`, `logs/`, `.venv`, `node_modules`.

Data lives on the host: `./var` is mounted into `/app/var`, so characters, drafts and
users (`var/dndsheet.sqlite3`) survive `docker compose down` and rebuilds. Old
`var/characters/*.json` files are imported into the database on first start and kept
on disk as a backup.

```powershell
docker compose exec app ls /app/var   # the database from inside
```

Environment the image uses: `DNDSHEET_DATA_DIR=/app/var`, `DNDSHEET_CONTENT_DIR=/app/content`,
`DNDSHEET_SPA_DIST=/app/frontend/dist` (all set in `docker-compose.yml`).

**PDF works in Docker.** `GET /api/v1/characters/<id>/export/pdf` returns A4 pages with
Cyrillic text — unlike Windows without GTK, where it's 503.

After code changes:

```powershell
docker compose up -d --build     # rebuild and restart
```

**Auto-rebuild.** `watch-docker.cmd` (or `docker compose up -d --build` followed by
`docker compose watch`) watches `frontend/`, `backend/src`, `backend/pyproject.toml` and
`content/translations`: on save the image is rebuilt and the container restarts (1–2 min
per build). Keep the window open; closing it stops watching, the container keeps running
the last version.

**Fast dev mode.** `dev-docker.cmd` (or `docker compose --profile dev up api-dev web-dev`)
runs Vite on http://127.0.0.1:5173 and the API with `uvicorn --reload` on 8001. Code is
mounted from disk, so changes in `frontend/` and `backend/src` show up in seconds,
without rebuilding the image.

**Tests in Docker.** `test-docker.cmd` (or `docker compose --profile test run --rm --build test`)
runs `pytest` and the import contracts in an image with the corpus and WeasyPrint — so
including the PDF tests that are skipped on Windows. CI runs exactly this image
(see [docs/ci.md](docs/ci.md)).

PostgreSQL is in compose but not used by the app yet (state is SQLite in `var/`).
Start it if needed: `docker compose --profile db up -d` (port 5433).

## 3.2 Telegram sign-in and who sees what

- **Without signing in** — the compendium only (`#/kb`): species, classes with
  subclasses, backgrounds, feats, spells, optional features, items; plus shared
  read-only sheets (`#/s/<token>`).
- **Signed in** — your own characters and drafts. They're in the server database, so the
  same player sees them from a phone, a laptop or another browser. Someone else's
  character "doesn't exist" for the API (404).
- **The sheet syncs itself**: every 4 seconds it asks for the version number and reloads
  if the sheet was changed on another device. Two simultaneous edits of the same version
  can't overwrite each other — the second gets "the sheet was changed on another device"
  and the screen shows the fresh version.

**Setting up the bot** (needs a public HTTPS address — Telegram doesn't allow the
widget on `localhost`):

1. In [@BotFather](https://t.me/BotFather): `/newbot` → bot name and username, get the token.
2. There, `/setdomain` → choose the bot → enter the site's domain (without `https://`).
3. Create `.env` next to `docker-compose.yml` (not in git):

   ```
   DNDSHEET_TELEGRAM_BOT=bot_username_without_at
   DNDSHEET_TELEGRAM_BOT_TOKEN=123456:ABC...
   DNDSHEET_DEV_LOGIN=0
   DNDSHEET_OWNER_TELEGRAM_ID=your_numeric_id   # optional
   ```

   For production these values are stored in the repository encrypted —
   `deploy/secrets/prod.env` (git-crypt + GPG); see [`deploy/README.md`](deploy/README.md).

4. `docker compose up -d --build`. The home page shows the "Log in with Telegram" button.

The server checks Telegram's signature (HMAC with the bot token) and freshness (up to a
day), then issues its own 30-day cookie session (HttpOnly, SameSite=Lax; `Secure` when the
site is served over HTTPS or the proxy sends `X-Forwarded-Proto: https`; force it with
`DNDSHEET_COOKIE_SECURE=1`). The database stores only a SHA-256 of the session token.
The Telegram Mini App signs in with `initData` and sends the session as a Bearer header
(see [docs/deploy.md](docs/deploy.md)).

**Who gets old characters.** Characters imported from files have no owner. They go to
the user from `DNDSHEET_OWNER_TELEGRAM_ID`, or, if it isn't set, to the first user who
signs in.

**Development sign-in** (`DNDSHEET_DEV_LOGIN=1`, on by default in compose) — a "player
name" field instead of Telegram, to work on `localhost`. Anyone who can see the page can
sign in under any name, which is why the port is bound to `127.0.0.1` only.
**Turn it off before exposing the site** (`DNDSHEET_DEV_LOGIN=0` in `.env`).

**No sign-in at all** (`DNDSHEET_AUTH=off`) — single-player mode: everything belongs to
a "local player". The tests run this way.

**MCP for AI assistants** (`/mcp`, [`docs/mcp.md`](docs/mcp.md)) — with sign-in on, set
`DNDSHEET_PUBLIC_URL` to the address clients use (default `http://localhost:8000`): it's
the OAuth issuer, the resource tokens are bound to and the only allowed `Host` for `/mcp`.
With `DNDSHEET_AUTH=off`, `/mcp` needs no token.

---

## 4. What to look at right away

| URL | What it is |
|---|---|
| `http://127.0.0.1:8000/` | SPA: home page, your characters, compendium |
| `http://127.0.0.1:8000/healthz` | `{"status":"ok"}` |
| `http://127.0.0.1:8000/#/create` | the character creation wizard (6 steps) |
| `http://127.0.0.1:8000/#/character/<id>/level-up` | level-up: class, hit points, subclass, abilities, spells |
| `http://127.0.0.1:8000/#/bugs` | "Found a bug?" |
| `http://127.0.0.1:8000/api/v1/characters` | saved characters |
| `http://127.0.0.1:8000/api/v1/demo/sheet` | `SheetDocument` (JSON) |
| `http://127.0.0.1:8000/api/v1/renderers` | `{"formats":["markdown","pdf"]}` |
| `http://127.0.0.1:8000/docs` | Swagger UI |

In the SPA, hover or focus a term to see the original English text.

---

## 5. Tests and quality gates

```powershell
python scripts\preflight.py                                            # no dependencies, stdlib only
uv run pytest backend -q --cov --cov-config=backend/pyproject.toml  # backend tests, coverage ≥ 80%
uv run lint-imports backend/pyproject.toml                  # bounded-context contracts

cd frontend
npm run typecheck                                                      # tsc --noEmit
npm run lint                                                           # ESLint, 0 warnings
npm run test:coverage                                                  # vitest, coverage ≥ 80%
npm run build                                                          # tsc + vite build
```

Coverage of a branch's new code, as CI checks it on a PR (docs/ci.md § Coverage):

```powershell
uv run pytest backend -q --cov --cov-config=backend/pyproject.toml --cov-report=xml:coverage/backend.xml
uvx diff-cover coverage/backend.xml frontend/coverage/cobertura-coverage.xml --compare-branch origin/main --fail-under 80
```

Frontend tests answer `fetch` from `frontend/src/test/tape.json.gz`. When an API
response changes shape, re-record it (needs the unlocked corpus):

```powershell
uv run python scripts/record_frontend_tape.py
```

`scripts/preflight.py` checks: syntax of every `.py`, the JSON contract, `SheetDocument`
invariants (field references, `id == key`, bilingual labels, value types), domain purity
(an import-linter substitute), the domain's golden numbers and that the formula evaluator
doesn't let `__import__` through.

The renderer conformance suite on its own:

```powershell
uv run pytest backend -k conformance -v
```

---

## 5.1 Pre-commit checks

Configured in `.pre-commit-config.yaml` (modeled on GloPros). Once:

```powershell
pre-commit install          # pre-commit and commit-msg hooks
cd frontend; npm install    # ESLint and Prettier with its plugin — the hooks use these
```

From then on every `git commit` checks the changed files:

| Hook | What it does |
| --- | --- |
| ruff-check, ruff (isort), ruff-format | Python: lint, import order, formatting (`ruff.toml`) |
| prettier | frontend: formatting and import order (`frontend/.prettierrc.json`) |
| eslint | frontend: lint (`frontend/eslint.config.js`), zero warnings |
| tsc | frontend: type check |
| shellcheck, shfmt | `.sh` scripts (2-space indent) |
| trufflehog | secrets in changed files (Docker image) |
| secrets-encrypted | everything git-crypt should encrypt (secrets, corpus) is ciphertext in the index |
| end-of-file, trailing-whitespace, BOM, json/yaml/toml, large files, conflicts | small checks from pre-commit-hooks |
| gitlint | commit message: title ≤ 100 characters, body lines ≤ 160 |

Formatters fix files themselves and stop the commit: review the changes, `git add`,
commit again. Run everything by hand: `pre-commit run --all-files`.

## 6. PDF: why 503 and what to do

`GET /api/v1/demo/export/pdf` returns 503 until WeasyPrint works. On Windows the pip
package alone doesn't work without GTK (Pango).

> **PDF already works in Docker** (section 3.1): the image installs WeasyPrint and the
> system libraries. 503 remains only when running without the container.

Options without the container:

1. **GTK runtime locally** — install GTK3 and add its `bin` to `PATH`.
2. **Docker / WSL for PDF** — the same as production, Windows stays clean. *(recommended)*
3. **Swap the adapter for Chromium printing** — no native dependencies, but a heavier runtime.

Swapping the adapter doesn't touch the domain: everything is behind the `SheetRenderer`
port (`backend/src/dndsheet/export/domain/renderer.py`).

---

## 7. Troubleshooting

### `Access is denied` / `The directory is not empty` when recreating `.venv`

A process from an interrupted install holds the files:

```powershell
Get-Process | Where-Object { $_.Path -like '*dnd-sheet\.venv\Scripts\python.exe' } |
  ForEach-Object { Stop-Process -Id $_.Id -Force }
Remove-Item -Recurse -Force .venv
python -m venv .venv
```

### `No module named pip` in `.venv`

The venv was created with `--without-pip` (happens when `ensurepip` failed). Recreate:

```powershell
python -m venv --clear .venv
.\.venv\Scripts\python.exe -m ensurepip --upgrade
```

### `spawn EPERM` during `npm run build`

A sandbox restriction when an agent runs the command: esbuild can't spawn a child
process. In a normal terminal the build works. If you see it in your own terminal, check
the antivirus or run `npm rebuild esbuild`.

### Cyrillic shows as `??????` in the console

Only the display; files are UTF-8. For readable output:

```powershell
chcp 65001
$env:PYTHONIOENCODING = "utf-8"
```

### Port in use

```powershell
Get-NetTCPConnection -LocalPort 8000 | Select-Object OwningProcess
```

or run on another port: `--port 8010` (and update the proxy in `frontend/vite.config.ts`).

### `ModuleNotFoundError: No module named 'dndsheet'`

`uv sync` was skipped or the command uses another interpreter. Use `uv run …` or
`.\.venv\Scripts\python.exe`, not the global `python`.

### The compendium is empty / many tests fail after cloning

The corpus is encrypted — run `git-crypt unlock` (section 0).

---

## 8. Full reinstall from scratch

```powershell
Remove-Item -Recurse -Force .venv, frontend\node_modules, frontend\dist -ErrorAction SilentlyContinue
uv sync
cd frontend; npm install; npm run contract; npm run build
```

---

## 9. Linux (short)

The `Makefile` has `install`, `test`, `arch`, `contract`, `dev`, `web-dev`, `web-build` targets:

```bash
make install
make test
make arch
make web-build
```

---

## 10. Where things are

```
backend/src/dndsheet/
  shared/        # kernel: Ability, AbilityScore, DiceExpression, Armor, Money; rules tables
  characters/    # Character aggregate, wizard, sheet, level-up, DerivedStatsCalculator, SQLite store
  compendium/    # compendium: JSONL corpus, indexes, service, API
  sheets/        # SheetDocument, formulas, labels, build_document
  export/        # SheetRenderer port, registry, Markdown/PDF adapters, Jinja template
  identity/      # users, Telegram sign-in (widget and Mini App), sessions (SQLite)
  api/           # FastAPI: create_app()
contract/        # JSON Schema + fixtures (single source of types)
content/         # glossary, sources, translations; encrypted corpus and indexes
frontend/        # React SPA (Vite, TanStack Query, Radix Tooltip)
deploy/          # Terraform, server files, encrypted secrets
.github/         # CI and deploy workflows, rulesets for main
docs/            # plan, ADRs, per-area docs
scripts/         # preflight, ingest, translations, deploy, hooks
```
