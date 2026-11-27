"""Дзеркало 5e.tools → записи компендіуму (формат contract/compendium-format.json).

Дзеркало віддає не HTML, а дерево `entries`: рядки з inline-тегами (`{@atk mw}`,
`{@damage 1d6}`) і вузли-контейнери (таблиці, списки, вставки). Тому це не
парсер розмітки, а рендерер: він збирає з дерева той самий текст, який
DDB-конвеєр діставав зі сторінок, і розкладає структурні поля у `data`.

Джерела даних (усе — `content/raw`):

  <тека>/bestiary-*.json        статблоки книги
  _index/races-5etools.json     види й підраси всіх книг
  _index/backgrounds-5etools.json
  _index/feats-5etools.json
  _index/mirror-items.json      магічні предмети
  _index/mirror-items-base.json звичайне спорядження
  _index/mirror-spells/*.json   закляття
  _index/mirror-class/*.json    класи, підкласи й уміння підкласів
  _index/books-5etools.json     каталог книг (назва, дата, тека)
  _index/adventures-5etools.json

Запуск (розбирає всі теки, які ще не мають записів у корпусі):

    python -m scripts.ingest.mirror5e --all
    python -m scripts.ingest.mirror5e --folder ps-amonkhet --print
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys

from ..normalize import canonical as compendium_format
from . import config
from .entities import slugify

# --- константи ------------------------------------------------------------

ABILITIES = ("str", "dex", "con", "int", "wis", "cha")
ABILITY_TITLES = {
    "str": "Strength",
    "dex": "Dexterity",
    "con": "Constitution",
    "int": "Intelligence",
    "wis": "Wisdom",
    "cha": "Charisma",
}
ABILITY_SHORT = {key: key.upper() for key in ABILITIES}
LONG_ABILITIES = {
    "str": "strength",
    "dex": "dexterity",
    "con": "constitution",
    "int": "intelligence",
    "wis": "wisdom",
    "cha": "charisma",
}

SIZE_NAMES = {
    "T": "Tiny",
    "S": "Small",
    "M": "Medium",
    "L": "Large",
    "H": "Huge",
    "G": "Gargantuan",
}
SIZE_ORDER = ("T", "S", "M", "L", "H", "G")

ALIGNMENT_NAMES = {
    "L": "lawful",
    "N": "neutral",
    "C": "chaotic",
    "G": "good",
    "E": "evil",
    "U": "unaligned",
    "A": "any",
    "NX": "neutral",
}

SCHOOL_NAMES = {
    "A": "abjuration",
    "C": "conjuration",
    "D": "divination",
    "E": "enchantment",
    "V": "evocation",
    "I": "illusion",
    "N": "necromancy",
    "T": "transmutation",
    "P": "psionic",
}

# Досвід за рівень небезпеки (DMG, таблиця «Experience Points»).
CR_XP = {
    "0": 10,
    "1/8": 25,
    "1/4": 50,
    "1/2": 100,
    "1": 200,
    "2": 450,
    "3": 700,
    "4": 1100,
    "5": 1800,
    "6": 2300,
    "7": 2900,
    "8": 3900,
    "9": 5000,
    "10": 5900,
    "11": 7200,
    "12": 8400,
    "13": 10000,
    "14": 11500,
    "15": 13000,
    "16": 15000,
    "17": 18000,
    "18": 20000,
    "19": 22000,
    "20": 25000,
    "21": 33000,
    "22": 41000,
    "23": 50000,
    "24": 62000,
    "25": 75000,
    "26": 90000,
    "27": 105000,
    "28": 120000,
    "29": 135000,
    "30": 155000,
}

# Тип предмета: код дзеркала → слово, яким його називає книга.
ITEM_TYPES = {
    "M": "weapon",
    "R": "weapon",
    "A": "ammunition",
    "LA": "armor",
    "MA": "armor",
    "HA": "armor",
    "S": "shield",
    "P": "potion",
    "RG": "ring",
    "RD": "rod",
    "SC": "scroll",
    "ST": "staff",
    "WD": "wand",
    "W": "wondrous item",
    "SCF": "spellcasting focus",
    "T": "tool",
    "AT": "tool",
    "GS": "gaming set",
    "INS": "instrument",
    "G": "gear",
    "OTH": "gear",
    "FD": "food and drink",
    "EXP": "explosive",
    "MNT": "mount",
    "VEH": "vehicle",
    "SHP": "ship",
    "AIR": "ship",
    "SWAW": "ship",
    "GV": "generic variant",
    "TB": "treasure",
    "$A": "art object",
    "$C": "art object",
    "$G": "art object",
    "$M": "art object",
}

WEAPON_PROPERTIES = {
    "2H": "two-handed",
    "F": "finesse",
    "H": "heavy",
    "L": "light",
    "R": "reach",
    "S": "special",
    "T": "thrown",
    "V": "versatile",
    "A": "ammunition",
    "AF": "ammunition",
    "BF": "burst fire",
    "RLD": "reload",
}

ATK_LABELS = {
    "mw": "Melee Weapon Attack",
    "rw": "Ranged Weapon Attack",
    "ms": "Melee Spell Attack",
    "rs": "Ranged Spell Attack",
    "m": "Melee Attack",
    "r": "Ranged Attack",
}

# Теги, у яких третя частина — те, як назву показати в тексті:
# {@item artisan's tools|PHB|інструменти ремісника}.
DISPLAY_THIRD = {
    "action",
    "background",
    "boon",
    "charoption",
    "class",
    "condition",
    "creature",
    "cult",
    "deity",
    "disease",
    "feat",
    "hazard",
    "item",
    "language",
    "object",
    "optfeature",
    "psionic",
    "race",
    "recipe",
    "reward",
    "sense",
    "skill",
    "spell",
    "status",
    "table",
    "trap",
    "vehicle",
    "variantrule",
    "weapon",
}

# Теки, які не є книгою дзеркала (OCR купленого PDF).
NOT_MIRROR = {"gotg-pdf"}


# --- inline-теги ----------------------------------------------------------

TAG_RE = re.compile(r"\{@(\w+)(?: ([^{}]*))?\}")
# Другий синтаксис дзеркала: {#itemEntry Grenade|DMG} — показом є перше поле.
REF_TAG_RE = re.compile(r"\{#(\w+)(?: ([^{}]*))?\}")


def _tag(name: str, body: str | None) -> str:
    """Один тег `{@ім'я тіло}` → текст. Незнайомі теги лишають першу частину."""
    body = (body or "").strip()
    parts = body.split("|")
    if name == "atk":
        labels = [ATK_LABELS.get(code.strip(), code.strip()) for code in body.split(",")]
        return " or ".join(labels) + ":"
    if name == "hit":
        value = body or "0"
        return value if value.startswith(("+", "-")) else f"+{value}"
    if name == "h":
        return "Hit: "
    if name == "dc":
        return f"DC {body}"
    if name == "recharge":
        return f"(Recharge {body})"
    if name == "chance":
        # {@chance 30|30 percent|30%} — показ першого поля плюс слово.
        return f"{parts[0].strip()} percent"
    if name in ("scaledamage", "scaledice"):
        return parts[-1].strip()
    if name == "ability":
        names = [ABILITY_TITLES.get(part.strip().lower(), part.strip()) for part in body.split(",")]
        return ", ".join(name for name in names if name)
    if name == "link":
        # {@link url|текст}: показуємо текст, а не адресу.
        return parts[1].strip() if len(parts) > 1 else parts[0].strip()
    if name == "quickref":
        # {@quickref Cover||3||three-quarters cover}: показ остання частина.
        return parts[-1].strip() if len(parts) > 1 else parts[0].strip()
    if name in ("adventure", "book"):
        # {@adventure Chain Lightning|IDRotF|17|Chain Lightning} — показ четвертий,
        # {@adventure appendix C|IDRotF|21} — перший (третього поля немає).
        return parts[3].strip() if len(parts) >= 4 and parts[3].strip() else parts[0].strip()
    if name == "subclass":
        # {@subclass Knowledge Domain|Cleric|PHB|Knowledge domain}: четверта.
        return parts[3].strip() if len(parts) >= 4 and parts[3].strip() else parts[0].strip()
    if name in DISPLAY_THIRD and len(parts) >= 3 and parts[2].strip():
        return parts[2].strip()
    if name == "5etools":
        # {@5etools feat|feats.html} — «див. розділ на сайті»: показом є перше поле.
        return parts[0].strip()
    return parts[0].strip()


def inline(text: str) -> str:
    """Розкрити inline-теги в рядку.

    Тег може стояти всередині іншого ({@item X|CoA|… {@note …}}), тому
    одного проходу не досить: після заміни внутрішнього тега зовнішній стає
    звичайним і розкривається наступним колом.
    """
    if not text or ("{@" not in text and "{#" not in text):
        return text or ""
    for _ in range(4):
        replaced = TAG_RE.sub(lambda match: _tag(match.group(1), match.group(2)), text)
        replaced = REF_TAG_RE.sub(lambda match: (match.group(2) or "").split("|")[0].strip(), replaced)
        if replaced == text:
            break
        text = replaced
    return text


# --- рендерер дерева entries ---------------------------------------------


def _join(blocks: list[str]) -> str:
    return "\n\n".join(block for block in blocks if block and block.strip())


def _named(name: str, body: str) -> str:
    """«Назва. Тіло» — так книга подає вміння, риси й властивості."""
    head = (name or "").strip()
    body = (body or "").strip()
    if not body:
        return head
    if head.endswith((":", ".")):
        return f"{head} {body}"
    return f"{head}. {body}"


def _flat(text: str) -> str:
    """Один рядок із блоку — для комірок таблиць і пунктів списку."""
    return re.sub(r"\s+", " ", text).strip()


def _clean_name(name, source: str | None = None) -> str:
    """Назва без розрізнювача дзеркала.

    5e.tools дописує код книги в дужках, коли назва повторюється в кількох
    книгах («Knowledge Domain (PSA)»), але книга так її не називає. Дужки з
    назвою сетингу («Minotaur (Amonkhet)») лишаються: це частина назви.
    """
    text = str(name or "").strip()
    if not source:
        return text
    match = re.match(r"^(.*?)\s*\(([^()]+)\)$", text)
    if match and match.group(2).strip().lower() == str(source).strip().lower():
        return match.group(1).strip()
    return text


# --- _copy: записи, що посилаються на інший запис -------------------------
#
# Дзеркало не дублює текст: «Ammit» — це `_copy` від «Giant Crocodile» (MM) із
# заміною слова, «Hippopotamus» — від «Elephant» із дописаною рисою. Без
# розкриття `_copy` від книги лишається назва й рядок типу (з 24 статблоків
# Plane Shift: Amonkhet так губились 21).


def _replace_txt(node, replace: str, with_: str, ignore_case: bool = False):
    if isinstance(node, str):
        if ignore_case:
            return re.sub(re.escape(replace), with_.replace("\\", "\\\\"), node, flags=re.IGNORECASE)
        return node.replace(replace, with_)
    if isinstance(node, list):
        return [_replace_txt(value, replace, with_, ignore_case) for value in node]
    if isinstance(node, dict):
        return {key: _replace_txt(value, replace, with_, ignore_case) for key, value in node.items()}
    return node


def _replace_named(entries, name: str, replacement):
    if not isinstance(entries, list):
        return entries
    for index, entry in enumerate(entries):
        if isinstance(entry, dict) and entry.get("name") == name:
            entries[index] = replacement
            return entries
        if isinstance(entry, str) and entry == name:
            entries[index] = replacement
            return entries
    entries.append(replacement)
    return entries


def _apply_mods(target: dict, mods: dict) -> dict:
    for key, operations in mods.items():
        if isinstance(operations, dict):
            operations = [operations]
        if not isinstance(operations, list):
            continue
        for operation in operations:
            if not isinstance(operation, dict):
                continue
            mode = operation.get("mode")
            items = operation.get("items")
            if key == "*":
                if mode == "replaceTxt" and isinstance(operation.get("replace"), str):
                    target = _replace_txt(
                        target,
                        operation["replace"],
                        operation.get("with") or "",
                        "i" in str(operation.get("flags") or ""),
                    )
                elif mode == "setProp" and operation.get("prop"):
                    target[operation["prop"]] = items
                continue
            existing = target.get(key)
            if mode == "appendArr":
                addition = items if isinstance(items, list) else [items]
                target[key] = (existing if isinstance(existing, list) else []) + [
                    entry for entry in addition if entry is not None
                ]
            elif mode == "prependArr":
                addition = items if isinstance(items, list) else [items]
                target[key] = [entry for entry in addition if entry is not None] + (
                    existing if isinstance(existing, list) else []
                )
            elif mode == "replaceArr":
                replacement = items[0] if isinstance(items, list) and items else items
                if isinstance(existing, list):
                    target[key] = _replace_named(list(existing), operation.get("replace"), replacement)
                elif isinstance(existing, str) and isinstance(replacement, str):
                    target[key] = existing.replace(str(operation.get("replace")), replacement)
                elif existing is None:
                    target[key] = items
            elif mode == "removeArr":
                names = operation.get("names") or []
                if isinstance(existing, list):
                    target[key] = [
                        entry for entry in existing if not (isinstance(entry, dict) and entry.get("name") in names)
                    ]
            elif mode == "insertArr":
                if isinstance(existing, list):
                    index = operation.get("index", 0)
                    addition = items if isinstance(items, list) else [items]
                    target[key] = existing[:index] + addition + existing[index:]
            elif mode == "setProp" and operation.get("prop"):
                target[operation["prop"]] = items
    return target


def resolve_copy(row: dict, index: dict[tuple[str, str], dict], depth: int = 0) -> dict:
    """Розкрити `_copy` (ланцюжком) у повний запис дзеркала."""
    if not isinstance(row, dict) or depth > 8:
        return row
    copy = row.get("_copy")
    if not isinstance(copy, dict):
        return row
    # Регістр у назвах дзеркала нестабільний: «Kuo-Toa» в MM, а посилаються
    # на «kuo-toa». Тому покажчик — з назвою в casefold.
    parent = index.get((str(copy.get("name")).casefold(), copy.get("source")))
    if parent is None:
        return row
    merged = {key: value for key, value in resolve_copy(parent, index, depth + 1).items() if key != "_copy"}
    merged.update({key: value for key, value in row.items() if key != "_copy"})
    mods = copy.get("_mod")
    if isinstance(mods, dict):
        merged = _apply_mods(merged, mods)
    merged.pop("_copy", None)
    return merged


def _index_rows(rows) -> dict[tuple[str, str], dict]:
    index: dict[tuple[str, str], dict] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("name"):
            index.setdefault((str(row["name"]).casefold(), row.get("source")), row)
    return index


_MONSTER_INDEX: dict[tuple[str, str], dict] | None = None


def monster_index() -> dict[tuple[str, str], dict]:
    """Усі статблоки дзеркала, які лежать на диску — база для `_copy`.

    Книги, чиї монстри лише посилаються на Monster Manual, лежать у
    content/raw/<тека>/bestiary-*.json, а самі MM/VGM/MTF/MPMM/VRGR/SKT/LLK —
    окремими файлами в content/raw/_index/bestiary/ (їх тягне
    fetch_5etools.py; без них 594 посилання лишились би без тексту).
    """
    global _MONSTER_INDEX
    if _MONSTER_INDEX is not None:
        return _MONSTER_INDEX
    index: dict[tuple[str, str], dict] = {}
    paths = list(config.RAW_DIR.glob("*/bestiary-*.json"))
    base = config.INDEX_DIR / "bestiary"
    if base.is_dir():
        paths += list(base.glob("*.json"))
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        for monster in payload.get("monster") or []:
            if isinstance(monster, dict) and monster.get("name"):
                index.setdefault((str(monster["name"]).casefold(), monster.get("source")), monster)
    _MONSTER_INDEX = index
    return index


def _entity_rows(name: str, *keys: str) -> list[dict]:
    """Розкриті (без `_copy`) рядки з довідкового корпусу дзеркала."""
    rows: list[dict] = []
    for key in keys:
        rows.extend(row for row in _load_index(name, key) if isinstance(row, dict))
    index = _index_rows(rows)
    return [resolve_copy(row, index) for row in rows]


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return inline(value)
    if isinstance(value, dict):
        roll = value.get("roll")
        if isinstance(roll, dict):
            if "exact" in roll:
                return str(roll["exact"])
            if "min" in roll and "max" in roll:
                return f"{roll['min']}–{roll['max']}"
        if "entry" in value:
            return _flat(render(value["entry"]))
        if value.get("type") == "cell" and "entry" in value:
            return _flat(render(value["entry"]))
        return _flat(render(value))
    if isinstance(value, list):
        return _flat(_join([render(item) for item in value]))
    return str(value)


def _table(node: dict) -> str:
    labels = node.get("colLabels") or []
    rows = node.get("rows") or []
    body: list[list[str]] = []
    for row in rows:
        if isinstance(row, dict):
            row = row.get("row") or []
        if not isinstance(row, list):
            continue
        body.append([_cell(cell) for cell in row])
    if not body:
        return ""
    width = max([len(labels)] + [len(row) for row in body])
    if width == 0:
        return ""
    head = [inline(str(label)) for label in labels] + [""] * (width - len(labels))
    lines = [
        "| " + " | ".join(head) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    for row in body:
        padded = row + [""] * (width - len(row))
        lines.append("| " + " | ".join(cell.replace("|", "/") for cell in padded) + " |")
    return "\n".join(lines)


def _list(node: dict) -> str:
    """Список: пункти-рядки, списки-«назва: значення» і блоки з таблицями.

    Пункт може містити не лише речення, а й таблицю (Sword of Zariel: чотири
    таблиці рис усередині одного пункту). Такі пункти не можна стискати в один
    рядок — вони стають окремим блоком.
    """
    style = node.get("style") or ""
    pieces: list[tuple[str, str]] = []
    for item in node.get("items") or []:
        if isinstance(item, str):
            text = inline(item).strip()
            if text:
                pieces.append(("bullet", "- " + text))
            continue
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        inner = render(item.get("entry")) or render(item.get("entries")) or render(item.get("items"))
        head = inline(name).strip() if name else ""
        multiline = "\n" in inner.strip()
        if head and style.startswith("list-hang"):
            if multiline:
                pieces.append(("block", _named(head, inner)))
            else:
                pieces.append(("hang", _named(head, _flat(inner))))
        elif head:
            if multiline:
                pieces.append(("block", _named(head, inner)))
            else:
                pieces.append(("bullet", f"- {head}: {_flat(inner)}"))
        else:
            text = inner if multiline else _flat(inner)
            if text.strip():
                pieces.append(("block" if multiline else "bullet", text if multiline else "- " + text))

    out: list[str] = []
    previous = ""
    for kind, text in pieces:
        if out:
            out.append("\n" if kind == previous == "hang" else "\n\n")
        out.append(text)
        previous = kind
    return "".join(out)


def _spellcasting(node: dict) -> str:
    """Блок «Spellcasting» у статблоці."""
    chunks: list[str] = []
    for entry in node.get("headerEntries") or []:
        chunks.append(render(entry))
    for key, label in (
        ("constant", "Constant"),
        ("will", "At will"),
        ("rest", "Rest"),
        ("recharge", "Recharge"),
    ):
        values = node.get(key)
        if values:
            chunks.append(f"{label}: " + ", ".join(inline(str(v)) for v in values))
    daily = node.get("daily") or {}
    for key in sorted(daily, key=lambda item: str(item).lstrip("0")):
        values = daily[key]
        if not isinstance(values, list):
            continue
        # «1e» — раз на день кожне, «1» — раз на день, «2r» — після відпочинку.
        marker = str(key)
        count = marker.rstrip("er")
        if marker.endswith("e"):
            label = f"{count}/day each"
        elif marker.endswith("r"):
            label = f"{count}/rest"
        else:
            label = f"{count}/day"
        chunks.append(label + ": " + ", ".join(inline(str(v)) for v in values))
    spells = node.get("spells") or {}
    for level in sorted(spells, key=lambda item: int(item) if str(item).isdigit() else 99):
        block = spells[level]
        if not isinstance(block, dict):
            continue
        values = block.get("spells") or []
        slots = block.get("slots")
        if not values:
            continue
        if str(level) == "0":
            label = "At will"
        else:
            label = f"{level}st level" if level == "1" else f"{level}th level"
            if slots:
                label += f" ({slots} slots)"
        chunks.append(f"{label}: " + ", ".join(inline(str(v)) for v in values))
    for entry in node.get("footerEntries") or []:
        chunks.append(render(entry))
    return _named(node.get("name") or "Spellcasting", _join(chunks))


def _ability_block(node: dict, kind: str) -> str:
    attributes = [ABILITY_TITLES.get(str(a), str(a)) for a in node.get("attributes") or []]
    if not attributes:
        return ""
    joined = " or ".join(attributes)
    if kind == "abilityDc":
        return f"Spell save DC = 8 + your proficiency bonus + your {joined} modifier"
    return f"Spell attack modifier = your proficiency bonus + your {joined} modifier"


def _flatten_ref(node: dict) -> str:
    """`{@refX ...}`-вузол: показуємо назву, на яку він посилається."""
    for key, value in node.items():
        if key.startswith("ref") and isinstance(value, str):
            return inline(value.split("|")[0])
    return ""


def render(node, *, feature_index: dict | None = None) -> str:
    """Дерево entries → текст книги."""
    return _join(_blocks(node, feature_index=feature_index))


def _blocks(node, *, feature_index: dict | None = None) -> list[str]:
    if node is None:
        return []
    if isinstance(node, str):
        text = inline(node).strip()
        return [text] if text else []
    if isinstance(node, list):
        out: list[str] = []
        for child in node:
            out.extend(_blocks(child, feature_index=feature_index))
        return out
    if not isinstance(node, dict):
        return []

    kind = node.get("type")
    name = node.get("name")

    if kind == "table":
        table = _table(node)
        if name:
            return [_named(inline(name), table)] if table else [inline(name)]
        return [table] if table else []
    if kind == "tableGroup":
        inner = _join([render(child, feature_index=feature_index) for child in node.get("tables") or []])
        return [_named(inline(name or ""), inner)] if name else _blocks(inner)
    if kind == "list":
        return [_list(node)]
    if kind == "spellcasting":
        return [_spellcasting(node)]
    if kind in ("abilityDc", "abilityAttackMod"):
        return [_ability_block(node, kind)]
    if kind in (
        "entries",
        "section",
        "part",
        "inset",
        "insetReadaloud",
        "quote",
        "optfeature",
        "variant",
        "variantSub",
        "homebrew",
    ):
        if kind == "homebrew":
            return []
        inner = _join(_blocks(node.get("entries"), feature_index=feature_index))
        if kind == "quote":
            by = node.get("by")
            if by:
                inner = f"{inner}\n\n— {inline(by)}"
        if kind.startswith("variant"):
            return [_named(f"Variant: {inline(name)}" if name else "Variant", inner)]
        if name:
            return [_named(inline(name), inner)]
        return [inner] if inner else []
    if kind in ("item", "itemSub", "itemSubGroup", "itemGroup", "case"):
        inner = _join(_blocks(node.get("entries") or node.get("entry"), feature_index=feature_index))
        if name:
            return [_named(inline(name), inner)]
        return [inner] if inner else []
    if kind in ("inline", "inlineBlock", "options", "actions"):
        return _blocks(node.get("entries"), feature_index=feature_index)
    if kind == "attack":
        inner = _join(
            [
                render(node.get("attackEntries"), feature_index=feature_index),
                render(node.get("hitEntries"), feature_index=feature_index),
            ]
        )
        return [_named(inline(name or ""), inner)] if name else _blocks(inner)
    if kind == "dice":
        dice = []
        for part in node.get("toRoll") or []:
            if not isinstance(part, dict):
                continue
            number = part.get("number") or 1
            dice.append(f"{number}d{part.get('faces')}" if part.get("faces") else str(number))
        return [" + ".join(dice)]
    if kind == "bonus":
        return [f"+{node.get('value')}" if node.get("value") else ""]
    if kind == "bonusSpeed":
        return [f"+{node.get('value')} ft."] if node.get("value") else []
    if kind in (
        "refSubclassFeature",
        "refClassFeature",
        "refOptionalfeature",
        "refFeat",
        "refBackground",
        "refRace",
        "refCreature",
        "refItem",
        "refSpell",
        "refDeity",
        "refCondition",
        "refDisease",
    ):
        reference = _flatten_ref(node)
        if kind == "refSubclassFeature" and feature_index:
            feature = feature_index.get(reference)
            if feature is not None:
                return _blocks(feature, feature_index=feature_index)
        return [reference] if reference else []
    if kind == "code":
        return [str(node.get("preformatted") or node.get("code") or "")]
    if kind == "link":
        return [_flat(inline(node.get("text") or ""))]
    if kind == "statblockInline":
        data = node.get("data") or {}
        if isinstance(data, dict) and data.get("name"):
            return [monster_text(data)]
        return []
    if kind in (
        "image",
        "gallery",
        "video",
        "hr",
        "flowchart",
        "dataCreature",
        "dataItem",
        "dataSpell",
        "dataBackground",
        "dataClass",
        "dataFeat",
        "dataOptionalfeature",
        "dataObject",
        "dataRecipe",
        "dataVehicle",
        "source",
        "spellHeader",
        "optfeatureHeader",
    ):
        return []
    # Невідомий вузол: усе, що можна показати, показуємо.
    for key in ("entries", "items", "entry"):
        if key in node:
            return _blocks(node[key], feature_index=feature_index)
    return [inline(name)] if name else []


# --- статблок -------------------------------------------------------------


def _size_names(value) -> list[str]:
    codes = value if isinstance(value, list) else [value]
    names = [SIZE_NAMES.get(str(code), str(code)) for code in codes if code]
    return names


def _type_line(obj: dict) -> str:
    size = " or ".join(_size_names(obj.get("size"))) or "Medium"
    raw_type = obj.get("type")
    tags: list[str] = []
    if isinstance(raw_type, dict):
        tags = [str(tag) for tag in raw_type.get("tags") or []]
        swarm = raw_type.get("swarmSize")
        base = str(raw_type.get("type") or "")
        if swarm:
            swarm_size = "/".join(_size_names(swarm)).lower()
            creature = f"swarm of {swarm_size} {base}s"
        else:
            creature = base
    else:
        creature = str(raw_type or "")
    alignment = obj.get("alignment") or []
    if isinstance(alignment, str):
        alignment = [alignment]
    words = [ALIGNMENT_NAMES.get(str(code), str(code).lower()) for code in alignment]
    aligned = " ".join(word for word in words if word) or "unaligned"
    head = f"{size} {creature}".strip()
    if tags:
        head += f" ({', '.join(tags)})"
    return f"{head}, {aligned}"


def _ac(obj: dict) -> tuple[str | None, int | None]:
    value = obj.get("ac")
    if isinstance(value, int):
        return str(value), value
    if isinstance(value, dict):
        if isinstance(value.get("ac"), int):
            extra = ""
            source = value.get("from") or []
            if source:
                extra = f" ({', '.join(inline(str(part)) for part in source)})"
            return f"{value['ac']}{extra}", value["ac"]
        return None, None
    if isinstance(value, list):
        for entry in value:
            if isinstance(entry, int):
                return str(entry), entry
            if isinstance(entry, dict) and isinstance(entry.get("ac"), int):
                extra = ""
                source = entry.get("from") or []
                if source:
                    extra = f" ({', '.join(inline(str(part)) for part in source)})"
                return f"{entry['ac']}{extra}", entry["ac"]
    return None, None


def _speed_text(value) -> str | None:
    if isinstance(value, (int, str)):
        number = value if isinstance(value, str) else f"{value} ft."
        return number if "ft" in number else f"{number} ft."
    if not isinstance(value, dict):
        return None
    parts: list[str] = []
    for mode in ("walk", "burrow", "climb", "fly", "swim"):
        entry = value.get(mode)
        if entry is None:
            continue
        if isinstance(entry, dict):
            number = entry.get("number")
            condition = entry.get("condition")
            piece = f"{mode} {number} ft." if mode != "walk" else f"{number} ft."
            if condition:
                piece += f" ({inline(str(condition))})"
        else:
            piece = f"{mode} {entry} ft." if mode != "walk" else f"{entry} ft."
        parts.append(piece)
    for alternate in value.get("alternate") or []:
        if isinstance(alternate, dict):
            number = alternate.get("number")
            condition = alternate.get("condition")
            if number:
                piece = f"{number} ft."
                if condition:
                    piece += f" ({inline(str(condition))})"
                parts.append(piece)
    return ", ".join(parts) or None


def _signed(value) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if text.startswith(("+", "-", "−")):
        return text
    return f"+{int(text)}" if re.fullmatch(r"-?\d+", text) else text


def _modifier(score) -> str:
    try:
        bonus = (int(score) - 10) // 2
    except (TypeError, ValueError):
        return ""
    sign = "+" if bonus >= 0 else "−"
    return f"{sign}{abs(bonus)}"


def _abilities_line(obj: dict) -> str | None:
    parts: list[str] = []
    for key in ABILITIES:
        score = obj.get(key)
        if score is None:
            continue
        parts.append(f"{ABILITY_SHORT[key]} {score} ({_modifier(score)})")
    return " · ".join(parts) or None


def _named_numbers(value, titles: dict[str, str], plural: str, order=None) -> str | None:
    if not isinstance(value, dict):
        return None
    keys = [key for key in (order or ()) if key in value]
    keys += [key for key in sorted(value) if key not in keys]
    parts: list[str] = []
    for key in keys:
        title = titles.get(key.lower(), key.title())
        parts.append(f"{title} {_signed(value[key])}".strip())
    if not parts:
        return None
    text = ", ".join(parts)
    return f"{plural} {text}" if plural else text


def _list_text(value, prefix: str | None = None) -> str | None:
    if value is None:
        return None
    entries = value if isinstance(value, list) else [value]
    parts: list[str] = []
    for entry in entries:
        if isinstance(entry, dict):
            note = entry.get("note")
            for key in ("resist", "immune", "vulnerable", "conditionImmune"):
                if key in entry:
                    parts.extend(inline(str(v)) for v in entry[key])
                    break
            else:
                parts.append(inline(str(entry)))
            if note and parts:
                parts[-1] = f"{parts[-1]} ({inline(str(note))})"
        else:
            parts.append(inline(str(entry)))
    if not parts:
        return None
    joiner = "; " if any("," in part for part in parts) else ", "
    text = joiner.join(parts) if joiner == ", " else ", ".join(parts)
    return f"{prefix} {text}" if prefix else text


def _skills_text(value) -> str | None:
    if not isinstance(value, dict):
        return None
    titles = {
        key: key.title()
        for key in (
            "acrobatics",
            "animal handling",
            "arcana",
            "athletics",
            "deception",
            "history",
            "insight",
            "intimidation",
            "investigation",
            "medicine",
            "nature",
            "perception",
            "performance",
            "persuasion",
            "religion",
            "sleight of hand",
            "stealth",
            "survival",
        )
    }
    parts = [f"{titles.get(key.lower(), key.title())} {_signed(value[key])}".strip() for key in sorted(value)]
    return "Skills " + ", ".join(parts) if parts else None


def _hit_points(obj: dict) -> int | None:
    """Середні хіти. Частина книг тримає число в hp.special (AWM)."""
    hp = obj.get("hp")
    if not isinstance(hp, dict):
        return None
    average = hp.get("average")
    if isinstance(average, (int, float)):
        return int(average)
    special = hp.get("special")
    if isinstance(special, (int, float)):
        return int(special)
    if isinstance(special, str):
        # «127 (17d8 + 51) reduced to 107…» — перше число і є хіти;
        # «—(immune to damage)» числа не має взагалі.
        match = re.match(r"\s*(\d+)", special)
        if match:
            return int(match.group(1))
    return None


def _challenge(obj: dict) -> tuple[str | None, int | None]:
    value = obj.get("cr")
    if isinstance(value, dict):
        value = value.get("cr")
    if value is None:
        return None, None
    text = str(value)
    return text, CR_XP.get(text)


def _legendary_intro(name: str, count: int) -> str:
    lowered = name.lower()
    verb = "regains" if not lowered.endswith("s") else "regain"
    return (
        f"The {lowered} can take {count} legendary actions, choosing from the options "
        f"below. Only one legendary action option can be used at a time and only at the "
        f"end of another creature's turn. The {lowered} {verb} spent legendary actions at "
        f"the start of its turn."
    )


def _feature_blocks(entries, *, feature_index: dict | None = None) -> list[str]:
    """Риси/дії статблока: кожна — «Назва. Текст»."""
    out: list[str] = []
    for entry in entries or []:
        if isinstance(entry, str):
            out.append(inline(entry))
            continue
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        inner = _join(_blocks(entry.get("entries") or entry.get("entry"), feature_index=feature_index))
        if name:
            out.append(_named(inline(name), inner))
        elif inner:
            out.append(inner)
    return out


def monster_text(obj: dict) -> str:
    blocks: list[str] = [_type_line(obj)]
    ac_text, _ = _ac(obj)
    if ac_text:
        blocks.append(f"Armor Class {ac_text}")
    hp = obj.get("hp") if isinstance(obj.get("hp"), dict) else {}
    hit_points = _hit_points(obj)
    if hit_points is not None:
        formula = hp.get("formula")
        line = f"Hit Points {hit_points}"
        if formula:
            line += f" ({formula})"
        blocks.append(line)
    elif hp.get("special"):
        blocks.append(f"Hit Points {inline(str(hp['special']))}")
    speed = _speed_text(obj.get("speed"))
    if speed:
        blocks.append(f"Speed {speed}")
    abilities = _abilities_line(obj)
    if abilities:
        blocks.append(abilities)
    saves = _named_numbers(
        obj.get("save"), {key: ABILITY_SHORT[key].title() for key in ABILITIES}, "Saving Throws", ABILITIES
    )
    if saves:
        blocks.append(saves)
    skills = _skills_text(obj.get("skill"))
    if skills:
        blocks.append(skills)
    if obj.get("vulnerable"):
        text = _list_text(obj.get("vulnerable"), "Damage Vulnerabilities")
        if text:
            blocks.append(text)
    if obj.get("resist"):
        text = _list_text(obj.get("resist"), "Damage Resistances")
        if text:
            blocks.append(text)
    if obj.get("immune"):
        text = _list_text(obj.get("immune"), "Damage Immunities")
        if text:
            blocks.append(text)
    if obj.get("conditionImmune"):
        text = _list_text(obj.get("conditionImmune"), "Condition Immunities")
        if text:
            blocks.append(text)
    senses: list[str] = []
    if obj.get("senses"):
        senses.extend(inline(str(part)) for part in obj["senses"])
    if obj.get("passive") is not None:
        senses.append(f"passive Perception {obj['passive']}")
    if senses:
        blocks.append("Senses " + ", ".join(senses))
    languages = obj.get("languages")
    if languages:
        entries = languages if isinstance(languages, list) else [languages]
        blocks.append("Languages " + ", ".join(inline(str(part)) for part in entries))
    cr_text, xp = _challenge(obj)
    if cr_text:
        line = f"Challenge {cr_text}"
        if xp is not None:
            line += f" ({xp:,} XP)"
        blocks.append(line)

    blocks.extend(_feature_blocks(obj.get("trait")))
    # «Spellcasting» у дзеркалі — не риса, а окремий ключ зі своїм деревом.
    casting = obj.get("spellcasting")
    if isinstance(casting, dict):
        casting = [casting]
    for node in casting or []:
        if isinstance(node, dict):
            blocks.append(_spellcasting(node))

    sections = (
        ("action", "Actions", obj.get("actionHeader")),
        ("bonus", "Bonus Actions", obj.get("bonusHeader")),
        ("reaction", "Reactions", obj.get("reactionHeader")),
    )
    for key, title, header in sections:
        items = _feature_blocks(obj.get(key))
        if not items:
            continue
        blocks.append(title)
        if header:
            blocks.extend(render(entry) for entry in header if render(entry))
        blocks.extend(items)

    legendary = _feature_blocks(obj.get("legendary"))
    if legendary:
        blocks.append("Legendary Actions")
        header = obj.get("legendaryHeader")
        intro = _join(render(entry) for entry in header) if header else ""
        count = obj.get("legendaryActions")
        if not intro:
            intro = _legendary_intro(obj.get("name") or "creature", count or 3)
        blocks.append(intro)
        blocks.extend(legendary)

    mythic = _feature_blocks(obj.get("mythic"))
    if mythic:
        blocks.append("Mythic Actions")
        header = obj.get("mythicHeader")
        if header:
            intro = _join(render(entry) for entry in header)
            if intro:
                blocks.append(intro)
        blocks.extend(mythic)

    return _join(blocks)


def monster_data(obj: dict) -> dict:
    _ac_text, ac_value = _ac(obj)
    cr_text, xp = _challenge(obj)
    hp = obj.get("hp") or {}
    raw_type = obj.get("type")
    subtype = None
    if isinstance(raw_type, dict):
        tags = [str(tag) for tag in raw_type.get("tags") or []]
        subtype = ", ".join(tags) if tags else None
        swarm = raw_type.get("swarmSize")
        if swarm:
            subtype = ", ".join(filter(None, [f"swarm of {SIZE_NAMES.get(str(swarm), swarm).lower()}", subtype]))
    alignment = obj.get("alignment") or []
    if isinstance(alignment, str):
        alignment = [alignment]
    words = [ALIGNMENT_NAMES.get(str(code), str(code).lower()) for code in alignment]
    speed = obj.get("speed")
    walk = None
    if isinstance(speed, dict):
        walk = speed.get("walk")
        if isinstance(walk, dict):
            walk = walk.get("number")
    elif isinstance(speed, int):
        walk = speed
    return {
        "size": " or ".join(_size_names(obj.get("size"))).lower() or None,
        "creature_type": str(raw_type.get("type") if isinstance(raw_type, dict) else raw_type or "").lower() or None,
        "subtype": subtype,
        "alignment": " ".join(word for word in words if word) or None,
        "armor_class": ac_value,
        "hit_points": _hit_points(obj),
        "hit_dice": hp.get("formula") if isinstance(hp, dict) else None,
        "speed": _speed_text(speed),
        "abilities": {key: obj.get(key) for key in ABILITIES},
        "challenge_rating": cr_text,
        "xp": xp,
        "saving_throws": _named_numbers(
            obj.get("save"), {key: ABILITY_SHORT[key].title() for key in ABILITIES}, "", ABILITIES
        ),
        "skills": _flat(_skills_text(obj.get("skill")) or "").replace("Skills ", "") or None,
        "damage_vulnerabilities": _list_text(obj.get("vulnerable")),
        "damage_resistances": _list_text(obj.get("resist")),
        "damage_immunities": _list_text(obj.get("immune")),
        "condition_immunities": _list_text(obj.get("conditionImmune")),
        "senses": ", ".join(
            [inline(str(part)) for part in obj.get("senses") or []]
            + ([f"passive Perception {obj['passive']}"] if obj.get("passive") is not None else [])
        )
        or None,
        "languages": ", ".join(
            inline(str(part))
            for part in (obj.get("languages") if isinstance(obj.get("languages"), list) else [obj.get("languages")])
            if part
        )
        or None,
    }


# --- види, підраси --------------------------------------------------------


def _ability_increases(value) -> dict[str, int] | None:
    if not isinstance(value, list):
        return None
    merged: dict[str, int] = {}
    for block in value:
        if not isinstance(block, dict):
            continue
        for key, bonus in block.items():
            name = LONG_ABILITIES.get(key)
            if name and isinstance(bonus, int):
                merged[name] = merged.get(name, 0) + bonus
    return merged or None


def _speed_walk(value) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, dict):
        walk = value.get("walk")
        if isinstance(walk, dict):
            walk = walk.get("number")
        return walk if isinstance(walk, int) else None
    return None


def species_text(obj: dict, *, feature_index: dict | None = None) -> str:
    return render(obj.get("entries"), feature_index=feature_index)


def species_data(obj: dict, *, subrace_of: str | None = None, parent: dict | None = None) -> dict:
    """Поля виду. Підраса успадковує від виду те, чого сама не задає."""
    size = " / ".join(name.lower() for name in _size_names(obj.get("size"))) or None
    speed = _speed_walk(obj.get("speed"))
    abilities = _ability_increases(obj.get("ability"))
    if parent:
        if size is None:
            size = " / ".join(name.lower() for name in _size_names(parent.get("size"))) or None
        if speed is None:
            speed = _speed_walk(parent.get("speed"))
        if abilities is None:
            abilities = _ability_increases(parent.get("ability"))
    return {
        "ability_increases": abilities,
        "size": size,
        "speed": speed,
        "subrace_of": subrace_of.lower() if subrace_of else None,
    }


# --- передісторії ---------------------------------------------------------


def background_feature(obj: dict) -> str | None:
    """Назва вміння передісторії («Shelter of the Faithful»)."""

    def walk(node):
        if isinstance(node, dict):
            name = node.get("name")
            if isinstance(name, str):
                lowered = name.lower()
                if lowered.startswith("feature"):
                    return name.split(":", 1)[-1].strip()
            for key in ("entries", "items", "entry"):
                found = walk(node.get(key))
                if found:
                    return found
        elif isinstance(node, list):
            for child in node:
                found = walk(child)
                if found:
                    return found
        return None

    return walk(obj.get("entries"))


# --- риси -----------------------------------------------------------------


def feat_prerequisite(obj: dict) -> str | None:
    value = obj.get("prerequisite")
    if not value:
        return None
    blocks = value if isinstance(value, list) else [value]
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, str):
            parts.append(inline(block))
            continue
        if not isinstance(block, dict):
            continue
        for key, item in block.items():
            if key in ABILITIES and isinstance(item, int):
                parts.append(f"{ABILITY_TITLES[key]} {item}")
            elif key == "level":
                parts.append(f"Level {item}")
            elif key == "ability":
                abilities = item if isinstance(item, list) else [item]
                for ability in abilities:
                    if isinstance(ability, dict):
                        parts.extend(
                            f"{ABILITY_TITLES.get(name, name)} {score}"
                            for name, score in ability.items()
                            if name in ABILITIES
                        )
            elif key == "race":
                races = item if isinstance(item, list) else [item]
                names = [inline(str(entry.get("name") if isinstance(entry, dict) else entry)) for entry in races]
                parts.append("Race: " + ", ".join(name for name in names if name))
            elif key == "campaign":
                parts.append("Campaign: " + ", ".join(str(name) for name in item))
            elif key == "spellcasting":
                parts.append("The ability to cast at least one spell")
            elif key == "proficiency":
                entries = item if isinstance(item, list) else [item]
                for entry in entries:
                    if isinstance(entry, dict):
                        parts.append("Proficiency with " + ", ".join(str(name) for name in entry))
                    elif isinstance(entry, str):
                        parts.append(inline(entry))
            elif key in ("other", "special", "feature"):
                text = item if isinstance(item, str) else ", ".join(str(name) for name in item)
                parts.append(inline(text))
            elif key == "psionics":
                parts.append("Psionics")
    cleaned = [part for part in parts if part]
    return ", ".join(dict.fromkeys(cleaned)) or None


# --- опційні вміння -------------------------------------------------------
#
# Дзеркало тримає їх не в теці книги, а одним покажчиком
# (`_index/mirror-optionalfeatures.json`), бо те саме вміння буває в кількох
# книгах і в кількох класах одразу. Групує їх код `featureType`: книга такого
# слова не пише («Eldritch Invocation», «Maneuver»), тому код перекладаємо.

OPTIONAL_FEATURE_TYPES = {
    "EI": "eldritch invocation",
    "MV:B": "maneuver (battle master)",
    "MM": "metamagic",
    "ED": "elemental discipline",
    "AI": "artificer infusion",
    "AS": "arcane shot",
    "FS:F": "fighting style (fighter)",
    "FS:P": "fighting style (paladin)",
    "FS:R": "fighting style (ranger)",
    "FS:B": "fighting style (bard)",
    "RN": "rune",
    "PB": "pact boon",
    "RP": "renown perk",
}


def optional_feature_types(obj: dict) -> list[str] | None:
    """Коди `featureType` → людські назви груп (невідомий код лишаємо як є)."""
    value = obj.get("featureType")
    codes = value if isinstance(value, list) else [value]
    labels = [
        OPTIONAL_FEATURE_TYPES.get(str(code).strip(), str(code).strip().lower())
        for code in codes
        if isinstance(code, str) and code.strip()
    ]
    return labels or None


def _requirement_ref(value) -> str:
    """Посилання в передумові: «eldritch blast#c» → «eldritch blast cantrip»."""
    text = str(value or "").strip()
    name, _, suffix = text.partition("#")
    shown = inline(name).strip()
    if not shown:
        return ""
    if suffix.strip().lower() == "c":
        return f"{shown} cantrip"
    return shown


