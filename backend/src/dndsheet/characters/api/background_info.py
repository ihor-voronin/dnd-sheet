"""Передісторія для листа: що вона дає і який у неї текст.

У агрегаті є лише ключ, назва й механіки (навички, інструменти, мови, риса).
Текст «звідки це» живе в довіднику: там опис, рядок Equipment і розділ
`#### Feature: Military Rank`. Цей модуль вирізає їх для вкладки
«Передісторія», а вміння беруться з уже зібраних володінь персонажа — тобто
саме ті, які гравець обрав (мова, інструмент), а не «скільки можна обрати».

Результат кешується на застосунку: тексти книг не змінюються.
"""

from __future__ import annotations

import re
from typing import Any

from dndsheet.characters.api import backgrounds_uk
from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.proficiencies import ProficiencyKind
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import EntryQuery
from dndsheet.shared.errors import NotFoundError

#: `#### Feature: Military Rank` — так оформлені риси передісторій.
FEATURE_HEAD = re.compile(r"^#{2,4}\s+Feature:\s*(.+?)\s*$", re.IGNORECASE)
HEADING = re.compile(r"^#{2,4}\s+")
MECHANICAL = ("Skill Proficiencies:", "Tool Proficiencies:", "Languages:", "Equipment:")


def enrich_background(
    payload: dict[str, Any],
    character: Character,
    service: CompendiumService,
    cache: dict[str, Any] | None = None,
) -> None:
    background = character.background
    if background is None:
        payload["background_details"] = None
        return
    store = cache if cache is not None else {}
    key = f"background:{background.name_en.casefold()}"
    if key not in store:
        store[key] = _details(service, character)
    payload["background_details"] = store[key]


def _details(service: CompendiumService, character: Character) -> dict[str, Any]:
    background = character.background
    entry = _entry(service, background.name_en)
    text = entry.text_en or "" if entry is not None else ""
    description, equipment = _split_description(text)
    feature_text = _feature_text(text, background.feature_en)
    equipment_rows, equipment_money = parse_equipment(equipment)

    items = character.all_proficiencies().items
    mine = [
        item
        for item in items
        if item.source.kind.value == "background" and item.source.key == background.key
    ]

    def values(kind: ProficiencyKind) -> list[str]:
        return sorted({str(item.value) for item in mine if item.kind is kind})

    chosen = [
        item
        for item in character.chosen.items
        if item.source.kind.value == "background" and item.source.key == background.key
    ]

    def remaining(kind: ProficiencyKind, total: int) -> int:
        picked = sum(1 for item in chosen if item.kind is kind)
        return max(0, total - picked)

    return backgrounds_uk.enrich_sheet(
        {
            "key": background.key,
            "name_en": background.name_en,
            "source_id": background.source_id,
            "feature_en": background.feature_en,
            "feature_text": feature_text,
            "description": description,
            "equipment": equipment,
            "equipment_rows": equipment_rows,
            "money": equipment_money,
            "skills": values(ProficiencyKind.SKILL),
            "tools": values(ProficiencyKind.TOOL),
            "languages": values(ProficiencyKind.LANGUAGE),
            "skill_any": remaining(ProficiencyKind.SKILL, background.skill_any),
            "tools_any": remaining(ProficiencyKind.TOOL, background.tools_any),
            "languages_any": remaining(
                ProficiencyKind.LANGUAGE, background.languages_any_standard
            ),
        }
    )


def _entry(service: CompendiumService, name: str):  # noqa: ANN202
    """Запис довідника за точною назвою (без «базових правил»)."""
    page = service.entries(EntryQuery(category=Category.BACKGROUND, q=name, limit=100))
    wanted = name.strip().casefold()
    matches = [
        entry for entry in page.items if entry.name_en.strip().casefold() == wanted
    ]
    if not matches:
        return None
    matches.sort(key=lambda entry: (entry.source_id == "basic-rules-2014", entry.id))
    return matches[0]


