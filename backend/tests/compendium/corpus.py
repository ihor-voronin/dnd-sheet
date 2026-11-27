"""Маленький корпус довідника для тестів — збирається на диску.

Корпус пишеться в `logs/_pytest/`, а не в `tmp_path`: у пісочниці сесії
системна тека temp недоступна для запису, а `logs/` доступна й так само
одноразова (той самий прийом, що в тестах формату корпусу).

Це не `conftest.py` навмисно: фабрику записів імпортують тести, а не лише
фікстури, а два `conftest` з однаковою назвою в різних теках легко
переплутати.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parents[3] / "logs" / "_pytest" / "compendium"


def record(
    source_id: str,
    category: str,
    slug: str,
    name_en: str,
    *,
    data: dict | None = None,
    text: str | None = None,
    name_uk: str | None = None,
    text_uk: str | None = None,
    license: str = "proprietary",
    page: int | None = None,
    status: str = "raw",
) -> dict:
    """Запис у канонічному порядку ключів (`contract/compendium-format.json`)."""
    body = text if text is not None else f"# {name_en}\n\nТекст запису {name_en}."
    if category == "spell":
        body = f"Evocation cantrip\n\n{name_en} — опис закляття."
    return {
        "id": f"{source_id}/{category}/{slug}",
        "schema": "compendium-entry/1",
        "source_id": source_id,
        "category": category,
        "name_en": name_en,
        "name_uk": name_uk,
        "edition": "2014",
        "license": license,
        "url": None,
        "page": page,
        "text_en": body,
        "text_uk": text_uk,
        "data": data or {},
        "status": status,
        "fetched_at": None,
        "notes": [],
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


DEMO_SPELLS = [
    record(
        "demo",
        "spell",
        "fireball",
        "Fireball",
        data={"level": 3, "school": "evocation", "classes": None},
        page=241,
    ),
    record(
        "demo",
        "spell",
        "burning-hands",
        "Burning Hands",
        data={"level": 1, "school": "evocation", "classes": ["sorcerer", "wizard"]},
    ),
    record(
        "demo",
        "spell",
        "magic-missile",
        "Magic Missile",
        data={"level": 1, "school": "evocation", "classes": None},
        license="srd",
    ),
    record(
        "demo",
        "spell",
        "chill-touch",
        "Chill Touch",
        data={"level": 0, "school": "necromancy", "classes": None},
    ),
]

DEMO_ENTRIES = [
    record(
        "demo",
        "class",
        "fighter",
        "Fighter",
        text="# Fighter\n\nA master of martial combat.",
        page=70,
    ),
    record(
        "demo",
        "class",
        "wizard",
        "Wizard",
        text="# Wizard\n\nA scholarly magic-user.",
        page=112,
    ),
    record(
        "demo",
        "subclass",
        "champion",
        "Champion",
        data={"class": "fighter", "level": 3},
    ),
    record(
        "demo",
        "subclass",
        "battle-master",
        "Battle Master",
        data={"class": "fighter", "level": 3},
    ),
    record(
        "demo",
        "species",
        "elf",
        "Elf",
        data={"size": "medium", "speed": 30, "subrace_of": None},
    ),
    record(
        "demo",
        "background",
        "acolyte",
        "Acolyte",
        data={"feature": "Shelter of the Faithful"},
    ),
    record("demo", "feat", "actor", "Actor", data={"prerequisite": None}),
    record(
        "demo",
        "optionalfeature",
        "agonizing-blast",
        "Agonizing Blast",
        data={"feature_type": ["eldritch invocation"], "prerequisite": None},
    ),
    record(
        "demo",
        "optionalfeature",
        "riposte",
        "Riposte",
        data={"feature_type": ["maneuver (battle master)"], "prerequisite": None},
    ),
    record(
        "demo",
        "item",
        "longsword",
        "Longsword",
        data={"item_type": "weapon", "rarity": None, "magical": False},
    ),
    record(
        "demo",
        "item",
        "bag-of-holding",
        "Bag of Holding",
        data={"item_type": "wondrous item", "rarity": "uncommon", "magical": True},
    ),
    record("demo", "rule", "adventuring", "Adventuring", text="# Adventuring\n\nПравила."),
]

#: Друга книга — щоб перевірити фільтр за джерелом і вибір кращого дубля.
OTHER_SPELLS = [
    record(
        "other",
        "spell",
        "magic-missile",
        "Magic Missile",
        data={"level": 1, "school": "evocation", "classes": None},
    ),
]


def build_content(root: Path, *, spell_lists: bool = True) -> Path:
    content = root / "content"
    if content.exists():
        shutil.rmtree(content)
    write_jsonl(content / "compendium" / "demo" / "spell.jsonl", DEMO_SPELLS)
    write_jsonl(content / "compendium" / "demo" / "class.jsonl", DEMO_ENTRIES[:2])
    write_jsonl(content / "compendium" / "demo" / "subclass.jsonl", DEMO_ENTRIES[2:4])
    write_jsonl(content / "compendium" / "demo" / "species.jsonl", DEMO_ENTRIES[4:5])
    write_jsonl(content / "compendium" / "demo" / "background.jsonl", DEMO_ENTRIES[5:6])
    write_jsonl(content / "compendium" / "demo" / "feat.jsonl", DEMO_ENTRIES[6:7])
    write_jsonl(content / "compendium" / "demo" / "optionalfeature.jsonl", DEMO_ENTRIES[7:9])
    write_jsonl(content / "compendium" / "demo" / "item.jsonl", DEMO_ENTRIES[9:11])
    write_jsonl(content / "compendium" / "demo" / "rule.jsonl", DEMO_ENTRIES[11:])
    write_jsonl(content / "compendium" / "other" / "spell.jsonl", OTHER_SPELLS)

    (content / "sources.yml").write_text(
        'sources:\n  - id: demo\n    title: "Demo Book"\n    type: core\n  - id: other\n    title: "Other Book"\n',
        encoding="utf-8",
    )

    if spell_lists:
        payload = {
            "schema": "spell-lists/1",
            "generated_at": "2026-01-01T00:00:00+00:00",
            "sources": {"demo": "sources__demo__spells.html"},
            "skipped": [],
            "problems": [],
            "lists": {
                "demo": {
                    "Wizard": {
                        "0": ["Chill Touch", "Fire Bolt"],
                        "1": ["Burning Hands", "Magic Missile"],
                        "3": ["Fireball", "Неіснуюче закляття"],
                    },
                    "Fighter": {"1": ["Burning Hands"]},
                }
            },
        }
        target = content / "index" / "spell-lists.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    return content
