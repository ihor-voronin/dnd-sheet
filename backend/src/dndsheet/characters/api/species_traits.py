"""Особливості виду з книги: опис і список умінь.

Механіки виду (`origin-mechanics.json`) містять числа — бонуси, швидкість,
темний зір. Але в Harengon, наприклад, крім чисел є «Hare-Trigger» і «Rabbit
Hop», і саме їх бракувало на екрані створення: гравець бачив лише «без
бонусів». Текст умінь живе в записі довідника (`text_en`), тому його треба
вирізати звідти.

Формат тексту не однаковий, і це головна складність:

* у більшості видів є заголовок `### Harengon Traits`;
* у підрас умінь може не бути взагалі (у «Hill Dwarf» текст — це два рядки
  «Назва. Текст»);
* деякі книги (EEPC) віддали текст **одним рядком**: заголовки й уміння
  злиті в суцільний абзац. Такий текст спершу «перегортається» назад:
  перед фразою з великих літер, що стоїть на початку речення, ставиться
  розрив;
* у 50 із 64 підрас немає власного запису: «Lightfoot Halfling» у корпусі —
  запис «Lightfoot», а «Beasthide Shifter» — розділ у тексті «Shifter».

Тому пошук іде трьома кроками: точна назва → назва без слова-батька
(«Lightfoot», «Drow») → розділ із цією ознакою в тексті батька.

Текст не перекладається: у корпусі немає українських описів видів. Мова
визначається, щоб екран міг сказати «мовою книги», а не вдавати переклад.
Кеш живе на застосунку: тексти книг не змінюються.
"""

from __future__ import annotations

import re
from typing import Any

from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import MAX_LIMIT, EntryQuery
from dndsheet.shared.errors import NotFoundError

#: Заголовок розділу особливостей: `### Harengon Traits`, `## Dwarf Traits`.
TRAITS_HEADER = re.compile(r"^#{1,6}\s+.*\btraits\b", re.IGNORECASE)
#: Заголовок, надрукований великими літерами: «VARIANT HUMAN TRAITS».
UPPER_HEADING = re.compile(r"^[A-Z][A-Z0-9'’\- ,/]{2,60}$")
#: Будь-який Markdown-заголовок — кінець розділу особливостей.
HEADING = re.compile(r"^#{1,6}\s+")
#: «Назва. Текст» — одна особливість. Дужки й дефіси трапляються в назвах
#: («Hare-Trigger», «Thri-kreen Telepathy»), коми — ні.
TRAIT = re.compile(
    r"^(?:\*\*)?([A-ZА-ЯЁ][A-Za-zА-Яа-яЁё0-9'’()\- ]{1,38})\.(?:\*\*)?\s+(\S.*)$",
    re.DOTALL,
)
#: Вступні фрази перед списком умінь — вони не є умінням.
PREAMBLE = re.compile(
    r"^(?:as a .{0,80}?,? you have the following|.{0,80}?has the following)",
    re.IGNORECASE | re.DOTALL,
)
QUOTE = re.compile(r"^[—–-]\s*\S")
TABLE = re.compile(r"^\|")
CYRILLIC = re.compile(r"[А-Яа-яЁёІіЇїЄєҐґ]")
UKRAINIAN = re.compile(r"[ІіЇїЄєҐґ]")

#: Фраза з великих літер на початку речення — кандидат у злитий заголовок.
#: Дозволені маленькі сполучники: «Beak and Feather», «Plane of Air».
TITLE_PHRASE = re.compile(
    r"(?<=[.!?]\s)((?:[A-Z][A-Za-z'’\-]+|[a-z]+)(?:\s+(?:[A-Z][A-Za-z'’\-]+|of|the|and|or|in|on|to|with)){0,4})"
)
CONNECTORS = frozenset({"of", "the", "and", "or", "in", "on", "to", "with"})
STOP_WORDS = frozenset(
    {"descent", "the", "and", "or", "of", "bloodline", "lineage"}
)


