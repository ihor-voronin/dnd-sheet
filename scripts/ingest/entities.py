"""Розбиття сторінки книги на окремі сутності компендіуму.

D&D Beyond віддає книгу сторінками-розділами: одна сторінка — це десятки
заклять, рис або предметів. Для білдера персонажа така гранулярність
непридатна: потрібен один запис на закляття, а не «Spell Descriptions (A-B)».

Тут описано, як різати markdown сторінки на сутності. Поки що реалізовано
закляття — вони мають найрегулярнішу структуру:

    ### Acid Splash
    Conjuration cantrip
    Casting Time: 1 action
    Range: 60 feet
    Components: V, S
    Duration: Instantaneous
    <опис>
    <блок «At Higher Levels», якщо є>
"""

from __future__ import annotations

import re

# «2nd-level abjuration», «1st-level conjuration (ritual)», «Evocation cantrip».
LEVEL_RE = re.compile(
    r"^(?:(?P<level>\d+)(?:st|nd|rd|th)-level\s+(?P<school>\w+)(?P<ritual>\s*\(ritual\))?"
    r"|(?P<cantrip_school>\w+)\s+cantrip)$",
    re.IGNORECASE,
)

FIELD_RE = re.compile(
    r"^(?P<key>Casting Time|Range|Components|Duration|Attack/Save|Damage/Effect)"
    r"\s*:\s*(?P<value>.+)$",
    re.IGNORECASE,
)

HEADING_SPELL = "### "
HEADING_SECTION = "## "
HEADING_PAGE = "# "


def iter_blocks(markdown: str) -> list[str]:
    """Абзаци markdown (розділені порожнім рядком)."""
    return [block.strip() for block in re.split(r"\n\s*\n", markdown) if block.strip()]


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "unnamed"


def _finalize_spell(block: dict) -> dict | None:
    name = block["name"]
    body = block["blocks"]
    if not body:
        return None

    data: dict = {
        "level": None,
        "school": None,
        "ritual": False,
        "concentration": False,
        "casting_time": None,
        "range": None,
        "components": None,
        "duration": None,
        "at_higher_levels": None,
    }

    rest = list(body)
    header = LEVEL_RE.match(rest[0])
    if not header:
        # Без рядка «Nth-level school» це не закляття, а підрозділ-список
        # («Bard Spells», «Spell Descriptions») на тій самій сторінці.
        return None
    rest = rest[1:]
    if header.group("cantrip_school"):
        data["level"] = 0
        data["school"] = header.group("cantrip_school").lower()
    else:
        data["level"] = int(header.group("level"))
        data["school"] = header.group("school").lower()
    data["ritual"] = bool(header.group("ritual"))

    description: list[str] = []
    for paragraph in rest:
        field = FIELD_RE.match(paragraph)
        if field:
            key = field.group("key").lower().replace(" ", "_").replace("/", "_")
            data[key] = field.group("value").strip()
            continue
        if paragraph.lower().startswith("at higher levels"):
            data["at_higher_levels"] = paragraph
            continue
        if paragraph.startswith("###") or paragraph.startswith("##"):
            continue
        description.append(paragraph)

    if data["duration"]:
        data["concentration"] = "concentration" in str(data["duration"]).lower()

    return {
        "name": name,
        "category": "spell",
        "text": "\n\n".join([body[0], *description]).strip(),
        "data": data,
    }


def split_spells(markdown: str) -> list[dict]:
    """Закляття зі сторінки описів заклять."""
    entities: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is not None:
            entity = _finalize_spell(current)
            if entity:
                entities.append(entity)
            current = None

    for block in iter_blocks(markdown):
        if block.startswith(HEADING_SPELL):
            flush()
            current = {"name": block[len(HEADING_SPELL) :].strip(), "blocks": []}
        elif block.startswith(HEADING_SECTION) or block.startswith(HEADING_PAGE):
            flush()
        elif current is not None:
            current["blocks"].append(block)

    flush()
    return entities


# --- монстри -------------------------------------------------------------

HEADING_ENTITY_RE = re.compile(r"^(#{2,3})\s+(?P<name>.+?)\s*$")