def _requirement_level(value) -> str | None:
    if isinstance(value, int):
        return f"Level {value}"
    if not isinstance(value, dict):
        return None
    level = value.get("level")
    if not isinstance(level, int):
        return None
    text = f"Level {level}"
    klass = value.get("class")
    if isinstance(klass, dict) and klass.get("name"):
        text += f" {inline(str(klass['name'])).strip()}"
    subclass = value.get("subclass")
    if isinstance(subclass, dict) and subclass.get("name"):
        text += f" ({inline(str(subclass['name'])).strip()})"
    return text


def optional_feature_prerequisite(obj: dict) -> str | None:
    """Передумова вибору — одним рядком, як у книзі: «Level 9 Warlock».

    Ключі дзеркала: `level` (рівень, іноді з класом), `pact` (вид пакту),
    `spell` (закляття, яке треба вміти), `item` (предмет), `optionalfeature`
    (інше опційне вміння), `otherSummary` (довільний текст).
    """
    value = obj.get("prerequisite")
    if not value:
        return None
    blocks = value if isinstance(value, list) else [value]
    parts: list[str] = []
    for block in blocks:
        if isinstance(block, str):
            parts.append(inline(block))
            continue
        if not isinstance(block, dict):
            continue
        for key, item in block.items():
            if key == "level":
                level = _requirement_level(item)
                if level:
                    parts.append(level)
            elif key == "pact":
                parts.append(f"Pact of the {inline(str(item)).strip()}")
            elif key == "spell":
                spells = item if isinstance(item, list) else [item]
                names = [
                    str(entry.get("entrySummary") or entry.get("entry") or "")
                    if isinstance(entry, dict)
                    else _requirement_ref(entry)
                    for entry in spells
                ]
                shown = ", ".join(inline(name).strip() for name in names if name)
                parts.append("Spell: " + shown)
            elif key == "item":
                items = item if isinstance(item, list) else [item]
                shown = ", ".join(
                    inline(str(entry)).strip()
                    if not isinstance(entry, dict)
                    else inline(str(entry.get("name") or "")).strip()
                    for entry in items
                )
                parts.append("Item: " + shown)
            elif key == "optionalfeature":
                features = item if isinstance(item, list) else [item]
                shown = ", ".join(_requirement_ref(str(entry).split("|")[0]) for entry in features)
                parts.append("Feature: " + shown)
            elif key == "otherSummary" and isinstance(item, dict):
                parts.append(inline(str(item.get("entrySummary") or item.get("entry") or "")))
            elif isinstance(item, str):
                parts.append(inline(item))
    cleaned = [part.strip() for part in parts if part and part.strip()]
    return ", ".join(dict.fromkeys(cleaned)) or None


