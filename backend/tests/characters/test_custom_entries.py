"""Власні вміння й закляття: те, що є за столом, але немає в книгах.

Правил із них лист не виводить: це текст гравця з позначкою «власне». Числа
є лише в лічильника вміння («2 рази на короткий відпочинок»), і відпочинок
відновлює його так само, як класові ресурси.
"""

from __future__ import annotations

import pytest
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.custom_features import MAX_CUSTOM_FEATURES, CustomFeature
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.services.feature_resources import resources_for
from dndsheet.characters.domain.services.rest import RestService
from dndsheet.characters.domain.spells import OTHER_CLASS, KnownSpell
from dndsheet.characters.infrastructure.character_json import character_from_record, character_to_record
from dndsheet.shared.errors import NotFoundError, ValidationError
from dndsheet.shared.kernel import Ability, AbilityScore
from helpers import make_character


def feature(feature_id: str = "a1", name: str = "Дар майстра", **extra) -> CustomFeature:  # noqa: ANN003
    return CustomFeature(id=feature_id, name=name, **extra)


def custom_spell(name: str = "Благословення столу", level: int = 1, cls: str = OTHER_CLASS, **extra) -> KnownSpell:  # noqa: ANN003
    return KnownSpell(name_en=name, level=level, class_key=cls, custom=True, prepared=True, **extra)


def cleric(rules, wis: int = 10):  # noqa: ANN001, ANN201
    abilities = {ability: AbilityScore(10) for ability in Ability}
    abilities[Ability.WIS] = AbilityScore(wis)
    return make_character(rules, abilities=abilities, classes=[CharacterClass(class_key="cleric", level=1)])


# ---------------------------------------------------------------------------
# власне вміння
# ---------------------------------------------------------------------------


def test_feature_trims_and_defaults() -> None:
    item = feature(name="  Перстень  ", text="  Світиться.  ", origin="  ")
    assert item.name == "Перстень"
    assert item.text == "Світиться."
    assert item.origin is None
    assert item.resource_key is None


@pytest.mark.parametrize(
    "extra",
    [
        {"name": " "},
        {"name": "x" * 121},
        {"text": "x" * 4001},
        {"origin": "x" * 121},
        {"level": 0},
        {"level": 21},
        {"level": True},
        {"uses": 0},
        {"uses": 100, "recharge": "long"},
        {"uses": 2},
        {"uses": 2, "recharge": "dawn"},
        {"recharge": "short"},
    ],
)
def test_feature_rejects_bad_values(extra: dict) -> None:
    with pytest.raises(ValidationError):
        feature(**extra)


@pytest.mark.parametrize("bad_id", ["", "a b", "x" * 41, "../x"])
def test_feature_rejects_bad_id(bad_id: str) -> None:
    with pytest.raises(ValidationError):
        feature(feature_id=bad_id)


def test_feature_with_uses_becomes_a_resource_that_rests_restore(rules) -> None:  # noqa: ANN001
    character = make_character(rules)
    character.add_custom_feature(feature("a1", "Іскра", uses=2, recharge="short"))
    character.add_custom_feature(feature("b2", "Тінь", uses=1, recharge="long"))
    character.add_custom_feature(feature("c3", "Просто текст"))
    modifiers = DerivedStatsCalculator().compute(character).ability_modifiers

    keys = {item.key: item for item in resources_for(character, modifiers)}
    assert keys["custom:a1"].total == 2 and keys["custom:a1"].recharge == "short"
    assert keys["custom:a1"].class_key == "custom"
    assert "custom:c3" not in keys

    character.set_state(character.state.with_feature_used({"custom:a1": 2, "custom:b2": 1}))
    RestService().short_rest(character)
    assert character.state.feature_used == {"custom:b2": 1}
    report = RestService().long_rest(character)
    assert "Тінь" in report.features_reset
    assert dict(character.state.feature_used) == {}


def test_update_feature_keeps_or_trims_the_counter(rules) -> None:  # noqa: ANN001
    character = make_character(rules)
    character.add_custom_feature(feature("a1", uses=3, recharge="long"))
    character.set_state(character.state.with_feature_used({"custom:a1": 3}))
    version = character.version

    character.update_custom_feature(feature("a1", uses=2, recharge="long"))
    assert character.state.feature_used["custom:a1"] == 2
    assert character.version == version + 1

    # Те саме ще раз — нічого не змінилося, версія та сама.
    character.update_custom_feature(feature("a1", uses=2, recharge="long"))
    assert character.version == version + 1

    character.update_custom_feature(feature("a1", text="Тепер без лічильника"))
    assert "custom:a1" not in character.state.feature_used
    assert character.custom_feature("a1").text == "Тепер без лічильника"


def test_remove_feature_drops_its_counter(rules) -> None:  # noqa: ANN001
    character = make_character(rules)
    character.add_custom_feature(feature("a1", uses=1, recharge="short"))
    character.set_state(character.state.with_feature_used({"custom:a1": 1}))
    character.remove_custom_feature("a1")
    assert character.custom_features == ()
    assert "custom:a1" not in character.state.feature_used
    with pytest.raises(NotFoundError):
        character.remove_custom_feature("a1")
    with pytest.raises(NotFoundError):
        character.update_custom_feature(feature("zz"))


