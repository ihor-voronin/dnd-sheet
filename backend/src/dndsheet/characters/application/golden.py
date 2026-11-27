"""Еталонні персонажі: числа, які зобовʼязані збігатися з правилами.

Це не «демо-дані»: це контракт. Кожен золотий персонаж має очікуваний лист
у тестах, і якщо зміна коду зсуне хоч одне число — тест упаде. Сенс саме в
тому, що фіксовані числа видно очима й можна перевірити з книгою.

Склад навмисно покриває різні гілки правил:

* **Воїн 1** — максимум кості хітів d10, важка броня + щит, рятівні кидки
  STR/CON, людський бонус +1 до всього;
* **Варлок 1** — Pact Magic: комірки не за таблицею заклинателя, DC від CHA,
  опір вогню, темний зір;
* **Воїн 2 / Візард 3** — мультиклас: сумарний рівень 5, бонус майстерності 3,
  рівень заклинателя 3, комірки 4/2, дві кістки хітів в пулі.
"""

from __future__ import annotations

from dataclasses import dataclass

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.inventory import Inventory, InventoryItem, ItemKind
from dndsheet.characters.domain.ports import RulesSource
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    Proficiencies,
    SourceKind,
)
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.shared.kernel import Ability, AbilityScore, Money, Skill


@dataclass(frozen=True, slots=True)
class GoldenCase:
    """Еталонний персонаж і те, що про нього треба знати на екрані."""

    key: str
    title_uk: str
    summary_uk: str
    character: Character


def _scores(**scores: int) -> dict[Ability, AbilityScore]:
    return {Ability(name): AbilityScore(value) for name, value in scores.items()}


def _skill(skill: Skill, kind: SourceKind, key: str) -> Proficiency:
    return Proficiency(
        kind=ProficiencyKind.SKILL,
        value=skill.value,
        source=GrantSource.of(kind, key),
    )


def _picks(*items: Proficiency) -> Proficiencies:
    return Proficiencies(items=items)


def build_golden_cases(rules: RulesSource) -> tuple[GoldenCase, ...]:
    """Три еталонні персонажі, зібрані через порт правил."""
    return (_fighter(rules), _warlock(rules), _multiclass(rules))


def _fighter(rules: RulesSource) -> GoldenCase:
    character = Character(
        id="golden-fighter-1",
        name="Дарія Залізний Крок",
        abilities=_scores(str=15, dex=13, con=14, int=9, wis=11, cha=7),
        rules=rules,
        species_key="human",
        background_key="soldier",
        classes=[CharacterClass(class_key="fighter", level=1)],
        chosen=_picks(
            _skill(Skill.PERCEPTION, SourceKind.CLASS, "fighter"),
            _skill(Skill.SURVIVAL, SourceKind.CLASS, "fighter"),
        ),
        inventory=Inventory(
            items=(
                InventoryItem(
                    name_en="chain mail",
                    kind=ItemKind.ARMOR,
                    weight_lb=55,
                    equipped=True,
                    armor_base=16,
                    dex_cap=0,
                ),
                InventoryItem(name_en="shield", kind=ItemKind.SHIELD, weight_lb=6, equipped=True),
                InventoryItem(name_en="longsword", kind=ItemKind.WEAPON, weight_lb=3),
                InventoryItem(name_en="dungeoneer's pack", kind=ItemKind.PACK),
            ),
            money=Money(gp=10),
        ),
        hp=HitPointState(current=12),
    )
    return GoldenCase(
        key="fighter-1",
        title_uk="Воїн 1",
        summary_uk=(
            "Людина, Солдат. Важка броня й щит, максимум d10, рятівні кидки STR/CON, "
            "бонус майстерності +2."
        ),
        character=character,
    )


