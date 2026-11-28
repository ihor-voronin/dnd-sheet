"""Каталог портретів: які є, як їх звати і які порадити персонажеві.

Портрет — це комбінація «група виду × стать × клас × варіант». Самі малюнки
робить `visuals.application.portraits` з цієї ж комбінації, тож каталог —
єдине джерело правди: id портрета однозначно задає, що на ньому.

Id стабільні (`elf-f-wizard-1`): їх зберігає лист персонажа, тож міняти
схему id можна лише разом з міграцією збережених листів.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cache

CLASSES: tuple[str, ...] = (
    "artificer",
    "barbarian",
    "bard",
    "cleric",
    "druid",
    "fighter",
    "monk",
    "paladin",
    "ranger",
    "rogue",
    "sorcerer",
    "warlock",
    "wizard",
)

CLASS_UK: dict[str, str] = {
    "artificer": "винахідник",
    "barbarian": "варвар",
    "bard": "бард",
    "cleric": "жрець",
    "druid": "друїд",
    "fighter": "воїн",
    "monk": "монах",
    "paladin": "паладин",
    "ranger": "слідопит",
    "rogue": "пройдисвіт",
    "sorcerer": "чародій",
    "warlock": "чорнокнижник",
    "wizard": "чарівник",
}

#: Стать персонажа: `female`, `male` або не вказано (None).
GENDERS: tuple[str, ...] = ("female", "male")
GENDER_UK: dict[str, str] = {"female": "жіноча", "male": "чоловіча"}

#: Стать на портреті: f/m — жіночий/чоловічий, x — без ознак статі (птахолюди, ворфорджі…).
_PORTRAIT_GENDER = {"female": "f", "male": "m"}

_ID = re.compile(r"^[a-z][a-z-]{1,24}-[fmx]-[a-z]{3,10}-[1-9]$")


@dataclass(frozen=True, slots=True)
class Group:
    """Група видів, що на портреті виглядають однаково (ельфи, дворфи, драконороджені…)."""

    key: str
    label: str
    #: Чи є на портретах жіночі й чоловічі варіанти; інакше — лише «x».
    gendered: bool
    #: Скільки варіантів на кожну пару «стать × клас».
    variants: int
    #: Підрядки англійських назв видів, що належать групі (`"half-elf"`, `"drow"`).
    species: tuple[str, ...]


# Порядок важливий: спершу вужчі назви («half-elf» раніше за «elf», «drow» раніше за «elf»).
GROUPS: tuple[Group, ...] = (
    Group("half-elf", "півельф", True, 2, ("half-elf",)),
    Group("half-orc", "піворк", True, 2, ("half-orc", "orc")),
    Group("drow", "дроу", True, 1, ("drow", "shadar-kai", "pallid")),
    Group("elf", "ельф", True, 2, ("elf", "eladrin")),
    Group("duergar", "дуергар", True, 1, ("duergar",)),
    Group("dwarf", "дворф", True, 2, ("dwarf",)),
    Group("halfling", "напіврослик", True, 2, ("halfling", "kender")),
    Group("gnome", "гном", True, 2, ("gnome",)),
    Group("tiefling", "тіфлінґ", True, 2, ("tiefling",)),
    Group("dragonborn", "драконороджений", False, 3, ("dragonborn",)),
    Group("aasimar", "аазімар", True, 1, ("aasimar",)),
    Group("goliath", "ґоліат", True, 1, ("goliath",)),
    Group("firbolg", "фірболґ", True, 1, ("firbolg",)),
    Group("genasi-fire", "ґеназі вогню", True, 1, ("fire genasi",)),
    Group("genasi-water", "ґеназі води", True, 1, ("water genasi",)),
    Group("genasi-air", "ґеназі повітря", True, 1, ("air genasi",)),
    Group("genasi-earth", "ґеназі землі", True, 1, ("earth genasi", "genasi")),
    Group("tabaxi", "табаксі", False, 2, ("tabaxi",)),
    Group("leonin", "леонін", True, 1, ("leonin",)),
    Group("kenku", "кенку", False, 1, ("kenku",)),
    Group("aarakocra", "ааракокра", False, 1, ("aarakocra",)),
    Group("owlin", "овлін", False, 1, ("owlin",)),
    Group("tortle", "тортл", False, 1, ("tortle",)),
    Group("lizardfolk", "ящіролюд", False, 1, ("lizardfolk", "troglodyte")),
    Group("kobold", "кобольд", False, 1, ("kobold",)),
    Group("warforged", "ворфордж", False, 2, ("warforged",)),
    Group("triton", "тритон", True, 1, ("triton", "sea elf", "merfolk", "locathah")),
    Group("gith", "ґіт", True, 1, ("gith",)),
    Group("hobgoblin", "хобґоблін", True, 1, ("hobgoblin",)),
    Group("bugbear", "бугбер", False, 1, ("bugbear",)),
    Group("goblin", "ґоблін", True, 1, ("goblin",)),
    Group("changeling", "чейнджлінг", False, 2, ("changeling",)),
    Group("minotaur", "мінотавр", False, 1, ("minotaur",)),
    Group("loxodon", "локсодон", False, 1, ("loxodon",)),
    Group("harengon", "харегон", True, 1, ("harengon",)),
    Group("satyr", "сатир", True, 1, ("satyr", "centaur")),
    Group("fairy", "фея", True, 1, ("fairy",)),
    Group("shifter", "перевертень", True, 1, ("shifter", "gnoll")),
    Group("yuan-ti", "юань-ті", True, 1, ("yuan-ti",)),
    Group("dhampir", "дгампір", True, 1, ("dhampir", "reborn", "zombie", "skeleton")),
    Group("hexblood", "гексблад", True, 1, ("hexblood",)),
    Group("vedalken", "ведалкен", True, 1, ("vedalken", "simic", "kalashtar", "verdan")),
    Group("human", "людина", True, 3, ("human",)),
)

GROUP_BY_KEY: dict[str, Group] = {group.key: group for group in GROUPS}


@dataclass(frozen=True, slots=True)
class Portrait:
    group: str
    gender: str  # f | m | x
    class_key: str
    variant: int

    @property
    def id(self) -> str:
        return f"{self.group}-{self.gender}-{self.class_key}-{self.variant}"

    @property
    def label(self) -> str:
        """Опис для `alt`: «Портрет: ельф, жіночий, чарівник (2)»."""
        group = GROUP_BY_KEY[self.group].label
        gender = {"f": "жіночий", "m": "чоловічий"}.get(self.gender)
        parts = [group, gender, CLASS_UK[self.class_key]] if gender else [group, CLASS_UK[self.class_key]]
        suffix = f" ({self.variant})" if self.variant > 1 else ""
        return "Портрет: " + ", ".join(parts) + suffix

    def as_dict(self) -> dict[str, str | int]:
        return {
            "id": self.id,
            "group": self.group,
            "gender": self.gender,
            "class": self.class_key,
            "variant": self.variant,
            "label": self.label,
        }


@cache
def all_portraits() -> tuple[Portrait, ...]:
    found: list[Portrait] = []
    for group in GROUPS:
        genders = ("f", "m") if group.gendered else ("x",)
        for gender in genders:
            for class_key in CLASSES:
                for variant in range(1, group.variants + 1):
                    found.append(Portrait(group.key, gender, class_key, variant))
    return tuple(found)


@cache
def _by_id() -> dict[str, Portrait]:
    return {portrait.id: portrait for portrait in all_portraits()}


def portrait(portrait_id: str) -> Portrait | None:
    return _by_id().get(portrait_id)


def is_known(portrait_id: str) -> bool:
    return portrait_id in _by_id()


def looks_like_id(value: str) -> bool:
    """Лише форма id — для домену, що не знає каталогу."""
    return bool(_ID.match(value))


def species_group(species_name: str | None) -> str | None:
    """Група за англійською назвою виду чи підраси: «Mountain Dwarf» → dwarf."""
    if not species_name:
        return None
    name = species_name.strip().casefold()
    for group in GROUPS:
        if any(token in name for token in group.species):
            return group.key
    return None


def recommend(
    *,
    species: str | None = None,
    class_key: str | None = None,
    gender: str | None = None,
    limit: int = 24,
) -> tuple[Portrait, ...]:
    """Портрети, які варто показати першими: свій вид, своя стать, свій клас.

    Порядок: вид+стать+клас → вид+стать (інші класи) → інші види того ж класу
    й статі. Без статі — обидві. Невідомий вид — одразу клас і стать.
    """
    group = species_group(species)
    wanted_gender = _PORTRAIT_GENDER.get(gender or "")
    klass = (class_key or "").strip().casefold() or None

    def gender_fits(item: Portrait) -> bool:
        return wanted_gender is None or item.gender in (wanted_gender, "x")

    tiers: list[list[Portrait]] = [[], [], []]
    for item in all_portraits():
        if not gender_fits(item):
            continue
        if group and item.group == group:
            tiers[0 if item.class_key == klass else 1].append(item)
        elif klass and item.class_key == klass and item.variant == 1:
            tiers[2].append(item)
    result: list[Portrait] = []
    for tier in tiers:
        for item in tier:
            if len(result) >= limit:
                return tuple(result)
            result.append(item)
    return tuple(result)