def optionalfeature_text(obj: dict, *, feature_index: dict | None = None) -> str:
    return render(obj.get("entries"), feature_index=feature_index)


def optionalfeature_data(obj: dict) -> dict:
    return {
        "feature_type": optional_feature_types(obj),
        "prerequisite": optional_feature_prerequisite(obj),
    }


# --- підкласи -------------------------------------------------------------


def _level_label(level: int, class_name: str) -> str:
    suffix = "th" if 11 <= level % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(level % 10, "th")
    return f"*{level}{suffix}-level {class_name} feature*"


def subclass_text(obj: dict, features: list[dict], *, feature_index: dict | None = None) -> str:
    """Тіло підкласу: вступ + уміння за рівнями (як у книзі)."""
    class_name = str(obj.get("className") or "")
    short = _clean_name(obj.get("shortName"), obj.get("source"))

    def own(feature: dict) -> bool:
        return (
            _clean_name(feature.get("subclassShortName"), feature.get("subclassSource")) == short
            and feature.get("subclassSource") == obj.get("source")
            and feature.get("className") == class_name
        )

    ordered = sorted(
        [feature for feature in features if own(feature)],
        key=lambda feature: (feature.get("level") or 0, feature.get("name") or ""),
    )
    # Дзеркало інколи тримає ту саму рису двічі — на 1-му й на 3-му рівні
    # (перевидання під правила 2024). Лишаємо першу, нижчу за рівнем.
    unique: list[dict] = []
    seen: set[str] = set()
    for feature in ordered:
        key = _flat(_clean_name(feature.get("name"), feature.get("source"))).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(feature)
    ordered = unique
    if not ordered:
        return render(obj.get("entries"), feature_index=feature_index)
    # Вступ підкласу — риса, названа так само, як підклас (Pyromancer →
    # «Pyromancer», а не «Heart of Fire», яка теж 1-го рівня). Якщо такої
    # немає (PHB-підкласи), вступ — найнижча за рівнем риса.
    name_key = _flat(_clean_name(obj.get("name"), obj.get("source"))).lower()
    intro_index = next(
        (
            index
            for index, feature in enumerate(ordered)
            if _flat(_clean_name(feature.get("name"), feature.get("source"))).lower() == name_key
        ),
        0,
    )
    intro = ordered[intro_index]
    blocks: list[str] = [render(intro.get("entries"), feature_index=feature_index)]
    for feature in ordered:
        if feature is intro:
            continue
        name = _clean_name(feature.get("name"), feature.get("source"))
        level = int(feature.get("level") or 0)
        body = render(feature.get("entries"), feature_index=feature_index)
        blocks.append(f"## {name}\n\n{_level_label(level, class_name)}\n\n{body}")
    return _join(blocks)