def species_details(
    service: CompendiumService,
    name_en: str,
    *,
    parent_name_en: str | None = None,
    cache: dict[str, dict[str, Any] | None] | None = None,
) -> dict[str, Any] | None:
    """Опис і особливості виду; `None`, якщо тексту немає (лишається механіка)."""
    store = cache if cache is not None else {}
    key = (name_en or "").strip().casefold()
    if not key:
        return None
    cache_key = f"{key}||{(parent_name_en or '').strip().casefold()}"
    if cache_key in store:
        return store[cache_key]

    found: dict[str, Any] | None = None
    entry = _resolve(service, store, key, parent_name_en)
    if entry is not None:
        found = parse_species_text(entry.text_en or "", source_id=entry.source_id)
    if (found is None or not found["traits"]) and parent_name_en:
        # Підраса може бути описана в іншій книзі, ніж батько («Fallen Aasimar»
        # — у VGtM, а «Aasimar» — в EGtW), тому пробуємо всі варіанти.
        for parent in _resolve_all(service, store, parent_name_en.strip().casefold()):
            section = _section(parent.text_en or "", name_en, parent.name_en)
            if not section:
                continue
            parsed = parse_species_text(section, source_id=parent.source_id)
            if parsed is not None and (len(parsed["traits"]) > 0 or not found):
                parsed["from_parent"] = parent.name_en
                if found is None or len(parsed["traits"]) > len(found["traits"]):
                    found = parsed
    if found is None or not found["traits"]:
        # Останнє джерело — розділ правила: у SCAG/EGtW/MToF підраси описані
        # в тексті глави («GHOSTWISE HALFLINGS», «#### Pallid Elf»), а окремих
        # записів виду для них немає.
        parsed = _rule_traits(service, store, name_en, parent_name_en, found)
        if parsed is not None and (found is None or len(parsed["traits"]) > len(found["traits"])):
            found = parsed
    store[cache_key] = found
    return found


def parse_species_text(text: str, *, source_id: str | None = None) -> dict[str, Any]:
    """Розібрати текст виду на опис і особливості."""
    blocks = _blocks(text)
    start, has_header = _traits_start(blocks)

    description: list[str] = []
    for block in blocks[:start]:
        if PREAMBLE.match(block) or _is_noise(block):
            continue
        description.append(block)

    traits: list[dict[str, str]] = []
    for block in blocks[start:]:
        if _heading(block.splitlines()[0]):
            break  # наступний розділ книги — уміння скінчилися
        if _is_noise(block):
            continue
        match = TRAIT.match(block)
        if match:
            traits.append(
                {"name_en": match.group(1).strip(), "text": match.group(2).strip()}
            )
            continue
        if PREAMBLE.match(block) and not traits:
            continue
        if traits:
            traits[-1]["text"] = f"{traits[-1]['text']}\n\n{block}".strip()
        elif not has_header:
            # Проза без заголовка — це опис, а не уміння.
            description.append(block)

    whole = " ".join(description) + " " + " ".join(t["text"] for t in traits)
    return {
        "source_id": source_id,
        "description": "\n\n".join(description).strip(),
        "traits": traits,
        "lang": _language(whole),
    }


# ---------------------------------------------------------------------------
# внутрішнє: текст
# ---------------------------------------------------------------------------


def _blocks(text: str) -> list[str]:
    normalised = _reflow((text or "").replace("\r\n", "\n").replace("\r", "\n"))
    blocks = [re.sub(r"[ \t]+", " ", part).strip() for part in re.split(r"\n\s*\n", normalised)]
    blocks = [block for block in blocks if block]
    result: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) > 1 and sum(1 for line in lines if TRAIT.match(line)) > 1:
            result.extend(lines)
        else:
            result.extend(_split_inline_traits(block))
    return result