def _split_description(text: str) -> tuple[str, str]:
    """Опис до першого підзаголовка; рядок Equipment — окремо."""
    head = re.split(r"(?m)^#{2,4}\s+", text, maxsplit=1)[0]
    lines: list[str] = []
    equipment = ""
    for line in head.splitlines():
        stripped = line.strip()
        if stripped.startswith(MECHANICAL):
            if stripped.startswith("Equipment:"):
                equipment = stripped.split(":", 1)[1].strip()
            continue
        lines.append(line.rstrip())
    description = "\n".join(lines).strip()
    while "\n\n\n" in description:
        description = description.replace("\n\n\n", "\n\n")
    return description, equipment


def _feature_text(text: str, feature: str | None) -> str:
    if not feature:
        return ""
    lines = text.splitlines()
    wanted = feature.strip().casefold()
    start = None
    for position, line in enumerate(lines):
        match = FEATURE_HEAD.match(line.strip())
        if match and match.group(1).strip().casefold() == wanted:
            start = position + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if HEADING.match(line.strip()):
            break
        body.append(line.rstrip())
    return "\n".join(body).strip()


def background_details(
    service: CompendiumService,
    name_en: str,
    feature_en: str | None = None,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Опис, риса й спорядження передісторії — для кроку візарда.

    Спорядження розбирається з рядка `Equipment:` книги на предмети; там, де
    книга пропонує вибір («prayer book or prayer wheel»), варіанти лишаються
    окремими, щоб екран дав вибрати.
    """
    store = cache if cache is not None else {}
    key = f"background-details:{(name_en or '').strip().casefold()}"
    if key in store:
        return store[key]
    entry = _entry(service, name_en or "")
    text = entry.text_en or "" if entry is not None else ""
    description, equipment_line = _split_description(text)
    rows, money = parse_equipment(equipment_line)
    found = {
        "description": description,
        "feature_en": feature_en,
        "feature_text": _feature_text(text, feature_en),
        "equipment": rows,
        "money": money,
        "source_id": entry.source_id if entry is not None else None,
    }
    # Переклад — окремим шаром: назва риси, опис, текст і кожна фраза
    # спорядження; оригінал лишається в payload для звірки з книгою.
    store[key] = backgrounds_uk.enrich_details(found)
    return store[key]


#: «a pouch containing 10 gp» — гроші з набору передісторії.
GOLD = re.compile(r"(\d+)\s*gp\b", re.IGNORECASE)


def parse_equipment(line: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Рядок Equipment → предмети з варіантами й гроші."""
    if not line:
        return [], {}
    rows: list[dict[str, Any]] = []
    money: dict[str, int] = {}
    for chunk in _split_top_level(line):
        chunk = _strip_lead(chunk)
        if not chunk:
            continue
        gold = GOLD.search(chunk)
        if gold:
            money["gp"] = money.get("gp", 0) + int(gold.group(1))
        choices = [_strip_lead(part) for part in _split_or(chunk)]
        choices = [part for part in choices if part]
        if not choices:
            continue
        rows.append(
            {
                "text": choices[0],
                "choices": choices if len(choices) > 1 else [],
            }
        )
    return rows, money


def _split_top_level(text: str) -> list[str]:
    """Поділити за комами, не чіпаючи коми в дужках."""
    parts: list[str] = []
    buffer = ""
    depth = 0
    for char in text:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            parts.append(buffer)
            buffer = ""
        else:
            buffer += char
    parts.append(buffer)
    return parts


def _split_or(text: str) -> list[str]:
    """Поділити «a or b or c» поза дужками."""
    parts: list[str] = []
    buffer = ""
    depth = 0
    index = 0
    lowered = text.lower()
    while index < len(text):
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if depth == 0 and lowered.startswith(" or ", index):
            parts.append(buffer)
            buffer = ""
            index += 4
            continue
        buffer += char
        index += 1
    parts.append(buffer)
    return parts


def _strip_lead(text: str) -> str:
    value = text.strip().strip(".")
    for prefix in ("and ", "a set of ", "an ", "a ", "the "):
        if value.lower().startswith(prefix):
            value = value[len(prefix) :]
            break
    return value.strip()


__all__ = ["background_details", "enrich_background", "parse_equipment"]
