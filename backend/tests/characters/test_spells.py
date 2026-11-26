"""Закляття поза рівнем: щоденна підготовка й власні закляття.

Кожне очікуване число — з книги гравця:

* підготовлених не більше ніж «модифікатор + рівень класу», мінімум 1
  (PHB, p. 201) — у жреця 1 з МУД 16 це 4, з МУД 10 — 1;
* підготовка — це **набір на день**, а не позначка: учорашні закляття не
  лишаються підготовленими;
* заговори підготовкою не змінюються (вони змінюються з рівнем);
* рівень закляття не вище за слоти класу;
* власне закляття (якого немає в книзі) лист позначає, але правил із нього не
  виводить; воно завжди доступне й займає місце серед підготовлених.
"""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Ability, AbilityScore

from helpers import make_character


def cleric(rules, *, level: int = 1, wis: int = 16):  # noqa: ANN001, ANN201
    abilities = {ability: AbilityScore(10) for ability in Ability}
    abilities[Ability.WIS] = AbilityScore(wis)
    return make_character(
        rules,
        abilities=abilities,
        classes=[CharacterClass(class_key="cleric", level=level)],
    )


def spell(name: str, level: int = 1, *, cls: str = "cleric", **extra) -> KnownSpell:  # noqa: ANN003
    return KnownSpell(name_en=name, level=level, class_key=cls, **extra)


# ---------------------------------------------------------------------------
# ліміт підготовлених
# ---------------------------------------------------------------------------


def test_prepared_limit_is_modifier_plus_level(rules) -> None:  # noqa: ANN001
    assert cleric(rules, level=1, wis=16).prepared_limit("cleric") == 4  # 3 + 1
    assert cleric(rules, level=5, wis=16).prepared_limit("cleric") == 8  # 3 + 5
    # Мінімум один: навіть з відʼємним модифікатором клас готує хоч одне.
    assert cleric(rules, level=1, wis=8).prepared_limit("cleric") == 1


def test_class_without_preparation_has_no_limit(rules) -> None:  # noqa: ANN001
    fighter = make_character(rules)  # Воїн не готує закляття
    with pytest.raises(ValidationError):
        fighter.prepared_limit("fighter")
    with pytest.raises(ValidationError):
        fighter.prepare_spells("fighter", [spell("bless")])


# ---------------------------------------------------------------------------
# підготовка на день
# ---------------------------------------------------------------------------


def test_preparation_replaces_the_set(rules) -> None:  # noqa: ANN001
    character = cleric(rules)
    character.prepare_spells("cleric", [spell("bless"), spell("shield of faith")])
    assert sorted(item.name_en for item in character.spells) == ["bless", "shield of faith"]
    assert all(item.prepared for item in character.spells)

    # Наступного дня жрець готує інше — учорашні не лишаються.
    character.prepare_spells("cleric", [spell("guiding bolt")])
    assert [item.name_en for item in character.spells] == ["guiding bolt"]
    assert character.spells[0].prepared is True


def test_preparation_keeps_cantrips(rules) -> None:  # noqa: ANN001
    character = cleric(rules)
    character.learn_spell(spell("light", 0))
    character.prepare_spells("cleric", [spell("bless")])

    levels = sorted((item.name_en, item.level) for item in character.spells)
    assert levels == [("bless", 1), ("light", 0)]
    assert next(item for item in character.spells if item.is_cantrip).prepared is False


def test_preparation_respects_limit(rules) -> None:  # noqa: ANN001
    character = cleric(rules, wis=10)  # ліміт 1
    with pytest.raises(ValidationError) as error:
        character.prepare_spells("cleric", [spell("bless"), spell("guiding bolt")])
    assert "можна 1" in str(error.value)


def test_preparation_rejects_cantrips_in_the_list(rules) -> None:  # noqa: ANN001
    character = cleric(rules)
    with pytest.raises(ValidationError) as error:
        character.prepare_spells("cleric", [spell("light", 0)])
    assert "заговори" in str(error.value)


def test_preparation_rejects_spell_above_slots(rules) -> None:  # noqa: ANN001
    character = cleric(rules)  # жрець 1: найвищий рівень заклять — 1
    with pytest.raises(ValidationError) as error:
        character.prepare_spells("cleric", [spell("lesser restoration", 2)])
    assert "максимум 1" in str(error.value)