# «Medium humanoid (aarakocra), neutral good», «Huge dragon, chaotic evil»,
# «Small fey» (без вирівнювання, як у Candlekeep Mysteries), «Medium or Small
# humanoid» (двоїстий розмір), «Small swarm of Tiny beasts, unaligned».
# Тип істоти — зі списку справжніх типів: без нього будь-який абзац, що
# починається з «Large ...», зійшов би за статблок.
CREATURE_SIZES = r"Tiny|Small|Medium|Large|Huge|Gargantuan"
CREATURE_TYPES = (
    r"aberration|beast|celestial|construct|dragon|elemental|fey|fiend|giant"
    r"|humanoid|monstrosity|ooze|plant|undead"
)
CREATURE_RE = re.compile(
    rf"^(?P<size>{CREATURE_SIZES})(?:\s+or\s+(?:{CREATURE_SIZES}))?\s+"
    rf"(?P<ctype>swarm of [A-Za-z ]+?|{CREATURE_TYPES})"
    r"(?:\s*\((?P<subtype>[^)]*)\))?"
    r"(?:,\s*(?P<alignment>.+))?$",
    re.IGNORECASE,
)
_CREATURE_TYPE_WORDS = frozenset(
    "aberration beast celestial construct dragon elemental fey fiend giant "
    "humanoid monstrosity ooze plant undead".split()
)

# Мітки статблока. У HTML між <strong> і значенням іноді немає пробілу, тому
# роздільник — будь-який, і «SkillsPerception +5» теж розпізнаємо.
STAT_LABELS = (
    "Armor Class",
    "Hit Points",
    "Speed",
    "Saving Throws",
    "Skills",
    "Damage Vulnerabilities",
    "Damage Resistances",
    "Damage Immunities",
    "Condition Immunities",
    "Senses",
    "Languages",
    "Challenge",
)
STAT_LINE_RE = re.compile(
    r"^(?P<label>" + "|".join(STAT_LABELS) + r")\s*:?\s*(?P<value>.+)$",
    re.IGNORECASE,
)
ABILITY_RE = re.compile(r"\b(?P<key>STR|DEX|CON|INT|WIS|CHA)\s+(?P<score>\d+)")
_ABILITY_LABELS = frozenset({"STR", "DEX", "CON", "INT", "WIS", "CHA"})
DICE_RE = re.compile(r"\((?P<dice>\d+d\d+(?:\s*[+-]\s*\d+)?)\)")
CR_RE = re.compile(r"^(?P<cr>\d+(?:/\d+)?)")
# «Challenge 10 (5,900 XP)», але й «Challenge 18 (20 ,000 XP)» — у згорнутих
# таблицях кома в числі відділена пробілом.
XP_RE = re.compile(r"\((?P<xp>\d[\d\s,]*?)\s*XP\)", re.IGNORECASE)

_KEY_BY_LABEL = {
    "armor class": "armor_class",
    "hit points": "hit_points",
    "speed": "speed",
    "saving throws": "saving_throws",
    "skills": "skills",
    "damage vulnerabilities": "damage_vulnerabilities",
    "damage resistances": "damage_resistances",
    "damage immunities": "damage_immunities",
    "condition immunities": "condition_immunities",
    "senses": "senses",
    "languages": "languages",
    "challenge": "challenge_rating",
}


