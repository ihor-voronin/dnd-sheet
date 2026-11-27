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
# 2. Виконання: python + FastAPI + зібрана SPA + корпус довідника
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DNDSHEET_DATA_DIR=/app/var \
    DNDSHEET_CONTENT_DIR=/app/content \
    DNDSHEET_SPA_DIST=/app/frontend/dist

# Бібліотеки для WeasyPrint (PDF) і шрифти з кирилицею для нього ж
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libffi8 \
        shared-mime-info \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/ /app/backend/

# Корпус довідника: без нього сервіс піднімається, але лист будувати ні з чого.
# content/raw (джерельні книги) у образ не кладемо — він потрібен лише ingest.
COPY content/sources.yml /app/content/sources.yml
COPY content/compendium/ /app/content/compendium/
COPY content/bestiary/ /app/content/bestiary/
COPY content/index/ /app/content/index/
# Переклади (українські назви й тексти). Без них сервіс працює, але показує
# оригінал книги — тобто мовчки англійською, чого ніхто не помітить.
COPY content/translations/ /app/content/translations/

RUN pip install "/app/backend[pdf]"

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
# 3. Тести: той самий образ + корпус + dev-залежності.
#    docker compose --profile test run --rm test
#    (у застосунку `app` ціль — `runtime`, тож цей етап у нього не потрапляє)
# ---------------------------------------------------------------------------
FROM runtime AS test

USER root

# Тести читають контракт, глосарій, фронтенд (термінологія) і скрипти нормалізації.
COPY contract/ /app/contract/
COPY content/glossary.uk.yml /app/content/glossary.uk.yml
COPY frontend/src/ /app/frontend/src/
COPY scripts/ /app/scripts/

RUN pip install "/app/backend[dev,pdf]"

ENV DNDSHEET_DATA_DIR=/tmp/dndsheet-test

CMD ["sh", "-c", "python -m pytest backend -q && lint-imports --config backend/pyproject.toml"]
