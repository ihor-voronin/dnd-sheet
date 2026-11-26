"""Dragonlance: Shadow of the Dragon Queen → записи довідника.

Книга є лише в російському фанатському перекладі (PDF, 205 сторінок), але зі
справжнім текстовим шаром: OCR не потрібен. Особливість шару — увесь текст
сторінки лежить одним блоком без координат (сторінка — це скан, а текст
накладено зверху), тому розмітку доводиться брати не з геометрії, а зі шрифтів:
заголовки набрано `AlegreyaSC-*`, вбудовані підзаголовки — жирним `Mookmania-Bold`,
а блоки статистики — зменшеним кеглем.

Що з книги беремо (для листка персонажа):

* `species` — Кендер;
* `background` — Соламнійський лицар і Маг Вищого Чарівництва;
* `feat` — девʼять рис (Оруженосець Соламнії, три Лицарі, три Адепти, Обраний
  Богом, Посвячений у Вище Чарівництво);
* `subclass` — Місячне чарівництво (чародій);
* `item` — спорядження, облогові машини й чотири магічні предмети (додаток А);
* `monster` — статблоки (додатки Б і В);
* `rule` — правила, на які посилається листок (варіант виду, бонусні риси,
  організації, зброя Армії драконів).

Текст запису — як у книзі, російською. Структуровані значення `data` (розмір,
тип істоти, рідкість предмета, клас) перекладаються в канонічний словник
корпусу: інакше «всі монстри» мали б два різні набори значень.

    python scripts/pdf/build_sotdq.py --pages    # лише розібрати сторінки в markdown
    python scripts/pdf/build_sotdq.py            # зібрати записи
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.normalize import canonical as compendium_format  # noqa: E402

PDF = ROOT / "content" / "raw" / "sotdq" / "source.pdf"
PAGES_DIR = ROOT / "content" / "raw" / "sotdq" / "pages"
SOURCE = "sotdq"
LICENSE = "proprietary"
URL = None
FETCHED = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
NOTE = "текст — російський фанатський переклад (оригінал: Wizards of the Coast, 2022)"

DISPLAY_FONT = "AlegreyaSC"
ITALIC = "Mookmania-Italic"
SIDEBAR_FONT = "AlegreyaSansSC"

HEADING_MIN = 11.5
CHAPTER_SIZE = 28.0

BRACKET = re.compile(r"^(?P<ru>.+?)\s*\[(?P<en>[^\]]+)\]\s*$")


# --- шрифтовий шар --------------------------------------------------------

class Line:
    """Рядок текстового шару: текст, кегль, шрифт, чи починається з жирного."""

    __slots__ = ("text", "size", "font", "bold_lead", "page")

    def __init__(self, text: str, size: float, font: str, bold_lead: bool, page: int) -> None:
        self.text = text
        self.size = size
        self.font = font
        self.bold_lead = bold_lead
        self.page = page

    def __repr__(self) -> str:  # pragma: no cover — лише для налагодження
        return f"Line({self.page}, {self.size}, {self.font}, {self.text[:40]!r})"


def read_lines(doc: pymupdf.Document) -> list[Line]:
    """Рядки всієї книги в порядку читання."""
    lines: list[Line] = []
    for page_index in range(doc.page_count):
        for block in doc[page_index].get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for raw_line in block["lines"]:
                spans = [span for span in raw_line["spans"] if span["text"].strip()]
                if not spans:
                    continue
                text = ""
                for index, span in enumerate(spans):
                    piece = span["text"]
                    if index and text and not text.endswith(" ") and not piece.startswith(" "):
                        # Стиль змінюється без пробілу: «ремесла» + «Реоркс».
                        if text[-1].isalnum() and piece[0].isalnum():
                            text += " "
                    text += piece
                text = re.sub(r"\s+", " ", text).strip()
                if not text:
                    continue
                main = max(spans, key=lambda span: len(span["text"]))
                bold_lead = "Bold" in spans[0]["font"] and len(spans[0]["text"].strip()) > 0
                lines.append(
                    Line(text, round(main["size"], 1), main["font"], bold_lead, page_index + 1)
                )
    return lines


def is_display(line: Line) -> bool:
    return line.font.startswith(DISPLAY_FONT)


def is_heading(line: Line) -> bool:
    return is_display(line) and line.size >= HEADING_MIN


def heading_level(line: Line) -> int:
    if not is_heading(line):
        return 0
    if line.size >= CHAPTER_SIZE:
        return 1
    if line.size >= 16:
        return 2
    if line.size >= 13:
        return 3
    if "Bold" in line.font:
        return 4  # назва статблока
    return 5      # підрозділ сторінки (риса, предмет, локація)


def is_stat_section(line: Line) -> bool:
    """«Особенности», «Действия», «Реакции» — підзаголовок статблока."""
    return is_display(line) and "Bold" in line.font and line.size < HEADING_MIN


def is_italic_detail(line: Line) -> bool:
    """Курсивні рядки-атрибути: тип істоти, тип предмета, «Особенность 1 уровня»."""
    return line.font.startswith(ITALIC)


def is_sidebar(line: Line) -> bool:
    return line.font.startswith(SIDEBAR_FONT)


# --- гігієна тексту -------------------------------------------------------

HYPHEN_TAIL = re.compile(r"[-\u2010\u2011\u2012]$")
CYRILLIC = re.compile(r"[а-яёіїєґa-z]", re.IGNORECASE)


def join_pair(left: str, right: str) -> str:
    """Склеює два рядки, прибираючи перенос («гибель-» + «миру»)."""
    if HYPHEN_TAIL.search(left) and CYRILLIC.match(right[:1] or ""):
        return left[:-1] + right
    return left + " " + right


def clean(text: str) -> str:
    text = text.replace("\u00ad", "").replace("\ufeff", "")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# --- вузли документа ------------------------------------------------------

@dataclass
class Node:
    kind: str                       # heading | statsection | italic | para | sidebar
    text: str
    level: int = 0
    page: int = 0
    lines: list[Line] = field(default_factory=list)


def build_nodes(lines: list[Line]) -> list[Node]:
    """Потік вузлів: заголовки, атрибути, абзаци."""
    nodes: list[Node] = []
    paragraph: Node | None = None

    def flush() -> None:
        nonlocal paragraph
        if paragraph is not None and paragraph.text.strip():
            nodes.append(paragraph)
        paragraph = None

    for line in lines:
        if is_heading(line):
            flush()
            nodes.append(
                Node("heading", clean(line.text), heading_level(line), line.page, [line])
            )
        elif is_stat_section(line):
            flush()
            nodes.append(Node("statsection", clean(line.text), 4, line.page, [line]))
        elif is_italic_detail(line):
            flush()
            nodes.append(Node("italic", clean(line.text), 0, line.page, [line]))
        elif is_sidebar(line):
            flush()
            nodes.append(Node("sidebar", clean(line.text), 0, line.page, [line]))
        elif paragraph is None or line.bold_lead or line.size != paragraph.lines[-1].size:
            flush()
            paragraph = Node("para", clean(line.text), 0, line.page, [line])
        else:
            paragraph.text = join_pair(paragraph.text, line.text)
            paragraph.lines.append(line)
    flush()
    return merge_headings(nodes)


def merge_headings(nodes: list[Node]) -> list[Node]:
    """Назва, що переноситься: «Кагонестиский лесной саван» + «[Kagonesti …]»."""
    merged: list[Node] = []
    for node in nodes:
        if merged and node.kind == "heading" and merged[-1].kind == "heading":
            previous = merged[-1]
            same_style = previous.level == node.level and previous.page == node.page
            continues = (
                previous.text.endswith("-")
                or node.text.startswith(("[", "("))
                or node.text[:1].islower()
            )
            if same_style and continues:
                previous.text = join_pair(previous.text, node.text)
                previous.lines.extend(node.lines)
                continue
        merged.append(node)
    return merged


def split_name(text: str) -> tuple[str, str | None]:
    """«Анколокс [Anhkolox]» → («Анколокс», «Anhkolox»)."""
    match = BRACKET.match(text)
    if match:
        return match.group("ru").strip(), match.group("en").strip()
    return text.strip(), None


# --- сторінки в markdown --------------------------------------------------

def render_md(nodes: list[Node]) -> str:
    parts: list[str] = []
    for node in nodes:
        if node.kind == "heading":
            parts.append("#" * node.level + " " + node.text)
        elif node.kind == "statsection":
            parts.append("#### " + node.text)
        else:
            parts.append(node.text)
    return "\n\n".join(part for part in parts if part.strip())


def dump_pages(doc: pymupdf.Document, lines: list[Line]) -> None:
    PAGES_DIR.mkdir(parents=True, exist_ok=True)
    by_page: dict[int, list[Line]] = {}
    for line in lines:
        by_page.setdefault(line.page, []).append(line)
    for page_index in range(doc.page_count):
        nodes = build_nodes(by_page.get(page_index + 1, []))
        (PAGES_DIR / f"{page_index + 1:03d}.md").write_text(
            render_md(nodes) + "\n", encoding="utf-8"
        )


# --- словники значень -----------------------------------------------------

SIZES = (
    ("крошечн", "tiny"),
    ("мал", "small"),
    ("средн", "medium"),
    ("больш", "large"),
    ("огромн", "huge"),
    ("громадн", "gargantuan"),
    ("исполинск", "gargantuan"),
)

CREATURES = (
    ("нежит", "undead"),
    ("гуманоид", "humanoid"),
    ("дракон", "dragon"),
    ("звер", "beast"),
    ("аберраци", "aberration"),
    ("конструкт", "construct"),
    ("элементал", "elemental"),
    ("исчади", "fiend"),
    ("небожител", "celestial"),
    ("великан", "giant"),
    ("фей", "fey"),
    ("фея", "fey"),
    ("растени", "plant"),
    ("слиз", "ooze"),
    ("монстр", "monstrosity"),
)

ALIGNMENTS = (
    ("законно-добр", "lawful good"),
    ("законно-нейтральн", "lawful neutral"),
    ("законно-зл", "lawful evil"),
    ("нейтрально-добр", "neutral good"),
    ("нейтрально-зл", "neutral evil"),
    ("нейтрально-нейтральн", "neutral"),
    ("хаотично-добр", "chaotic good"),
    ("хаотично-нейтральн", "chaotic neutral"),
    ("хаотично-зл", "chaotic evil"),
    ("без мировоззр", "unaligned"),
    ("не имеющ", "unaligned"),
    ("нейтральн", "neutral"),
)

RARITIES = (
    ("легендарн", "legendary"),
    ("очень редк", "very rare"),
    ("редк", "rare"),
    ("необычн", "uncommon"),
    ("обычн", "common"),
    ("артефакт", "artifact"),
    ("разн", "varies"),
    ("варьир", "varies"),
)

ITEM_TYPES = (
    ("чудесн", "wondrous item"),
    ("волшебн", "wondrous item"),
    ("рукопашн", "weapon"),
    ("дальнобойн", "weapon"),
    ("воинск", "weapon"),
    ("простое", "weapon"),
    ("оружие", "weapon"),
    ("доспех", "armor"),
    ("брон", "armor"),
    ("щит", "shield"),
    ("кольц", "ring"),
    ("жезл", "rod"),
    ("посох", "staff"),
    ("палочк", "wand"),
    ("свиток", "scroll"),
    ("зель", "potion"),
    ("татуировк", "tattoo"),
    ("снаряжени", "gear"),
)

CLASSES = {
    "чародей": "sorcerer",
    "волшебник": "wizard",
    "колдун": "warlock",
    "бард": "bard",
    "жрец": "cleric",
    "друид": "druid",
    "воин": "fighter",
    "паладин": "paladin",
    "паладайн": "paladin",
    "следопыт": "ranger",
    "плут": "rogue",
    "монах": "monk",
    "варвар": "barbarian",
}

ABILITY_LABELS = {
    "сил": ("str", "СИЛ"),
    "лов": ("dex", "ЛОВ"),
    "тел": ("con", "ТЕЛ"),
    "инт": ("int", "ИНТ"),
    "мдр": ("wis", "МДР"),
    "хар": ("cha", "ХАР"),
}


def pick(table, text: str) -> str | None:
    lowered = (text or "").lower()
    for needle, value in table:
        if lowered.startswith(needle) or needle in lowered:
            return value
    return None


def split_creature_line(text: str) -> tuple[str | None, str | None, str | None, str | None]:
    """«Огромная нежить, нейтрально-злая» → size, type, subtype, alignment."""
    text = text.strip().rstrip(".")
    alignment = None
    if "," in text:
        head, _, tail = text.rpartition(",")
        alignment = pick(ALIGNMENTS, tail.strip())
        text = head.strip()
    size = None
    size_word = ""
    first = text.split(" ", 1)[0].lower() if text else ""
    for needle, value in SIZES:
        if first.startswith(needle):
            size = value
            size_word = text.split(" ", 1)[0]
            break
    rest = text[len(size_word):].strip() if size_word else text
    subtype = None
    if "(" in rest and ")" in rest:
        rest, _, extra = rest.partition("(")
        subtype = extra.rstrip(")").strip()
        rest = rest.strip()
    creature = pick(CREATURES, rest.lower())
    return size, creature, subtype, alignment



# --- статблоки ------------------------------------------------------------

FIELD_LABELS = {
    "skills": "Навыки",
    "damage_immunities": "Иммунитет к урону",
    "damage_resistances": "Сопротивление к урону",
    "damage_vulnerabilities": "Уязвимость к урону",
    "condition_immunities": "Иммунитет к состояниям",
    "senses": "Чувства",
    "languages": "Языки",
}

STAT_FIELD_PREFIXES = (
    ("навыки", "skills"),
    ("иммунитет к состоянию", "condition_immunities"),
    ("иммунитет к состояниям", "condition_immunities"),
    ("иммунитет к урону", "damage_immunities"),
    ("сопротивление к урону", "damage_resistances"),
    ("сопротивление", "damage_resistances"),
    ("уязвимость к урону", "damage_vulnerabilities"),
    ("уязвимость", "damage_vulnerabilities"),
    ("чувства", "senses"),
    ("языки", "languages"),
)

# Підзаголовки всередині блоку. Вони набрані тим самим шрифтом, що й назва
# статблока, і на різних сторінках мають різний кегль (10.7 і 12.1), тому
# розрізняти їх за розміром неможливо — лише за текстом.
STAT_SECTION_TEXTS = {
    "особенности",
    "действия",
    "реакции",
    "бонусные действия",
    "легендарные действия",
    "легендарные варианты",
    "действия логова",
    "особенности логова",
    "региональные эффекты",
    "снаряжение",
}

CREATURE_LINE_RE = re.compile(
    r"^(?:крошечн|мал|средн|больш|огромн|громадн|исполинск)\w*\s+[а-яё]", re.IGNORECASE
)
BRACKET_ONLY = re.compile(r"^\[(?P<en>[^\]]+)\]$")

# Назви, яких книга не дублює англійською в дужках (їх довелося взяти з
# оригінального видання).
MONSTER_EN = {
    "Карадок": "Karadok",
    "Канзальди Огнеглазая": "Kansaldi Fire-Eyes",
    "Лохезет": "Lohezet",
    "Лорд Сот": "Lord Soth",
    "Алая Погибель": "Crimson Death",
    "Рыцарь-скелет": "Skeleton Knight",
    "Вестерн Керн": "Wersten Kern",
}
CR_RE = re.compile(
    r"^(?:ПО|Показатель опасности|Уровень опасности)\s*(?P<cr>[0-9/]+)\s*\((?P<rest>[^)]*)\)"
)
XP_RE = re.compile(r"(?:Опыт|XP)\s*([0-9 ,]+)")
ABILITY_RE = re.compile(
    r"(?P<label>Сил|Лов|Тел|Инт|Мдр|Хар)\s*(?P<score>-?\d{1,2})"
    r"(?:\s*(?P<mod>[+-]\d{1,2}))?(?:\s*(?P<save>[+-]\d{1,2}))?"
)
STAT_HEAD_RE = re.compile(r"^(?:КД\b|Класс доспеха|Хиты\b|Скорость\b)", re.IGNORECASE)


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def is_stat_section(line: "Line") -> bool:
    return (
        is_display(line)
        and "Bold" in line.font
        and line.text.strip().lower().rstrip(":") in STAT_SECTION_TEXTS
    )


def is_stat_name(line: "Line") -> bool:
    return (
        is_display(line)
        and "Bold" in line.font
        and line.size >= HEADING_MIN
        and not is_stat_section(line)
    )


def parse_abilities(lines: list["Line"]) -> tuple[dict[str, int | None], str | None]:
    """Шість характеристик із розсипу таблиці («Мод Спас», «Сил 22+6 +6»)."""
    scores: dict[str, int | None] = {
        "str": None, "dex": None, "con": None, "int": None, "wis": None, "cha": None
    }
    saves: list[str] = []
    joined = " ".join(line.text for line in lines)
    for match in ABILITY_RE.finditer(joined):
        key, label = ABILITY_LABELS[match.group("label").lower()]
        score = int(match.group("score"))
        if not 1 <= score <= 30:
            continue
        scores[key] = score
        modifier = match.group("mod")
        save = match.group("save")
        if save is not None and modifier is not None and save != modifier:
            saves.append(f"{label.title()} {save}")
    return scores, (", ".join(saves) if saves else None)


def stat_blocks(lines: list["Line"]) -> list[tuple[str, str | None, int, list["Line"]]]:
    """(назва, англійська назва, сторінка, рядки блоку).

    Опорна точка — рядок типу істоти («Огромная нежить, нейтрально-злая»):
    він є в кожному блоці й трапляється рівно один раз. Назва ж у цій
    верстці стоїть то перед ним, то після (на сторінках, де текст наклали
    іншим порядком, назва опиняється в кінці сторінки), тому шукаємо її і
    назад, і вперед.
    """
    creature_positions = [
        index
        for index, line in enumerate(lines)
        if is_italic_detail(line) and CREATURE_LINE_RE.match(line.text)
    ]
    blocks: list[tuple[str, str | None, int, list["Line"]]] = []
    for order, position in enumerate(creature_positions):
        hard_end = (
            creature_positions[order + 1]
            if order + 1 < len(creature_positions)
            else len(lines)
        )
        end = hard_end
        for cursor in range(position + 1, hard_end):
            candidate = lines[cursor]
            # Звичайний заголовок (не жирний дисплейний) — це вже інший розділ.
            if is_display(candidate) and "Bold" not in candidate.font:
                end = cursor
                break

        name_index = None
        for cursor in range(position - 1, max(position - 5, -1), -1):
            candidate = lines[cursor]
            if is_stat_name(candidate):
                name_index = cursor
                break
            if is_display(candidate):
                break
        if name_index is None:
            for cursor in range(position + 1, end):
                if is_stat_name(lines[cursor]):
                    name_index = cursor
                    break

        name = ""
        english = None
        consumed: set[int] = set()
        if name_index is not None:
            text = lines[name_index].text
            consumed.add(name_index)
            if BRACKET_ONLY.match(text):
                # Назва англійською стоїть окремим рядком, російська — вище.
                english = BRACKET_ONLY.match(text).group("en").strip()
                for cursor in range(name_index - 1, max(name_index - 4, -1), -1):
                    candidate = lines[cursor]
                    if is_stat_section(candidate):
                        continue
                    if is_display(candidate):
                        name = candidate.text
                        consumed.add(cursor)
                    break
            else:
                name, english = split_name(text)
                for neighbour in (name_index + 1, name_index - 1):
                    if english or not 0 <= neighbour < len(lines):
                        continue
                    extra = lines[neighbour].text.strip()
                    if BRACKET_ONLY.match(extra):
                        english = BRACKET_ONLY.match(extra).group("en").strip()
                        consumed.add(neighbour)
        if not english:
            english = MONSTER_EN.get(name)
        body = [line for index, line in enumerate(lines[position:end], start=position) if index not in consumed]
        blocks.append((name, english, lines[position].page, body))
    return blocks


def parse_stat_block(name: str, english: str | None, page: int, body: list["Line"]) -> dict:
    creature_line = next((line.text for line in body if is_italic_detail(line)), "")
    size, creature_type, subtype, alignment = split_creature_line(creature_line)

    armor_class = hit_points = xp = None
    hit_dice = speed = challenge = None
    fields: dict[str, str] = {}
    ability_lines: list[Line] = []
    tail_start = len(body)
    in_stats = False
    current_field: str | None = None

    for position, line in enumerate(body):
        text = line.text
        lowered = text.lower()
        if is_italic_detail(line):
            continue  # рядок типу істоти вже розібрано
        if STAT_HEAD_RE.match(text):
            in_stats = False
            current_field = None
            if lowered.startswith(("кд ", "класс доспеха")):
                match = re.search(r"(\d+)", text)
                if match and armor_class is None:
                    armor_class = int(match.group(1))
            elif lowered.startswith("хиты"):
                match = re.search(r"(\d+)\s*\(([^)]+)\)", text)
                if match:
                    hit_points = int(match.group(1))
                    hit_dice = match.group(2).replace("к", "d").strip()
            elif lowered.startswith("скорость"):
                speed = re.sub(r"^Скорость\s*:?\s*", "", text).strip()
                in_stats = True  # далі — розсип таблиці характеристик
            continue
        if lowered.startswith(("по ", "показатель опасности", "уровень опасности")):
            match = CR_RE.match(text)
            if match:
                challenge = match.group("cr")
                xp_match = XP_RE.search(match.group("rest"))
                if xp_match:
                    xp = int(re.sub(r"[ ,]", "", xp_match.group(1)))
            tail_start = position + 1
            in_stats = False
            current_field = None
            break
        key = next(
            (target for needle, target in STAT_FIELD_PREFIXES if lowered.startswith(needle)),
            None,
        )
        if key is not None:
            in_stats = False
            value = text
            for needle, _ in STAT_FIELD_PREFIXES:
                value = re.sub(rf"^{needle}\s*:?\s*", "", value, count=1, flags=re.IGNORECASE)
            fields[key] = (fields[key] + " " + value).strip() if key in fields else value.strip()
            current_field = key
            continue
        if in_stats:
            ability_lines.append(line)
            continue
        if current_field is not None and not is_display(line):
            fields[current_field] = (fields[current_field] + " " + text).strip()
            continue
        if tail_start == len(body):
            tail_start = position
            break

    abilities, saving_throws = parse_abilities(ability_lines)
    fields = {key: " ".join(value.split()) for key, value in fields.items()}

    parts_tail: list[str] = []
    paragraph: list[Line] = []
    for line in body[tail_start:]:
        if is_stat_section(line):
            if paragraph:
                parts_tail.append(join_lines(paragraph))
                paragraph = []
            parts_tail.append(line.text)
            continue
        if is_display(line):
            continue  # назва сусіднього блоку, що потрапила в проміжок
        if line.bold_lead and paragraph:
            parts_tail.append(join_lines(paragraph))
            paragraph = [line]
            continue
        if paragraph and line.size != paragraph[-1].size:
            parts_tail.append(join_lines(paragraph))
            paragraph = [line]
            continue
        paragraph.append(line)
    if paragraph:
        parts_tail.append(join_lines(paragraph))

    parts: list[str] = []
    if creature_line:
        parts.append(creature_line)
    for line in body:
        if STAT_HEAD_RE.match(line.text):
            parts.append(line.text)
    if abilities["str"] is not None:
        parts.append(
            " · ".join(
                f"{label} {ability} ({ability_modifier(ability):+d})"
                for key, label in ABILITY_LABELS.values()
                if (ability := abilities[key]) is not None
            )
        )
    if saving_throws:
        parts.append(f"Спасброски {saving_throws}")
    for key in (
        "skills",
        "damage_vulnerabilities",
        "damage_resistances",
        "damage_immunities",
        "condition_immunities",
        "senses",
        "languages",
    ):
        if key in fields:
            parts.append(f"{FIELD_LABELS[key]} {fields[key]}")
    for line in body:
        if line.text.lower().startswith(("по ", "показатель опасности", "уровень опасности")):
            parts.append(line.text)
            break
    parts.extend(parts_tail)

    return {
        "name": name,
        "english": english,
        "page": page,
        "text": "\n\n".join(part for part in parts if part.strip()),
        "data": {
            "size": size,
            "creature_type": creature_type,
            "subtype": subtype,
            "alignment": alignment,
            "armor_class": armor_class,
            "hit_points": hit_points,
            "hit_dice": hit_dice,
            "speed": speed,
            "abilities": abilities,
            "challenge_rating": challenge,
            "xp": xp,
            "saving_throws": saving_throws,
            "skills": fields.get("skills"),
            "damage_vulnerabilities": fields.get("damage_vulnerabilities"),
            "damage_resistances": fields.get("damage_resistances"),
            "damage_immunities": fields.get("damage_immunities"),
            "condition_immunities": fields.get("condition_immunities"),
            "senses": fields.get("senses"),
            "languages": fields.get("languages"),
        },
    }


def join_lines(lines: list["Line"]) -> str:
    text = lines[0].text
    for line in lines[1:]:
        text = join_pair(text, line.text)
    return re.sub(r"\s+", " ", text).strip()


def lines_to_paragraphs(lines: list["Line"]) -> list[str]:
    """Рядки → абзаци: новий абзац на жирному початку або зміні кегля."""
    parts: list[str] = []
    paragraph: list["Line"] = []
    for line in lines:
        if paragraph and line.bold_lead:
            parts.append(join_lines(paragraph))
            paragraph = [line]
            continue
        if paragraph and line.size != paragraph[-1].size:
            parts.append(join_lines(paragraph))
            paragraph = [line]
            continue
        paragraph.append(line)
    if paragraph:
        parts.append(join_lines(paragraph))
    return parts


# --- сутності з розділу «Створення персонажа» ------------------------------

SPECIES = [
    {
        "ru": "Кендеры",
        "en": "Kender",
        "data": {"size": "small", "speed": 30, "subrace_of": None},
    }
]

BACKGROUNDS = [
    {"ru": "Соламнийский рыцарь", "en": "Knight of Solamnia"},
    {"ru": "Маги Высшего Волшебства", "en": "Mage of High Sorcery"},
]

FEATS = [
    ("Оруженосец Соламнии", "Squire of Solamnia"),
    ("Рыцарь Короны", "Knight of the Crown"),
    ("Рыцарь Меча", "Knight of the Sword"),
    ("Рыцарь Розы", "Knight of the Rose"),
    ("Адепт Черных ряс", "Adept of the Black Robes"),
    ("Адепт Красных Ряс", "Adept of the Red Robes"),
    ("Адепт Белых Ряс", "Adept of the White Robes"),
    ("Избранный Богом", "Divinely Favored"),
    ("Посвящённый в Высшее Волшебство", "Initiate of High Sorcery"),
]

SUBCLASS = {
    "ru": "Лунное чародейство",
    "en": "Lunar Sorcery",
    "data": {"class": "sorcerer", "level": 1},
}

RULES = [
    ("Вариант вида", "Species Variant", ("Кендеры",), False),
    ("Бонусные черты", "Bonus Feats", ("Соламнийский рыцарь",), False),
    ("Рыцари Соламнии", "Knights of Solamnia", ("Маги Высшего Волшебства",), False),
    ("Маги Высшего Волшебства", "Mages of High Sorcery", ("Происхождения",), False),
    ("Оружие Армии Драконов", "Dragon Army Weapons", (), True),
]

ITEM_NAMES = [
    ("Фаргаб", "Fargab"),
    ("Хупак", "Hoopak"),
    ("Безудар", "Narycrash"),
    ("Пародрак", "Boilerdrak"),
    ("Гномомет", "Gnomeflinger"),
    ("Драконье копьё", "Dragonlance"),
    ("Шлем летающей цитадели", "Flying Citadel Helm"),
    ("Кагонестиский лесной саван", "Kagonesti Forest Shroud"),
    ("Зеркало отраженного прошлого", "Mirror of Reflected Pasts"),
]

EQUIPMENT_FIELDS = {
    "цена": "cost",
    "урон": "damage",
    "вес (в фунтах)": "weight",
    "вес": "weight",
    "свойства": "properties",
}


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def heading_key(text: str) -> str:
    """Назва для пошуку: без лапок, зірочок і зайвих пробілів."""
    text = text.strip().strip("«»\"'“”„*").strip()
    return re.sub(r"\s+", " ", text).lower()


def heading_index(nodes: list["Node"], text: str, page_min: int = 0) -> int:
    needle = heading_key(text)
    for index, node in enumerate(nodes):
        if node.kind == "heading" and node.page >= page_min and heading_key(node.text).startswith(needle):
            return index
    raise LookupError(f"немає заголовка {text!r}")


def section_nodes(
    nodes: list["Node"],
    text: str,
    *,
    stops: tuple[str, ...] = (),
    stop_bold: bool = False,
    page_min: int = 0,
) -> tuple[list["Node"], "Node"]:
    """Вузли від заголовка `text` до кінця його розділу.

    Розділ закінчується на заголовку того самого або вищого рівня, на
    явно названому заголовку (`stops`) або — для правил про зброю — на назві
    статблоку (`stop_bold`).
    """
    start = heading_index(nodes, text, page_min=page_min)
    heading = nodes[start]
    stop_set = {stop.lower() for stop in stops}
    result: list["Node"] = []
    for node in nodes[start + 1 :]:
        if node.kind == "heading":
            lowered = node.text.strip().lower()
            if lowered in stop_set:
                break
            if stop_bold and node.level == 4:
                break
            if node.level <= heading.level:
                break
        result.append(node)
    return result, heading


def entity_text(nodes: list["Node"]) -> str:
    parts = [node.text for node in nodes if node.text.strip()]
    return clean("\n\n".join(parts))


def feature_name(text: str) -> str | None:
    match = re.search(r"Черта:\s*([^\n]+)", text)
    if match:
        return match.group(1).strip().rstrip(".")
    match = re.search(r"Вы получаете черту\s+([^.\n]+)", text)
    return match.group(1).strip() if match else None


def prerequisite(text: str) -> str | None:
    match = re.search(r"^Требовани[ея]:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def take_prerequisite(nodes: list["Node"]) -> tuple[str | None, list["Node"]]:
    """Знімає блок «Требование: …» разом із перенесенням на наступний рядок.

    У книзі вимога стоїть окремим абзацом і переноситься («…черта Оруженосец
    рыцаря Со-» / «ламнии»), тому одного рядка замало: прибираємо абзац і
    продовження, доки воно починається з малої літери.
    """
    if not nodes:
        return None, nodes
    first = nodes[0]
    if first.kind not in {"para", "italic"} or not re.match(r"^\s*Требовани[ея]", first.text):
        return None, nodes
    value = first.text
    rest = list(nodes[1:])
    while rest and (
        rest[0].kind == "italic"
        or (rest[0].kind == "para" and rest[0].text[:1].islower())
        or (rest[0].kind == "para" and len(rest[0].text) < 40 and not rest[0].text.endswith("."))
    ):
        value = join_pair(value, rest[0].text)
        rest.pop(0)
    value = re.sub(r"^\s*Требовани[ея]:\s*", "", value)
    return value.strip(), rest


# --- предмети -------------------------------------------------------------

def item_type_from(text: str) -> tuple[str | None, str | None, bool]:
    """«Hукопашное оружие (длинное копьё, пика), легендарное» → тип, база, магія."""
    lowered = text.lower()
    if not lowered.strip():
        return None, None, False
    magical = bool(re.search(r"чудесн|волшебн|магическ", lowered)) and "не магическ" not in lowered
    base = None
    match = re.search(r"\(([^)]*)\)", text)
    if match:
        base = match.group(1).strip()
        lowered = lowered.replace(match.group(0).lower(), "")
    item_type = pick(ITEM_TYPES, lowered.strip())
    if item_type is None and pick(RARITIES, lowered):
        item_type = "wondrous item"
    return item_type, base, magical


def parse_item(nodes: list["Node"], ru: str, en: str) -> dict:
    body = [node for node in nodes if node.kind != "heading"]
    type_line = next((node.text for node in body if node.kind == "italic"), "")
    item_type, base_item, magical = item_type_from(type_line)
    rarity = pick(RARITIES, type_line)
    whole = " ".join(node.text for node in body)
    attunement = bool(re.search(r"настройк", whole, re.IGNORECASE))
    if base_item and re.search(r"настройк", base_item, re.IGNORECASE):
        base_item = None
    data: dict = {
        "item_type": item_type,
        "rarity": rarity,
        "magical": magical or rarity is not None,
        "attunement": attunement,
        "base_item": base_item,
        "group": None,
        "cost": None,
        "weight": None,
        "armor_class": None,
        "damage": None,
        "properties": None,
        "stealth": None,
        "strength": None,
    }
    parts: list[str] = []
    description: list["Line"] = []
    current_field: str | None = None
    for node in body:
        for line in node.lines:
            text = line.text.strip()
            lowered = text.lower()
            key = next(
                (value for needle, value in EQUIPMENT_FIELDS.items() if lowered.startswith(needle)),
                None,
            )
            if key is not None and ":" in text:
                # Рядок атрибута завжди один: «Цена: 1 зм.» Продовження опису,
                # яке приклеїлося в тому ж абзаці, лишається текстом.
                data[key] = re.sub(r"^[^:]+:\s*", "", text).strip()
                current_field = key
                continue
            match = re.match(r"^Класс доспеха:\s*(\d+)", text, re.IGNORECASE)
            if match:
                data["armor_class"] = match.group(1)
                current_field = None
                continue
            # Перенесення значення («дробящий (при дальнобойной атаке)») — це ще
            # атрибут, а не опис: воно коротке й без завершення речення.
            if current_field is not None and len(text) < 70 and not text.endswith("."):
                data[current_field] = f"{data[current_field]} {text}".strip()
                continue
            current_field = None
            description.append(line)
    parts = lines_to_paragraphs(description)
    if data["item_type"] is None:
        # Пристрої без рядка типу: у книзі вони подані як «Большой объект» або
        # без нього взагалі, але для листка це спорядження.
        data["item_type"] = "siege weapon" if re.search(r"объект", whole, re.IGNORECASE) else "gear"
    return {
        "name": ru,
        "english": en,
        "text": clean("\n\n".join(parts)),
        "data": data,
    }


# --- записи ---------------------------------------------------------------

def make_record(
    *,
    category: str,
    name_en: str,
    name_ru: str,
    slug: str,
    text: str,
    data: dict,
    page: int | None,
) -> dict:
    notes = [NOTE]
    if name_ru and name_ru.strip() and name_ru.strip() != name_en:
        notes.append(f"у книзі: {name_ru.strip()}")
    return {
        "id": f"{SOURCE}/{category}/{slug}",
        "schema": "compendium-entry/1",
        "source_id": SOURCE,
        "category": category,
        "name_en": name_en,
        "name_uk": None,
        "edition": "2014",
        "license": LICENSE,
        "url": URL,
        "page": page,
        "text_en": text,
        "text_uk": None,
        "data": data,
        "status": "raw",
        "fetched_at": FETCHED,
        "notes": notes,
    }


def build_records(nodes: list["Node"], lines: list["Line"]) -> list[dict]:
    records: list[dict] = []

    for spec in SPECIES:
        body, heading = section_nodes(nodes, spec["ru"])
        data = dict(spec["data"])
        data.setdefault("ability_increases", {})
        records.append(
            make_record(
                category="species",
                name_en=spec["en"],
                name_ru=spec["ru"],
                slug=slugify(spec["en"]),
                text=entity_text(body),
                data=data,
                page=heading.page,
            )
        )

    for spec in BACKGROUNDS:
        body, heading = section_nodes(
            nodes,
            spec["ru"],
            stops=("Безделушки",),
            # «Маги Высшего Волшебства» — це і розділ про організацію (с. 28),
            # і передісторія (с. 30); беремо саме передісторію.
            page_min=29 if spec["en"] == "Mage of High Sorcery" else 0,
        )
        _, body = take_prerequisite(body)
        text = entity_text(body)
        records.append(
            make_record(
                category="background",
                name_en=spec["en"],
                name_ru=spec["ru"],
                slug=slugify(spec["en"]),
                text=text,
                data={"feature": feature_name(text)},
                page=heading.page,
            )
        )

    for ru, en in FEATS:
        body, heading = section_nodes(nodes, ru)
        requirement, body = take_prerequisite(body)
        records.append(
            make_record(
                category="feat",
                name_en=en,
                name_ru=ru,
                slug=slugify(en),
                text=entity_text(body),
                data={"prerequisite": requirement},
                page=heading.page,
            )
        )

    body, heading = section_nodes(nodes, SUBCLASS["ru"])
    records.append(
        make_record(
            category="subclass",
            name_en=SUBCLASS["en"],
            name_ru=SUBCLASS["ru"],
            slug=slugify(SUBCLASS["en"]),
            text=entity_text(body),
            data=dict(SUBCLASS["data"]),
            page=heading.page,
        )
    )

    for ru, en, stops, stop_bold in RULES:
        body, heading = section_nodes(nodes, ru, stops=stops, stop_bold=stop_bold)
        records.append(
            make_record(
                category="rule",
                name_en=en,
                name_ru=ru,
                slug=slugify(en),
                text=entity_text(body),
                data={},
                page=heading.page,
            )
        )

    for ru, en in ITEM_NAMES:
        # Додаток А; без нижньої межі назва «Драконье копьё» знаходиться ще на
        # обкладинці, а «гномомёт» — у тексті пригоди.
        body, heading = section_nodes(nodes, ru, page_min=170)
        item = parse_item([heading, *body], ru, en)
        records.append(
            make_record(
                category="item",
                name_en=en,
                name_ru=ru,
                slug=slugify(en),
                text=item["text"],
                data=item["data"],
                page=heading.page,
            )
        )

    for name, english, page, body in stat_blocks(lines):
        monster = parse_stat_block(name, english, page, body)
        if not monster["data"]["creature_type"]:
            continue  # облогові машини з додатку А — це предмети, не істоти
        records.append(
            make_record(
                category="monster",
                name_en=monster["english"] or monster["name"],
                name_ru=monster["name"],
                slug=slugify(monster["english"] or monster["name"]),
                text=monster["text"],
                data=monster["data"],
                page=monster["page"],
            )
        )

    return records


def write_records(records: list[dict]) -> dict[str, int]:
    """Пише записи в корпуси й приводить їх до канону."""
    spec = compendium_format.load_spec()
    by_category: dict[str, list[dict]] = {}
    for record in records:
        canonical, _ = compendium_format.canonicalize(record, spec)
        by_category.setdefault(canonical["category"], []).append(canonical)

    for category, rows in by_category.items():
        directory = spec.category_dir(category, SOURCE)
        directory.mkdir(parents=True, exist_ok=True)
        compendium_format.write_jsonl(directory / f"{category}.jsonl", rows)

    _, _, problems = compendium_format.normalize_source(SOURCE, spec, write=True)
    if problems:
        for problem in problems:
            print("ПРОБЛЕМА:", problem, file=sys.stderr)
    return {category: len(rows) for category, rows in by_category.items()}


def main(argv: list[str] | None = None) -> int:
    args = set(argv or sys.argv[1:])
    doc = pymupdf.open(PDF)
    lines = read_lines(doc)
    if "--pages" in args:
        dump_pages(doc, lines)
        print(f"сторінок: {doc.page_count} → {PAGES_DIR}")
        return 0

    nodes = build_nodes(lines)
    records = build_records(nodes, lines)
    counters = write_records(records)
    total = sum(counters.values())
    print("записи:", ", ".join(f"{key}={value}" for key, value in sorted(counters.items())))
    print("разом:", total)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
