"""Механіки класів, видів і передісторій → `content/index/*-mechanics.json`.

Навіщо окремий індекс: корпус довідника містить **текст** («Second Wind…») і
майже нічого з того, що потрібно порахувати лист — хіт-дайс, володіння,
стартові характеристики виду, слоти заклять. Ці числа є в дзеркалі 5e.tools
(`content/raw/_index/mirror-class/`, `races-5etools.json`, …), але дзеркало
тримає їх у форматі з `_copy`/`_mod`, тегами `{@item …}` і таблицями з
підписами-посиланнями. Розбирати це на кожен запит — марно, тому збираємо
один раз у два допоміжні файли:

* `content/index/class-mechanics.json` — класи 2014;
* `content/index/origin-mechanics.json` — види, підраси, передісторії.

Індекси похідні: без них застосунок працює, але візард чесно каже, що
механік немає. Схема — `class-mechanics/1` і `origin-mechanics/1`.

Запуск:
    python -m scripts.ingest.mechanics --write    # записати обидва індекси
    python -m scripts.ingest.mechanics --check    # порівняти з тим, що на диску
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from . import config
from .mirror5e import (
    OTHER_EDITION,
    _clean_name,
    _index_rows,
    inline,
    owned_sources,
    resolve_copy,
)

CLASS_SCHEMA = "class-mechanics/1"
ORIGIN_SCHEMA = "origin-mechanics/1"

CLASS_TARGET = config.CONTENT_DIR / "index" / "class-mechanics.json"
ORIGIN_TARGET = config.CONTENT_DIR / "index" / "origin-mechanics.json"

#: Дзеркало позначає 2014 рік як `classic`, 2024 — як `one`. Записи без
#: позначки — старі книги, тобто теж 2014.
CLASSIC_EDITIONS = (None, "classic")

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
SKILLS = (
    "athletics",
    "acrobatics",
    "sleight of hand",
    "stealth",
    "arcana",
    "history",
    "investigation",
    "nature",
    "religion",
    "animal handling",
    "insight",
    "medicine",
    "perception",
    "survival",
    "deception",
    "intimidation",
    "performance",
    "persuasion",
)
_SKILL_KEYS = {skill.replace(" ", "_"): skill for skill in SKILLS}

_DAMAGE_TYPES = {
    "acid",
    "bludgeoning",
    "cold",
    "fire",
    "force",
    "lightning",
    "necrotic",
    "piercing",
    "poison",
    "psychic",
    "radiant",
    "slashing",
    "thunder",
}

_SIZE_CODES = {"T": "tiny", "S": "small", "M": "medium", "L": "large", "H": "huge", "G": "gargantuan"}

#: Яке джерело показати, коли одна раса є в кількох книгах: спершу те, що в
#: базових правилах, далі основні книги, і лише потім сетинги.
SOURCE_PRIORITY = {"PHB": 0, "DMG": 3, "MM": 4, "TCE": 5, "XGE": 6, "VGM": 8, "MPMM": 9}

_ORDINALS = {
    "cantrip": 0,
    "1st": 1,
    "2nd": 2,
    "3rd": 3,
    "4th": 4,
    "5th": 5,
    "6th": 6,
    "7th": 7,
    "8th": 8,
    "9th": 9,
}


# ---------------------------------------------------------------------------
# дрібні перетворення
# ---------------------------------------------------------------------------


_SPELL_CHOOSE_CLASS = re.compile(r"class=([A-Za-z0-9]+)")


def _slug(value: Any) -> str:
    """«Life Domain» → «life-domain»: так само, як id у корпусі довідника."""
    text = plain(str(value or "")).casefold()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _spell_tokens(value: Any) -> list[Any]:
    """Будь-яка форма `additionalSpells` → рядки-посилання й `{"choose": …}`."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        if "choose" in value:
            return [value]
        tokens: list[Any] = []
        for item in value.values():
            tokens.extend(_spell_tokens(item))
        return tokens
    if isinstance(value, list):
        tokens = []
        for item in value:
            tokens.extend(_spell_tokens(item))
        return tokens
    return []


def _spell_ref(token: str) -> tuple[str, int, int]:
    """`thaumaturgy#c` → (thaumaturgy, 0, 0); `hellish rebuke#2` → (…, 2, 2).

    Другий елемент — рівень закляття (0 — заговор), третій — рівень, на якому
    його кастують уроджено (5e.tools пише його після `#`).
    """
    text = token.split("|", maxsplit=1)[0].strip()
    cast_level = 0
    if "#" in text:
        text, _, marker = text.partition("#")
        if marker.isdigit():
            cast_level = int(marker)
        elif marker.casefold() == "c":
            cast_level = 0
    name = plain(text).casefold()
    if not name:
        return "", 0, 0
    spell_level = 0 if token.endswith("#c") else (cast_level or 1)
    return name, spell_level, cast_level


