"""Лист для друку: усе, що є на екрані, — українською й готовим до шаблону.

Джерело — той самий `_sheet_payload`, що й у вкладок листа, тож PDF не
розходиться з екраном: ті самі числа, переклади вмінь, заклять і предметів.
Тут лише приводимо дані до вигляду аркуша: підписи українською, англійська
назва поруч дрібно (правило «Українська (English)»), тексти правил — блоками
(абзаци, списки, таблиці), щоб шаблон не розбирав markdown.

Шаблон — `export/infrastructure/templates/character.html.jinja`.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Mapping

from dndsheet.characters.api import uk_text
from dndsheet.characters.api.species_traits import species_details
from dndsheet.compendium.application.service import CompendiumService
from dndsheet.compendium.domain.entry import Category
from dndsheet.compendium.domain.query import EntryQuery
from dndsheet.shared.kernel import SKILL_ABILITY, Ability, Skill
from dndsheet.sheets.domain.labels import (
    ALIGNMENT_LABELS,
    DEMO_ABILITIES,
    DEMO_SKILLS,
    LANGUAGE_LABELS,
    NOTE_LABELS,
)
from dndsheet.visuals.application import avatars

ABILITY_ORDER = (Ability.STR, Ability.DEX, Ability.CON, Ability.INT, Ability.WIS, Ability.CHA)
ABILITY_SHORT = {
    Ability.STR: "СИЛ",
    Ability.DEX: "СПР",
    Ability.CON: "СТА",
    Ability.INT: "ІНТ",
    Ability.WIS: "МУД",
    Ability.CHA: "ХАР",
}

_ALPHABET = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"


def uk_sort_key(text: str) -> tuple[int, ...]:
    """Українська абетка: «І» після «И», а не перед «А», як у кодовій таблиці."""
    return tuple(_ALPHABET.find(char) if char in _ALPHABET else 100 + ord(char) for char in text.casefold())


#: Навички за абеткою — як на паперовому аркуші.
SKILL_ORDER = sorted(Skill, key=lambda skill: uk_sort_key(DEMO_SKILLS[skill][0]))

#: Властивості зброї в примітках атак (коли примітка прийшла англійською).
WEAPON_PROPERTIES = {
    "versatile": "універсальна",
    "finesse": "фехтувальна",
    "light": "легка",
    "heavy": "важка",
    "thrown": "метальна",
    "two-handed": "дворучна",
    "reach": "досяжність",
    "loading": "перезаряджання",
    "ammunition": "боєприпаси",
    "special": "особлива",
    "range": "дальність",
}


def weapon_notes(text: str) -> str:
    value = text or ""
    for english, ukrainian in WEAPON_PROPERTIES.items():
        value = re.sub(rf"\b{re.escape(english)}\b", ukrainian, value, flags=re.IGNORECASE)
    return value[:1].upper() + value[1:] if value else value


DAMAGE_TYPES = {
    "acid": "кислота",
    "bludgeoning": "дробильний",
    "cold": "холод",
    "fire": "вогонь",
    "force": "силове поле",
    "lightning": "блискавка",
    "necrotic": "некротичний",
    "piercing": "колотий",
    "poison": "отрута",
    "psychic": "психічний",
    "radiant": "сяйво",
    "slashing": "рубаний",
    "thunder": "грім",
}

SCHOOLS = {
    "abjuration": "захисна",
    "conjuration": "виклик",
    "divination": "віщування",
    "enchantment": "чари",
    "evocation": "втілення",
    "illusion": "ілюзія",
    "necromancy": "некромантія",
    "transmutation": "перетворення",
}

TRAINING = {
    "light": "легка броня",
    "medium": "середня броня",
    "heavy": "важка броня",
    "shield": "щити",
    "simple": "проста зброя",
    "martial": "воєнна зброя",
}

TOOLS = {
    "thieves' tools": "злодійські інструменти",
    "vehicles (land)": "транспорт (наземний)",
    "vehicles (water)": "транспорт (водний)",
    "cartographer's tools": "інструменти картографа",
    "navigator's tools": "інструменти навігатора",
    "smith's tools": "інструменти коваля",
    "tinker's tools": "інструменти майстра",
    "carpenter's tools": "інструменти теслі",
    "mason's tools": "інструменти муляра",
    "jeweler's tools": "інструменти ювеліра",
    "potter's tools": "інструменти гончара",
    "weaver's tools": "інструменти ткача",
    "woodcarver's tools": "інструменти різьбяра",
    "leatherworker's tools": "інструменти кожумʼяки",
    "glassblower's tools": "інструменти склодува",
    "cobbler's tools": "інструменти шевця",
    "alchemist's supplies": "приладдя алхіміка",
    "brewer's supplies": "приладдя пивовара",
    "calligrapher's supplies": "приладдя каліграфа",
    "painter's supplies": "приладдя художника",
    "cook's utensils": "кухонне приладдя",
    "disguise kit": "набір для маскування",
    "forgery kit": "набір для підробок",
    "herbalism kit": "набір травника",
    "poisoner's kit": "набір отруйника",
    "gaming set": "ігровий набір",
    "dice set": "набір кісток",
    "playing card set": "набір гральних карт",
    "dragonchess set": "набір драконячих шахів",
    "three-dragon ante set": "набір «Три дракони»",
    "musical instrument": "музичний інструмент",
}

ITEM_KINDS = {
    "weapon": "зброя",
    "armor": "броня",
    "shield": "щит",
    "gear": "речі",
    "tool": "інструмент",
    "pack": "набір",
    "magic": "магічне",
    "consumable": "витратне",
}

#: Назва в тексті книги → назва запису довідника (таблиці SRD): «Leather Armor» → «Leather».
ITEM_ALIASES = {
    "leather armor": "leather",
    "studded leather armor": "studded leather",
    "padded armor": "padded",
    "hide armor": "hide",
    "half plate armor": "half plate",
    "plate armor": "plate",
    "splint armor": "splint",
    "light crossbow": "crossbow, light",
    "hand crossbow": "crossbow, hand",
    "heavy crossbow": "crossbow, heavy",
}

#: Спорядження, якого в довіднику предметів немає (набори, осередки) — як на екрані.
GEAR_UK = {
    "explorer's pack": "Набір дослідника",
    "priest's pack": "Набір священника",
    "burglar's pack": "Набір зломщика",
    "diplomat's pack": "Набір дипломата",
    "entertainer's pack": "Набір артиста",
    "scholar's pack": "Набір учня",
    "dungeoneer's pack": "Набір підземельника",
    "arcane focus": "Арканний осередок",
    "druidic focus": "Друїдичний осередок",
    "holy symbol": "Священний символ",
    "component pouch": "Сумка для компонентів",
}

#: Атаки без предмета в довіднику.
SPECIAL_NAMES = {
    "unarmed strike": "Удар без зброї",
    "claws": "Кігті",
    "bite": "Укус",
    "horns": "Роги",
    "hooves": "Копита",
    "talons": "Пазурі",
}

#: Закляття не з класу: група на сторінці заклять мультикласу.
OTHER_SOURCES = {
    "src:species": "Від виду",
    "src:subclass": "Від підкласу",
    "src:feat": "Від риси",
    "src:fighting-style": "Від бойового стилю",
    "src:invocation": "Містичні виклики",
    "src:pact-boon": "Дар угоди",
    "src:secrets": "Магічні таємниці",
    "src:feature": "Від уміння",
    # Власні закляття поза класом (дар майстра, предмет).
    "other": "Власні, поза класом",
}

COINS = (("pp", "пм"), ("gp", "зм"), ("ep", "ем"), ("sp", "см"), ("cp", "мм"))

#: Особливості виду, які аркуш уже показує числами (характеристики, швидкість, мови).
_MECHANICAL_TRAITS = {
    "ability score increase",
    "age",
    "alignment",
    "size",
    "speed",
    "languages",
    "subrace",
    "creature type",
}

_UNITS = (
    (r"\bbonus action\b", "бонусна дія"),
    (r"\bactions\b", "дії"),
    (r"\baction\b", "дія"),
    (r"\breaction\b", "реакція"),
    (r"\bminutes?\b", "хв"),
    (r"\bhours?\b", "год"),
    (r"\bdays?\b", "дн"),
    (r"\bseconds?\b", "с"),
    (r"\brounds?\b", "раунд"),
    (r"\bfeet\b", "фт"),
    (r"\bfoot\b", "фт"),
    (r"\bmiles?\b", "миля"),
    (r"\bSelf\b", "на себе"),
    (r"\bTouch\b", "дотик"),
    (r"\bSight\b", "видиме"),
    (r"\bUnlimited\b", "без обмежень"),
    (r"\bInstantaneous\b", "миттєво"),
    (r"\bConcentration\b", "концентрація"),
    (r"\bup to\b", "до"),
    (r"\buntil dispelled\b", "до розвіювання"),
    (r"\bcone\b", "конус"),
    (r"\bsphere\b", "сфера"),
    (r"\bradius\b", "радіус"),
    (r"\bcube\b", "куб"),
    (r"\bcylinder\b", "циліндр"),
    (r"\bline\b", "лінія"),
    (r"\bSpecial\b", "особлива"),
)


def units(text: str | None) -> str:
    """«1 bonus action», «30 feet», «Concentration, up to 1 minute» — українською."""
    value = (text or "").strip()
    for pattern, replacement in _UNITS:
        value = re.sub(pattern, replacement, value, flags=re.IGNORECASE)
    return value


def components_short(raw: str | None) -> str:
    """«V, S, M (a pinch of salt)» → «В, С, М»: подробиці матеріалу — у розширеному листі."""
    letters = re.sub(r"\([^)]*\)", "", raw or "")
    mapping = {"V": "В", "S": "С", "M": "М"}
    return ", ".join(mapping.get(part.strip(), part.strip()) for part in letters.split(",") if part.strip())


def signed(value: int | float | None) -> str:
    if value is None:
        return "—"
    number = int(value)
    return f"+{number}" if number >= 0 else f"−{abs(number)}"


def damage_text(raw: str | None) -> str:
    """«1d8+3 slashing» → «1d8+3 рубаний»; кілька типів через «+» теж."""
    text = (raw or "").strip()
    for english, ukrainian in DAMAGE_TYPES.items():
        text = re.sub(rf"\b{english}\b", ukrainian, text, flags=re.IGNORECASE)
    return text.replace("-", "−") if re.match(r"^\d+d\d+-\d", text) else text


# ---------------------------------------------------------------------------
# тексти правил: абзаци, списки, таблиці
# ---------------------------------------------------------------------------

_LEVEL_LINE = re.compile(r"^\*\d+(?:st|nd|rd|th)-level .*\*$", re.IGNORECASE)


def _clean(text: str) -> str:
    return text.replace("**", "").replace("*", "").strip()


def rule_blocks(text: str | None) -> list[dict[str, Any]]:
    """Текст правила як блоки: `p`, `h`, `ul`, `table` — той самий розбір, що й `RuleText` на екрані."""
    blocks: list[dict[str, Any]] = []
    for raw in re.split(r"\n{2,}", (text or "").strip()):
        block = raw.strip()
        if not block:
            continue
        lines = [line.strip() for line in block.split("\n")]
        heading = re.match(r"^#{2,5}\s+(.+)$", block)
        if heading:
            blocks.append({"kind": "h", "text": _clean(heading.group(1))})
            continue
        table = _table(lines)
        if table is not None:
            blocks.append({"kind": "table", **table})
            continue
        if all(line.startswith(("- ", "• ")) for line in lines):
            blocks.append({"kind": "ul", "items": [_clean(line[2:]) for line in lines]})
            continue
        lead = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", block, re.DOTALL)
        if lead and lead.group(2):
            blocks.append({"kind": "p", "lead": _clean(lead.group(1)), "text": _clean(lead.group(2))})
            continue
        if _LEVEL_LINE.match(block):
            blocks.append({"kind": "p", "text": _clean(block), "muted": True})
            continue
        blocks.append({"kind": "p", "text": _clean(" ".join(lines))})
    return blocks


def _table(lines: list[str]) -> dict[str, Any] | None:
    rows = [line for line in lines if line]
    if len(rows) < 2 or not all(line.startswith("|") and line.endswith("|") for line in rows):
        return None
    cells = [[cell.strip() for cell in line[1:-1].split("|")] for line in rows]
    if not all(re.match(r"^:?-{2,}:?$", cell) for cell in cells[1]):
        return None
    return {
        "header": [_clean(cell) for cell in cells[0]],
        "rows": [[_clean(cell) for cell in row] for row in cells[2:]],
    }


# ---------------------------------------------------------------------------
# збирання
# ---------------------------------------------------------------------------


def build_print_view(
    sheet: Mapping[str, Any],
    *,
    compendium: CompendiumService,
    display_name: Callable[[str], str],
    species_parent: str | None = None,
    species_cache: dict[str, Any] | None = None,
    feat_titles: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    character = sheet["character"]
    item_names = uk_text.read("items").get("names", {})

    def item_name(name_en: str, entry_id: str | None = None) -> dict[str, str]:
        uk = (item_names.get(entry_id) if entry_id else None) or _item_by_name(name_en)
        return _pair(name_en, uk)

    by_name = {
        str(item.get("name_en", "")).casefold(): item.get("entry_id")
        for item in sheet["inventory"]["items"]
        if item.get("entry_id")
    }

    def _item_by_name(name_en: str) -> str | None:
        lowered = name_en.casefold()
        if lowered in SPECIAL_NAMES:
            return SPECIAL_NAMES[lowered]
        if lowered in GEAR_UK:
            return GEAR_UK[lowered]
        name_en = ITEM_ALIASES.get(lowered, name_en)
        entry_id = by_name.get(name_en.casefold())
        if entry_id is None:
            # Предмет без запису в інвентарі (атака еталону, природна зброя):
            # шукаємо в довіднику точну назву — пошук ставить її першою.
            found = compendium.entries(EntryQuery(category=Category.ITEM, q=name_en, limit=3)).items
            entry_id = next((entry.id for entry in found if entry.name_en.casefold() == name_en.casefold()), None)
        return item_names.get(entry_id) if entry_id else None

    classes = character["classes"]
    class_line = " / ".join(f"{_uk(display_name(entry['name_en']))} {entry['level']}" for entry in classes)
    subclasses = [
        entry.get("subclass_name_uk") or entry.get("subclass_name") or entry["subclass"].rsplit("/", 1)[-1]
        for entry in classes
        if entry.get("subclass")
    ]
    species = character.get("species") or {}
    species_name = species.get("name_en") or ""
    background = sheet.get("background_details") or {}
    alignment = character.get("alignment")

    view: dict[str, Any] = {
        "name": character["name"],
        # Портрет у шапці аркуша: світла версія, вбудована в сторінку.
        "portrait": avatars.paper_data_uri(str((character.get("portrait") or {}).get("id") or "")),
        "header": [
            {"label": "Клас і рівень", "value": class_line or "—", "small": ", ".join(subclasses)},
            {"label": "Вид", "value": _uk(display_name(species_name)) if species_name else "—", "small": species_name},
            {
                "label": "Передісторія",
                "value": background.get("name_uk") or (character.get("background") or {}).get("name_en") or "—",
                "small": background.get("name_en") or "",
            },
            {
                "label": "Світогляд",
                "value": ALIGNMENT_LABELS.get(alignment, (alignment or "—", ""))[0] if alignment else "—",
                "small": "",
            },
            {"label": "Рівень персонажа", "value": str(character["total_level"]), "small": ""},
        ],
        "proficiency_bonus": signed(sheet["proficiency_bonus"]),
        "inspiration": bool(sheet["state"].get("inspiration")),
        "abilities": [
            {
                "name": DEMO_ABILITIES[ability][0],
                "short": ABILITY_SHORT[ability],
                "score": sheet["abilities"][ability.value]["total"],
                "mod": signed(sheet["abilities"][ability.value]["modifier"]),
            }
            for ability in ABILITY_ORDER
        ],
        "saves": [
            {
                "name": DEMO_ABILITIES[ability][0],
                "value": signed(sheet["saving_throws"][ability.value]["value"]),
                "proficient": sheet["saving_throws"][ability.value]["proficient"],
            }
            for ability in ABILITY_ORDER
        ],
        "skills": [
            {
                "name": DEMO_SKILLS[skill][0],
                "ability": ABILITY_SHORT[SKILL_ABILITY[skill]],
                "value": signed(sheet["skills"][skill.value]["value"]),
                "proficient": sheet["skills"][skill.value]["proficient"],
                "expertise": sheet["skills"][skill.value].get("expertise", False),
                "disadvantage": sheet["skills"][skill.value].get("disadvantage", False),
            }
            for skill in SKILL_ORDER
        ],
        "passives": [
            ("Спостережливість", sheet["passive_perception"]),
            ("Проникливість", sheet["passive_insight"]),
            ("Розслідування", sheet["passive_investigation"]),
        ],
        "combat": _combat(sheet),
        "senses": _senses(sheet),
        "attacks": [
            {
                **item_name(attack["name_en"]),
                "bonus": signed(attack.get("attack_bonus")) if attack.get("attack_bonus") is not None else "—",
                "damage": damage_text(attack.get("damage")),
                "range": units(attack.get("range")),
                "notes": weapon_notes(attack.get("notes") or ""),
            }
            for attack in sheet.get("attacks", [])
        ],
        "attacks_per_action": sheet.get("attacks_per_action", 1),
        "resources": [
            {
                **_pair(resource["name_en"], resource.get("name_uk")),
                "total": resource["total"],
                "used": resource["used"],
                "recharge": "короткий відпочинок" if resource["recharge"] == "short" else "тривалий відпочинок",
                "boxes": resource["total"] <= 12,
            }
            for resource in sheet.get("feature_resources", [])
        ],
        "proficiencies": _proficiencies(sheet.get("proficiencies", []), item_name),
        "features": _features(sheet, display_name, feat_titles or {}),
        "species_traits": _species_traits(compendium, species_name, species_parent, species_cache),
        "background": _background(background),
        "spellcasting": _spellcasting(sheet, display_name, compendium),
        "inventory": _inventory(sheet, item_name),
        "notes": _notes(sheet["state"].get("notes") or {}),
    }
    return view


def _uk(label: str) -> str:
    """«Чаклун (Warlock)» → «Чаклун»: англійська на аркуші йде окремим дрібним рядком."""
    match = re.match(r"^(.*?)\s*\(([^()]*)\)$", label)
    return match.group(1) if match and match.group(1) else label


def _pair(name_en: str, uk: str | None) -> dict[str, str]:
    # Ключі предметів у старих записах — малими літерами («chain mail»).
    if name_en and name_en == name_en.lower():
        name_en = " ".join(word[:1].upper() + word[1:] for word in name_en.split(" "))
    uk_clean = (uk or "").strip()
    if not uk_clean or uk_clean.casefold() == name_en.casefold():
        return {"title": name_en, "en": ""}
    return {"title": uk_clean, "en": name_en}


def _combat(sheet: Mapping[str, Any]) -> dict[str, Any]:
    hp = sheet["hit_points"]
    dice = sheet["resources"].get("hit_dice") or {}
    return {
        "ac": sheet["armor_class"]["value"],
        "ac_parts": " + ".join(f"{part['label']} {part['value']}" for part in sheet["armor_class"].get("parts", [])),
        "initiative": signed(sheet["initiative"]),
        "speed": sheet["speed"],
        "hp_max": hp["maximum"],
        "hp_current": hp["current"],
        "hp_temp": hp.get("temporary") or 0,
        "hit_dice": " + ".join(f"{info['total']}{die}" for die, info in dice.items()),
        "hit_dice_left": " + ".join(f"{info['total'] - info['used']}{die}" for die, info in dice.items()),
        "death_successes": sheet["state"]["death_saves"].get("successes", 0),
        "death_failures": sheet["state"]["death_saves"].get("failures", 0),
        "exhaustion": sheet["state"].get("exhaustion", 0),
    }


def _senses(sheet: Mapping[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if sheet.get("darkvision"):
        rows.append(("Темний зір", f"{sheet['darkvision']} фт"))
    if sheet.get("blindsight"):
        rows.append(("Сліпе чуття", f"{sheet['blindsight']} фт"))
    if sheet.get("resistances"):
        rows.append(("Опір", ", ".join(DAMAGE_TYPES.get(value, value) for value in sheet["resistances"])))
    for note in sheet.get("resistance_notes", []) + sheet.get("roll_notes", []):
        text = note.get("text") if isinstance(note, Mapping) else str(note)
        if text:
            rows.append(("Примітка", text))
    return rows


def _proficiencies(
    rows: Iterable[Mapping[str, Any]], item_name: Callable[..., dict[str, str]]
) -> list[tuple[str, str]]:
    groups: dict[str, list[str]] = {"armor": [], "weapon": [], "tool": [], "language": []}
    for row in rows:
        kind = row.get("kind")
        if kind not in groups:
            continue
        value = str(row.get("value", "")).strip()
        key = value.casefold()
        if kind == "language":
            label = LANGUAGE_LABELS.get(key, (value, ""))[0]
        elif kind == "tool":
            label = TOOLS.get(key, value)
        else:
            label = TRAINING.get(key) or _weapon_label(value, item_name)
        if label not in groups[kind]:
            groups[kind].append(label)
    titles = {"armor": "Броня", "weapon": "Зброя", "tool": "Інструменти", "language": "Мови"}
    return [(titles[kind], ", ".join(values)) for kind, values in groups.items() if values]


def _weapon_label(value: str, item_name: Callable[..., dict[str, str]]) -> str:
    """Володіння конкретною зброєю: «quarterstaffs» у класу — це «quarterstaff» у довіднику."""
    for candidate in (value, value[:-1] if value.endswith("s") else value):
        pair = item_name(candidate.title())
        if pair["en"]:
            return pair["title"].lower()
    return value


def _features(
    sheet: Mapping[str, Any], display_name: Callable[[str], str], feat_titles: Mapping[str, str]
) -> list[dict[str, Any]]:
    """Уміння класів (за класом і рівнем) і риси — з текстами."""
    groups: dict[str, dict[str, Any]] = {}
    for feature in sheet.get("features", []):
        group_title = _uk(display_name(feature.get("class_name") or "")) or "Уміння"
        group = groups.setdefault(group_title, {"title": group_title, "items": []})
        group["items"].append(
            {
                **_pair(feature["name_en"], feature.get("name_uk")),
                "meta": f"{feature['level']} рівень" if feature.get("level") else "",
                "blocks": rule_blocks(feature.get("text_uk") or feature.get("description")),
            }
        )
    feats = [
        {
            **_pair(feat.get("name_en", ""), feat.get("name_uk")),
            "meta": "риса",
            "blocks": rule_blocks(feat.get("description_uk") or feat.get("description")),
        }
        for feat in sheet.get("feat_details", [])
    ]
    result = list(groups.values())
    if feats:
        result.append({"title": "Риси", "items": feats})
    custom = [
        {
            "title": feature.get("name") or "",
            "en": "",
            "meta": _custom_feature_meta(feature),
            "blocks": rule_blocks(feature.get("text")),
        }
        for feature in sheet.get("custom_features", [])
    ]
    if custom:
        result.append({"title": "Власні вміння", "items": custom})
    choices = [
        {
            "title": choice.get("title_uk") or choice.get("title") or choice.get("label") or "",
            "en": "",
            "meta": "вибір",
            "blocks": [{"kind": "p", "text": ", ".join(_choice_values(choice))}],
        }
        for choice in sheet.get("class_choices", [])
        if _choice_values(choice)
    ]
    if choices:
        result.append({"title": "Вибори класу", "items": choices})
    return result


def _custom_feature_meta(feature: Mapping[str, Any]) -> str:
    """«власне · дар майстра · 3 рівень · 2 / короткий відпочинок»."""
    parts = ["власне"]
    if feature.get("origin"):
        parts.append(str(feature["origin"]))
    if feature.get("level"):
        parts.append(f"{feature['level']} рівень")
    if feature.get("uses"):
        rest = "короткий відпочинок" if feature.get("recharge") == "short" else "тривалий відпочинок"
        parts.append(f"{feature['uses']} / {rest}")
    return " · ".join(parts)


def _choice_values(choice: Mapping[str, Any]) -> list[str]:
    values = choice.get("chosen_labels") or choice.get("chosen") or []
    return [str(value) for value in values if value]


def _species_traits(
    compendium: CompendiumService,
    species_name: str,
    parent: str | None,
    cache: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not species_name:
        return []
    details = species_details(compendium, species_name, parent_name_en=parent, cache=cache)
    traits = []
    for trait in (details or {}).get("traits") or []:
        name_en = str(trait.get("name_en") or "")
        if name_en.strip().casefold() in _MECHANICAL_TRAITS:
            continue
        traits.append(
            {
                **_pair(name_en, trait.get("name_uk")),
                "meta": "вид",
                "blocks": rule_blocks(trait.get("text_uk") or trait.get("text")),
            }
        )
    return traits


def _background(details: Mapping[str, Any]) -> dict[str, Any] | None:
    if not details:
        return None
    feature_en = details.get("feature_en") or ""
    return {
        **_pair(details.get("name_en") or "", details.get("name_uk")),
        "description": rule_blocks(details.get("description_uk") or details.get("description")),
        "feature": _pair(feature_en, details.get("feature_uk")) if feature_en else None,
        "feature_text": rule_blocks(details.get("feature_text_uk") or details.get("feature_text")),
    }


def _book_spell_name(compendium: CompendiumService, name: str) -> str:
    """Назва закляття як у книзі: доменні закляття приходять ключем («beacon of hope»)."""
    found = compendium.entries(EntryQuery(category=Category.SPELL, q=name, limit=5)).items
    return next((entry.name_en for entry in found if entry.name_en.casefold() == name.casefold()), name)


def _spellcasting(
    sheet: Mapping[str, Any], display_name: Callable[[str], str], compendium: CompendiumService
) -> dict[str, Any] | None:
    casting = sheet.get("spellcasting") or {}
    spells = sheet.get("spells") or []
    classes = casting.get("classes") or []
    pact_slots = (casting.get("slots") or {}).get("pact") or {}
    pact = (
        {"total": pact_slots.get("slots", 0), "level": pact_slots.get("level", 0)} if pact_slots.get("slots") else None
    )
    if not spells and not classes and not pact:
        return None
    slots_state = (sheet.get("resources") or {}).get("slots") or {}
    slots = [
        {"level": int(level), "total": info["total"], "used": info.get("used", 0)}
        for level, info in sorted(slots_state.items(), key=lambda pair: int(pair[0]))
        if info.get("total")
    ]
    preparers = {entry.get("key") for entry in classes if entry.get("prepares")}
    by_level: dict[int, list[dict[str, Any]]] = {}
    for spell in spells:
        level = int(spell.get("level") or 0)
        name_en = spell["name_en"]
        custom = bool(spell.get("custom"))
        # Власне закляття назвав гравець: ні перекладу, ні пошуку в книзі.
        uk_name = None if custom else uk_text.name_uk("spells", name_en)
        if uk_name is None and not custom:
            # Заговори виду й доменні закляття записані ключем («thaumaturgy»,
            # «beacon of hope») — беремо назву з книги, за нею й переклад.
            name_en = _book_spell_name(compendium, name_en)
            uk_name = uk_text.name_uk("spells", name_en)
        tags = ["власне"] if custom else []
        if spell.get("concentration"):
            tags.append("конц.")
        if spell.get("ritual"):
            tags.append("рит.")
        higher = spell.get("at_higher_levels_uk") or spell.get("at_higher_levels") or ""
        by_level.setdefault(level, []).append(
            {
                **_pair(name_en, uk_name),
                "prepared": bool(spell.get("prepared") or spell.get("always_prepared")),
                "always": bool(spell.get("always_prepared")),
                # Позначка підготовки має сенс лише для класів, що готують (жрець, маг…).
                "preparable": spell.get("class_key") in preparers and spell.get("source", "class") == "class",
                "school": SCHOOLS.get(str(spell.get("school") or "").casefold(), spell.get("school") or ""),
                "time": units((spell.get("casting_time") or "").split(",")[0]),
                "range": units(spell.get("range")),
                "duration": units(spell.get("duration")),
                "components": spell.get("components") or "",
                "components_short": components_short(spell.get("components")),
                "tags": " ".join(tags),
                "class": (
                    _uk(display_name(spell.get("class_key", "").title()))
                    if spell.get("class_key") and spell.get("class_key") != "other"
                    else ""
                ),
                "group": spell.get("class_key") or f"src:{spell.get('source') or 'other'}",
                "blocks": rule_blocks(spell.get("description_uk") or spell.get("description")),
                "higher": rule_blocks(
                    re.sub(
                        r"^\s*(?:\*\*)?(?:At Higher Levels|На вищих рівнях)\.(?:\*\*)?\s*",
                        "",
                        higher,
                        flags=re.IGNORECASE,
                    )
                ),
            }
        )
    # У мультикласі закляття групуються за класом усередині рівня: від класу
    # залежать складність рятівного кидка й бонус атаки (PHB, p. 164).
    order = [entry.get("key") for entry in classes]
    info = {
        entry.get("key"): {
            "title": _uk(display_name(entry.get("name_en") or "")),
            "dc": entry.get("save_dc"),
            "attack": signed(entry.get("attack_bonus")),
        }
        for entry in classes
    }

    def group_rank(key: str) -> tuple[int, str]:
        return (order.index(key), "") if key in order else (len(order), key)

    levels = []
    for level, rows in sorted(by_level.items()):
        rows = sorted(rows, key=lambda row: uk_sort_key(row["title"]))
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault(row["group"], []).append(row)
        levels.append(
            {
                "level": level,
                "title": "Заговори" if level == 0 else f"{level} рівень",
                "spells": rows,
                "groups": [
                    {
                        "key": key,
                        **(
                            info.get(key)
                            or {"title": OTHER_SOURCES.get(key, "Інші джерела"), "dc": None, "attack": None}
                        ),
                        "spells": groups[key],
                    }
                    for key in sorted(groups, key=group_rank)
                ],
            }
        )
    return {
        "classes": [
            {
                "name": _uk(display_name(entry.get("name_en") or "")),
                "ability": DEMO_ABILITIES[Ability(entry["ability"])][0] if entry.get("ability") else "—",
                "dc": entry.get("save_dc"),
                "attack": signed(entry.get("attack_bonus")),
                "mode": "готує" if entry.get("prepares") else "знає",
                "limit": entry.get("prepared_limit") or entry.get("spells_known_limit"),
                "cantrips": entry.get("cantrips_limit"),
            }
            for entry in classes
        ],
        "slots": slots,
        "pact": pact,
        "levels": levels,
    }


def _inventory(sheet: Mapping[str, Any], item_name: Callable[..., dict[str, str]]) -> dict[str, Any]:
    inventory = sheet.get("inventory") or {}
    items = []
    for item in inventory.get("items", []):
        marks = []
        if item.get("equipped"):
            marks.append("вдягнено" if item.get("kind") in {"armor", "shield"} else "у руках")
        if item.get("attuned"):
            marks.append("настроєно")
        if item.get("pact_weapon"):
            marks.append("зброя угоди")
        notes = str(item.get("notes") or "")
        notes = re.sub(r"^від (класу|передісторії)( · )?", "", notes).strip()
        items.append(
            {
                **(
                    {"title": item["name_uk"], "en": ""}
                    if item.get("name_uk")
                    else item_name(item["name_en"], item.get("entry_id"))
                ),
                "kind": ITEM_KINDS.get(item.get("kind", ""), item.get("kind", "")),
                "quantity": item.get("quantity", 1),
                "weight": item.get("weight_lb") or 0,
                "marks": ", ".join(marks),
                "notes": notes,
            }
        )
    money = inventory.get("money") or {}
    carrying = sheet.get("carrying") or {}
    return {
        "items": items,
        "coins": [(label, money.get(code, 0)) for code, label in COINS],
        "weight": round(float(carrying.get("weight") or 0), 1),
        "capacity": carrying.get("capacity"),
    }


def _notes(notes: Mapping[str, str]) -> list[dict[str, Any]]:
    order = ("appearance", "backstory", "allies", "enemies", "notes")
    # «Передісторія» на аркуші — це вже background; нотатка «backstory» — історія героя.
    titles = {"backstory": "Історія персонажа", "allies": "Союзники й організації"}
    rows = []
    for key in order:
        rows.append(
            {
                "title": titles.get(key) or NOTE_LABELS.get(key, (key, ""))[0],
                "blocks": rule_blocks(notes.get(key, "")),
                "key": key,
            }
        )
    for key, text in notes.items():
        if key not in order and text:
            rows.append({"title": NOTE_LABELS.get(key, (key, ""))[0], "blocks": rule_blocks(text), "key": key})
    return rows