def subclass_level(obj: dict, features: list[dict]) -> int | None:
    short = _clean_name(obj.get("shortName"), obj.get("source"))
    levels = [
        feature.get("level")
        for feature in features
        if _clean_name(feature.get("subclassShortName"), feature.get("subclassSource")) == short
        and feature.get("subclassSource") == obj.get("source")
        and feature.get("className") == obj.get("className")
        and isinstance(feature.get("level"), int)
    ]
    return min(levels) if levels else None


# --- предмети -------------------------------------------------------------


def _price(value) -> str | None:
    """Ціна в cp → рядок у gp/sp/cp."""
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    cp = int(value)
    if cp % 100 == 0:
        return f"{cp // 100:,} gp"
    if cp % 10 == 0:
        return f"{cp // 10} sp"
    return f"{cp} cp"


def _weight(value) -> str | None:
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    amount = f"{value:g}"
    return f"{amount} lb."


def _item_type(obj: dict) -> str | None:
    raw = obj.get("type")
    if isinstance(raw, str) and raw:
        code = raw.split("|")[0]
        if code in ITEM_TYPES:
            return ITEM_TYPES[code]
        if code.startswith("$"):
            return "art object"
    if obj.get("wondrous"):
        return "wondrous item"
    if obj.get("staff"):
        return "staff"
    if obj.get("wand"):
        return "wand"
    if obj.get("ring"):
        return "ring"
    if obj.get("potion"):
        return "potion"
    if obj.get("rod"):
        return "rod"
    return None