def species_spell_grants(row: Mapping[str, Any]) -> tuple[list[str], dict | None, list[dict]]:
    """Що вид дає **на 1 рівні**: заговори, вибір заговору, уроджені закляття.

    Дивимось лише `known`/`innate` з ключем «1» (або «_» — «одразу»): решта
    (3-й, 5-й рівень) — це вже підвищення рівня, етап 7.
    """
    cantrips: list[str] = []
    granted: list[dict] = []
    choice: dict | None = None
    for block in row.get("additionalSpells") or []:
        if not isinstance(block, dict):
            continue
        for section in ("known", "innate"):
            data = block.get(section)
            if not isinstance(data, dict):
                continue
            for level_key, value in data.items():
                if str(level_key) not in ("1", "_"):
                    continue
                for token in _spell_tokens(value):
                    if isinstance(token, dict):
                        match = _SPELL_CHOOSE_CLASS.search(str(token.get("choose") or ""))
                        if match:
                            choice = {
                                "from_class": match.group(1).casefold(),
                                "count": int(token.get("count") or 1),
                            }
                        continue
                    name, spell_level, _ = _spell_ref(str(token))
                    if not name:
                        continue
                    if spell_level == 0:
                        if name not in cantrips:
                            cantrips.append(name)
                    elif all(item["name"] != name for item in granted):
                        granted.append({"name": name, "level": spell_level})
    return cantrips, choice, granted


def subclass_spell_grants(subclasses: list[Any] | None, class_source: str) -> dict[str, dict[str, list[str]]]:
    """Закляття підкласів на 1 рівні: домен жреця й розширений список патрона.

    `prepared` — завжди підготовлені (домен), `expanded` — додані до списку
    класу (патрон). Ключ — slug назви підкласу, як в id корпусу.
    """
    result: dict[str, dict[str, list[str]]] = {}
    for sub in subclasses or []:
        if not isinstance(sub, dict):
            continue
        source = str(sub.get("classSource") or sub.get("source") or "")
        if source != class_source:
            continue
        slug = _slug(sub.get("name"))
        if not slug:
            continue
        prepared: list[str] = []
        expanded: list[str] = []
        for block in sub.get("additionalSpells") or []:
            if not isinstance(block, dict):
                continue
            for section, bucket, keys in (
                ("prepared", prepared, ("1",)),
                ("expanded", expanded, ("1", "s1")),
            ):
                data = block.get(section)
                if not isinstance(data, dict):
                    continue
                for level_key, value in data.items():
                    # `prepared` ключується рівнем персонажа (1, 3, 5…),
                    # `expanded` — рівнем закляття (`s1` для 1 рівня).
                    if str(level_key) not in keys:
                        continue
                    for token in _spell_tokens(value):
                        if not isinstance(token, str):
                            continue
                        name, _, _ = _spell_ref(token)
                        if name and name not in bucket:
                            bucket.append(name)
        if prepared or expanded:
            entry = result.setdefault(slug, {})
            if prepared:
                entry["prepared"] = prepared
            if expanded:
                entry["expanded"] = expanded
    return result


def plain(value: Any) -> str:
    """Текст із тегами 5e.tools: `{@item chain mail|phb}` → `chain mail`."""
    if value is None:
        return ""
    return " ".join(inline(str(value)).split())


def choice_count(value: Any) -> int:
    """`{"any": 2}` / `{"anyStandard": 1}` / `{"choose": {"count": 1}}` → число."""
    if not isinstance(value, dict):
        return 0
    for key, amount in value.items():
        if key == "choose" and isinstance(amount, dict):
            count = amount.get("count")
            if isinstance(count, int) and count > 0:
                return count
            # `choose` без count — один вибір (так записані інструменти дворфів).
            return 1 if amount.get("from") else 0
        if key.startswith("any") and isinstance(amount, int):
            return amount
    return 0


def abilities_from_value(value: Any) -> tuple[dict[str, int], dict[str, Any] | None]:
    """Блок характеристик 5e.tools → (фіксовані бонуси, вибір).

    `[{"cha": 2, "choose": {"from": [...], "count": 2}}]` — фіксовані +2 CHA
    і два бонуси по +1 на вибір. Підраси можуть давати кілька блоків одразу.
    """
    fixed: dict[str, int] = {}
    choose: dict[str, Any] | None = None
    if not isinstance(value, list):
        return fixed, None
    for block in value:
        if not isinstance(block, dict):
            continue
        raw_choose = block.get("choose")
        if isinstance(raw_choose, dict):
            options = [item for item in raw_choose.get("from") or [] if item in ABILITIES]
            count = raw_choose.get("count")
            if isinstance(count, int) and count > 0 and options:
                choose = {
                    "count": count,
                    "amount": int(raw_choose.get("amount") or 1),
                    "from": options,
                }
        for key, bonus in block.items():
            if key in ABILITIES and isinstance(bonus, int):
                fixed[key] = fixed.get(key, 0) + bonus
    return fixed, choose


def skills_from_value(value: Any) -> tuple[list[str], int]:
    """`skillProficiencies` → (конкретні навички, скільком будь-яким)."""
    skills: list[str] = []
    any_count = 0
    if not isinstance(value, list):
        return skills, any_count
    for block in value:
        if not isinstance(block, dict):
            continue
        any_count += choice_count(block)
        for key, enabled in block.items():
            if not enabled:
                continue
            skill = _SKILL_KEYS.get(str(key).casefold())
            if skill and skill not in skills:
                skills.append(skill)
    return skills, any_count