def _monster_data(body: list[str]) -> dict:
    data: dict = {
        "size": None,
        "creature_type": None,
        "subtype": None,
        "alignment": None,
        "armor_class": None,
        "hit_points": None,
        "hit_dice": None,
        "speed": None,
        "abilities": {},
        "challenge_rating": None,
        "xp": None,
    }
    for index, block in enumerate(body):
        line = block.lstrip("> ").strip()
        if not line:
            continue

        # У HTML між <strong>Skills</strong> і значенням немає пробілу, тому
        # виходить «SkillsHistory +12». Повертаємо пробіл, інакше значення
        # починається з чужого слова.
        for label in STAT_LABELS:
            if line.startswith(label) and len(line) > len(label) and line[len(label)].isupper():
                line = f"{label} {line[len(label):]}"
                break

        # Вертикальна таблиця характеристик: у частині книг D&D Beyond віддає
        # «STR», «16 (+3)», «DEX», «12 (+1)» окремими абзацами, тому в рядку
        # «STR» немає числа — беремо його з наступного абзацу.
        if line.upper() in _ABILITY_LABELS and index + 1 < len(body):
            following = body[index + 1].lstrip("> ").strip()
            score = re.match(r"^(\d{1,2})\b", following)
            if score:
                data["abilities"][line.lower()] = int(score.group(1))
                continue

        creature = CREATURE_RE.match(line)
        if creature and data["creature_type"] is None and len(line) < 120:
            ctype = creature.group("ctype").strip().lower()
            if ctype.startswith("swarm") or ctype in _CREATURE_TYPE_WORDS:
                data["size"] = creature.group("size").lower()
                data["creature_type"] = ctype
                data["subtype"] = (creature.group("subtype") or "").strip() or None
                data["alignment"] = (creature.group("alignment") or "").strip() or None
                continue

        for match in ABILITY_RE.finditer(line):
            data["abilities"][match.group("key").lower()] = int(match.group("score"))

        stat = STAT_LINE_RE.match(line)
        if not stat or len(line) > 400:
            continue
        label = stat.group("label").lower()
        value = stat.group("value").strip()
        key = _KEY_BY_LABEL[label]

        if key == "armor_class":
            numbers = re.search(r"\d+", value)
            data["armor_class"] = int(numbers.group()) if numbers else None
        elif key == "hit_points":
            numbers = re.search(r"\d+", value)
            data["hit_points"] = int(numbers.group()) if numbers else None
            dice = DICE_RE.search(value)
            data["hit_dice"] = dice.group("dice") if dice else None
        elif key == "challenge_rating":
            rating = CR_RE.match(value)
            data["challenge_rating"] = rating.group("cr") if rating else None
            xp = XP_RE.search(value)
            data["xp"] = (
                int(re.sub(r"[\s,]", "", xp.group("xp"))) if xp else None
            )
        else:
            data[key] = value
    return data


def _is_plain_name(block: str) -> bool:
    """Абзац-назва статблока: короткий рядок без розділових знаків у кінці.

    У Basic Rules і в додатках назва монстра — не заголовок markdown, а
    звичайний абзац («Aboleth»), за яким іде рядок типу істоти. Без цієї
    перевірки вся сторінка лишалася одним записом «Monster Stat Blocks».
    """
    text = block.strip()
    if not text or "\n" in text or len(text) > 80:
        return False
    if text.startswith(("#", "-", "*", ">", "|", "`", "!")):
        return False
    if text.endswith((".", ";", ":", ",")):
        return False
    lowered = text.lower()
    if lowered.startswith("variant") or ":" in text:
        return False
    return not text[0].isdigit()


def _is_creature_line(block: str) -> bool:
    """Рядок типу істоти («Large aberration, lawful evil»), що йде за назвою."""
    text = block.lstrip("> ").strip()
    if len(text) >= 140 or "\n" in text:
        return False
    return bool(CREATURE_RE.match(text))


def split_monsters(markdown: str) -> list[dict]:
    """Монстри зі сторінки бестіарію — по одному запису на статблок.

    Сторінка «Monsters (A)» — це десятки монстрів під заголовками ## і ###.
    Але не кожен заголовок є монстром: «An Aboleth's Lair» описує лігво, а
    «Angels» — групу, чиї статблоки лежать у підзаголовках. Тому запис
    створюється лише тоді, коли в тілі є повний статблок.

    Назва статблока може бути і звичайним абзацом (Basic Rules, додатки
    PHB): тоді новий статблок починається там, де короткий рядок-назва
    стоїть безпосередньо перед рядком типу істоти.
    """
    entities: list[dict] = []
    current: dict | None = None
    blocks = iter_blocks(markdown)

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        body = current["blocks"]
        text = "\n\n".join(body)
        has_stat = "Armor Class" in text and "Hit Points" in text and "Challenge" in text
        if has_stat and body:
            entities.append(
                {
                    "name": current["name"],
                    "category": "monster",
                    "text": text,
                    "data": _monster_data(body),
                }
            )
        current = None

    for index, block in enumerate(blocks):
        heading = HEADING_ENTITY_RE.match(block)
        if heading:
            flush()
            current = {"name": heading.group("name").strip(), "blocks": []}
            continue
        following = blocks[index + 1] if index + 1 < len(blocks) else ""
        if _is_plain_name(block) and _is_creature_line(following):
            if current is not None and not current["blocks"]:
                # Назва контейнера («Monster Stat Blocks») — не назва статблока.
                current["name"] = block.strip()
            else:
                flush()
                current = {"name": block.strip(), "blocks": []}
            continue
        if current is not None:
            current["blocks"].append(block)

    flush()
    return entities


# --- предмети ------------------------------------------------------------