def test_feature_ids_are_unique_and_count_is_limited(rules) -> None:  # noqa: ANN001
    character = make_character(rules)
    character.add_custom_feature(feature("a1"))
    with pytest.raises(ValidationError):
        character.add_custom_feature(feature("a1", name="Інше"))
    for index in range(MAX_CUSTOM_FEATURES - 1):
        character.add_custom_feature(feature(f"n{index}"))
    with pytest.raises(ValidationError):
        character.add_custom_feature(feature("over"))


# ---------------------------------------------------------------------------
# власне закляття
# ---------------------------------------------------------------------------


def test_spell_outside_class_is_only_custom() -> None:
    with pytest.raises(ValidationError):
        KnownSpell(name_en="Fireball", level=3, class_key=OTHER_CLASS)
    assert custom_spell().outside_class


@pytest.mark.parametrize(
    "extra",
    [
        {"school": "evocation"},
        {"casting_time": "1 action"},
        {"concentration": True},
        {"ritual": True},
    ],
)
def test_book_spell_has_no_custom_meta(extra: dict) -> None:
    with pytest.raises(ValidationError):
        KnownSpell(name_en="Bless", level=1, class_key="cleric", **extra)


def test_custom_spell_meta_is_trimmed_and_bounded() -> None:
    spell = custom_spell(school="  воплочення ", range=" ")
    assert spell.school == "воплочення"
    assert spell.range is None
    with pytest.raises(ValidationError):
        custom_spell(duration="x" * 121)
    with pytest.raises(ValidationError):
        custom_spell(description="x" * 4001)
    with pytest.raises(ValidationError):
        custom_spell(name="x" * 121)


def test_fighter_learns_a_spell_outside_any_class(rules) -> None:  # noqa: ANN001
    fighter = make_character(rules)  # воїн не чарує
    fighter.learn_spell(custom_spell(level=3, school="воплочення", concentration=True))
    assert fighter.spells[0].class_key == OTHER_CLASS
    with pytest.raises(ValidationError):
        fighter.learn_spell(custom_spell(name="БЛАГОСЛОВЕННЯ СТОЛУ"))


def test_spell_outside_class_takes_no_place_in_limits(rules) -> None:  # noqa: ANN001
    character = cleric(rules)  # ліміт підготовлених 1
    character.learn_spell(custom_spell())
    character.learn_spell(KnownSpell(name_en="bless", level=1, class_key="cleric", prepared=True))
    assert len(character.spells) == 2


def test_update_custom_spell(rules) -> None:  # noqa: ANN001
    character = cleric(rules)
    character.learn_spell(custom_spell())
    character.learn_spell(custom_spell(name="Друге"))
    version = character.version

    character.update_custom_spell("благословення столу", OTHER_CLASS, custom_spell(name="Нове ім'я", level=2))
    assert [spell.name_en for spell in character.spells] == ["Нове ім'я", "Друге"]
    assert character.version == version + 1

    character.update_custom_spell("Нове ім'я", OTHER_CLASS, custom_spell(name="Нове ім'я", level=2))
    assert character.version == version + 1

    with pytest.raises(ValidationError):
        character.update_custom_spell("Нове ім'я", OTHER_CLASS, custom_spell(name="Друге"))
    with pytest.raises(ValidationError):
        character.update_custom_spell("немає", OTHER_CLASS, custom_spell())
    # Перенести в клас — ліміт класу діє (1 підготовлене), друге вже не влізе.
    character.update_custom_spell("Нове ім'я", OTHER_CLASS, custom_spell(name="Нове ім'я", cls="cleric"))
    with pytest.raises(ValidationError):
        character.update_custom_spell("Друге", OTHER_CLASS, custom_spell(name="Друге", cls="cleric"))


def test_book_spell_is_not_updated(rules) -> None:  # noqa: ANN001
    character = cleric(rules)
    character.learn_spell(KnownSpell(name_en="bless", level=1, class_key="cleric"))
    with pytest.raises(ValidationError):
        character.update_custom_spell("bless", "cleric", custom_spell(name="bless", cls="cleric"))


# ---------------------------------------------------------------------------
# запис
# ---------------------------------------------------------------------------


def test_record_roundtrip_keeps_custom_entries(rules) -> None:  # noqa: ANN001
    character = make_character(rules)
    character.add_custom_feature(feature("a1", text="Текст", origin="майстер", level=3, uses=2, recharge="short"))
    character.learn_spell(
        custom_spell(
            school="ілюзія",
            casting_time="1 дія",
            range="9 м",
            duration="1 хвилина",
            components="В, С",
            concentration=True,
            ritual=True,
            description="Робить диво.",
        )
    )
    record = character_to_record(character)
    assert record["custom_features"][0]["origin"] == "майстер"
    assert record["spells"][0]["school"] == "ілюзія"

    restored = character_from_record(record, rules)
    assert restored.custom_features == character.custom_features
    assert restored.spells == character.spells
    assert character_to_record(restored) == record


def test_bad_custom_feature_record_is_rejected(rules) -> None:  # noqa: ANN001
    record = character_to_record(make_character(rules))
    record["custom_features"] = [{"name": "без id"}]
    with pytest.raises(ValidationError):
        character_from_record(record, rules)


def test_book_spell_record_has_no_custom_meta(rules) -> None:  # noqa: ANN001
    character = cleric(rules, wis=16)
    character.learn_spell(KnownSpell(name_en="bless", level=1, class_key="cleric"))
    assert "school" not in character_to_record(character)["spells"][0]
