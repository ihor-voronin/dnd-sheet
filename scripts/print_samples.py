"""Заклинателі середніх рівнів для перевірки сторінки заклять у PDF.

Маг 4 (книга заклять, підготовка), чаклун 5 (магія угоди, комірки 3 рівня),
жрець 5 (доменні закляття завжди підготовлені, комірки 1–3 рівнів). Персонажі
збираються прямо з домену — як еталонні (`golden`), лише з більшими рівнями.
"""

from __future__ import annotations

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.inventory import Inventory, InventoryItem, ItemKind
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiencies,
    Proficiency,
    ProficiencyKind,
    SourceKind,
)
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.shared.kernel import Ability, AbilityScore, Money, Skill


def _scores(**values: int) -> dict[Ability, AbilityScore]:
    return {Ability(name): AbilityScore(value) for name, value in values.items()}


def _skills(class_key: str, *skills: Skill) -> Proficiencies:
    return Proficiencies(
        items=tuple(
            Proficiency(
                kind=ProficiencyKind.SKILL, value=skill.value, source=GrantSource.of(SourceKind.CLASS, class_key)
            )
            for skill in skills
        )
    )


def _spells(class_key: str, rows: list[tuple[str, int, str]], **flags: bool) -> tuple[KnownSpell, ...]:
    return tuple(
        KnownSpell(
            name_en=name,
            level=level,
            class_key=class_key,
            entry_id=f"phb-2014/spell/{slug}",
            **flags,
        )
        for name, level, slug in rows
    )


def wizard_4(rules) -> Character:  # noqa: ANN001
    cantrips = _spells(
        "wizard",
        [
            ("Fire Bolt", 0, "fire-bolt"),
            ("Mage Hand", 0, "mage-hand"),
            ("Light", 0, "light"),
            ("Prestidigitation", 0, "prestidigitation"),
        ],
    )
    prepared = _spells(
        "wizard",
        [
            ("Magic Missile", 1, "magic-missile"),
            ("Shield", 1, "shield"),
            ("Mage Armor", 1, "mage-armor"),
            ("Sleep", 1, "sleep"),
            ("Misty Step", 2, "misty-step"),
            ("Scorching Ray", 2, "scorching-ray"),
            ("Hold Person", 2, "hold-person"),
        ],
        prepared=True,
    )
    book = _spells(
        "wizard", [("Detect Magic", 1, "detect-magic"), ("Find Familiar", 1, "find-familiar"), ("Web", 2, "web")]
    )
    return Character(
        id="sample-wizard-4",
        name="Ілара Сріблоока",
        abilities=_scores(str=8, dex=14, con=14, int=17, wis=12, cha=10),
        rules=rules,
        species_key="human",
        background_key="sage",
        classes=[CharacterClass(class_key="wizard", level=4, subclass_key="phb-2014/subclass/school-of-evocation")],
        chosen=_skills("wizard", Skill.ARCANA, Skill.INVESTIGATION),
        spells=cantrips + prepared + book,
        inventory=Inventory(
            items=(InventoryItem(name_en="quarterstaff", kind=ItemKind.WEAPON, weight_lb=4),), money=Money(gp=40)
        ),
    )


def warlock_5(rules) -> Character:  # noqa: ANN001
    cantrips = _spells(
        "warlock",
        [
            ("Eldritch Blast", 0, "eldritch-blast"),
            ("Mage Hand", 0, "mage-hand"),
            ("Minor Illusion", 0, "minor-illusion"),
        ],
    )
    known = _spells(
        "warlock",
        [
            ("Hex", 1, "hex"),
            ("Armor of Agathys", 1, "armor-of-agathys"),
            ("Misty Step", 2, "misty-step"),
            ("Hold Person", 2, "hold-person"),
            ("Hunger of Hadar", 3, "hunger-of-hadar"),
            ("Counterspell", 3, "counterspell"),
        ],
    )
    return Character(
        id="sample-warlock-5",
        name="Морвен Попелиця",
        abilities=_scores(str=8, dex=14, con=14, int=10, wis=12, cha=18),
        rules=rules,
        species_key="tiefling",
        background_key="charlatan",
        classes=[CharacterClass(class_key="warlock", level=5, subclass_key="phb-2014/subclass/the-fiend")],
        chosen=_skills("warlock", Skill.ARCANA, Skill.INTIMIDATION),
        spells=cantrips + known,
        inventory=Inventory(
            items=(InventoryItem(name_en="light crossbow", kind=ItemKind.WEAPON, weight_lb=5),), money=Money(gp=60)
        ),
    )