def _base_item(obj: dict) -> str | None:
    value = obj.get("baseItem")
    if isinstance(value, str) and value:
        return inline(value.split("|")[0])
    return None


def item_text(obj: dict) -> str:
    item_type = _item_type(obj)
    rarity = obj.get("rarity")
    if rarity in ("none", "unknown", ""):
        rarity = None
    magical = (
        bool(rarity)
        or bool(obj.get("wondrous"))
        or bool(obj.get("type") and str(obj.get("type")).split("|")[0] in {"W", "WD", "RG", "P", "SC", "RD", "ST"})
    )
    body = render(obj.get("entries"))
    if magical:
        head = item_type[:1].upper() + item_type[1:] if item_type else "Magic item"
        base = _base_item(obj)
        if base and item_type in ("weapon", "armor", "shield"):
            head = f"{head} ({base})"
        if rarity:
            head += f", {rarity}"
        if obj.get("reqAttune"):
            requirement = obj["reqAttune"]
            if isinstance(requirement, str) and requirement:
                head += f" (requires attunement {inline(requirement)})"
            else:
                head += " (requires attunement)"
        blocks = [head]
        if body:
            blocks.append(body)
        return _join(blocks)

    row = [
        (item_type or "gear").capitalize() if item_type else "Gear",
        inline(str(obj.get("name") or "")),
        _price(obj.get("value")),
        _weight(obj.get("weight")),
    ]
    line = " · ".join(part for part in row if part)
    return _join([line, body])


def item_data(obj: dict) -> dict:
    rarity = obj.get("rarity")
    if rarity in ("none", "unknown", ""):
        rarity = None
    damage = None
    if obj.get("dmg1"):
        damage = f"{obj['dmg1']}"
        if obj.get("dmg2"):
            damage += f" ({obj['dmg2']})"
        if obj.get("dmgType"):
            damage += f" {obj['dmgType'].lower()}"
    properties = obj.get("property")
    property_names = None
    if isinstance(properties, list) and properties:
        words = []
        for code in properties:
            code = str(code).split("|")[0]
            words.append(WEAPON_PROPERTIES.get(code, code))
        property_names = ", ".join(words)
    strength = obj.get("strength")
    return {
        "item_type": _item_type(obj),
        "rarity": rarity,
        "magical": bool(rarity) or bool(obj.get("wondrous")),
        "attunement": bool(obj.get("reqAttune")),
        "base_item": _base_item(obj),
        "group": None,
        "cost": _price(obj.get("value")),
        "weight": _weight(obj.get("weight")),
        "armor_class": str(obj["ac"]) if isinstance(obj.get("ac"), int) else None,
        "damage": damage,
        "properties": property_names,
        "stealth": "Disadvantage" if obj.get("stealth") else None,
        "strength": f"Str {strength}" if strength else None,
    }


