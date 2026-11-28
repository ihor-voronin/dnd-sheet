"""Емблеми довідника й візарда: класи, школи магії, розділи.

Форми — з game-icons.net (CC BY 3.0, автори в `emblems.json` і на /kb/credits),
кольори — наші: малюємо `currentColor`, тож емблема бере колір тексту теми.

Серверні сторінки вставляють лише ті емблеми, що є на сторінці, одним
прихованим `<svg>` із `<symbol>` наприкінці `<body>` (`Sprite`): жодного
зайвого запиту, і довідник лишається легким. SPA бере файли
`/assets/emblems/<версія>/<назва>.svg` як маску (CSS `mask`), теж у кольорі теми.
"""

from __future__ import annotations

import hashlib
import json
from functools import cache
from pathlib import Path

PREFIX = "/assets/emblems"
_FILE = Path(__file__).with_name("emblems.json")


@cache
def _emblems() -> dict[str, dict[str, str]]:
    return json.loads(_FILE.read_text(encoding="utf-8"))


VERSION = hashlib.sha256(_FILE.read_bytes()).hexdigest()[:10]

CLASSES = frozenset(
    [
        "artificer",
        "barbarian",
        "bard",
        "cleric",
        "druid",
        "fighter",
        "monk",
        "paladin",
        "ranger",
        "rogue",
        "sorcerer",
        "warlock",
        "wizard",
    ]
)
SCHOOLS = frozenset(
    ["abjuration", "conjuration", "divination", "enchantment", "evocation", "illusion", "necromancy", "transmutation"]
)


def names() -> list[str]:
    return list(_emblems())


def exists(name: str) -> bool:
    return name in _emblems()


def class_emblem(class_key: str | None) -> str | None:
    key = (class_key or "").strip().casefold()
    return f"class-{key}" if key in CLASSES else None


def school_emblem(school: str | None) -> str | None:
    key = (school or "").strip().casefold()
    return f"school-{key}" if key in SCHOOLS else None


def url(name: str) -> str:
    return f"{PREFIX}/{VERSION}/{name}.svg"


def svg_file(name: str) -> str | None:
    """Окремий файл для SPA (маска): заливка будь-яка, видно лише форму."""
    found = _emblems().get(name)
    if found is None:
        return None
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><path d="{found["d"]}"/></svg>'


def credits() -> list[dict[str, str]]:
    """Що й чиє: для сторінки подяк."""
    rows = [
        {"name": name, **{key: value for key, value in item.items() if key != "d"}}
        for name, item in _emblems().items()
    ]
    return sorted(rows, key=lambda row: (row["author"], row["icon"]))


class Sprite:
    """Емблеми однієї сторінки: `use()` малює посилання, `markup()` — самі форми.

    Порядок не важливий: `<use href="#e-…">` знаходить символ і нижче за текстом.
    """

    def __init__(self) -> None:
        self._used: dict[str, None] = {}

    def use(self, name: str | None, css: str = "emblem") -> str:
        if not name or not exists(name):
            return ""
        self._used[name] = None
        # Емблема — прикраса поруч із назвою: читачам екрана її не озвучуємо.
        # Розмір задає CSS сторінки (він у <head>), тож місце відоме до малювання.
        return f'<svg class="{css}" aria-hidden="true"><use href="#e-{name}"/></svg>'

    def markup(self) -> str:
        if not self._used:
            return ""
        symbols = "".join(
            f'<symbol id="e-{name}" viewBox="0 0 512 512"><path d="{_emblems()[name]["d"]}"/></symbol>'
            for name in self._used
        )
        return f'<svg class="sprite" width="0" height="0" aria-hidden="true" focusable="false">{symbols}</svg>'
