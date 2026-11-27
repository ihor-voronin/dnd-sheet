"""Описи вмінь для вкладки «Уміння»: класові й підкласові.

Домен знає лише назви й рівні (`feature_rows`), а текст живе в довіднику.
Тут він вирізається з Markdown-тексту класу чи підкласу:

* класові вміння — заголовки `###` (наприклад `### Second Wind`), рівень
  береться з індексу механік, а не з тексту;
* підкласові — заголовки `##`, рівень читається з курсивного підпису
  `*6th-level Cleric feature*`, який стоїть на початку розділу.

Текст правила лишається джерелом англійською: український переклад — окремий
шар (`classes_uk`, файли в `content/translations/classes/`), і він додає
`name_uk`/`text_uk` до тих самих записів. Кеш живе на застосунку — тексти книг
не змінюються.
"""

from __future__ import annotations

import re
from typing import Any

from dndsheet.characters.api import classes_uk, subclasses_uk
from dndsheet.characters.domain.character import Character
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.shared.errors import NotFoundError

#: Заголовок класового вміння: рівно три решітки.
CLASS_HEADING = re.compile(r"^###\s+(.+?)\s*$")
#: Кінець класового розділу — заголовок вищого рівня (## або #).
CLASS_BOUNDARY = re.compile(r"^#{1,2}\s+")
#: Заголовок підкласового вміння: рівно дві решітки.
SUBCLASS_HEADING = re.compile(r"^##\s+(.+?)\s*$")
SUBCLASS_BOUNDARY = re.compile(r"^#\s+")
#: `*6th-level Cleric feature*` — рівень підкласового вміння.
LEVEL_MARK = re.compile(r"\*(\d+)(?:st|nd|rd|th)-level", re.IGNORECASE)


def enrich_features(
    payload: dict[str, Any],
    character: Character,
    service: CompendiumService,
    cache: dict[str, Any] | None = None,
) -> None:
    """Дописати `description` класовим умінням і додати підкласові."""
    store = cache if cache is not None else {}
    features: list[dict[str, Any]] = list(payload.get("features") or [])
    class_order = {entry.class_key: position for position, (entry, _) in enumerate(character.class_entries())}

    for feature in features:
        texts = _class_texts(store, service, feature.get("class_key") or "")
        if texts:
            feature["description"] = texts.get(str(feature.get("name_en") or ""), "")
        # Переклад уміння — окремим шаром: назва й текст показуються
        # українською, оригінал лишається в payload для звірки з книгою.
        classes_uk.enrich_feature(feature)

    for entry, definition in character.class_entries():
        if not entry.subclass_key:
            continue
        for item in _subclass_features(store, service, entry.subclass_key):
            if item["level"] > entry.level:
                continue
            features.append(
                subclasses_uk.enrich_feature(
                    {
                        "name_en": item["name_en"],
                        "level": item["level"],
                        "class_key": entry.class_key,
                        "class_name": definition.name_en,
                        "source": "subclass",
                        "subclass_name": item["subclass_name"],
                        "subclass_name_uk": item.get("subclass_name_uk"),
                        "description": item["description"],
                    }
                )
            )

    features.sort(
        key=lambda item: (
            class_order.get(str(item.get("class_key")), 99),
            int(item.get("level") or 1),
            0 if item.get("source") == "class" else 1,
            str(item.get("name_en") or "").casefold(),
        )
    )
    payload["features"] = features
    payload["feat_details"] = _feat_details(store, service, character)


def _feat_details(
    store: dict[str, Any], service: CompendiumService, character: Character
) -> list[dict[str, Any]]:
    """Вибрані риси з текстом: на екрані вони живуть разом з уміннями."""
    details: list[dict[str, Any]] = []
    for key in character.feats:
        entry = _feat_entry(store, service, key)
        if entry is None:
            details.append({"key": key, "name_en": key, "description": ""})
            continue
        details.append(
            {
                "key": key,
                "name_en": entry.name_en,
                "name_uk": entry.name_uk,
                "source_id": entry.source_id,
                "description": entry.text_en or "",
            }
        )
    return details