# --- закляття -------------------------------------------------------------


def _casting_time(value) -> str | None:
    if not isinstance(value, list) or not value:
        return None
    parts: list[str] = []
    for block in value:
        if not isinstance(block, dict):
            continue
        number = block.get("number") or 1
        unit = str(block.get("unit") or "action")
        if unit == "bonus":
            unit = "bonus action"
        elif unit in ("minute", "hour"):
            unit += "" if number == 1 else "s"
        elif unit != "reaction":
            unit += "" if number == 1 else "s"
        text = f"{number} {unit}"
        condition = block.get("condition")
        if condition:
            text += f", {inline(str(condition))}"
        parts.append(text)
    return ", ".join(parts) or None


_DISTANCE_UNITS = {"feet": "feet", "mile": "mile", "miles": "miles", "touch": "touch"}


def _range_text(value) -> str | None:
    if not isinstance(value, dict):
        return None
    kind = value.get("type")
    distance = value.get("distance")
    if kind == "special":
        return "Special"
    if kind == "unlimited":
        return "Unlimited"
    if kind == "sight":
        return "Sight"
    if kind == "self":
        return "Self"
    if kind == "touch":
        return "Touch"
    if kind == "point":
        if isinstance(distance, dict):
            inner = str(distance.get("type") or "")
            if inner in ("touch", "self", "sight", "unlimited"):
                return inner.capitalize()
            if distance.get("amount") is None and inner == "special":
                return "Special"
            amount = distance.get("amount")
            unit = _DISTANCE_UNITS.get(str(distance.get("type")), str(distance.get("type")))
            if amount is not None:
                return f"{amount} {unit}"
        return None
    if (
        kind in ("radius", "sphere", "cone", "line", "cube", "cylinder")
        and isinstance(distance, dict)
        and distance.get("amount") is not None
    ):
        unit = _DISTANCE_UNITS.get(str(distance.get("type")), str(distance.get("type")))
        shape = {"radius": "radius", "sphere": "radius", "cylinder": "radius"}.get(kind, kind)
        return f"Self ({distance['amount']}-{unit} {shape})"
    return None


def _components(obj: dict) -> str | None:
    value = obj.get("components")
    if not isinstance(value, dict):
        return None
    parts: list[str] = []
    if value.get("v"):
        parts.append("V")
    if value.get("s"):
        parts.append("S")
    material = value.get("m")
    if material:
        if isinstance(material, dict):
            # Текст уже називає ціну й витратність («worth 500 gp ... the spell
            # consumes»), тому cost сюди не дописуємо — інакше ціна двічі.
            text = material.get("text")
            text = inline(str(text)) if text else None
            parts.append(f"M ({text})" if text else "M")
        else:
            parts.append(f"M ({inline(str(material))})")
    return ", ".join(parts) or None


def _duration(obj: dict) -> tuple[str | None, bool]:
    value = obj.get("duration")
    if not isinstance(value, list) or not value:
        return None, False
    block = value[0]
    if not isinstance(block, dict):
        return None, False
    concentration = bool(block.get("concentration"))
    kind = block.get("type")
    if kind == "instant":
        text = "Instantaneous"
    elif kind == "permanent":
        text = "Until dispelled"
    elif kind == "special":
        text = "Special"
    elif kind == "timed":
        inner = block.get("duration") or {}
        amount = inner.get("amount")
        unit = str(inner.get("type") or "round")
        if amount is not None:
            unit += "" if amount == 1 else "s"
            text = f"up to {amount} {unit}" if concentration else f"{amount} {unit}"
        else:
            text = "Special"
    else:
        text = str(kind).title() if kind else "Special"
    if concentration and text not in ("Instantaneous", "Until dispelled"):
        text = "Concentration, " + text
    elif concentration:
        text = "Concentration, " + text.lower()
    return text, concentration


def _spell_classes(obj: dict) -> list[str] | None:
    value = obj.get("classes")
    names: list[str] = []
    if isinstance(value, dict):
        for key in ("fromClassList", "fromClassListVariant"):
            for entry in value.get(key) or []:
                if isinstance(entry, dict):
                    name = entry.get("name")
                    if name:
                        names.append(str(name).lower())
    return sorted(set(names)) or None


def _at_higher_levels(obj: dict) -> str | None:
    for entry in obj.get("entriesHigherLevel") or []:
        if isinstance(entry, dict):
            name = str(entry.get("name") or "")
            if name.lower().startswith("at higher levels"):
                return render(entry.get("entries"))
    return None


def spell_data(obj: dict) -> dict:
    school = SCHOOL_NAMES.get(str(obj.get("school") or "").upper())
    duration, concentration = _duration(obj)
    meta = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
    return {
        "level": obj.get("level") if isinstance(obj.get("level"), int) else None,
        "school": school,
        "ritual": bool(meta.get("ritual") or obj.get("ritual")),
        "concentration": concentration,
        "casting_time": _casting_time(obj.get("time")),
        "range": _range_text(obj.get("range")),
        "components": _components(obj),
        "duration": duration,
        "classes": _spell_classes(obj),
        "at_higher_levels": _at_higher_levels(obj),
    }


def spell_text(obj: dict) -> str:
    blocks = [render(obj.get("entries"))]
    higher = _at_higher_levels(obj)
    if higher:
        blocks.append(f"At Higher Levels. {higher}")
    return _join(blocks)


# --- збірка записів -------------------------------------------------------


def record(
    *,
    folder: str,
    category: str,
    name: str,
    text: str,
    data: dict,
    license_value: str,
    url: str | None,
    page,
    fetched_at: str,
    notes: list[str] | None = None,
) -> dict:
    return {
        "id": f"{folder}/{category}/{slugify(name)}",
        "schema": "compendium-entry/1",
        "source_id": folder,
        "category": category,
        "name_en": name,
        "name_uk": None,
        "edition": "2014",
        "license": license_value,
        "url": url,
        "page": page if isinstance(page, int) else None,
        "text_en": text,
        "text_uk": None,
        "data": data,
        "status": "raw",
        "fetched_at": fetched_at,
        "notes": notes or [],
    }


def load_catalogue() -> dict[str, dict]:
    """Каталог дзеркала: id книги → запис (назва, дата, група)."""
    catalogue: dict[str, dict] = {}
    for name, key in (("books-5etools.json", "book"), ("adventures-5etools.json", "adventure")):
        path = config.INDEX_DIR / name
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for entry in payload.get(key) or []:
            entry = dict(entry)
            entry["_kind"] = key
            catalogue[entry["id"]] = entry
    return catalogue


def folder_sources(folders: list[str]) -> dict[str, str]:
    """Код дзеркала → тека корпусу. Покриває і `PS-A`, і `PSA`."""
    mapping: dict[str, str] = {}
    for folder in folders:
        mapping.setdefault(folder, folder)
        for path in (config.RAW_DIR / folder).glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                continue
            if not isinstance(payload, dict):
                continue
            for key in ("bookData", "adventureData"):
                for entry in payload.get(key) or []:
                    if not isinstance(entry, dict):
                        continue
                    for field in ("id", "source"):
                        value = entry.get(field)
                        if isinstance(value, str) and value:
                            mapping.setdefault(value, folder)
            monsters = payload.get("monster")
            if isinstance(monsters, list) and monsters:
                value = monsters[0].get("source")
                if isinstance(value, str) and value:
                    mapping.setdefault(value, folder)
    return mapping


def mirror_folders() -> list[str]:
    """Усі теки дзеркала на диску (без теки-покажчика й PDF-книги).

    Книга дзеркала впізнається за іменем файлу (`book-`, `adventure-`,
    `bestiary-`): у теках DDB-конвеєра теж лежить `_checkpoint.json`, і без
    цієї перевірки вони потрапляли б у список як «книги дзеркала».
    """
    folders: list[str] = []
    for path in sorted(config.RAW_DIR.iterdir()):
        if not path.is_dir() or path.name.startswith("_") or path.name in NOT_MIRROR:
            continue
        if any(any(path.glob(f"{prefix}-*.json")) for prefix in ("book", "adventure", "bestiary")):
            folders.append(path.name)
    return folders


def pending_folders() -> list[str]:
    """Теки дзеркала, які ще не внесені в реєстр як розібрані."""
    sources = _sources()
    done = {
        source_id
        for source_id, meta in sources.items()
        if meta.get("status") in ("ingested", "translated", "verified")
    }
    return [folder for folder in mirror_folders() if folder not in done]


def book_url(folder: str, catalogue: dict[str, dict], sources: dict[str, dict]) -> str | None:
    """Адреса книги на дзеркалі — та сама, з якої її завантажено."""
    entry = catalogue.get(_book_id(folder, sources))
    if entry is None:
        for candidate in catalogue.values():
            if candidate["id"].lower() == folder or candidate.get("source", "").lower() == folder:
                entry = candidate
                break
    if entry is None:
        # Тека корпусу не має коду в реєстрі (`phb-2014` — це `PHB` на
        # дзеркалі), тому шукаємо код за назвою книги: та сама мапа, що
        # зіставляє розібрані книги з дзеркалом.
        code = _code_for(folder)
        if code:
            entry = catalogue.get(code)
    if entry is None:
        return None
    page = "adventure.html" if entry.get("_kind") == "adventure" else "book.html"
    return f"https://5e.tools/{page}#{entry['id'].lower()}"


_FILE_CODES: dict[str, str] | None = None


def _code_for(folder: str) -> str | None:
    """Тека корпусу → код дзеркала (`phb-2014` → `PHB`), якщо книга розібрана."""
    global _FILE_CODES
    if _FILE_CODES is None:
        _FILE_CODES = {value: code for code, value in owned_sources().items()}
    return _FILE_CODES.get(folder)


def _book_id(folder: str, sources: dict[str, dict]) -> str:
    meta = sources.get(folder) or {}
    return str(meta.get("mirror") or folder)


