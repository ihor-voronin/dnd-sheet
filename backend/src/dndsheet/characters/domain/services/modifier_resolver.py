"""Збирач бонусів: хто саме дав цифру й на що вона впливає.

`DerivedStatsCalculator` не лазить по правилах сам: спершу `ModifierResolver`
збирає **модифікатори** з джерелами (вид, передісторія, клас, риси, предмети,
ручні оверрайди), а обчислювач лише складає їх. З цього виходить те, що
потрібно на листі: «16 = 15 + 1 (людина)», а не голе 16.

Стекування: бонуси до характеристик і КЗ додаються; володіння не стекуються
(володієш або ні), тому вони живуть у `Proficiencies`, а не тут.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from dndsheet.characters.domain.proficiencies import GrantSource, SourceKind


class ModifierKind(StrEnum):
    """До чого застосовується число."""

    ABILITY = "ability"
    ARMOR_CLASS = "armor_class"
    SPEED = "speed"
    MAX_HIT_POINTS_PER_LEVEL = "max_hit_points_per_level"
    #: Готова надбавка до максимуму хітів (уже помножена на рівні).
    MAX_HIT_POINTS = "max_hit_points"
    #: Пасивні значення (ключ — навичка: perception, investigation).
    PASSIVE = "passive"
    INITIATIVE = "initiative"
    SAVING_THROW = "saving_throw"
    SKILL = "skill"
    SPELL_DC = "spell_dc"
    ATTACK = "attack"


@dataclass(frozen=True, slots=True)
class Modifier:
    """Один доданок правила: скільки, до чого й хто дав."""

    kind: ModifierKind
    value: int
    source: GrantSource
    key: str | None = None
    note_en: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValueError("модифікатор має бути цілим числом")


@dataclass(frozen=True, slots=True)
class ModifierSet:
    """Усі зібрані модифікатори разом із запитами до них."""

    items: tuple[Modifier, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.items)

    def of(self, kind: ModifierKind, key: str | None = None) -> tuple[Modifier, ...]:
        wanted = key.casefold() if key else None
        return tuple(
            item
            for item in self.items
            if item.kind is kind and (wanted is None or (item.key or "").casefold() == wanted)
        )

    def total(self, kind: ModifierKind, key: str | None = None) -> int:
        return sum(item.value for item in self.of(kind, key))

    def ability_bonus(self, ability: str) -> int:
        return self.total(ModifierKind.ABILITY, ability)

    def by_source(self) -> dict[GrantSource, tuple[Modifier, ...]]:
        grouped: dict[GrantSource, list[Modifier]] = {}
        for item in self.items:
            grouped.setdefault(item.source, []).append(item)
        return {source: tuple(values) for source, values in grouped.items()}

    def add(self, *items: Modifier) -> "ModifierSet":
        return ModifierSet(items=self.items + tuple(items))


class ModifierResolver:
    """Збирає модифікатори з правил персонажа.

    Поки що джерела: вид (фіксовані бонуси й обраний вибір) і вручну вписані
    бонуси. Риси з числовими бонусами (ASI) і предмети — етапи 7 і 4; коли
    вони зʼявляться, додається ще один блок тут, а не в обчислювачі.
    """

    def resolve(self, character) -> ModifierSet:  # noqa: ANN001 — Character, щоб не було циклу
        collected: list[Modifier] = []

        species = character.species
        if species is not None:
            source = GrantSource.of(SourceKind.SPECIES, species.key)
            for bonus in species.ability_bonuses:
                collected.append(
                    Modifier(
                        kind=ModifierKind.ABILITY,
                        value=bonus.amount,
                        source=source,
                        key=bonus.ability.value,
                        note_en="species",
                    )
                )
            choice = species.ability_choice
            if choice is not None:
                for ability in character.ability_bonus_choices:
                    collected.append(
                        Modifier(
                            kind=ModifierKind.ABILITY,
                            value=choice.amount,
                            source=source,
                            key=ability.value,
                            note_en="species-choice",
                        )
                    )
            # Правила 2022: вид без фіксованих бонусів — гравець розставив сам.
            for ability, amount in character.ability_spread.items():
                collected.append(
                    Modifier(
                        kind=ModifierKind.ABILITY,
                        value=amount,
                        source=source,
                        key=ability.value,
                        note_en="species-free",
                    )
                )

        collected.extend(_rule_modifiers(character))
        return ModifierSet(items=tuple(collected))


# ---------------------------------------------------------------------------
# числа з правил класу, підкласу, виду й рис (PHB 2014)
# ---------------------------------------------------------------------------

#: Вимога Сили важкої броні (PHB, p. 145).
_ARMOR_STRENGTH = {"chain mail": 13, "splint": 15, "splint armor": 15, "plate": 15, "plate armor": 15}

#: Unarmored Movement ченця (PHB, p. 78): +10 фт з 2 рівня, далі +5 кожні 4.
_MONK_SPEED = ((18, 30), (14, 25), (10, 20), (6, 15), (2, 10))


def _slug(value: str | None) -> str:
    return (value or "").strip().casefold().rsplit("/", 1)[-1]


def _rule_modifiers(character) -> list[Modifier]:  # noqa: ANN001, C901 — таблиця правил
    """Бонуси, які правила дають без вибору гравця.

    Те, що вимагає рішення (+1 до характеристики від «Actor» тощо), сюди не
    входить: це вибір, а не правило. Сюди — лише однозначне:

    * Jack of All Trades (бард 2): ½ бонусу майстерності, вниз, до перевірок
      без володіння, зокрема ініціативи (PHB, p. 54);
    * Remarkable Athlete (чемпіон 7): ½ вгору до перевірок СИЛ/СПР/СТА без
      володіння й до ініціативи (PHB, p. 72); з Jack of All Trades не
      складається — береться більше;
    * Aura of Protection (паладин 6): + модифікатор Харизми (мін. 1) до всіх
      рятівних кидків (PHB, p. 85);
    * Unarmored Movement (чернець 2+) без броні й щита; Fast Movement (варвар
      5) без важкої броні;
    * Dwarven Toughness (пагорбовий дворф): +1 хіт за кожен рівень;
      Draconic Resilience (драконячий родовід): +1 хіт за рівень чародія;
    * риси Alert (+5 ініціатива), Mobile (+10 фт), Tough (+2 хіти за рівень),
      Observant (+5 до пасивних Спостережливості й Розслідування).
    """
    from dndsheet.characters.domain.proficiencies import ProficiencyKind
    from dndsheet.shared.kernel import SKILL_ABILITY, Ability, Skill, proficiency_bonus

    items: list[Modifier] = []
    levels = {entry.class_key: entry.level for entry in character.classes if entry.level > 0}
    subclasses = {
        entry.class_key: _slug(entry.subclass_key)
        for entry in character.classes
        if entry.subclass_key
    }
    feats = {_slug(feat) for feat in character.feats}
    total_level = max(1, character.total_level)
    proficiency = proficiency_bonus(total_level)
    armor = character.inventory.worn_armor
    shield = character.inventory.worn_shield
    heavy_armor = armor is not None and armor.dex_cap == 0

    def add(kind: ModifierKind, value: int, kind_src: SourceKind, key_src: str, key=None, note=None):  # noqa: ANN001, ANN202
        if value:
            items.append(
                Modifier(
                    kind=kind,
                    value=value,
                    source=GrantSource.of(kind_src, key_src),
                    key=key,
                    note_en=note,
                )
            )

    # --- перевірки без володіння: Jack of All Trades / Remarkable Athlete ---
    jack = proficiency // 2 if levels.get("bard", 0) >= 2 else 0
    athlete = (
        -(-proficiency // 2)
        if levels.get("fighter", 0) >= 7 and subclasses.get("fighter") == "champion"
        else 0
    )
    if jack or athlete:
        owned = character.all_proficiencies()
        for skill in Skill:
            if owned.has(ProficiencyKind.SKILL, skill.value):
                continue
            physical = SKILL_ABILITY[skill] in (Ability.STR, Ability.DEX, Ability.CON)
            best = max(jack, athlete if physical else 0)
            source = ("fighter", "remarkable-athlete") if best == athlete and physical and athlete > jack else ("bard", "jack-of-all-trades")
            add(ModifierKind.SKILL, best, SourceKind.CLASS, source[0], key=skill.value, note=source[1])
        best_init = max(jack, athlete)
        add(
            ModifierKind.INITIATIVE,
            best_init,
            SourceKind.CLASS,
            "fighter" if athlete > jack else "bard",
            note="remarkable-athlete" if athlete > jack else "jack-of-all-trades",
        )

    # --- Aura of Protection ---
    if levels.get("paladin", 0) >= 6:
        charisma = (character.ability_total(Ability.CHA) - 10) // 2
        add(ModifierKind.SAVING_THROW, max(1, charisma), SourceKind.CLASS, "paladin", note="aura-of-protection")

    # --- швидкість ---
    monk = levels.get("monk", 0)
    if monk and armor is None and shield is None:
        bonus = next((value for level, value in _MONK_SPEED if monk >= level), 0)
        add(ModifierKind.SPEED, bonus, SourceKind.CLASS, "monk", note="unarmored-movement")
    # Важка броня без потрібної Сили: −10 фт (PHB, p. 144); дворфів не сповільнює.
    need = _ARMOR_STRENGTH.get(armor.name_en.strip().casefold()) if armor is not None else None
    if need and character.ability_total(Ability.STR) < need and character.species_key != "dwarf":
        add(ModifierKind.SPEED, -10, SourceKind.ITEM, armor.name_en, note="heavy-armor-strength")
    if levels.get("barbarian", 0) >= 5 and not heavy_armor:
        add(ModifierKind.SPEED, 10, SourceKind.CLASS, "barbarian", note="fast-movement")

    # --- хіти ---
    if _slug(character.subspecies_key) == "hill dwarf":
        add(ModifierKind.MAX_HIT_POINTS, total_level, SourceKind.SPECIES, "hill dwarf", note="dwarven-toughness")
    if subclasses.get("sorcerer") == "draconic-bloodline":
        add(ModifierKind.MAX_HIT_POINTS, levels.get("sorcerer", 0), SourceKind.CLASS, "sorcerer", note="draconic-resilience")

    # --- бойовий стиль: Defense +1 КБ у броні (PHB, p. 72) ---
    # shortcut: Dueling/Great Weapon/Two-Weapon лише як текст, автоматично не рахуються.
    if armor is not None and character.has_class_choice("defense"):
        add(ModifierKind.ARMOR_CLASS, 1, SourceKind.CLASS, "fighting-style", note="defense")

    # --- риси ---
    for ability in Ability:
        add(ModifierKind.ABILITY, character.ability_bonus_from_feats(ability), SourceKind.FEAT, "feat", key=ability.value, note="feat")
    if "alert" in feats:
        add(ModifierKind.INITIATIVE, 5, SourceKind.FEAT, "alert", note="alert")
    if "mobile" in feats:
        add(ModifierKind.SPEED, 10, SourceKind.FEAT, "mobile", note="mobile")
    if "tough" in feats:
        add(ModifierKind.MAX_HIT_POINTS, 2 * total_level, SourceKind.FEAT, "tough", note="tough")
    if "observant" in feats:
        add(ModifierKind.PASSIVE, 5, SourceKind.FEAT, "observant", key="perception", note="observant")
        add(ModifierKind.PASSIVE, 5, SourceKind.FEAT, "observant", key="investigation", note="observant")
    return items