def _feat_entry(store: dict[str, Any], service: CompendiumService, key: str) -> Any:
    cache_key = "feat-entries"
    entries = store.get(cache_key)
    if entries is None:
        entries = {entry.id.casefold(): entry for entry in service.feats()}
        store[cache_key] = entries
    return entries.get((key or "").strip().casefold())


def class_texts_all(
    service: CompendiumService,
    class_key: str,
    cache: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Тексти умінь класу з **усіх** його записів у корпусі.

    Глава класу одна, але в різних книгах вона різна: у PHB — базові вміння, у
    TCoE — опційні («Sorcerous Versatility», «Magical Guidance»). Механіки
    класу зливають обидві, тож і тексти треба злити, інакше опційні вміння
    лишаються без опису. Перемагає перший запис (книга, а не «базові
    правила»), бо він повніший.
    """
    store = cache if cache is not None else {}
    key = f"class-texts-all:{class_key}"
    if key in store:
        return store[key]
    texts: dict[str, str] = {}
    for entry in _class_entries_all(store, service, class_key):
        for name, text in _sections(
            entry.text_en or "", CLASS_HEADING, CLASS_BOUNDARY
        ).items():
            texts.setdefault(name, text)
    store[key] = texts
    return texts


def _class_entries_all(
    store: dict[str, Any], service: CompendiumService, class_key: str
) -> list[Any]:
    cache_key = "class-entries"
    entries = store.get(cache_key)
    if entries is None:
        try:
            entries = [summary.entry for summary in service.classes()]
        except NotFoundError:  # pragma: no cover — порожній корпус
            entries = []
        store[cache_key] = entries
    candidates = [
        entry for entry in entries if entry.id.casefold().endswith(f"/class/{class_key}")
    ]
    # «Базові правила» повторюють PHB, але з біднішим текстом — беремо книгу.
    return sorted(candidates, key=lambda entry: (entry.source_id == "basic-rules-2014", entry.id))


def _class_texts(
    store: dict[str, Any],
    service: CompendiumService,
    class_key: str,
) -> dict[str, str]:
    key = f"class:{class_key}"
    if key in store:
        return store[key]
    entry = _class_entry(store, service, class_key)
    texts = _sections(entry.text_en or "", CLASS_HEADING, CLASS_BOUNDARY) if entry else {}
    store[key] = texts
    return texts


def _class_entry(
    store: dict[str, Any], service: CompendiumService, class_key: str
) -> Any:
    cache_key = "class-entries"
    entries = store.get(cache_key)
    if entries is None:
        try:
            entries = [summary.entry for summary in service.classes()]
        except NotFoundError:  # pragma: no cover — порожній корпус
            entries = []
        store[cache_key] = entries
    candidates = [
        entry for entry in entries if entry.id.casefold().endswith(f"/class/{class_key}")
    ]
    if not candidates:
        return None
    # «Базові правила» повторюють PHB, але з біднішим текстом — беремо книгу.
    candidates.sort(key=lambda entry: (entry.source_id == "basic-rules-2014", entry.id))
    return candidates[0]


def _subclass_features(
    store: dict[str, Any], service: CompendiumService, subclass_key: str
) -> list[dict[str, Any]]:
    key = f"subclass:{subclass_key}"
    if key in store:
        return store[key]
    try:
        entry = service.entry(subclass_key)
    except NotFoundError:
        store[key] = []
        return []
    sections = _sections(entry.text_en or "", SUBCLASS_HEADING, SUBCLASS_BOUNDARY)
    items: list[dict[str, Any]] = []
    for name, text in sections.items():
        match = LEVEL_MARK.search(text[:400])
        level = int(match.group(1)) if match else 1
        items.append(
            subclasses_uk.enrich_feature(
                {
                    "name_en": name,
                    "level": level,
                    "description": _strip_level_mark(text),
                    "subclass_name": entry.name_en,
                    "subclass_name_uk": subclasses_uk.name_uk(entry.name_en),
                }
            )
        )
    store[key] = items
    return items


def _strip_level_mark(text: str) -> str:
    """Прибрати курсивний підпис рівня з початку розділу.

    У книзі розділ починається рядком `*10th-level Cleric feature*`; рівень уже
    є окремим полем, тож у тексті він зайвий — і перекладачеві нема чого
    перекладати в цьому рядку.
    """
    lines = text.lstrip("\n").splitlines()
    while lines and lines[0].startswith("*") and "level" in lines[0].casefold():
        lines = lines[1:]
    return "\n".join(lines).lstrip("\n").strip()


def subclass_features(
    service: CompendiumService,
    subclass_key: str,
    cache: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Уміння підкласу з рівнями — для вкладки «Уміння» і вибору підкласу."""
    return _subclass_features(cache if cache is not None else {}, service, subclass_key)


def _sections(
    text: str, heading: re.Pattern[str], boundary: re.Pattern[str]
) -> dict[str, str]:
    """Розрізати Markdown на розділи за заголовками одного рівня."""
    sections: dict[str, str] = {}
    name: str | None = None
    buffer: list[str] = []
    for line in text.splitlines():
        match = heading.match(line)
        if match:
            if name is not None:
                sections[name] = "\n".join(buffer).strip()
            name = match.group(1).strip()
            buffer = []
            continue
        if boundary.match(line):
            if name is not None:
                sections[name] = "\n".join(buffer).strip()
                name = None
                buffer = []
            continue
        if name is not None:
            buffer.append(line)
    if name is not None:
        sections[name] = "\n".join(buffer).strip()
    return sections


def class_details(
    service: CompendiumService,
    class_key: str,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Опис класу й текст кожного вміння — для кроку «Клас» у візарді.

    Числа класу живуть в індексі механік, а «що це за клас» — лише в книзі,
    тому екран бере опис звідси (так само, як лист бере тексти вмінь).
    """
    store = cache if cache is not None else {}
    entry = _class_entry(store, service, class_key)
    if entry is None:
        return {"description": "", "features": []}
    texts = _class_texts(store, service, class_key)
    payload: dict[str, Any] = {
        "description": _intro(entry.text_en or ""),
        "features": [
            {"name_en": name, "text": text} for name, text in texts.items()
        ],
    }
    return classes_uk.enrich_details(payload)


def _intro(text: str) -> str:
    """Проза на початку глави класу — до першого розділу `##`."""
    lines = text.replace("\r\n", "\n").splitlines()
    collected: list[str] = []
    started = False
    for line in lines:
        heading = re.match(r"^(#{1,6})\s+", line)
        if heading:
            level = len(heading.group(1))
            if started and level <= 2:
                break
            continue
        if line.strip():
            started = True
            collected.append(line)
        elif collected:
            collected.append(line)
    return "\n".join(collected).strip()


#: Рядок рівня, надрукований звичайним текстом (у TCoE — «3rd-level sorcerer
#: feature»): у списку рівень уже є окремим полем, тож у тілі він зайвий.
LEVEL_LINE_EN = re.compile(r"^\d+(?:st|nd|rd|th)-level [^\n]*?feature\s*\n+", re.IGNORECASE)
LEVEL_LINE_UK = re.compile(r"^Уміння [^\n]*?\d+-го рівня\s*\n+")


def strip_level_line(payload: dict[str, Any]) -> dict[str, Any]:
    """Прибрати перший абзац-підпис рівня з тексту (для показу, не для ключа)."""
    for field, pattern in (("text", LEVEL_LINE_EN), ("text_uk", LEVEL_LINE_UK)):
        value = payload.get(field)
        if isinstance(value, str) and value:
            payload[field] = pattern.sub("", value, count=1)
    return payload


__all__ = [
    "class_details",
    "class_texts_all",
    "enrich_features",
    "strip_level_line",
    "subclass_features",
]