# «Wondrous item, very rare», «Armor (chain mail), legendary (requires
# attunement)», «Potion, common». Рідкість — обовʼязкова ознака: без неї це не
# предмет, а звичайний підрозділ.
#
# Тип беремо лише зі списку справжніх типів предметів. Раніше шаблон приймав
# будь-який текст перед комою, і «Languages Abyssal, Common» із монстрячого
# статблока ставало предметом із рідкістю «common».
ITEM_KINDS = (
    r"wondrous item|magic item|melee weapon|ranged weapon|weapon|armor|shield"
    r"|potion|ring|rod|scroll|staff|wand|tattoo|treasure"
)
ITEM_TYPE_RE = re.compile(
    r"^(?P<kind>" + ITEM_KINDS + r")\b"
    r"(?:\s*\((?P<base>[^)]*)\))?"
    r"\s*,\s*(?P<rarity>rarity varies|very rare|legendary|artifact|uncommon|common|rare|varies)\b"
    r"(?P<rest>.*)$",
    re.IGNORECASE,
)


def split_items(markdown: str) -> list[dict]:
    """Магічні предмети зі сторінки-списку (DMG «Magic Items (E-N)» тощо)."""
    entities: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        body = current["blocks"]
        if body:
            kind = ITEM_TYPE_RE.match(body[0].lstrip("> ").strip())
            if kind:
                rest = kind.group("rest") or ""
                entities.append(
                    {
                        "name": current["name"],
                        "category": "item",
                        "text": "\n\n".join(body),
                        "data": {
                            "item_type": kind.group("kind").strip().lower(),
                            "base_item": (kind.group("base") or "").strip() or None,
                            "rarity": kind.group("rarity").strip().lower(),
                            "attunement": "requires attunement" in rest.lower(),
                        },
                    }
                )
        current = None

    for block in iter_blocks(markdown):
        heading = HEADING_ENTITY_RE.match(block)
        if heading:
            flush()
            current = {"name": heading.group("name").strip(), "blocks": []}
            continue
        if current is not None:
            current["blocks"].append(block)

    flush()
    return entities


# --- звичайне спорядження (таблиці) --------------------------------------

# Таблиці спорядження впізнаються за шапкою, а не за назвою сторінки: у PHB
# це «Weapon Name | Cost | Damage | Weight | Properties», у Basic Rules те саме.
_TABLE_SEP_RE = re.compile(r"^\|[\s:\-|]+\|$")
_TABLE_SPLIT_RE = re.compile(r"\s*\|\s*")


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in _TABLE_SPLIT_RE.split(line.strip().strip("|"))]


def _tables(markdown: str):
    """Усі markdown-таблиці сторінки: (заголовок таблиці, рядки).

    Заголовок — найближчий h2/h3 над таблицею: саме він називає розділ
    («Tools», «Mounts and Vehicles»), а шапка таблиці дає лише колонки.
    """
    lines = markdown.splitlines()
    section = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        heading = ANY_HEADING_RE.match(line)
        if heading and len(heading.group(1)) <= 3:
            section = heading.group("name").strip()
            index += 1
            continue
        if line.startswith("|") and index + 1 < len(lines) and _TABLE_SEP_RE.match(lines[index + 1]):
            header = _cells(line)
            rows: list[list[str]] = []
            index += 2
            while index < len(lines) and lines[index].startswith("|"):
                rows.append(_cells(lines[index]))
                index += 1
            yield section, header, rows
            continue
        index += 1


def _equipment_kind(section: str, header: list[str]) -> str | None:
    head = [cell.lower() for cell in header]
    if not head:
        return None
    if head[0] == "armor name":
        return "armor"
    if head[0] == "weapon name":
        return "weapon"
    if head[0] != "item":
        return None
    lowered = section.lower()
    if "tools" in lowered:
        return "tool"
    if "mounts" in lowered or "vehicles" in lowered or "tack" in lowered:
        return "mount"
    if "trade goods" in lowered:
        return "trade_good"
    if "adventuring gear" in lowered:
        return "gear"
    return None