def named_proficiencies(value: Any) -> list[str]:
    """`[{"battleaxe|phb": true}, {"any": 1}]` → назви предметів/інструментів."""
    names: list[str] = []
    if not isinstance(value, list):
        return names
    for block in value:
        if not isinstance(block, dict):
            continue
        for key, enabled in block.items():
            if not enabled or key.startswith("any") or key == "choose":
                continue
            name = plain(str(key).split("|")[0]).casefold()
            if name and name not in names:
                names.append(name)
    return names


def tools_any(value: Any) -> int:
    total = 0
    if not isinstance(value, list):
        return total
    for block in value:
        if isinstance(block, dict):
            total += choice_count(block)
    return total


def languages_from_value(value: Any) -> tuple[list[str], int]:
    """`[{"common": true, "dwarvish": true, "anyStandard": 1}]`."""
    languages: list[str] = []
    any_count = 0
    if not isinstance(value, list):
        return languages, any_count
    for block in value:
        if not isinstance(block, dict):
            continue
        any_count += choice_count(block)
        for key, enabled in block.items():
            if not enabled or key.startswith("any"):
                continue
            name = plain(key.split("|")[0]).casefold()
            if name and name not in languages:
                languages.append(name)
    return languages, any_count


def training_from_value(value: Any) -> list[str]:
    """Володіння зброєю/бронею/інструментами → читабельні назви."""
    names: list[str] = []
    if isinstance(value, dict):
        # armorProficiencies: {"light": true, "shield": true}
        for key, enabled in value.items():
            if enabled and not key.startswith("any") and key != "choose":
                name = plain(key).casefold()
                if name and name not in names:
                    names.append(name)
        return names
    if not isinstance(value, list):
        return names
    for item in value:
        if isinstance(item, dict):
            for name in training_from_value(item):
                if name not in names:
                    names.append(name)
            continue
        name = plain(str(item)).casefold()
        if name and name not in names:
            names.append(name)
    return names


# ---------------------------------------------------------------------------
# класи
# ---------------------------------------------------------------------------


def _slot_ordinal(label: str) -> int:
    """`{@filter 1st|spells|level=1|class=Warlock}` → 1."""
    text = plain(label).casefold().split(" ")[0]
    return _ORDINALS.get(text, 0)


def _pad_spell_row(row: list[int]) -> list[int]:
    """Таблиця слотів завжди дев'ять рівнів: артифіцер має лише п'ять.

    Доповнюємо нулями, щоб споживач не тримав у голові «а в артифіцера
    коротше»: рядок завжди відповідає рівням 1..9.
    """
    return (row + [0] * 9)[:9]


def _feature_ref(raw: Any) -> dict[str, Any] | None:
    """`"Second Wind|Fighter||1"` або `{"classFeature": "…", "gainSubclassFeature": true}`."""
    if isinstance(raw, dict):
        raw = raw.get("classFeature")
    if not isinstance(raw, str):
        return None
    parts = raw.split("|")
    name = plain(parts[0])
    level = None
    for part in parts[1:]:
        if part.strip().isdigit():
            level = int(part)
            break
    if not name or level is None:
        return None
    return {"name": name, "level": level}