def test_preparation_rejects_duplicates(rules) -> None:  # noqa: ANN001
    character = cleric(rules)
    with pytest.raises(ValidationError):
        character.prepare_spells("cleric", [spell("bless"), spell("Bless")])


def test_preparation_rejects_spell_of_other_class(rules) -> None:  # noqa: ANN001
    character = cleric(rules)
    with pytest.raises(ValidationError):
        character.prepare_spells("cleric", [spell("magic missile", cls="wizard")])


def test_preparation_survives_reload(rules) -> None:  # noqa: ANN001
    from dndsheet.characters.infrastructure.character_json import (
        character_from_record,
        character_to_record,
    )

    character = cleric(rules)
    character.prepare_spells("cleric", [spell("bless", entry_id="phb-2014/spell/bless")])
    restored = character_from_record(character_to_record(character), rules)

    assert [(item.name_en, item.prepared) for item in restored.spells] == [("bless", True)]


# ---------------------------------------------------------------------------
# власні закляття
# ---------------------------------------------------------------------------


def test_custom_spell_is_marked_and_kept(rules) -> None:  # noqa: ANN001
    character = cleric(rules)
    character.learn_spell(
        spell(
            "Благословення столу",
            custom=True,
            description="Усі союзники за столом отримують +1 до кидків атаки.",
            prepared=True,
        )
    )

    assert character.spells[0].custom is True
    assert character.spells[0].description.startswith("Усі союзники")
    # Підготовка книжкових заклять не прибирає власне: його додав гравець.
    character.prepare_spells("cleric", [spell("bless")])
    names = [item.name_en for item in character.spells]
    assert "Благословення столу" in names and "bless" in names


def test_custom_spell_counts_toward_the_limit(rules) -> None:  # noqa: ANN001
    character = cleric(rules, wis=10)  # ліміт 1
    character.learn_spell(
        spell("Наш власний вогонь", custom=True, description="1d6 вогню.", prepared=True)
    )
    # Одне місце вже зайняте власним закляттям — книжкове не влазить.
    with pytest.raises(ValidationError) as error:
        character.learn_spell(spell("bless", prepared=True))
    assert "можна 1" in str(error.value)


def test_custom_spell_is_not_part_of_preparation(rules) -> None:  # noqa: ANN001
    character = cleric(rules)
    custom = spell("Наш власний вогонь", custom=True, description="1d6 вогню.")
    character.learn_spell(custom.prepare(True))
    with pytest.raises(ValidationError):
        character.prepare_spells("cleric", [custom])


def test_custom_spell_rejects_compendium_id(rules) -> None:  # noqa: ANN001
    with pytest.raises(ValidationError) as error:
        KnownSpell(
            name_en="Своє",
            level=1,
            class_key="cleric",
            custom=True,
            entry_id="phb-2014/spell/bless",
        )
    assert "довідник" in str(error.value)


def test_book_spell_rejects_custom_text(rules) -> None:  # noqa: ANN001
    with pytest.raises(ValidationError):
        KnownSpell(
            name_en="bless",
            level=1,
            class_key="cleric",
            description="свій текст",
        )


# ---------------------------------------------------------------------------
# додавання поза рівнем
# ---------------------------------------------------------------------------


def test_learn_respects_prepared_limit_for_preparing_class(rules) -> None:  # noqa: ANN001
    wizard = make_character(
        rules,
        classes=[CharacterClass(class_key="wizard", level=1)],
        # INT 10: ліміт підготовлених = 1.
    )
    wizard.learn_spell(spell("magic missile", cls="wizard", prepared=True))
    with pytest.raises(ValidationError) as error:
        wizard.learn_spell(spell("shield", cls="wizard", prepared=True))
    assert "можна 1" in str(error.value)


def test_learn_unprepared_spell_is_not_limited(rules) -> None:  # noqa: ANN001
    wizard = make_character(rules, classes=[CharacterClass(class_key="wizard", level=1)])
    wizard.learn_spell(spell("magic missile", cls="wizard"))
    wizard.learn_spell(spell("shield", cls="wizard"))
    assert len(wizard.spells) == 2