def split_equipment_tables(markdown: str) -> list[dict]:
    """Звичайне спорядження з таблиць (зброя, броня, крам, інструменти).

    Магічні предмети мають рядок рідкості, тому їх ловить split_items. У зброї,
    броні й краму такого рядка немає — тільки таблиця, і без цього кроку листок
    не знав би, що довгий меч коштує 15 gp і важить 3 lb.
    """
    entities: list[dict] = []
    for section, header, rows in _tables(markdown):
        kind = _equipment_kind(section, header)
        if kind is None:
            continue
        columns = [cell.lower() for cell in header]
        group = None
        for row in rows:
            if len(row) != len(columns):
                continue
            name = row[0].strip()
            if not name or name.startswith("*"):
                continue
            values = [cell.strip() for cell in row[1:]]
            if all(value in ("", "-") for value in values):
                # Рядок-підзаголовок усередині таблиці: «Simple Melee Weapons».
                group = name
                continue
            data: dict = {
                "item_type": kind,
                "magical": False,
                "rarity": None,
                "cost": None,
                "weight": None,
                "group": group,
            }
            for column, value in zip(columns[1:], values):
                if column in ("cost", "weight", "damage", "properties", "armor class (ac)", "strength", "stealth"):
                    key = column.replace(" (ac)", "")
                    if value and value != "-":
                        data[key] = value
            entities.append(
                {
                    "name": name,
                    "category": "item",
                    "text": " · ".join(
                        part
                        for part in (
                            group,
                            name,
                            data.get("cost"),
                            data.get("weight"),
                            data.get("damage"),
                            data.get("properties"),
                        )
                        if part
                    ),
                    "data": data,
                }
            )
    return entities


# --- дерево заголовків ---------------------------------------------------

ANY_HEADING_RE = re.compile(r"^(#{1,6})\s+(?P<name>.+?)\s*$")

# Сторінки, де сутності живуть усередині великого розділу разом із правилами.
# Їх не можна заміняти сутностями: текст правил теж потрібен, тому сторінковий
# запис лишається, а сутності додаються поруч.
PARTIAL_PREFIXES = (
    "races",
    "character-races",
    "personality-and-background",
    "customization-options",
)

BACKGROUND_NON_ENTRIES = {
    "proficiencies",
    "additional languages",
    "equipment",
    "suggested characteristics",
    "customizing a background",
}


def page_is_partial(page_prefix: str) -> bool:
    return page_prefix.startswith(PARTIAL_PREFIXES)


def _tree(markdown: str) -> list[dict]:
    """Ієрархія заголовків сторінки разом із тілом кожного."""
    root: list[dict] = []
    stack: list[dict] = []
    for block in iter_blocks(markdown):
        heading = ANY_HEADING_RE.match(block)
        if heading:
            node = {
                "level": len(heading.group(1)),
                "title": heading.group("name").strip(),
                "blocks": [],
                "children": [],
            }
            while stack and stack[-1]["level"] >= node["level"]:
                stack.pop()
            (stack[-1]["children"] if stack else root).append(node)
            stack.append(node)
        elif stack:
            stack[-1]["blocks"].append(block)
    return root


def _render_node(node: dict) -> str:
    parts: list[str] = list(node["blocks"])
    for child in node["children"]:
        parts.append("#" * child["level"] + " " + child["title"])
        parts.append(_render_node(child))
    return "\n\n".join(part for part in parts if part)


def _walk(nodes: list[dict]):
    for node in nodes:
        yield node
        yield from _walk(node["children"])


def _find(nodes: list[dict], title: str, level: int | None = None) -> dict | None:
    for node in _walk(nodes):
        if node["title"].lower() == title.lower():
            if level is None or node["level"] == level:
                return node
    return None


def _species_entity(name: str, text: str, subrace_of: str | None = None) -> dict:
    body = text
    size = (
        re.search(r"size is (Tiny|Small|Medium|Large)", body, re.IGNORECASE)
        or re.search(r"^Size[:.]?\s*\**\s*(Tiny|Small|Medium|Large)", body, re.MULTILINE | re.IGNORECASE)
        or re.search(r"\b(Tiny|Small|Medium|Large)\b", body)
    )
    speed = (
        re.search(r"(?:walking )?speed is (\d+) feet", body, re.IGNORECASE)
        or re.search(r"^Speed[:.]?\s*\**\s*(\d+)", body, re.MULTILINE | re.IGNORECASE)
    )
    # «Your Dexterity score increases by 2 and your Constitution score
    # increases by 1» — другий бонус іде без «Your», тому шукаємо саму пару
    # «<Характеристика> score increases by <N>».
    increases = {
        match.group(1).lower(): int(match.group(2))
        for match in re.finditer(r"([A-Z][a-z]+) score increases? by (\d+)", body)
    }
    return {
        "name": name,
        "category": "species",
        "text": body,
        "data": {
            "size": size.group(1).lower() if size else None,
            "speed": int(speed.group(1)) if speed else None,
            "ability_increases": increases,
            "subrace_of": subrace_of,
        },
    }


