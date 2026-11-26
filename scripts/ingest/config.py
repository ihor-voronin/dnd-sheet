"""Шляхи, константи й налаштування конвеєра ingest."""

from __future__ import annotations

import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

CONTENT_DIR = REPO_ROOT / "content"
RAW_DIR = CONTENT_DIR / "raw"
INDEX_DIR = RAW_DIR / "_index"
# Корпуси записів: довідник (лист персонажа) і бестіарій (статблоки). Тут
# лишаються лише зручні шляхи — яка категорія в якому корпусі живе, визначає
# contract/compendium-format.json, і код питає його (`spec.corpus_dir`), щоб
# не тримати ту саму межу у двох місцях.
COMPENDIUM_DIR = CONTENT_DIR / "compendium"
BESTIARY_DIR = CONTENT_DIR / "bestiary"
SESSION_DIR = CONTENT_DIR / ".session"
COOKIE_FILE = SESSION_DIR / "cookies.json"
SOURCES_FILE = CONTENT_DIR / "sources.yml"
SCHEMA_FILE = REPO_ROOT / "contract" / "compendium-entry.schema.json"

BASE_URL = "https://www.dndbeyond.com"
SOURCE_ROOT = BASE_URL + "/sources/dnd/{source}"

# Пауза між запитами (сек). Менше — більший ризик CAPTCHA.
DEFAULT_DELAY = 1.2
DEFAULT_JITTER = 0.6
MAX_RETRIES = 4
TIMEOUT = 45.0

# Скільки сторінок максимум тягнути на одну книгу (захист від циклів).
MAX_PAGES_PER_SOURCE = 600


def url_for(source: str, path: str | None = None) -> str:
    base = SOURCE_ROOT.format(source=source)
    if not path or path == "/":
        return base
    return base + "/" + path.strip("/")