def _warlock(rules: RulesSource) -> GoldenCase:
    character = Character(
        id="golden-warlock-1",
        name="Тіра Вугільне Око",
        abilities=_scores(str=8, dex=13, con=13, int=12, wis=10, cha=15),
        rules=rules,
        species_key="tiefling",
        background_key="acolyte",
        classes=[CharacterClass(class_key="warlock", level=1)],
        chosen=_picks(
            _skill(Skill.ARCANA, SourceKind.CLASS, "warlock"),
            _skill(Skill.DECEPTION, SourceKind.CLASS, "warlock"),
        ),
        spells=(
            KnownSpell(
                name_en="Eldritch Blast", level=0, class_key="warlock", entry_id="phb-2014/spell/eldritch-blast"
            ),
            KnownSpell(
                name_en="Prestidigitation",
                level=0,
                class_key="warlock",
                entry_id="phb-2014/spell/prestidigitation",
            ),
            KnownSpell(
                name_en="Hex", level=1, class_key="warlock", entry_id="phb-2014/spell/hex"
            ),
            KnownSpell(
                name_en="Charm Person",
                level=1,
                class_key="warlock",
                entry_id="phb-2014/spell/charm-person",
            ),
        ),
        inventory=Inventory(
            items=(
                InventoryItem(
                    name_en="leather armor",
                    kind=ItemKind.ARMOR,
                    weight_lb=10,
                    equipped=True,
                    armor_base=11,
                ),
                InventoryItem(name_en="dagger", kind=ItemKind.WEAPON, weight_lb=1),
                InventoryItem(name_en="arcane focus", kind=ItemKind.GEAR, weight_lb=1),
            ),
            money=Money(gp=15),
        ),
        hp=HitPointState(current=9),
    )
    return GoldenCase(
        key="warlock-1",
        title_uk="Варлок 1",
        summary_uk=(
            "Тифлінг, Служитель. Pact Magic: 1 комірка 1 рівня, DC 13 від CHA, "
            "опір вогню, темний зір 60."
        ),
        character=character,
    )


def _multiclass(rules: RulesSource) -> GoldenCase:
    character = Character(
        id="golden-fighter-wizard",
        name="Марко Двоїстий Шлях",
        abilities=_scores(str=12, dex=13, con=11, int=14, wis=9, cha=7),
        rules=rules,
        species_key="human",
        background_key="soldier",
        classes=[
            CharacterClass(class_key="fighter", level=2),
            CharacterClass(class_key="wizard", level=3),
        ],
        chosen=_picks(
            _skill(Skill.PERCEPTION, SourceKind.CLASS, "fighter"),
            _skill(Skill.SURVIVAL, SourceKind.CLASS, "fighter"),
            # Маг другим класом навичок не дає (PHB, p. 164).
        ),
        spells=(
            KnownSpell(
                name_en="Fire Bolt", level=0, class_key="wizard", entry_id="phb-2014/spell/fire-bolt"
            ),
            KnownSpell(
                name_en="Mage Hand", level=0, class_key="wizard", entry_id="phb-2014/spell/mage-hand"
            ),
            KnownSpell(
                name_en="Prestidigitation",
                level=0,
                class_key="wizard",
                entry_id="phb-2014/spell/prestidigitation",
            ),
            KnownSpell(
                name_en="Magic Missile",
                level=1,
                class_key="wizard",
                entry_id="phb-2014/spell/magic-missile",
                prepared=True,
            ),
            KnownSpell(
                name_en="Shield", level=1, class_key="wizard", entry_id="phb-2014/spell/shield"
            ),
            KnownSpell(
                name_en="Misty Step",
                level=2,
                class_key="wizard",
                entry_id="phb-2014/spell/misty-step",
            ),
        ),
        inventory=Inventory(
            items=(
                InventoryItem(
                    name_en="chain mail",
                    kind=ItemKind.ARMOR,
                    weight_lb=55,
                    equipped=True,
                    armor_base=16,
                    dex_cap=0,
                ),
                InventoryItem(name_en="longsword", kind=ItemKind.WEAPON, weight_lb=3),
            ),
            money=Money(gp=25),
        ),
        hp=HitPointState(current=33),
    )
    return GoldenCase(
        key="fighter-2-wizard-3",
        title_uk="Воїн 2 / Візард 3",
        summary_uk=(
            "Мультиклас: сумарний рівень 5, бонус майстерності +3, рівень заклинателя 3 "
            "(комірки 4×1 і 2×2), кістки хітів d10×2 + d6×3."
        ),
        character=character,
    )