def build_folder(
    folder: str,
    *,
    mapping: dict[str, str],
    catalogue: dict[str, dict],
    sources: dict[str, dict],
    fetched_at: str,
    feature_index: dict[str, dict] | None = None,
) -> list[dict]:
    """Усі записи, які дає ця тека дзеркала."""
    meta = sources.get(folder) or {}
    license_value = meta.get("license", "proprietary")
    url = book_url(folder, catalogue, sources)
    records: list[dict] = []

    # 1) статблоки — лежать у самій теці; `_copy` тягне базу з Monster Manual
    # та інших файлів, тому спершу розкриваємо посилання.
    pool = monster_index()
    for path in sorted((config.RAW_DIR / folder).glob("bestiary-*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        for raw in payload.get("monster") or []:
            if not isinstance(raw, dict) or not raw.get("name"):
                continue
            monster = resolve_copy(raw, pool)
            text = monster_text(monster)
            if len(text) < 80:
                continue
            data = monster_data(monster)
            notes: list[str] = []
            hp = monster.get("hp") if isinstance(monster.get("hp"), dict) else {}
            if data.get("hit_points") is None and hp.get("special"):
                # Такі статблоки є (Meeseeks: «—(immune to damage)»): хітів
                # немає, бо істота невразлива. Це не прогалина розбору.
                notes.append("статблок без числових хітів: " + _flat(inline(str(hp["special"]))))
            records.append(
                record(
                    folder=folder,
                    category="monster",
                    name=_clean_name(monster["name"], monster.get("source")),
                    text=text,
                    data=data,
                    license_value=license_value,
                    url=url,
                    page=monster.get("page"),
                    fetched_at=fetched_at,
                    notes=notes,
                )
            )

    # 2) довідкові корпуси дзеркала — по коду джерела
    records.extend(
        _reference_records(
            folder,
            mapping=mapping,
            license_value=license_value,
            url=url,
            fetched_at=fetched_at,
            feature_index=feature_index or {},
        )
    )
    return _deduplicate(records)


def _owns(folder: str, mapping: dict[str, str], obj: dict, *fields: str) -> bool:
    for field in fields:
        value = obj.get(field)
        if isinstance(value, str) and mapping.get(value) == folder:
            return True
    return False


def _load_index(name: str, key: str | None = None):
    path = config.INDEX_DIR / name
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if key is None:
        return payload
    return payload.get(key) or []


def subclass_features() -> tuple[list[dict], list[dict], dict[str, dict]]:
    """Підкласи, їхні вміння (з усіх файлів класів) і покажчик умінь за назвою."""
    subclasses: list[dict] = []
    features: list[dict] = []
    index: dict[str, dict] = {}
    directory = config.INDEX_DIR / "mirror-class"
    if not directory.is_dir():
        return subclasses, features, index
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        for entry in payload.get("subclass") or []:
            if isinstance(entry, dict):
                subclasses.append(entry)
        for entry in payload.get("subclassFeature") or []:
            if not isinstance(entry, dict):
                continue
            features.append(entry)
    sub_index = _index_rows(subclasses)
    subclasses = [resolve_copy(entry, sub_index) for entry in subclasses]
    feature_index_rows = _index_rows(features)
    features = [resolve_copy(entry, feature_index_rows) for entry in features]
    index: dict[str, dict] = {}
    for entry in features:
        key = entry.get("name")
        if isinstance(key, str):
            index.setdefault(key, entry)
    return subclasses, features, index


_CLASS_DATA: tuple[list[dict], list[dict], dict[str, dict]] | None = None


def class_data() -> tuple[list[dict], list[dict], dict[str, dict]]:
    """Файли класів читаються один раз на запуск."""
    global _CLASS_DATA
    if _CLASS_DATA is None:
        _CLASS_DATA = subclass_features()
    return _CLASS_DATA


def _reference_records(
    folder: str,
    *,
    mapping: dict[str, str],
    license_value: str,
    url: str | None,
    fetched_at: str,
    feature_index: dict[str, dict],
) -> list[dict]:
    out: list[dict] = []

    races = _entity_rows("races-5etools.json", "race")
    subraces = _entity_rows("races-5etools.json", "subrace")
    races_by_name = {(row.get("name") or "").lower(): row for row in races}

    for race in races:
        if not _owns(folder, mapping, race, "source"):
            continue
        text = species_text(race, feature_index=feature_index)
        if len(text) < 80:
            continue
        out.append(
            record(
                folder=folder,
                category="species",
                name=_clean_name(race["name"], race.get("source")),
                text=text,
                data=species_data(race),
                license_value=license_value,
                url=url,
                page=race.get("page"),
                fetched_at=fetched_at,
            )
        )

    for subrace in subraces:
        if not _owns(folder, mapping, subrace, "source", "raceSource"):
            continue
        text = species_text(subrace, feature_index=feature_index)
        if len(text) < 80:
            continue
        # Дзеркало тримає підрасу окремо від виду: name="Hill", raceName="Dwarf",
        # а книга називає це «Hill Dwarf».
        parent = str(subrace.get("raceName") or "").strip()
        qualifier = _clean_name(subrace["name"], subrace.get("source"))
        name = (
            qualifier
            if not parent or parent.lower() in qualifier.lower()
            else (f"{qualifier} {parent}".strip() if qualifier else parent)
        )
        out.append(
            record(
                folder=folder,
                category="species",
                name=name,
                text=text,
                data=species_data(
                    subrace,
                    subrace_of=subrace.get("raceName"),
                    parent=races_by_name.get(str(subrace.get("raceName") or "").lower()),
                ),
                license_value=license_value,
                url=url,
                page=subrace.get("page"),
                fetched_at=fetched_at,
            )
        )

    for background in _entity_rows("backgrounds-5etools.json", "background"):
        if not _owns(folder, mapping, background, "source"):
            continue
        text = render(background.get("entries"), feature_index=feature_index)
        if len(text) < 80:
            continue
        out.append(
            record(
                folder=folder,
                category="background",
                name=_clean_name(background["name"], background.get("source")),
                text=text,
                data={"feature": background_feature(background)},
                license_value=license_value,
                url=url,
                page=background.get("page"),
                fetched_at=fetched_at,
            )
        )

    for feat in _entity_rows("feats-5etools.json", "feat"):
        if not _owns(folder, mapping, feat, "source"):
            continue
        text = render(feat.get("entries"), feature_index=feature_index)
        if len(text) < 80:
            continue
        out.append(
            record(
                folder=folder,
                category="feat",
                name=_clean_name(feat["name"], feat.get("source")),
                text=text,
                data={"prerequisite": feat_prerequisite(feat)},
                license_value=license_value,
                url=url,
                page=feat.get("page"),
                fetched_at=fetched_at,
            )
        )

    for spell in all_spells():
        if not _owns(folder, mapping, spell, "source"):
            continue
        text = spell_text(spell)
        if len(text) < 60:
            continue
        out.append(
            record(
                folder=folder,
                category="spell",
                name=_clean_name(spell["name"], spell.get("source")),
                text=text,
                data=spell_data(spell),
                license_value=license_value,
                url=url,
                page=spell.get("page"),
                fetched_at=fetched_at,
            )
        )

    subclasses, features, _ = class_data()
    for subclass in subclasses:
        if not _owns(folder, mapping, subclass, "source"):
            continue
        text = subclass_text(subclass, features, feature_index=feature_index)
        if len(text) < 60:
            continue
        out.append(
            record(
                folder=folder,
                category="subclass",
                name=_clean_name(subclass["name"], subclass.get("source")),
                text=text,
                data={
                    "class": str(subclass.get("className") or "").lower() or None,
                    "level": subclass_level(subclass, features),
                },
                license_value=license_value,
                url=url,
                page=subclass.get("page"),
                fetched_at=fetched_at,
            )
        )

    for item in all_items():
        if not _owns(folder, mapping, item, "source"):
            continue
        text = item_text(item)
        if len(text) < 12:
            continue
        out.append(
            record(
                folder=folder,
                category="item",
                name=_clean_name(item["name"], item.get("source")),
                text=text,
                data=item_data(item),
                license_value=license_value,
                url=url,
                page=item.get("page"),
                fetched_at=fetched_at,
            )
        )

    for feature in all_optional_features():
        if not _owns(folder, mapping, feature, "source"):
            continue
        text = optionalfeature_text(feature, feature_index=feature_index)
        if len(text) < 20:
            continue
        out.append(
            record(
                folder=folder,
                category="optionalfeature",
                name=_clean_name(feature["name"], feature.get("source")),
                text=text,
                data=optionalfeature_data(feature),
                license_value=license_value,
                url=url,
                page=feature.get("page"),
                fetched_at=fetched_at,
            )
        )
    return out


_FEATURES: list[dict] | None = None


def _iter_spells():
    directory = config.INDEX_DIR / "mirror-spells"
    if not directory.is_dir():
        return
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            continue
        for spell in payload.get("spell") or []:
            if isinstance(spell, dict) and spell.get("name"):
                yield spell


_SPELL_CACHE: list[dict] | None = None


def all_spells() -> list[dict]:
    """Закляття дзеркала з розкритими `_copy`."""
    global _SPELL_CACHE
    if _SPELL_CACHE is None:
        rows = list(_iter_spells())
        index = _index_rows(rows)
        _SPELL_CACHE = [resolve_copy(row, index) for row in rows]
    return _SPELL_CACHE


def _iter_items():
    for name, key in (("mirror-items.json", "item"), ("mirror-items-base.json", "baseitem")):
        for item in _load_index(name, key):
            if isinstance(item, dict) and item.get("name"):
                yield item


_ITEM_CACHE: list[dict] | None = None


def all_items() -> list[dict]:
    """Предмети дзеркала (магічні й звичайні) з розкритими `_copy`."""
    global _ITEM_CACHE
    if _ITEM_CACHE is None:
        rows = list(_iter_items())
        index = _index_rows(rows)
        _ITEM_CACHE = [resolve_copy(row, index) for row in rows]
    return _ITEM_CACHE


_OPTIONAL_CACHE: list[dict] | None = None


def all_optional_features() -> list[dict]:
    """Опційні вміння дзеркала (усі книги одною купою) з розкритими `_copy`."""
    global _OPTIONAL_CACHE
    if _OPTIONAL_CACHE is None:
        rows = [
            row
            for row in _load_index("mirror-optionalfeatures.json", "optionalfeature")
            if isinstance(row, dict) and row.get("name")
        ]
        index = _index_rows(rows)
        _OPTIONAL_CACHE = [resolve_copy(row, index) for row in rows]
    return _OPTIONAL_CACHE


def _deduplicate(records: list[dict]) -> list[dict]:
    """Один id — один запис: лишаємо повніший, згадку про інший — у notes."""
    best: dict[str, dict] = {}
    for entry in records:
        key = entry["id"]
        if key not in best:
            best[key] = entry
            continue
        previous = best[key]
        keep, drop = (entry, previous) if len(entry["text_en"]) > len(previous["text_en"]) else (previous, entry)
        keep = dict(keep)
        notes = list(keep.get("notes") or [])
        notes.append("той самий id мав коротший запис: " + _flat(drop["text_en"])[:160])
        keep["notes"] = notes
        best[key] = keep
    return list(best.values())


def save(folder: str, records: list[dict]) -> dict[str, int]:
    """Записи → JSONL у корпусах (канонічний формат)."""
    spec = compendium_format.load_spec()
    counters: dict[str, int] = {}
    by_corpus: dict[str, dict[str, list[dict]]] = {}
    canonical: list[dict] = []
    for entry in records:
        fixed, _ = compendium_format.canonicalize(entry, spec)
        canonical.append(fixed)
        corpus = spec.corpus_of(fixed["category"])
        by_corpus.setdefault(corpus, {}).setdefault(fixed["category"], []).append(fixed)
    for corpus, groups in by_corpus.items():
        directory = spec.corpus_dir(corpus) / folder
        directory.mkdir(parents=True, exist_ok=True)
        for category, items in groups.items():
            target = directory / f"{category}.jsonl"
            with target.open("w", encoding="utf-8") as handle:
                for item in items:
                    handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            counters[category] = len(items)
    counters["_total"] = len(canonical)
    return counters


def _norm_title(title: str) -> str:
    """Назва для порівняння: регістр, апострофи, пунктуація."""
    text = str(title or "").casefold()
    text = text.replace("’", "'").replace("‘", "'").replace("—", "-").replace("–", "-")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def owned_sources() -> dict[str, str]:
    """Код дзеркала → тека корпусу для книг, які вже розібрані.

    Коди різні (PHB → phb-2014, XGE → xgte, VRGR → vrgtr), тому єдиний
    надійний місток — назва книги: каталог дзеркала знає код і назву, реєстр
    джерел — теку й ту саму назву.
    """
    registry = _sources()
    catalogue = load_catalogue()
    by_title: dict[str, str] = {}
    for folder, meta in registry.items():
        title = meta.get("title")
        if isinstance(title, str) and title:
            by_title.setdefault(_norm_title(title), folder)
    owned: dict[str, str] = {}
    for code, entry in catalogue.items():
        folder = by_title.get(_norm_title(entry.get("name", "")))
        if folder:
            owned[code] = folder
    return owned


# Лінійка 2024+ — поза скоупом корпусу (edition=2014).
OTHER_EDITION = {
    "XPHB",
    "XDMG",
    "XMM",
    "XSAC",
    "XScreen",
    "FRHoF",
    "EFA",
    "RHW",
    "AU",
    "PL",
    "WoW",
    "LFL",
    "ABH",
    "NF",
    "FRAiF",
    "CaBoMP",
    "HFLotT",
    "AUD",
    "DDE",
    "ICC",
    "SoS",
    "RWG",
    "BQDD",
    "WttHC",
    "HotB",
    "HBTD",
    "BQGT",
    "DrDe-DaS",
    "DrDe-BD",
    "DrDe-TWoO",
    "DrDe-FWtVC",
    "DrDe-TDoN",
    "DrDe-TFV",
    "DrDe-BtS",
    "DrDe-SD",
    "DrDe-ACfaS",
    "DrDe-DotSC",
    "UtHftLH",
    "ScoEE",
    "LRDT",
    "FRAiF-TLLoL",
    "FFotR",
    "VNotEE",
    "HFStCM",
    "PaF",
    "TD",
    "DMTCRG",
}


def _present_names(folder: str, category: str) -> set[str]:
    """Назви записів цієї категорії, які вже лежать у теці книги."""
    spec = compendium_format.load_spec()
    path = spec.corpus_dir("compendium") / folder / f"{category}.jsonl"
    names: set[str] = set()
    if not path.exists():
        return names
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            names.add(_norm_title(json.loads(line).get("name_en", "")))
    return names


def missing_subclasses() -> dict[str, list[dict]]:
    """Підкласи дзеркала, яких немає в корпусі, згруповані за текою.

    Беремо лише лінійку 2014 і лише книги, які вже є в реєстрі. Записи, чиє
    ім'я в книзі вже є, пропускаємо: дзеркало тримає підклас двічі (редакція
    2014 і редакція 2024), а наша тека вже могла дістати його з іншого джерела.
    """
    owned = owned_sources()
    subclasses, features, feature_index = class_data()
    registry = _sources()
    catalogue = load_catalogue()
    present: dict[str, set[str]] = {folder: _present_names(folder, "subclass") for folder in set(owned.values())}
    grouped: dict[str, list[dict]] = {}
    for subclass in subclasses:
        source = subclass.get("source")
        if source in OTHER_EDITION:
            continue
        # Дзеркало тримає підклас двічі: друге входження — те саме вміння, але
        # з посиланням на клас редакції 2024 (classSource=XPHB) і з текстом
        # змінених умінь. Беремо лише редакцію 2014.
        if subclass.get("edition") == "one" or subclass.get("classSource") in OTHER_EDITION:
            continue
        folder = owned.get(str(source))
        if not folder:
            continue
        name = _clean_name(subclass.get("name"), subclass.get("source"))
        if _norm_title(name) in present.get(folder, set()):
            continue
        text = subclass_text(subclass, features, feature_index=feature_index)
        if len(text) < 60:
            continue
        meta = registry.get(folder) or {}
        grouped.setdefault(folder, []).append(
            record(
                folder=folder,
                category="subclass",
                name=name,
                text=text,
                data={
                    "class": str(subclass.get("className") or "").lower() or None,
                    "level": subclass_level(subclass, features),
                },
                license_value=meta.get("license", "proprietary"),
                url=book_url(folder, catalogue, registry),
                page=subclass.get("page"),
                fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            )
        )
        present.setdefault(folder, set()).add(_norm_title(name))
    return grouped


def missing_optional_features() -> dict[str, list[dict]]:
    """Опційні вміння дзеркала, яких немає в корпусі, згруповані за текою.

    `build_folder` дає їх лише тоді, коли книга має теку в дзеркалі. PHB, XGE
    і TCE таких тек не мають (вони в нас з D&D Beyond), а покажчик умінь
    дзеркала спільний для всіх книг — тому цим книгам їх дописує цей прохід,
    так само як підкласи. Лінійку 2024 (`XPHB`, `EFA`, `WoW`, `AU`) пропускаємо:
    корпус — це 2014.
    """
    owned = owned_sources()
    registry = _sources()
    catalogue = load_catalogue()
    present: dict[str, set[str]] = {
        folder: _present_names(folder, "optionalfeature") for folder in set(owned.values())
    }
    grouped: dict[str, list[dict]] = {}
    for feature in all_optional_features():
        source = feature.get("source")
        if source in OTHER_EDITION:
            continue
        folder = owned.get(str(source))
        if not folder:
            continue
        name = _clean_name(feature.get("name"), source)
        if _norm_title(name) in present.get(folder, set()):
            continue
        text = optionalfeature_text(feature)
        if len(text) < 20:
            continue
        meta = registry.get(folder) or {}
        grouped.setdefault(folder, []).append(
            record(
                folder=folder,
                category="optionalfeature",
                name=name,
                text=text,
                data=optionalfeature_data(feature),
                license_value=meta.get("license", "proprietary"),
                url=book_url(folder, catalogue, registry),
                page=feature.get("page"),
                fetched_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            )
        )
        present.setdefault(folder, set()).add(_norm_title(name))
    return grouped


def save_merge(folder: str, records: list[dict]) -> dict[str, int]:
    """Дописати записи до наявних JSONL книги (без перезапису наявного)."""
    spec = compendium_format.load_spec()
    counters: dict[str, int] = {}
    for entry in records:
        fixed, _ = compendium_format.canonicalize(entry, spec)
        corpus = spec.corpus_of(fixed["category"])
        directory = spec.corpus_dir(corpus) / folder
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{fixed['category']}.jsonl"
        existing: list[dict] = []
        if target.exists():
            for line in target.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    existing.append(json.loads(line))
        ids = {row.get("id") for row in existing}
        if fixed.get("id") in ids:
            continue
        existing.append(fixed)
        existing.sort(key=lambda row: str(row.get("id")))
        with target.open("w", encoding="utf-8") as handle:
            for row in existing:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        counters[fixed["category"]] = counters.get(fixed["category"], 0) + 1
    return counters


def parse_folders(folders: list[str], *, print_samples: int = 0) -> dict[str, dict[str, int]]:
    sources = _sources()
    catalogue = load_catalogue()
    mapping = folder_sources(folders)
    fetched_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    _, _, feature_index = class_data()
    report: dict[str, dict[str, int]] = {}
    for folder in folders:
        records = build_folder(
            folder,
            mapping=mapping,
            catalogue=catalogue,
            sources=sources,
            fetched_at=fetched_at,
            feature_index=feature_index,
        )
        counters = save(folder, records)
        report[folder] = counters
        summary = ", ".join(f"{key}={value}" for key, value in sorted(counters.items()))
        print(f"  {folder:14s} {summary}", flush=True)
        if print_samples:
            for entry in records[:print_samples]:
                print(f"\n--- {entry['id']} [{entry['category']}]")
                print(entry["text_en"][:600])
                print("data:", json.dumps(entry["data"], ensure_ascii=False))
    return report


def _sources() -> dict[str, dict]:
    import yaml

    payload = yaml.safe_load(config.SOURCES_FILE.read_text(encoding="utf-8"))
    return {entry["id"]: entry for entry in payload.get("sources") or []}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass

    parser = argparse.ArgumentParser(prog="scripts.ingest.mirror5e")
    parser.add_argument("--all", action="store_true", help="усі теки дзеркала")
    parser.add_argument("--folder", action="append", default=[], help="лише ця тека")
    parser.add_argument("--print", dest="show", type=int, default=0, help="показати перші N записів кожної теки")
    parser.add_argument("--list", action="store_true", help="лише перелік тек")
    parser.add_argument("--subclasses", action="store_true", help="добрати підкласи книг, які вже в корпусі")
    parser.add_argument(
        "--optionalfeatures", action="store_true", help="добрати опційні вміння книг, які вже в корпусі"
    )
    args = parser.parse_args(argv)

    if args.folder:
        folders = args.folder
    elif args.all:
        folders = mirror_folders()
    else:
        folders = pending_folders()
    if args.subclasses or args.optionalfeatures:
        grouped: dict[str, list[dict]] = {}
        if args.subclasses:
            for folder, records in missing_subclasses().items():
                grouped.setdefault(folder, []).extend(records)
        if args.optionalfeatures:
            for folder, records in missing_optional_features().items():
                grouped.setdefault(folder, []).extend(records)
        total = 0
        for folder, records in sorted(grouped.items()):
            counters = save_merge(folder, records)
            total += sum(counters.values())
            print(f"  {folder:14s} +{sum(counters.values())}")
        print(f"\nзаписів додано: {total}")
        return 0

    if args.list:
        for folder in folders:
            print(folder)
        return 0
    if not folders:
        print("немає тек для розбору")
        return 0

    print(f"тек: {len(folders)}")
    report = parse_folders(folders, print_samples=args.show)
    totals: dict[str, int] = {}
    for counters in report.values():
        for key, value in counters.items():
            if key.startswith("_"):
                continue
            totals[key] = totals.get(key, 0) + value
    print("\nразом: " + ", ".join(f"{key}={value}" for key, value in sorted(totals.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