#: Початок уміння всередині суцільного рядка: після кінця речення стоїть
#: коротка назва з великих літер і за нею крапка: «…by 1. Age. Aarakocra…».
#: Слова назви — з великої літери (1–4 слова), інакше звичайне коротке
#: речення («Your Dexterity score increases by 2.») теж різалося б.
INLINE_TRAIT = re.compile(
    r"(?<=[.!?]\s)([A-Z][A-Za-z'’\-]*(?:\s+[A-Z][A-Za-z'’\-]*){0,3})\.\s"
)


def _split_inline_traits(block: str) -> list[str]:
    """Розрізати суцільний рядок на уміння (тексти EEPC прийшли без розривів)."""
    if "\n" in block:
        return [block]
    matches = list(INLINE_TRAIT.finditer(block))
    if len(matches) < 2:
        return [block]
    parts: list[str] = []
    last = 0
    for match in matches:
        parts.append(block[last : match.start()].strip())
        last = match.start()
    parts.append(block[last:].strip())
    return [part for part in parts if part]


def _reflow(text: str) -> str:
    """Розділити суцільний текст там, де закінчується заголовок особливостей.

    Книги EEPC віддали текст одним рядком, і «Aarakocra Traits As an
    aarakocra…» злиплися. Самі уміння ріже `_split_inline_traits` — тут лише
    межа між заголовком і вступом.
    """
    return re.sub(r"(\bTraits)\s+(?=As an? |You have|Being able)", r"\1\n\n", text)


def _traits_start(blocks: list[str]) -> tuple[int, bool]:
    for index, block in enumerate(blocks):
        heading = _heading(block.splitlines()[0])
        if heading is not None and "trait" in heading[1]:
            return index + 1, True
    for index, block in enumerate(blocks):
        if TRAIT.match(block):
            return index, False
    return len(blocks), False


def _is_noise(block: str) -> bool:
    """Цитати, таблиці й самі заголовки в описі не потрібні."""
    first = block.splitlines()[0]
    return bool(QUOTE.match(first) or TABLE.match(first) or _heading(first))


def _language(text: str) -> str:
    if not CYRILLIC.search(text):
        return "en"
    return "uk" if UKRAINIAN.search(text) else "ru"


# ---------------------------------------------------------------------------
# внутрішнє: підраси
# ---------------------------------------------------------------------------


def _section(text: str, child_name: str, parent_name: str) -> str | None:
    """Розділ підраси в тексті батька: «Beasthide Shifter» → «### Beasthide …»."""
    lines = _reflow((text or "").replace("\r\n", "\n")).splitlines()
    for keyword in _keywords(child_name, parent_name):
        section = _section_by_keyword(lines, keyword)
        if section is not None:
            return section
    return None


def _section_by_keyword(lines: list[str], keyword: str) -> str | None:
    level = 0
    start = None
    for index, line in enumerate(lines):
        heading = _heading(line)
        if heading is None:
            continue
        heading_level, title = heading
        if start is None:
            if _has_word(title, keyword):
                start, level = index, heading_level
        elif heading_level <= level:
            return "\n".join(lines[start:index]).strip()
    if start is None:
        return None
    return "\n".join(lines[start:]).strip()


def _has_word(text: str, word: str) -> bool:
    """«warding» не має збігатися з «Awarding»: потрібні межі слова."""
    return re.search(rf"(?<![a-z]){re.escape(word)}(?![a-z])", text) is not None


def _phrase(text: str) -> str:
    """«Half-Elf» → «half elf»: порівнювати назви родами, а не словами."""
    return re.sub(r"[^a-zа-яёіїєґ]+", " ", text.casefold()).strip()


def _heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
    if match:
        return len(match.group(1)), match.group(2).casefold()
    text = line.strip()
    if UPPER_HEADING.match(text) and sum(1 for char in text if char.isupper()) >= 3:
        return 6, text.casefold()
    return None


