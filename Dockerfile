# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# 1. Build the SPA: node only in the build stage, it doesn't reach the final image
# ---------------------------------------------------------------------------
FROM node:22-alpine AS web

WORKDIR /web

# Manifests first — the dependency layer stays cached until the lock changes
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# tsc --noEmit && vite build (see frontend/package.json)
RUN npm run build


# ---------------------------------------------------------------------------
# 2. Python dependencies with uv, from uv.lock: exactly the locked versions, and
#    without the dev group — test tools never reach production. The package is
#    installed non-editable, so the final image needs no backend/ sources. No .pyc
#    (~40 MB less; Python compiles modules in memory at startup, half a second).
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS deps

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /src
# Manifests first: the dependency layer stays cached until the lock changes.
COPY pyproject.toml uv.lock ./
COPY backend/pyproject.toml backend/pyproject.toml
RUN uv sync --frozen --no-dev --extra pdf --no-install-workspace
COPY backend/ backend/
RUN uv sync --frozen --no-dev --extra pdf --no-editable


# ---------------------------------------------------------------------------
# 3. Runtime: python + FastAPI + the built SPA + the compendium corpus
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH \
    DNDSHEET_DATA_DIR=/app/var \
    DNDSHEET_CONTENT_DIR=/app/content \
    DNDSHEET_SPA_DIST=/app/frontend/dist

# Libraries for WeasyPrint (PDF) and Cyrillic fonts for it.
# WeasyPrint 53+ draws by itself (no cairo or gdk-pixbuf): only the libraries it
# opens via dlopen are needed — gobject/pango, pangoft2, fontconfig, harfbuzz (+subset).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libharfbuzz-subset0 \
        libffi8 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The compendium corpus: without it the service starts, but there's nothing to build a sheet from.
# content/raw (the source books) doesn't go into the image — only ingest needs it.
COPY content/sources.yml /app/content/sources.yml
COPY content/books_market.json /app/content/books_market.json
# The terminology glossary: the UA/EN table on the public glossary page (/kb/glossary).
COPY content/glossary.uk.yml /app/content/glossary.uk.yml
COPY content/compendium/ /app/content/compendium/
COPY content/bestiary/ /app/content/bestiary/
COPY content/index/ /app/content/index/
# Translations (Ukrainian names and texts). Without them the service works but shows
# the book's original — i.e. silently in English, which nobody would notice.
COPY content/translations/ /app/content/translations/

COPY --from=deps /opt/venv /opt/venv

COPY --from=web /web/dist /app/frontend/dist

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/var \
    && chown -R app:app /app/var

USER app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=6 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

# 0.0.0.0 is required: otherwise the port isn't visible outside the container
CMD ["python", "-m", "uvicorn", "dndsheet.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ---------------------------------------------------------------------------
# 4. Tests: the same image + the corpus + dev dependencies.
#    docker compose --profile test run --rm test
#    (the `app` service targets `runtime`, so this stage doesn't reach it)
# ---------------------------------------------------------------------------
FROM runtime AS test

USER root

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

# Tests read the backend sources (runtime no longer has them), the contract, the glossary,
# the frontend (terminology) and the normalization scripts.
COPY pyproject.toml uv.lock /app/
COPY backend/ /app/backend/
COPY contract/ /app/contract/
COPY frontend/src/ /app/frontend/src/
COPY scripts/ /app/scripts/

# The same locked environment plus the dev group (pytest, coverage, import-linter).
RUN uv sync --frozen --extra pdf --no-editable

ENV DNDSHEET_DATA_DIR=/tmp/dndsheet-test

# Coverage: below 80% the run fails (backend/pyproject.toml); the XML report goes to
# /coverage — CI mounts a folder there and checks the coverage of the PR's new lines.
CMD ["sh", "-c", "mkdir -p /coverage && python -m pytest backend -q --cov --cov-config=backend/pyproject.toml --cov-report=term --cov-report=xml:/coverage/backend.xml --junitxml=/coverage/backend-junit.xml && lint-imports --config backend/pyproject.toml"]