def cleric_5(rules) -> Character:  # noqa: ANN001
    cantrips = _spells(
        "cleric",
        [
            ("Sacred Flame", 0, "sacred-flame"),
            ("Guidance", 0, "guidance"),
            ("Spare the Dying", 0, "spare-the-dying"),
            ("Light", 0, "light"),
        ],
    )
    prepared = _spells(
        "cleric",
        [
            ("Guiding Bolt", 1, "guiding-bolt"),
            ("Healing Word", 1, "healing-word"),
            ("Sanctuary", 1, "sanctuary"),
            ("Aid", 2, "aid"),
            ("Prayer of Healing", 2, "prayer-of-healing"),
            ("Spirit Guardians", 3, "spirit-guardians"),
            ("Mass Healing Word", 3, "mass-healing-word"),
            ("Dispel Magic", 3, "dispel-magic"),
        ],
        prepared=True,
    )
    return Character(
        id="sample-cleric-5",
        name="Брат Аларик",
        abilities=_scores(str=14, dex=10, con=14, int=10, wis=17, cha=12),
        rules=rules,
        species_key="dwarf",
        subspecies_key="hill dwarf",
        background_key="acolyte",
        classes=[CharacterClass(class_key="cleric", level=5, subclass_key="phb-2014/subclass/life-domain")],
        chosen=_skills("cleric", Skill.MEDICINE, Skill.HISTORY),
        spells=cantrips + prepared,
        inventory=Inventory(
            items=(
                InventoryItem(name_en="mace", kind=ItemKind.WEAPON, weight_lb=4),
                InventoryItem(
                    name_en="chain mail", kind=ItemKind.ARMOR, weight_lb=55, equipped=True, armor_base=16, dex_cap=0
                ),
                InventoryItem(name_en="shield", kind=ItemKind.SHIELD, weight_lb=6, equipped=True),
            ),
            money=Money(gp=25),
        ),
    )


SAMPLES = {"wizard-4": wizard_4, "warlock-5": warlock_5, "cleric-5": cleric_5}


def multiclass_14(rules) -> Character:  # noqa: ANN001
    """Маг 4 / чаклун 5 / жрець 5: комірки за рівнем заклинателя 9 і окремо — угода."""
    wizard = wizard_4(rules).spells
    warlock = warlock_5(rules).spells
    # Жрець 5 з Мудрістю 15 готує 7 (2 + 5): без «Розвіювання магії».
    cleric = tuple(spell for spell in cleric_5(rules).spells if spell.name_en != "Dispel Magic")
    return Character(
        id="sample-multiclass-14",
        name="Сайлас Триєдиний",
        abilities=_scores(str=8, dex=12, con=14, int=16, wis=14, cha=15),
        rules=rules,
        species_key="human",
        background_key="sage",
        classes=[
            CharacterClass(class_key="wizard", level=4, subclass_key="phb-2014/subclass/school-of-evocation"),
            CharacterClass(class_key="warlock", level=5, subclass_key="phb-2014/subclass/the-fiend"),
            CharacterClass(class_key="cleric", level=5, subclass_key="phb-2014/subclass/life-domain"),
        ],
        chosen=_skills("wizard", Skill.ARCANA, Skill.INVESTIGATION),
        spells=wizard + warlock + cleric,
        inventory=Inventory(
            items=(InventoryItem(name_en="quarterstaff", kind=ItemKind.WEAPON, weight_lb=4),), money=Money(gp=120)
        ),
    )


SAMPLES["multiclass-14"] = multiclass_14