def _keywords(child_name: str, parent_name: str) -> list[str]:
    """Ознаки підраси за спаданням довжини: «Beasthide Shifter» → «beasthide».

    «Variant» — слово-маркер корпусу («Variant Human»), тому воно йде останнім
    і вживається, лише коли більше нема чого шукати.
    """
    child = child_name.casefold().replace(";", " ").replace("/", " ")
    parent = parent_name.casefold().replace("-", " ")
    for word in parent.split():
        child = child.replace(word, " ")
    words = [
        word
        for word in re.split(r"[^a-zа-яёіїєґ']+", child)
        if len(word) >= 3 and word not in STOP_WORDS
    ]
    ordered = sorted({word for word in words if word != "variant"}, key=len, reverse=True)
    if not ordered and "variant" in words:
        return ["variant"]
    return ordered


# ---------------------------------------------------------------------------
# внутрішнє: пошук запису
# ---------------------------------------------------------------------------


def _resolve(
    service: CompendiumService,
    store: dict[str, Any],
    name: str,
    parent_name_en: str | None,
):  # noqa: ANN202
    found = _resolve_all(service, store, name, parent_name_en)
    return _best(found) if found else None


def _resolve_all(
    service: CompendiumService,
    store: dict[str, Any],
    name: str,
    parent_name_en: str | None = None,
) -> list[Any]:
    """Усі записи-кандидати для виду: точна назва, дужки, «ядро», входження."""
    entries = _entries(service, store)
    # 1. точна назва
    if name in entries:
        return _ordered(entries[name])
    # 2. те, що в дужках: «Dragonborn (Chromatic)» → «chromatic dragonborn»,
    #    «Gnome (Deep)» → «deep gnome». Дужки — це ознака, а не батько.
    for inner in re.findall(r"\(([^)]+)\)", name):
        for token in sorted(_words(inner), key=len, reverse=True):
            if token in entries:
                return _ordered(entries[token])
            found = _contains(entries, token)
            if found:
                return found
    if not parent_name_en:
        for token in sorted(_words(name), key=len, reverse=True):
            found = _contains(entries, token)
            if found:
                return found
        return []
    # 3. назва без слова-батька: «Lightfoot Halfling» → «Lightfoot»
    parent = parent_name_en.strip().casefold()
    core = name
    for word in parent.replace("-", " ").split():
        core = core.replace(word, " ")
    core = re.sub(r"\s+", " ", core).strip(" ;")
    core_words = _words(core)
    for word in core_words:
        if word in entries:
            return _ordered(entries[word])
    # 4. запис, у назві якого є ознака: «Dark Elf (Drow)» для «Drow Elf»
    for word in sorted(core_words, key=len, reverse=True):
        found = _contains(entries, word)
        if found:
            return found
    return []


def _words(text: str) -> list[str]:
    return [word for word in re.split(r"[^a-zа-яёіїєґ']+", text.casefold()) if len(word) >= 3]


def _contains(entries: dict[str, list[Any]], token: str) -> list[Any]:
    matches = [
        entry
        for candidate, items in entries.items()
        if token in candidate
        for entry in items
    ]
    return _ordered(matches) if matches else []


def _best(items: list[Any]) -> Any:  # noqa: ANN401
    return _ordered(items)[0]


def _ordered(items: list[Any]) -> list[Any]:
    # «Базові правила» повторюють PHB, але з біднішим текстом — беремо книгу.
    return sorted(items, key=lambda entry: (entry.source_id == "basic-rules-2014", entry.id))