# «Dwarf Traits», «Tortle Traits», «Grung Traits», «Aasimar Traits».
TRAITS_RE = re.compile(r"^(?P<name>.+?)\s+Traits$", re.IGNORECASE)
SPECIES_NON_ENTRIES = {"class", "racial", "subrace", "subspecies", "creature", "monster"}

# Заголовки, схожі на вид, але ним не є: «Aasimar Subraces Traits» (розділ
# підрас), «Bugbear Racial Traits» (варіант раси), «Lazav’s Traits» (присвійний
# заголовок статблока НПС). Драконячі мітки Eberron — не вид, а заміна підраси.
SPECIES_NAME_STOP = re.compile(r"(?:subraces?|racial(?:\s+traits)?|traits)\.?$|['’]s$", re.IGNORECASE)


def _looks_like_species_name(name: str) -> bool:
    lowered = name.lower()
    if lowered in SPECIES_NON_ENTRIES or lowered.startswith("mark of "):
        return False
    return not SPECIES_NAME_STOP.search(name)

# Ознака виду в тілі «<Назва> Traits». До 2020 року бонуси писали в кожному виді
# («Ability Score Increase»), у MotM (2022) це спільне правило на всю книгу, а в
# описі виду лишився «Creature Type».
ABILITY_MARKERS = ("ability score increase", "creature type")


def _has_ability_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in ABILITY_MARKERS)


def _is_real_species(entity: dict) -> bool:
    """Справжній вид має бодай щось вимірюване: розмір, швидкість або бонуси.

    «Conflicted Souls» у VGtM — це врізка про злих аасімарів, а не вид: у ній
    немає ні розміру, ні швидкості, ні бонусів характеристик.
    """
    data = entity["data"]
    return bool(data["size"] or data["speed"] or data["ability_increases"])


def split_species(markdown: str) -> list[dict]:
    """Види та підраси зі сторінки.

    Ознака виду — підрозділ «<Назва> Traits» із абзацом «Ability Score
    Increase». Раніше вимагалось, щоб «X Traits» був рівно на рівень нижче від
    заголовка X — через це Tortle (сторінка «Tortle Race» → «Tortle Traits»),
    Grung (єдиний заголовок «Grung Traits») і Humblewood не розпізнавались.

    Підраса (Hill Dwarf, Wood Elf) — сусідній підрозділ того ж рівня, у якому
    теж є власний «Ability Score Increase».
    """
    entities: list[dict] = []
    seen: set[str] = set()

    def walk(nodes: list[dict], parent: dict | None) -> None:
        for node in nodes:
            match = TRAITS_RE.match(node["title"].strip())
            if match:
                name = match.group("name").strip()
                text = _render_node(node)
                container = node
                if parent is not None and parent["title"].strip().lower().startswith(name.lower()):
                    # «Dwarf» → «Dwarf Traits», «Tortle Race» → «Tortle Traits».
                    container = parent
                if (
                    _looks_like_species_name(name)
                    and _has_ability_marker(text)
                    and name not in seen
                ):
                    seen.add(name)
                    subraces: list[tuple[dict, str]] = []
                    if container is not node:
                        for child in container["children"]:
                            if child is node or child["level"] != node["level"]:
                                continue
                            child_text = _render_node(child)
                            if "ability score increase" in child_text.lower():
                                subraces.append((child, child_text))
                    pruned = {
                        **container,
                        "children": [
                            child
                            for child in container["children"]
                            if all(child is not sub[0] for sub in subraces)
                        ],
                    }
                    base = _species_entity(name, _render_node(pruned))
                    if _is_real_species(base):
                        entities.append(base)
                    for child, child_text in subraces:
                        if child["title"] in seen:
                            continue
                        if not _looks_like_species_name(child["title"]):
                            continue
                        seen.add(child["title"])
                        sub = _species_entity(child["title"], child_text, subrace_of=name)
                        if _is_real_species(sub):
                            entities.append(sub)
            walk(node["children"], node)

    walk(_tree(markdown), None)
    return entities


