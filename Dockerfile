# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# 1. Збірка SPA: node лише на етапі build, у фінальний образ не потрапляє
# ---------------------------------------------------------------------------
FROM node:22-alpine AS web

WORKDIR /web

# Спершу лише маніфести — шар із залежностями кешується, поки не змінився lock
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# tsc --noEmit && vite build (див. frontend/package.json)
RUN npm run build


# ---------------------------------------------------------------------------
# 2. Python-залежності окремо: у фінальний образ іде лише встановлене —
#    без вихідників backend/ і без .pyc (--no-compile: ~40 МБ менше; Python
#    компілює модулі в памʼяті при старті, це пів секунди).
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS deps

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY backend/ /src/backend/
RUN pip install --no-compile --prefix=/install "/src/backend[pdf]"


# ---------------------------------------------------------------------------
# 3. Виконання: python + FastAPI + зібрана SPA + корпус довідника
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DNDSHEET_DATA_DIR=/app/var \
    DNDSHEET_CONTENT_DIR=/app/content \
    DNDSHEET_SPA_DIST=/app/frontend/dist

# Бібліотеки для WeasyPrint (PDF) і шрифти з кирилицею для нього ж.
# WeasyPrint 53+ малює сам (без cairo й gdk-pixbuf): потрібні лише ті, що він
# відкриває через dlopen — gobject/pango, pangoft2, fontconfig, harfbuzz (+subset).
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

# Корпус довідника: без нього сервіс піднімається, але лист будувати ні з чого.
# content/raw (джерельні книги) у образ не кладемо — він потрібен лише ingest.
COPY content/sources.yml /app/content/sources.yml
COPY content/books_market.json /app/content/books_market.json
COPY content/compendium/ /app/content/compendium/
COPY content/bestiary/ /app/content/bestiary/
COPY content/index/ /app/content/index/
# Переклади (українські назви й тексти). Без них сервіс працює, але показує
# оригінал книги — тобто мовчки англійською, чого ніхто не помітить.
COPY content/translations/ /app/content/translations/

COPY --from=deps /install /usr/local

COPY --from=web /web/dist /app/frontend/dist

RUN useradd --create-home --uid 10001 app \
    && mkdir -p /app/var \
    && chown -R app:app /app/var

USER app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=6 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2).status == 200 else 1)"

# 0.0.0.0 обовʼязково: інакше порт назовні контейнера не видно
CMD ["python", "-m", "uvicorn", "dndsheet.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ---------------------------------------------------------------------------
# 4. Тести: той самий образ + корпус + dev-залежності.
#    docker compose --profile test run --rm test
#    (у застосунку `app` ціль — `runtime`, тож цей етап у нього не потрапляє)
# ---------------------------------------------------------------------------
FROM runtime AS test

USER root

# Тести читають вихідники backend (у runtime їх уже немає), контракт, глосарій,
# фронтенд (термінологія) і скрипти нормалізації.
COPY backend/ /app/backend/
COPY contract/ /app/contract/
COPY content/glossary.uk.yml /app/content/glossary.uk.yml
COPY frontend/src/ /app/frontend/src/
COPY scripts/ /app/scripts/

RUN pip install "/app/backend[dev,pdf]"

ENV DNDSHEET_DATA_DIR=/tmp/dndsheet-test

CMD ["sh", "-c", "python -m pytest backend -q && lint-imports --config backend/pyproject.toml"]
