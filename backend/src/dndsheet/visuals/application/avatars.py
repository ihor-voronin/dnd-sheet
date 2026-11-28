"""Портрети для API й сторінок: адреса файла, підпис, типовий портрет персонажа.

Адреса містить версію — хеш коду, що малює портрети: поки код той самий,
файл незмінний, тож браузер і Caddy тримають його рік (`/assets/*`). Змінили
малюнок — змінилась версія — нова адреса.
"""

from __future__ import annotations

import hashlib
import zlib
from functools import lru_cache
from pathlib import Path

from dndsheet.visuals.application import portraits
from dndsheet.visuals.domain import catalog
from dndsheet.visuals.domain.catalog import Portrait

PREFIX = "/assets/avatars"


def _version() -> str:
    digest = hashlib.sha256()
    for module in (portraits, catalog):
        digest.update(Path(str(module.__file__)).read_bytes())
    return digest.hexdigest()[:10]


VERSION = _version()


def url(portrait_id: str) -> str:
    return f"{PREFIX}/{VERSION}/{portrait_id}.svg"


@lru_cache(maxsize=4096)
def svg(portrait_id: str) -> str | None:
    found = catalog.portrait(portrait_id)
    return portraits.render(found) if found is not None else None


def card(item: Portrait) -> dict[str, str | int]:
    return {**item.as_dict(), "url": url(item.id)}


def species_name(species_name_en: str | None, subspecies_key: str | None) -> str | None:
    """Назва для групи: підраса точніша («drow elf»), але її може не бути."""
    parts = [part for part in (subspecies_key, species_name_en) if part]
    return " ".join(parts) if parts else None


def default_for(
    seed: str,
    *,
    species: str | None,
    class_key: str | None,
    gender: str | None,
) -> Portrait:
    """Портрет, поки гравець не обрав свій: перший із порад, але різний для різних героїв.

    Беремо серед порад зі своїм класом (якщо такі є) за стабільним хешем id
    персонажа — два ельфи-маги в одній партії не будуть близнюками.
    """
    advice = catalog.recommend(species=species, class_key=class_key, gender=gender)
    if not advice:
        advice = catalog.all_portraits()
    same_class = [item for item in advice if item.class_key == (class_key or "")]
    pool = same_class or list(advice)
    return pool[zlib.crc32(seed.encode()) % len(pool)]


def portrait_of(
    seed: str,
    *,
    chosen: str | None,
    species: str | None,
    class_key: str | None,
    gender: str | None,
) -> dict[str, str | int | bool]:
    """Що показати на листі: обраний портрет або типовий (`chosen: false`)."""
    found = catalog.portrait(chosen) if chosen else None
    item = found or default_for(seed, species=species, class_key=class_key, gender=gender)
    return {**card(item), "chosen": found is not None}