FEATS_SECTION_RE = re.compile(
    r"^(?:new\s+)?(?:feats?|(?:racial\s+)?feat descriptions?)$", re.IGNORECASE
)


def split_feats(markdown: str) -> list[dict]:
    """Риси зі сторінки.

    Розділ рис названо по-різному: PHB — «Feats» усередині розділу, TCoE —
    сторінка цілком, XGtE — «Racial Feat Descriptions». Тому шукаємо розділ за
    назвою, а риси беремо на рівень нижче від нього.
    """
    tree = _tree(markdown)
    entities: list[dict] = []
    seen: set[str] = set()
    for node in _walk(tree):
        if not FEATS_SECTION_RE.match(node["title"].strip()):
            continue
        for child in node["children"]:
            if child["level"] != node["level"] + 1:
                continue
            if child["title"] in seen:
                continue
            seen.add(child["title"])
            text = _render_node(child)
            prerequisite = re.search(r"^Prerequisite:\s*(.+)$", text, re.MULTILINE)
            entities.append(
                {
                    "name": child["title"],
                    "category": "feat",
                    "text": text,
                    "data": {
                        "prerequisite": (
                            prerequisite.group(1).strip() if prerequisite else None
                        )
                    },
                }
            )
    return entities


BACKGROUND_MARK_RE = re.compile(r"^\**\s*Skill Proficiencies\s*\**\s*:", re.IGNORECASE)
BACKGROUND_FEATURE_RE = re.compile(r"^\**\s*Feature\s*:", re.IGNORECASE)


def _background_feature(node: dict, text: str) -> str | None:
    for child in node["children"]:
        if BACKGROUND_FEATURE_RE.match(child["title"]):
            return child["title"].split(":", 1)[1].strip()
    match = re.search(r"^\**\s*Feature\s*:\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip().rstrip("*").strip() if match else None


def split_backgrounds(markdown: str) -> list[dict]:
    """Передісторії зі сторінки — за ознакою «Skill Proficiencies:», не за назвою розділу.

    Кожна офіційна передісторія має рядок «Skill Proficiencies:». Раніше пошук
    ішов від розділу «Backgrounds», тому SCAG (12 передісторій прямо на
    сторінці), GGtR (10 передісторій по сторінках гільдій), EGtW, SCC і решта
    сетингів не давали нічого.
    """
    entities: list[dict] = []

    def walk(nodes: list[dict]) -> None:
        for node in nodes:
            if (
                node["level"] >= 2
                and node["title"].lower() not in BACKGROUND_NON_ENTRIES
                and any(BACKGROUND_MARK_RE.match(block) for block in node["blocks"])
            ):
                text = _render_node(node)
                entities.append(
                    {
                        "name": node["title"],
                        "category": "background",
                        "text": text,
                        "data": {"feature": _background_feature(node, text)},
                    }
                )
            walk(node["children"])

    walk(_tree(markdown))
    return entities


# Порядок важливий лише для дедуплікації: якщо два розпізнавачі дали сутність з
# однаковою назвою в одній категорії, лишається перша.
DETECTORS = (
    split_monsters,
    split_spells,
    split_items,
    split_equipment_tables,
    split_backgrounds,
    split_species,
    split_feats,
)


def split_page(page_prefix: str, markdown: str, scope: str | None = None) -> list[dict]:
    """Сутності зі сторінки.

    Кожен розпізнавач шукає свою ознаку в тексті, а не в назві сторінки:
    статблок (AC + HP + Challenge), рядок «Nth-level school», рядок рідкості
    предмета, таблицю спорядження, «Skill Proficiencies:», «X Traits» з бонусом
    характеристики, розділ «Feats».

    Раніше розпізнавач вибирався за префіксом шляху сторінки, і все, що лежало
    не під очікуваним префіксом (предмети FToD/EGtW/GGtR, передісторії SCAG,
    види з TTP/OGA/Humblewood), просто не потрапляло в базу.

    scope — поле з sources.yml. Книги зі scope=monsters (Monster Manual,
    Monstrous Compendium, Mordenkainen's Tome) цілком складаються зі статблоків,
    тому для них працює лише розпізнавач монстрів.
    """
    if scope == "monsters":
        return split_monsters(markdown)
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for detector in DETECTORS:
        for entity in detector(markdown):
            key = (entity["category"], entity["name"])
            if key in seen:
                continue
            seen.add(key)
            found.append(entity)
    return found