def _rule_traits(
    service: CompendiumService,
    store: dict[str, Any],
    name: str,
    parent_name_en: str | None,
    current: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Розділ виду в тексті глави правил (SCAG, EGtW, MToF…).

    Розділів з тим самим словом у заголовку буває кілька («Asmodeus» є і в
    пригоді), тому беремо найкращий: той, що згадує батьківський вид і має
    більше умінь.
    """
    keywords = _keywords(name, parent_name_en or "")
    if not keywords:
        return None
    parent_phrase = _phrase(parent_name_en or "")
    index, chapter_titles = _rule_headings(service, store)
    # Главу, у якій немає заголовка з батьківським видом, не читаємо: інакше
    # «Asmodeus» знаходиться в пригоді, а «Winged» — у бестіарії.
    allowed: set[str] | None = None
    if parent_phrase:
        allowed = {
            entry_id
            for entry_id, titles in chapter_titles.items()
            if any(parent_phrase in _phrase(title) for title in titles)
        }
    # Ключові слова — від найточнішого: знайшли хоч один розділ за «storm»,
    # далі «mark» уже не переглядаємо (інакше перемагає чужий mark).
    for keyword in keywords:
        best: dict[str, Any] | None = None
        best_score = 0
        for item in index:
            if allowed is not None and item["entry"].id not in allowed:
                continue
            if not _has_word(item["title"], keyword):
                continue
            lines = (item["entry"].text_en or "").splitlines()
            section = _slice_section(lines, item["line"], item["level"])
            if not section:
                continue
            parsed = parse_species_text(section, source_id=item["entry"].source_id)
            # Один «пункт» у главі пригод — це не опис виду: беремо розділ,
            # у якому справді є список умінь.
            if not parsed or len(parsed["traits"]) < 2:
                continue
            score = len(parsed["traits"])
            if parent_phrase and parent_phrase in _phrase(item["title"]):
                score += 20
            if parent_phrase and parent_phrase in _phrase(section):
                score += 10
            if score > best_score:
                parsed["from_rule"] = item["entry"].name_en
                best, best_score = parsed, score
        if best is not None:
            return best
    return current


def _rule_headings(
    service: CompendiumService, store: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Заголовки глав правил: один прохід корпусом, далі — з кешу."""
    cache_key = "rule-headings"
    cached = store.get(cache_key)
    if cached is not None:
        return cached
    index: list[dict[str, Any]] = []
    titles: dict[str, list[str]] = {}
    try:
        offset, total = 0, None
        while total is None or offset < total:
            page = service.entries(
                EntryQuery(category=Category.RULE, limit=MAX_LIMIT, offset=offset)
            )
            total = page.total
            if not page.items:
                break
            for entry in page.items:
                for line_number, line in enumerate((entry.text_en or "").splitlines()):
                    heading = _heading(line)
                    if heading is not None:
                        index.append(
                            {
                                "entry": entry,
                                "line": line_number,
                                "level": heading[0],
                                "title": heading[1],
                            }
                        )
                        titles.setdefault(entry.id, []).append(heading[1])
            offset += len(page.items)
    except NotFoundError:  # pragma: no cover — порожній корпус
        index, titles = [], {}
    store[cache_key] = (index, titles)
    return index, titles


def _slice_section(lines: list[str], start: int, level: int) -> str:
    for index in range(start + 1, len(lines)):
        heading = _heading(lines[index])
        if heading is not None and heading[0] <= level:
            return "\n".join(lines[start:index]).strip()
    return "\n".join(lines[start:]).strip()


def _entries(service: CompendiumService, store: dict[str, Any]) -> dict[str, list[Any]]:
    cache_key = "species-entries"
    entries = store.get(cache_key)
    if entries is not None:
        return entries
    entries = {}
    try:
        offset, total = 0, None
        while total is None or offset < total:
            page = service.entries(
                EntryQuery(category=Category.SPECIES, limit=MAX_LIMIT, offset=offset)
            )
            total = page.total
            if not page.items:
                break
            for entry in page.items:
                entries.setdefault(entry.name_en.strip().casefold(), []).append(entry)
            offset += len(page.items)
    except NotFoundError:  # pragma: no cover — порожній корпус
        pass
    store[cache_key] = entries
    return entries


__all__ = ["parse_species_text", "species_details"]
