"""Українські назви самих підкласів — `content/translations/subclasses/entries.json`.

Назви підкласів уже частково живуть у `TERMS` на фронтенді, але там ключ — це
хвіст id («life-domain» → «Життя»), а не назва з книги («Life Domain»). Крок
підвищення рівня показує назву з довідника, тому для нього потрібен
переклад за **назвою**. Скрипт бере готові значення з `TERMS`, а решту
(нові книги: TCoE, EGtW, FToD…) — зі словника нижче.

Запуск: `python scripts/subclasses_uk_entries.py`
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ.setdefault("DNDSHEET_CONTENT_DIR", str(ROOT / "content"))

from dndsheet.compendium.infrastructure.factory import build_service  # noqa: E402

INPUT = ROOT / "var" / "uk" / "subclasses" / "input" / "entries.json"
OUTPUT = ROOT / "content" / "translations" / "subclasses" / "entries.json"
UK_TS = ROOT / "frontend" / "src" / "features" / "character" / "uk.ts"

ENTRY = re.compile(r'(?:"([^"]+)"|([A-Za-z][\w \'’\-]*)):\s*"([^"]+)"')

#: Підкласи, яких немає в `TERMS` (їхні id не мали української назви).
NAMES: dict[str, str] = {
    "Arcane Archer": "Арканний стрілець",
    "Arcane Trickster": "Містичний шахрай",
    "Assassin": "Убивця",
    "Battle Master": "Бойовий майстер",
    "Beast Master": "Володар звірів",
    "Bladesinging": "Клинковий спів",
    "Cavalier": "Кавалерист",
    "Champion": "Чемпіон",
    "Chronurgy Magic": "Хронургія",
    "Circle of Dreams": "Коло снів",
    "Circle of Spores": "Коло спор",
    "Circle of Stars": "Коло зірок",
    "Circle of Wildfire": "Коло дикого вогню",
    "Circle of the Land": "Коло землі",
    "Circle of the Moon": "Коло місяця",
    "Circle of the Shepherd": "Коло пастиря",
    "College of Creation": "Колегія творіння",
    "College of Eloquence": "Колегія красномовства",
    "College of Glamour": "Колегія чарів",
    "College of Lore": "Колегія знань",
    "College of Spirits": "Колегія духів",
    "College of Swords": "Колегія мечів",
    "College of Valor": "Колегія звитяги",
    "College of Whispers": "Колегія шепоту",
    "Drakewarden": "Драконовий страж",
    "Echo Knight": "Лицар відлуння",
    "Eldritch Knight": "Містичний лицар",
    "Fey Wanderer": "Фейський мандрівник",
    "Gloom Stalker": "Похмурий ловець",
    "Graviturgy Magic": "Гравітургія",
    "Horizon Walker": "Крокодавець обрію",
    "Hunter": "Мисливець",
    "Inquisitive": "Дослідник",
    "Lunar Sorcery": "Місячне чаклунство",
    "Mastermind": "Майстер інтриг",
    "Monster Slayer": "Вбивця монстрів",
    "Oath of Conquest": "Клятва завоювання",
    "Oath of Devotion": "Клятва відданості",
    "Oath of Glory": "Клятва слави",
    "Oath of Redemption": "Клятва спокути",
    "Oath of Vengeance": "Клятва помсти",
    "Oath of the Ancients": "Клятва давніх",
    "Oath of the Crown": "Клятва корони",
    "Oath of the Watchers": "Клятва вартових",
    "Oathbreaker": "Клятвовідступник",
    "Order of Scribes": "Орден писарів",
    "Path of Wild Magic": "Шлях дикої магії",
    "Path of the Ancestral Guardian": "Шлях пращурів-охоронців",
    "Path of the Battlerager": "Шлях буяна",
    "Path of the Beast": "Шлях звіра",
    "Path of the Berserker": "Шлях берсерка",
    "Path of the Giant": "Шлях велетня",
    "Path of the Storm Herald": "Шлях вісника бурі",
    "Path of the Totem Warrior": "Шлях воїна-тотема",
    "Path of the Zealot": "Шлях фанатика",
    "Phantom": "Фантом",
    "Psi Warrior": "Псіонічний воїн",
    "Purple Dragon Knight (Banneret)": "Лицар Пурпурного Дракона (Баннерет)",
    "Pyromancer": "Піромант",
    "Rune Knight": "Лицар рун",
    "Samurai": "Самурай",
    "School of Abjuration": "Школа захисту",
    "School of Conjuration": "Школа виклику",
    "School of Divination": "Школа віщування",
    "School of Enchantment": "Школа чар",
    "School of Evocation": "Школа втілення",
    "School of Illusion": "Школа ілюзії",
    "School of Necromancy": "Школа некромантії",
    "School of Transmutation": "Школа перетворення",
    "Scout": "Розвідник",
    "Soulknife": "Клинок душі",
    "Swarmkeeper": "Володар рою",
    "Swashbuckler": "Гультяй",
    "The Archfey": "Архіфея",
    "The Great Old One": "Великий Стародавній",
    "Thief": "Злодій",
    "War Magic": "Військова магія",
    "Way of Mercy": "Шлях милосердя",
    "Way of Shadow": "Шлях тіні",
    "Way of the Ascendant Dragon": "Шлях висхідного дракона",
    "Way of the Astral Self": "Шлях астрального я",
    "Way of the Drunken Master": "Шлях п'яного майстра",
    "Way of the Four Elements": "Шлях чотирьох стихій",
    "Way of the Kensei": "Шлях кенсея",
    "Way of the Long Death": "Шлях довгої смерті",
    "Way of the Open Hand": "Шлях відкритої долоні",
    "Way of the Sun Soul": "Шлях сонячної душі",
}


def normalise(text: str) -> str:
    return re.sub(r"[’ʼ'`]", "'", text.strip().casefold())


def ident(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def parse_terms(source: str) -> dict[str, str]:
    block = source.split("const TERMS", 1)[1].split("};", 1)[0]
    found: dict[str, str] = {}
    for match in ENTRY.finditer(block):
        key = (match.group(1) or match.group(2)).strip()
        found[normalise(key)] = match.group(3)
    return found


def collect() -> list[dict[str, str]]:
    """Назви підкласів із корпусу — вхід для скрипта (і для --missing)."""
    service = build_service()
    rows: dict[str, dict[str, str]] = {}
    for definition in service.class_definitions():
        for entry in service.subclasses(definition.name_en):
            rows.setdefault(
                entry.name_en,
                {
                    "id": ident(entry.name_en),
                    "name_en": entry.name_en,
                    "tail": entry.id.split("/")[-1],
                },
            )
    return [row for _, row in sorted(rows.items())]


def main() -> int:
    rows = collect()
    INPUT.parent.mkdir(parents=True, exist_ok=True)
    INPUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    terms = parse_terms(UK_TS.read_text(encoding="utf-8"))
    names = {normalise(key): value for key, value in NAMES.items()}

    translated: list[dict[str, str]] = []
    missing: list[str] = []
    for row in rows:
        value = names.get(normalise(row["name_en"])) or terms.get(normalise(row["tail"]))
        if not value:
            missing.append(row["name_en"])
            continue
        translated.append({"id": row["id"], "name_uk": value})

    if missing:
        print("БЕЗ ПЕРЕКЛАДУ:", *missing, sep="\n  ")
        return 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(translated, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"назв підкласів: {len(translated)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