def class_mechanics(klass: dict, file_name: str, subclasses: list[Any] | None = None) -> dict[str, Any]:
    """Один клас 2014 → запис індексу."""
    hd = klass.get("hd") if isinstance(klass.get("hd"), dict) else {}
    hit_die = hd.get("faces")
    hit_die = int(hit_die) if isinstance(hit_die, int) else 0

    start = klass.get("startingProficiencies") or {}
    skills: list[dict[str, Any]] = []
    skill_any = 0
    for block in start.get("skills") or []:
        if not isinstance(block, dict):
            continue
        raw_choose = block.get("choose") if isinstance(block.get("choose"), dict) else block
        options = [str(item).replace(" ", "_") for item in raw_choose.get("from") or []]
        count = raw_choose.get("count")
        if isinstance(count, int) and count > 0 and options:
            skills.append({"count": count, "from": options})
        else:
            skill_any += choice_count(block)

    multiclass = klass.get("multiclassing") or {}
    requirements: list[dict[str, int]] = []
    raw_req = multiclass.get("requirements")
    if isinstance(raw_req, dict):
        alternatives = raw_req.get("or") if isinstance(raw_req.get("or"), list) else [raw_req]
        for alternative in alternatives:
            if not isinstance(alternative, dict):
                continue
            scores = {
                key: int(value) for key, value in alternative.items() if key in ABILITIES and isinstance(value, int)
            }
            if scores:
                requirements.append(scores)
    gained = multiclass.get("proficienciesGained") or {}

    slots: list[list[int]] = []
    pact: list[list[int]] = []
    cantrips: list[int] = []
    spells_known: list[int] = []
    for group in klass.get("classTableGroups") or []:
        if not isinstance(group, dict):
            continue
        labels = [plain(label) for label in group.get("colLabels") or []]
        title = str(group.get("title") or "")
        if title.startswith("Spell Slots per Spell Level") and group.get("rowsSpellProgression"):
            slots = [_pad_spell_row([int(value) for value in row]) for row in group["rowsSpellProgression"]]
        if "pact" in str(klass.get("casterProgression") or "").casefold() and "Spell Slots" in labels:
            index_slots = labels.index("Spell Slots")
            index_level = labels.index("Slot Level") if "Slot Level" in labels else None
            for row in group.get("rows") or []:
                count = row[index_slots] if index_slots < len(row) else 0
                level = _slot_ordinal(row[index_level]) if index_level is not None else 0
                pact.append([int(count) if isinstance(count, int) else 0, level])
        if labels and labels[0].startswith("Cantrips Known") and group.get("rows"):
            cantrips = [int(row[0]) for row in group["rows"] if row and isinstance(row[0], int)]
        for position, label in enumerate(labels):
            if label == "Spells Known" and group.get("rows"):
                spells_known = [
                    int(row[position])
                    for row in group["rows"]
                    if position < len(row) and isinstance(row[position], int)
                ]
                break

    if not cantrips and isinstance(klass.get("cantripProgression"), list):
        cantrips = [int(value) for value in klass["cantripProgression"]]
    if not spells_known and isinstance(klass.get("spellsKnownProgression"), list):
        spells_known = [int(value) for value in klass["spellsKnownProgression"]]

    features: list[dict[str, Any]] = []
    subclass_level: int | None = None
    for raw in klass.get("classFeatures") or []:
        entry = _feature_ref(raw)
        if entry is None:
            continue
        features.append(entry)
        # Рівень підкласу — той, де клас уперше дає рису підкласу.
        if isinstance(raw, dict) and raw.get("gainSubclassFeature"):
            level = int(entry["level"])
            subclass_level = level if subclass_level is None else min(subclass_level, level)

    optional: dict[str, list[list[int]]] = {}
    for block in klass.get("optionalfeatureProgression") or []:
        if not isinstance(block, dict):
            continue
        name = plain(block.get("name") or "")
        progression = block.get("progression") or {}
        if isinstance(progression, list):
            # Список — це кількість на кожному рівні, з першого.
            progression = {str(level): count for level, count in enumerate(progression, start=1)}
        steps = sorted(
            (int(level), int(count))
            for level, count in progression.items()
            if str(level).isdigit() and isinstance(count, int)
        )
        if name and steps:
            optional[name] = [[level, count] for level, count in steps]

    equipment: list[dict[str, list[dict[str, Any]]]] = []
    for group in (klass.get("startingEquipment") or {}).get("defaultData") or []:
        if not isinstance(group, dict):
            continue
        equipment.append({choice: items_from_group(group.get(choice)) for choice in ("a", "b") if group.get(choice)})

    gold = plain((klass.get("startingEquipment") or {}).get("goldAlternative") or "")

    return {
        "name_en": plain(klass.get("name") or ""),
        "source_id": str(klass.get("source") or ""),
        "file": file_name,
        "edition": str(klass.get("edition") or "classic"),
        "srd": bool(klass.get("srd")),
        "basic_rules": bool(klass.get("basicRules")),
        "hit_die": hit_die,
        "saving_throws": [plain(item).casefold() for item in klass.get("proficiency") or []],
        "skill_choices": skills,
        "skill_any": skill_any,
        "armor_training": training_from_value(start.get("armor")),
        "weapon_training": training_from_value(start.get("weapons")),
        "tool_training": training_from_value(start.get("tools")),
        "spellcasting_ability": (
            str(klass["spellcastingAbility"]).casefold() if isinstance(klass.get("spellcastingAbility"), str) else None
        ),
        "caster_progression": (
            str(klass["casterProgression"]).casefold() if isinstance(klass.get("casterProgression"), str) else None
        ),
        "prepares_spells": bool(klass.get("preparedSpells")),
        "cantrips_known": cantrips,
        "spells_known": spells_known,
        "spell_slots": slots,
        "pact_slots": pact,
        "subclass_title": plain(klass.get("subclassTitle") or "") or None,
        "subclass_level": subclass_level,
        "multiclass_requirements": requirements,
        "multiclass_gained": {
            "armor": training_from_value(gained.get("armor")),
            "weapons": training_from_value(gained.get("weapons")),
            "tools": training_from_value(gained.get("tools")),
        },
        "features": sorted(features, key=lambda item: (item.get("level", 0), item["name"])),
        "optional_features": optional,
        "starting_equipment": equipment,
        "starting_gold": gold or None,
        "subclass_spells": subclass_spell_grants(subclasses, str(klass.get("source") or "")),
    }


