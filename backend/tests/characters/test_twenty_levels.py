"""Матриця «клас × 20 рівнів» і всі пари заклинательських класів.

Найдорожчі помилки ховаються в таблицях: невірний рядок слотів видно лише на
конкретному рівні — і саме там, де ним грають. Тому тут кожен із 13 класів
індексу проганяється через `SpellSlotService` на всіх 20 рівнях і порівнюється
зі своєю таблицею з PHB, а кожна пара заклинательських класів — з таблицею
мультикласу.

Тест не переписує числа з коду: очікування беруться з `ClassMechanics`, тобто з
`content/index/class-mechanics.json`, а для мультикласу — з `CASTER_SLOT_TABLE`.
Розійшлися таблиця класу й таблиця мультикласу — падає саме цей тест.
"""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.services.spell_slots import SpellSlotService
from dndsheet.compendium.infrastructure.mechanics_index import JsonMechanicsRepository
from dndsheet.shared.kernel import MAX_LEVEL
from dndsheet.shared.rules import (
    CasterProgression,
    caster_level,
    spell_slots,
)

LEVELS = range(1, MAX_LEVEL + 1)

#: Класи, які мусить знати індекс: 13 класів 2014 року.
CLASS_KEYS = (
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


@pytest.fixture(scope="module")
def classes() -> dict:
    repository = JsonMechanicsRepository()
    if not repository.available():
        pytest.skip("немає індексу механік (content/index/class-mechanics.json)")
    return dict(repository.classes())


def _casting(definition, level: int):
    return SpellSlotService().compute(
        [(CharacterClass(definition.key, level), definition)], {}, proficiency_bonus=2
    )


def _nonzero(table: tuple[int, ...]) -> dict[int, int]:
    return {level: count for level, count in enumerate(table, start=1) if count}


def _contribution(progression: CasterProgression | None, level: int) -> int:
    if progression is None or progression is CasterProgression.PACT:
        return 0
    divisor = progression.divisor
    if not divisor:
        return 0
    return (level + divisor - 1) // divisor if progression.rounds_up else level // divisor


# ---------------------------------------------------------------------------
# один клас: числа мусять дорівнювати його власній таблиці
# ---------------------------------------------------------------------------


def test_index_has_thirteen_classes(classes) -> None:
    assert sorted(classes) == sorted(CLASS_KEYS)


@pytest.mark.parametrize("key", CLASS_KEYS)
def test_single_class_slots_match_own_table(classes, key: str) -> None:
    """Половина заклинателів не йде через мультикласову таблицю.

    Таблиця мультикласу для paladin-а 5 дає 3 слоти 1 рівня, а його власна — 4
    і 2 другого. Тому клас із однією заклинательською лінією читає свою
    таблицю; інакше персонаж втрачав би слоти на непарних рівнях.
    """
    definition = classes[key]
    if not definition.casts_spells:
        assert _casting(definition, 1).slots.total == 0
        return
    for level in LEVELS:
        casting = _casting(definition, level)
        if definition.is_pact_magic:
            assert dict(casting.slots.by_level) == {}, f"{key} {level}: слоти не з Pact Magic"
            expected_pact = definition.pact_at(level)
            actual = casting.slots.pact
            if expected_pact[0] == 0:
                assert actual is None or actual.slots == 0
            else:
                assert actual is not None, f"{key} {level}: немає Pact Magic"
                assert (actual.slots, actual.slot_level) == expected_pact, f"{key} {level}"
        else:
            assert dict(casting.slots.by_level) == _nonzero(definition.slots_at(level)), (
                f"{key} {level}: слоти розійшлися з таблицею класу"
            )


@pytest.mark.parametrize("key", CLASS_KEYS)
def test_caster_level_of_one_class(classes, key: str) -> None:
    """Рівень заклинателя одного класу: повний — цілий, половина — вниз, артифіцер — вгору."""
    definition = classes[key]
    expected_progression = {
        "bard": CasterProgression.FULL,
        "cleric": CasterProgression.FULL,
        "druid": CasterProgression.FULL,
        "sorcerer": CasterProgression.FULL,
        "wizard": CasterProgression.FULL,
        "paladin": CasterProgression.HALF,
        "ranger": CasterProgression.HALF,
        "artificer": CasterProgression.ARTIFICER,
        "warlock": CasterProgression.PACT,
    }.get(key)
    assert definition.caster_progression is expected_progression, key
    for level in LEVELS:
        casting = _casting(definition, level)
        assert casting.caster_level == caster_level([(expected_progression, level)]), key


def test_caster_level_ignores_non_casters(classes) -> None:
    for key in ("barbarian", "fighter", "monk", "rogue"):
        for level in LEVELS:
            assert _casting(classes[key], level).caster_level == 0, f"{key} {level}"


# ---------------------------------------------------------------------------
# усі пари заклинательських класів
# ---------------------------------------------------------------------------


def _caster_keys(classes) -> list[str]:
    return sorted(key for key, definition in classes.items() if definition.casts_spells)


def test_every_pair_of_casters_uses_multiclass_table(classes) -> None:
    """Кожен розподіл рівнів між двома заклинателями — за таблицею мультикласу."""
    keys = _caster_keys(classes)
    assert len(keys) == 9
    checked = 0
    for first, second in _pairs(keys):
        definition_a, definition_b = classes[first], classes[second]
        for level_a in LEVELS:
            for level_b in range(1, MAX_LEVEL - level_a + 1):
                combined = _contribution(
                    definition_a.caster_progression, level_a
                ) + _contribution(definition_b.caster_progression, level_b)
                # Таблиця мультикласу — лише коли «Spellcasting» мають обидва
                # класи (PHB, p. 164). Pact Magic чаклуна — окрема риса, а
                # паладин і слідопит на 1 рівні ще не заклинателі: тоді слоти
                # дає власна таблиця другого класу.
                standard = [
                    (definition, level)
                    for definition, level in ((definition_a, level_a), (definition_b, level_b))
                    if not definition.is_pact_magic
                    and (definition.max_spell_level(level) > 0 or definition.cantrips_at(level) > 0)
                ]
                if len(standard) > 1:
                    expected = spell_slots(combined)
                elif standard:
                    expected = standard[0][0].slots_at(standard[0][1])
                else:
                    expected = ()
                casting = SpellSlotService().compute(
                    [
                        (CharacterClass(first, level_a), definition_a),
                        (CharacterClass(second, level_b), definition_b),
                    ],
                    {},
                    proficiency_bonus=2,
                )
                assert dict(casting.slots.by_level) == _nonzero(expected), (
                    f"{first} {level_a} / {second} {level_b}: "
                    f"рівень заклинателя {combined}, очікувались {_nonzero(expected)}"
                )
                casters = {first, second}
                if "warlock" in casters:
                    warlock_level = level_a if first == "warlock" else level_b
                    expected_pact = classes["warlock"].pact_at(warlock_level)
                    assert casting.slots.pact is not None
                    assert (
                        casting.slots.pact.slots,
                        casting.slots.pact.slot_level,
                    ) == expected_pact, f"Pact Magic: {first} {level_a} / {second} {level_b}"
                else:
                    assert casting.slots.pact is None
                checked += 1
    assert checked > 6000, f"перевірено лише {checked} розподілів"


def test_highest_slot_level_never_exceeds_nine(classes) -> None:
    for key in _caster_keys(classes):
        definition = classes[key]
        for level in LEVELS:
            assert _casting(definition, level).slots.highest_level <= 9


def test_half_caster_keeps_its_table_when_dipping_a_non_caster(classes) -> None:
    """Paladin 5 / Воїн 5 — це все ще один заклинательський клас.

    За суворою буквою PHB мультикласову таблицю застосовують, щойно класів
    більше одного, і тоді paladin 5 отримав би 3 слоти замість 4 + 2. Це
    відоме місце, яке за столом майже завжди грають інакше, тому свідомо:
    один заклинательський клас — його таблиця, незалежно від не-заклинателів.
    """
    casting = SpellSlotService().compute(
        [
            (CharacterClass("paladin", 5), classes["paladin"]),
            (CharacterClass("fighter", 5), classes["fighter"]),
        ],
        {},
        proficiency_bonus=3,
    )
    assert dict(casting.slots.by_level) == {1: 4, 2: 2}
    assert casting.slots_from == "class"
    assert casting.caster_level == 2, "рівень заклинателя лишається мультикласовим"


def test_true_multiclass_uses_combined_table(classes) -> None:
    """Paladin 3 / Візард 2: 1 + 2 = рівень заклинателя 3 — слоти 4 і 2."""
    casting = SpellSlotService().compute(
        [
            (CharacterClass("paladin", 3), classes["paladin"]),
            (CharacterClass("wizard", 2), classes["wizard"]),
        ],
        {},
        proficiency_bonus=3,
    )
    assert dict(casting.slots.by_level) == {1: 4, 2: 2}
    assert casting.slots_from == "multiclass"
    assert casting.caster_level == 3


def test_single_caster_is_marked_as_class_table(classes) -> None:
    for key in _caster_keys(classes):
        casting = _casting(classes[key], 5)
        assert casting.slots_from == "class", key
    assert _casting(classes["fighter"], 5).slots_from == "none"


def test_tables_have_twenty_rows(classes) -> None:
    """Структурна перевірка індексу: таблиці мусять бути на всі 20 рівнів."""
    for key, definition in classes.items():
        if definition.spell_slots:
            assert len(definition.spell_slots) == MAX_LEVEL, f"{key}: {len(definition.spell_slots)} рядків"
            assert all(len(row) == 9 for row in definition.spell_slots), key
        if definition.pact_slots:
            assert len(definition.pact_slots) == MAX_LEVEL, key
        if definition.cantrips_known:
            assert len(definition.cantrips_known) == MAX_LEVEL, f"{key}: заговори"
        if definition.spells_known is not None:
            assert len(definition.spells_known) == MAX_LEVEL, f"{key}: відомі закляття"
        assert definition.hit_die in (6, 8, 10, 12), key


def _pairs(items: list[str]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for index, first in enumerate(items):
        for second in items[index + 1 :]:
            result.append((first, second))
    return result