def items_from_group(value: Any) -> list[dict[str, Any]]:
    """Пункт стартового набору → `{item, quantity}` або `{equipment_type}`."""
    result: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return result
    for item in value:
        if isinstance(item, str):
            name = plain(item.split("|")[0]).casefold()
            if name:
                result.append({"item": name, "quantity": 1})
            continue
        if not isinstance(item, dict):
            continue
        quantity = item.get("quantity") if isinstance(item.get("quantity"), int) else 1
        if isinstance(item.get("item"), str):
            result.append({"item": plain(item["item"].split("|")[0]).casefold(), "quantity": quantity})
        elif isinstance(item.get("equipmentType"), str):
            result.append({"equipment_type": str(item["equipmentType"]), "quantity": quantity})
        elif isinstance(item.get("special"), str):
            result.append({"special": plain(item["special"]), "quantity": quantity})
    return result


def build_classes() -> tuple[dict[str, dict], dict[str, str], list[str]]:
    """Усі класи 2014 з дзеркала, ключ — назва в нижньому регістрі."""
    classes: dict[str, dict] = {}
    files: dict[str, str] = {}
    problems: list[str] = []
    directory = config.INDEX_DIR / "mirror-class"
    if not directory.is_dir():
        return classes, files, ["немає теки content/raw/_index/mirror-class"]

    owned = owned_sources()
    skipped: list[str] = []
    variants: dict[str, set[str]] = {}
    for path in sorted(directory.glob("class-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            problems.append(f"{path.name}: {exc}")
            continue
        for klass in payload.get("class") or []:
            if not isinstance(klass, dict) or not klass.get("name"):
                continue
            if klass.get("edition") not in CLASSIC_EDITIONS:
                continue
            source = str(klass.get("source") or "")
            if source in OTHER_EDITION or source not in owned:
                # Хоумбрю (WoW), 2024 і книжки, яких немає в корпусі, — не наші класи.
                skipped.append(f"{plain(klass['name'])} ({source or '?'})")
                continue
            candidate = class_mechanics(klass, path.name, payload.get("subclass"))
            if not candidate["hit_die"]:
                skipped.append(f"{candidate['name_en']} ({source}): без хіт-дайса")
                continue
            key = candidate["name_en"].strip().casefold()
            existing = classes.get(key)
            variants.setdefault(key, set()).add(source)
            # Одна назва в кількох книгах (SRD + основна): лишаємо ту, що
            # має більше механік, і фіксуємо, що варіант не єдиний.
            if existing is not None and _weight(candidate) <= _weight(existing):
                continue
            classes[key] = candidate
            files[key] = path.name

    for key, entry in classes.items():
        if not entry["saving_throws"]:
            problems.append(f"{key}: немає володінь кидками порятунку")
        if len(variants.get(key) or ()) > 1:
            entry["variants"] = sorted(variants[key])
    if skipped:
        problems.append("пропущено: " + ", ".join(sorted(set(skipped))))
    return classes, files, problems


def _weight(entry: Mapping[str, Any]) -> tuple[int, int, int]:
    """Наскільки запис повний: більше механік — кращий варіант для вибору."""
    return (
        1 if entry.get("srd") else 0,
        len(entry.get("features") or []),
        len(entry.get("spell_slots") or []),
    )


# ---------------------------------------------------------------------------
# види й передісторії
# ---------------------------------------------------------------------------


def species_mechanics(
    row: dict,
    *,
    subrace_of: str | None = None,
    parent: Mapping[str, Any] | None = None,
    parent_is_standard: bool = False,
    name: str | None = None,
) -> dict[str, Any]:
    """Поля виду. Підраса успадковує від виду те, чого сама не задає.

    Спадкування потрібне через 5e.tools: «Hill Dwarf» задає лише +1 WIS, а
    швидкість 25, темний зір 60 і +2 CON живуть у записі «Dwarf». Показувати
    підрасу без них — показувати половину правил.

    Виняток — «звичайний» варіант виду (`standard_variant`: людина +1 до
    всього): він не базовий, тому підраса його бонуси **заміняє**, а не додає.
    """
    fixed, choose = abilities_from_value(row.get("ability"))
    own_fixed = dict(fixed)
    cantrips, cantrip_choice, granted_spells = species_spell_grants(row)
    skills, skill_any = skills_from_value(row.get("skillProficiencies"))
    languages, languages_any = languages_from_value(row.get("languageProficiencies"))
    weapons = named_proficiencies(row.get("weaponProficiencies"))
    tools = named_proficiencies(row.get("toolProficiencies"))
    tools_count = tools_any(row.get("toolProficiencies"))
    resistances = [str(item).casefold() for item in row.get("resist") or [] if str(item).casefold() in _DAMAGE_TYPES]
    speed = _speed(row.get("speed")) if row.get("speed") is not None else None
    darkvision = int(row["darkvision"]) if isinstance(row.get("darkvision"), int) else 0
    sizes = [name_ for name_ in (row.get("size") or []) if name_ in _SIZE_CODES]

    if parent:
        if not sizes:
            sizes = [code for code in (parent.get("size") or []) if code in _SIZE_CODES]
        if speed is None:
            speed = _speed(parent.get("speed"))
        if not darkvision:
            darkvision = int(parent["darkvision"]) if isinstance(parent.get("darkvision"), int) else 0
        if not skills and not skill_any:
            skills, skill_any = skills_from_value(parent.get("skillProficiencies"))
        parent_languages, parent_any = languages_from_value(parent.get("languageProficiencies"))
        for language in parent_languages:
            if language not in languages:
                languages.append(language)
        languages_any = max(languages_any, parent_any)
        for weapon in named_proficiencies(parent.get("weaponProficiencies")):
            if weapon not in weapons:
                weapons.append(weapon)
        for tool in named_proficiencies(parent.get("toolProficiencies")):
            if tool not in tools:
                tools.append(tool)
        tools_count = max(tools_count, tools_any(parent.get("toolProficiencies")))
        if not resistances:
            resistances = [
                str(item).casefold() for item in parent.get("resist") or [] if str(item).casefold() in _DAMAGE_TYPES
            ]
        if not parent_is_standard:
            parent_fixed, parent_choice = abilities_from_value(parent.get("ability"))
            for ability, amount in parent_fixed.items():
                fixed[ability] = fixed.get(ability, 0) + amount
            if not choose and parent_choice:
                choose = parent_choice

    return {
        "name_en": name or plain(row.get("name") or ""),
        "source_id": str(row.get("source") or ""),
        "edition": str(row.get("edition") or "classic"),
        "srd": bool(row.get("srd")),
        "basic_rules": bool(row.get("basicRules")),
        "subrace_of": subrace_of,
        "size": [_SIZE_CODES[code] for code in sizes] or ["medium"],
        "speed": speed if speed is not None else 30,
        "ability_fixed": fixed,
        "own_ability_fixed": own_fixed,
        "ability_choice": choose,
        # Дзеркало не кодує вільний розподіл характеристик 2022 року
        # (MPMM, RHW): у полі `ability` там просто `null`, а правило живе
        # текстом. Позначаємо це чесно, щоб візард знав, що вибір робить
        # гравець, а не таблиця.
        "ability_unresolved": not fixed and choose is None,
        "skill_proficiencies": skills,
        "skill_any": skill_any,
        "weapon_proficiencies": weapons,
        "tool_proficiencies": tools,
        "tools_any": tools_count,
        "languages": languages,
        "languages_any_standard": languages_any,
        "darkvision": darkvision,
        "resistances": resistances,
        "shared_cantrips": cantrips,
        "cantrip_choice": cantrip_choice,
        "granted_spells": granted_spells,
    }


def _speed(value: Any) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        walk = value.get("walk")
        if isinstance(walk, dict):
            walk = walk.get("number")
        if isinstance(walk, int):
            return walk
    return 30


def background_mechanics(row: dict) -> dict[str, Any]:
    skills, skill_any = skills_from_value(row.get("skillProficiencies"))
    languages, languages_any = languages_from_value(row.get("languageProficiencies"))
    equipment: list[dict[str, Any]] = []
    for group in row.get("startingEquipment") or []:
        if isinstance(group, dict):
            equipment.append(
                {choice: items_from_group(group.get(choice)) for choice in ("_", "a", "b") if group.get(choice)}
            )
        elif isinstance(group, list):
            equipment.append({"_": items_from_group(group)})
    return {
        "name_en": plain(row.get("name") or ""),
        "source_id": str(row.get("source") or ""),
        "edition": str(row.get("edition") or "classic"),
        "srd": bool(row.get("srd")),
        "basic_rules": bool(row.get("basicRules")),
        "skill_proficiencies": skills,
        "skill_any": skill_any,
        "tool_proficiencies": named_proficiencies(row.get("toolProficiencies")),
        "tools_any": tools_any(row.get("toolProficiencies")),
        "languages": languages,
        "languages_any_standard": languages_any,
        "feat": plain(row.get("feats") or "") or None,
        "feature": _background_feature_name(row),
        "starting_equipment": equipment,
    }


def _background_feature_name(row: dict) -> str | None:
    """«Feature: Shelter of the Faithful» → `Shelter of the Faithful`."""
    found: dict[str, str | None] = {"name": None}

    def walk(node: Any) -> None:
        if found["name"] is not None:
            return
        if isinstance(node, dict):
            name = node.get("name")
            if isinstance(name, str) and name.casefold().startswith("feature"):
                found["name"] = name.split(":", 1)[-1].strip() or None
                return
            for key in ("entries", "items", "entry"):
                walk(node.get(key))
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(row.get("entries"))
    return found["name"]


def _load_rows(name: str, key: str) -> list[dict]:
    path = config.INDEX_DIR / name
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get(key) or []
    return [row for row in rows if isinstance(row, dict)]


def subrace_name(row: dict) -> str:
    """Дзеркало: name="Hill", raceName="Dwarf" → «Hill Dwarf» (як у корпусі)."""
    parent = plain(row.get("raceName") or "")
    qualifier = _clean_name(str(row.get("name") or ""), row.get("source"))
    if not parent or parent.casefold() in qualifier.casefold():
        return qualifier or parent
    return f"{qualifier} {parent}".strip()


def build_origins() -> tuple[dict, dict, list[str]]:
    problems: list[str] = []
    races = _load_rows("races-5etools.json", "race")
    subraces = _load_rows("races-5etools.json", "subrace")
    backgrounds = _load_rows("backgrounds-5etools.json", "background")
    owned = owned_sources()

    def ours(row: Mapping[str, Any]) -> bool:
        source = str(row.get("source") or "")
        return row.get("edition") in CLASSIC_EDITIONS and source in owned and source not in OTHER_EDITION

    races = [row for row in races if ours(row)]
    subraces = [row for row in subraces if ours(row)]
    backgrounds = [row for row in backgrounds if ours(row)]

    subraces = [resolve_copy(row, _index_rows(subraces)) for row in subraces]
    # Передісторії-варіанти («Baldur's Gate Acolyte») — це `_copy` від базової
    # передісторії: без розкриття в них немає ні навичок, ні інструментів.
    backgrounds = [resolve_copy(row, _index_rows(backgrounds)) for row in backgrounds]

    species: dict[str, dict] = {}
    species_order: list[str] = []
    parent_rows: dict[str, dict] = {}
    variants: dict[str, set[str]] = {}
    duplicates = 0
    for row in races:
        key = plain(row.get("name") or "").strip().casefold()
        if not key:
            continue
        candidate = species_mechanics(row)
        variants.setdefault(f"species:{key}", set()).add(candidate["source_id"])
        existing = species.get(key)
        if existing is not None:
            duplicates += 1
            if _origin_weight(candidate) <= _origin_weight(existing):
                continue
        species[key] = candidate
        parent_rows[key] = row
        if key not in species_order:
            species_order.append(key)

    # 1) «звичайні» варіанти виду (людина +1 до всього) — вливаємо в базовий
    #    запис, бо окремим вибором вони не є.
    standard: set[str] = set()
    unnamed = [row for row in subraces if not plain(row.get("name") or "").strip()]
    for row in unnamed:
        parent = plain(row.get("raceName") or "").strip().casefold()
        if parent not in species:
            problems.append(f"вид {parent!r}: стандартний варіант без базового запису")
            continue
        merge_standard(species[parent], species_mechanics(row, subrace_of=parent or None))
        standard.add(parent)

    # 2) іменовані підраси — окремий вибір, з успадкуванням від виду.
    subspecies: dict[str, dict] = {}
    for row in subraces:
        if not plain(row.get("name") or "").strip():
            continue
        name = subrace_name(row)
        key = name.strip().casefold()
        if not key:
            continue
        parent = plain(row.get("raceName") or "").strip().casefold()
        if parent and parent not in species:
            problems.append(f"підраса {key}: батьківського виду {parent!r} немає")
        candidate = species_mechanics(
            row,
            subrace_of=parent or None,
            parent=parent_rows.get(parent),
            parent_is_standard=parent in standard,
            name=name,
        )
        variants.setdefault(f"subspecies:{key}", set()).add(candidate["source_id"])
        existing = subspecies.get(key)
        if existing is not None:
            duplicates += 1
            if _origin_weight(candidate) <= _origin_weight(existing):
                continue
        subspecies[key] = candidate

    origin: dict[str, dict] = {}
    for row in backgrounds:
        key = plain(row.get("name") or "").strip().casefold()
        if not key:
            continue
        candidate = background_mechanics(row)
        variants.setdefault(f"backgrounds:{key}", set()).add(candidate["source_id"])
        existing = origin.get(key)
        if existing is not None:
            duplicates += 1
            if _origin_weight(candidate) <= _origin_weight(existing):
                continue
        origin[key] = candidate

    # Одна раса в кількох книгах — це не дубль, а варіанти: показуємо джерела,
    # щоб було видно, звідки взято числа, і можна було перемкнути книгу.
    for path, sources in variants.items():
        if len(sources) < 2:
            continue
        family, key = path.split(":", 1)
        bucket = {"species": species, "subspecies": subspecies, "backgrounds": origin}[family]
        if key in bucket:
            bucket[key]["variants"] = sorted(sources)

    for key, entry in species.items():
        if not entry["ability_fixed"] and not entry["ability_choice"] and not entry["subrace_of"]:
            problems.append(f"вид {key}: без бонусів характеристик (можливо, підраса)")
    for key, entry in origin.items():
        if not entry["skill_proficiencies"] and not entry["skill_any"]:
            problems.append(f"передісторія {key}: без володінь навичками")

    return (
        {"schema": ORIGIN_SCHEMA, "species": species, "subspecies": subspecies, "backgrounds": origin},
        {"species": species_order, "duplicates": duplicates},
        problems,
    )


def _origin_weight(entry: Mapping[str, Any]) -> tuple[int, int, int, int, str]:
    """Кращий варіант — той, де є що рахувати, і з базових книг."""
    return (
        1 if (entry.get("ability_fixed") or entry.get("ability_choice")) else 0,
        1 if entry.get("srd") else 0,
        1 if entry.get("basic_rules") else 0,
        -SOURCE_PRIORITY.get(str(entry.get("source_id")), 10),
        str(entry.get("source_id") or ""),
    )


def merge_standard(target: dict, extra: Mapping[str, Any]) -> None:
    """Влити «звичайний» варіант виду в базовий запис (людина: +1 до всього)."""
    for ability, amount in (extra.get("ability_fixed") or {}).items():
        target["ability_fixed"][ability] = target["ability_fixed"].get(ability, 0) + int(amount)
    if not target.get("ability_choice") and extra.get("ability_choice"):
        target["ability_choice"] = extra["ability_choice"]
    for field in ("skill_proficiencies", "weapon_proficiencies", "tool_proficiencies", "languages", "resistances"):
        current = list(target.get(field) or [])
        for item in extra.get(field) or []:
            if item not in current:
                current.append(item)
        target[field] = current
    for field in ("skill_any", "tools_any", "languages_any_standard"):
        target[field] = int(target.get(field) or 0) + int(extra.get(field) or 0)
    target["darkvision"] = max(int(target.get("darkvision") or 0), int(extra.get("darkvision") or 0))
    target["standard_variant"] = True
    # «Нерозвʼязаним» вид стає лише тоді, коли після злиття бонусів так і немає.
    target["ability_unresolved"] = not target.get("ability_fixed") and target.get("ability_choice") is None


# ---------------------------------------------------------------------------
# запис і звіт
# ---------------------------------------------------------------------------


def build_class_index() -> dict:
    classes, files, problems = build_classes()
    return {
        "schema": CLASS_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "classes": classes,
        "problems": problems,
        "stats": {
            "classes": len(classes),
            "with_spellcasting": sum(1 for entry in classes.values() if entry["spellcasting_ability"]),
            "with_pact": sum(1 for entry in classes.values() if entry["pact_slots"]),
            "files": len(set(files.values())),
        },
    }


def build_origin_index() -> dict:
    payload, extra, problems = build_origins()
    payload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload["problems"] = problems
    payload["stats"] = {
        "species": len(payload["species"]),
        "subspecies": len(payload["subspecies"]),
        "backgrounds": len(payload["backgrounds"]),
        "duplicates": extra.get("duplicates", 0),
    }
    payload["order"] = extra["species"]
    return payload


def report_class(payload: Mapping[str, Any]) -> None:
    print(f"класів: {payload['stats']['classes']}")
    for key, entry in sorted(payload["classes"].items()):
        schools = entry["caster_progression"] or "—"
        print(
            f"  {entry['name_en']:<12} d{entry['hit_die']:<3} "
            f"кидки: {','.join(entry['saving_throws']):<8} "
            f"закляття: {schools:<9} "
            f"підклас на {entry['subclass_level'] or '—'}  ({entry['source_id']})"
        )
    for problem in payload.get("problems") or []:
        print("  !", problem)


def report_origin(payload: Mapping[str, Any]) -> None:
    print(
        f"видів: {payload['stats']['species']}, підрас: {payload['stats']['subspecies']}, "
        f"передісторій: {payload['stats']['backgrounds']}"
    )
    for key, entry in sorted(payload["species"].items()):
        bonus = ", ".join(f"{k}{v:+d}" for k, v in entry["ability_fixed"].items()) or "—"
        choice = entry["ability_choice"]
        extra = f" + вибір {choice['count']}×{choice['amount']}" if choice else ""
        print(
            f"  {entry['name_en']:<16} {bonus}{extra:<12} швидкість {entry['speed']}  темний зір {entry['darkvision']}"
        )
    for problem in (payload.get("problems") or [])[:20]:
        print("  !", problem)


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Механіки класів, видів і передісторій")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true", help="записати індекси")
    group.add_argument("--check", action="store_true", help="не писати, лише порівняти")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    # Звіт — українською, а консоль Windows за замовчуванням не в UTF-8.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    class_payload = build_class_index()
    origin_payload = build_origin_index()

    if args.check:
        stale: list[str] = []
        for path, payload in ((CLASS_TARGET, class_payload), (ORIGIN_TARGET, origin_payload)):
            if not path.is_file():
                print(f"індексу немає: {path.relative_to(config.REPO_ROOT)}")
                stale.append(path.name)
                continue
            stored = json.loads(path.read_text(encoding="utf-8"))
            key = "classes" if path is CLASS_TARGET else None
            if key:
                same = stored.get(key) == payload.get(key)
            else:
                same = all(stored.get(part) == payload.get(part) for part in ("species", "subspecies", "backgrounds"))
            if not same:
                print(f"індекс застарів: {path.relative_to(config.REPO_ROOT)}")
                stale.append(path.name)
        if stale:
            return 1
        print("індекси механік актуальні")
        return 0

    _write(CLASS_TARGET, class_payload)
    _write(ORIGIN_TARGET, origin_payload)
    if not args.quiet:
        report_class(class_payload)
        print()
        report_origin(origin_payload)
        print()
        print(f"записано {CLASS_TARGET.relative_to(config.REPO_ROOT)}")
        print(f"записано {ORIGIN_TARGET.relative_to(config.REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
