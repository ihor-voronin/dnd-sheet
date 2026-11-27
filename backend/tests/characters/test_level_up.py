"""Підвищення рівня: план, застосування, межі правил.

Кожне очікуване число перевіряється з книгою гравця:

* Воїн 2 рівня: +середнє d10 (6) +0 Статури = 16 хітів, вміння «Action Surge»;
* кидок 8 на 3 рівні стає на **своє** місце в пулі, навіть якщо рівень узято
  в класі, який стоїть у списку не останнім;
* покращення характеристик дають рівні 4/6/8/12/14/16/19 — у Воїна їх
  більше, ніж у мага, і це береться з індексу механік, а не з константи;
* межа 20 діє і на характеристику, і на сумарний рівень;
* мультиклас вимагає 13 у ключовій характеристиці нового класу й наявних
  (PHB, p. 163).
"""

from __future__ import annotations

import pytest

from dndsheet.characters.application.level_up import LevelUpService
from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.services.level_up import LevelUpPlanner
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.shared.errors import ConflictError, ValidationError
from dndsheet.shared.kernel import Ability, AbilityScore

from helpers import make_character


class Subclasses:
    """Підкласи для тесту: домен бере їх із порту, а не з довідника."""

    def __init__(self, keys: dict[str, tuple[str, ...]] | None = None) -> None:
        self._keys = keys or {
            "fighter": ("phb-2014/subclass/champion",),
            "wizard": ("phb-2014/subclass/evocation",),
            "warlock": ("phb-2014/subclass/the-fiend",),
        }

    def subclass_keys(self, class_key: str) -> tuple[str, ...] | None:
        return self._keys.get(class_key.strip().casefold())


class Feats:
    def __init__(self, keys: tuple[str, ...] = ("phb-2014/feat/alert",)) -> None:
        self._keys = tuple(key.casefold() for key in keys)

    def has(self, feat_key: str) -> bool:
        return feat_key.strip().casefold() in self._keys

    def ability_options(self, feat_key: str) -> tuple:
        return ()


class Repository:
    def __init__(self, character) -> None:  # noqa: ANN001
        self.character = character

    def save(self, character) -> None:  # noqa: ANN001
        self.character = character

    def get(self, character_id: str):  # noqa: ANN201
        return self.character if character_id == self.character.id else None

    def ids(self) -> tuple[str, ...]:
        return (self.character.id,)


@pytest.fixture()
def service(rules) -> LevelUpService:  # noqa: ANN001
    character = make_character(rules)
    return LevelUpService(
        characters=Repository(character),
        subclasses=Subclasses(),
        feats=Feats(),
    )


def planner(rules) -> LevelUpPlanner:  # noqa: ANN001
    return LevelUpPlanner()


def mage_ready(rules, **overrides):  # noqa: ANN001, ANN003
    """Воїн 1, готовий до мультикласу в мага: STR 13 (вимога Воїна) і INT 13."""
    abilities = {ability: AbilityScore(10) for ability in Ability}
    abilities[Ability.STR] = AbilityScore(13)
    abilities[Ability.INT] = AbilityScore(13)
    return make_character(rules, abilities=abilities, **overrides)


# ---------------------------------------------------------------------------
# план
# ---------------------------------------------------------------------------


def test_plan_lists_every_class(rules) -> None:  # noqa: ANN001
    character = make_character(rules)
    plans = {plan.class_key: plan for plan in planner(rules).plans(character)}

    # Наявний Воїн і всі класи, які знає джерело правил.
    assert "fighter" in plans
    assert plans["fighter"].is_new_class is False
    assert plans["fighter"].new_level == 2
    # У фікстурі пʼять класів: Воїн, Варлок, Маг, Жрець, Плут.
    assert set(plans) == {"fighter", "warlock", "wizard", "cleric", "rogue"}
    assert plans["wizard"].is_new_class is True
    assert plans["wizard"].current_level == 0


def test_plan_fighter_second_level(rules) -> None:  # noqa: ANN001
    character = make_character(rules)
    plan = planner(rules).plan(character, "fighter")

    assert plan.hit_die == 10
    assert plan.constitution_modifier == 0
    assert plan.hp_average == 6  # половина d10 + 1
    assert plan.hp_best_roll == 10
    # «Action Surge» зʼявляється на 2 рівні; «Second Wind» уже був.
    assert [feature.name_en for feature in plan.features] == ["Action Surge"]
    assert plan.asi_pending is False
    assert plan.proficiency_bonus_before == plan.proficiency_bonus_after == 2
    assert plan.slots == ()


def test_plan_shows_multiclass_requirement(rules) -> None:  # noqa: ANN001
    character = make_character(rules)  # усі характеристики 10
    plan = planner(rules).plan(character, "wizard")

    assert plan.allowed is False
    assert "INT 13" in (plan.blocked_reason or "")
    assert plan.requirements == ("INT 13",)


def test_multiclass_allowed_with_requirement(rules) -> None:  # noqa: ANN001
    character = mage_ready(rules)

    plan = planner(rules).plan(character, "wizard")
    assert plan.allowed is True
    assert plan.blocked_reason is None
    # Новий клас дає ліміт заговорів мага й одразу слоти (див. наступний тест).
    assert plan.cantrips_after == 3


def test_new_class_slots_appear_in_plan(rules) -> None:  # noqa: ANN001
    character = mage_ready(rules)

    plan = planner(rules).plan(character, "wizard")
    assert [(row.level, row.before, row.after) for row in plan.slots] == [(1, 0, 2)]
    assert plan.caster_level_before == 0
    assert plan.caster_level_after == 1
    assert plan.max_spell_level == 1


def test_plan_marks_asi_levels(rules) -> None:  # noqa: ANN001
    character = make_character(
        rules, classes=[CharacterClass(class_key="fighter", level=3)]
    )
    plan = planner(rules).plan(character, "fighter")

    assert plan.new_level == 4
    assert plan.asi_pending is True
    assert plan.asi_slots == 1
    # Підклас обрано ще не був — на 3 рівні план просив би його.
    assert plan.subclass_required is True


def test_twenty_levels_have_no_plan(rules) -> None:  # noqa: ANN001
    character = make_character(
        rules, classes=[CharacterClass(class_key="fighter", level=20)]
    )
    assert planner(rules).plans(character) == ()
    with pytest.raises(ValidationError):
        planner(rules).plan(character, "fighter")


# ---------------------------------------------------------------------------
# застосування
# ---------------------------------------------------------------------------


def test_apply_fighter_second_level(service: LevelUpService) -> None:
    character, report = service.apply("c-1", {"class_key": "fighter", "hp": {"mode": "average"}})

    assert character.total_level == 2
    assert character.hit_dice_pool == {10: 2}
    # 10 (1 рівень, максимум d10) + 6 (середнє d10) = 16.
    assert report.hp_max_before == 10
    assert report.hp_max_after == 16
    assert report.features == ("Action Surge",)
    assert report.proficiency_bonus_after == 2


def test_apply_roll_uses_new_level(service: LevelUpService) -> None:
    character, report = service.apply(
        "c-1", {"class_key": "fighter", "hp": {"mode": "roll", "roll": 8}}
    )

    assert character.hp.rolls == (8,)
    assert report.hp_max_after == 18  # 10 + 8


def test_roll_for_earlier_class_does_not_shift_others(rules) -> None:  # noqa: ANN001
    """Кидок у класі, що стоїть не останнім, стає на своє місце в пулі."""
    character = make_character(
        rules,
        classes=[
            CharacterClass(class_key="fighter", level=2),
            CharacterClass(class_key="wizard", level=2),
        ],
        hp=HitPointState(rolls=(7, 5)),
    )
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses(), feats=Feats())

    # Маг дає середнє 4 (d6/2+1), тому 10 + 7 + 4 + 5 = 26.
    before = service.calculator.compute(character).hit_points.maximum
    assert before == 26

    character, report = service.apply(
        "c-1",
        {
            "class_key": "fighter",
            "hp": {"mode": "roll", "roll": 9},
            "subclass_key": "phb-2014/subclass/champion",
        },
    )

    # 10 + 7 + 9 (Воїн 3) + 4 (Маг 2 середнє) + 5 (Маг 1) = 35.
    assert character.hp.rolls == (7, 9, 5)
    assert report.hp_max_after == 35


def test_apply_multiclass(rules) -> None:  # noqa: ANN001
    character = mage_ready(rules)
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())

    character, report = service.apply(
        "c-1", {"class_key": "wizard", "hp": {"mode": "average"}}
    )

    assert report.is_new_class is True
    assert [entry.class_key for entry in character.classes] == ["fighter", "wizard"]
    assert character.total_level == 2
    assert report.hp_max_after == 10 + 4  # середнє d6 + 0 Статури
    sheet = service.calculator.compute(character)
    assert sheet.spellcasting.caster_level == 1
    assert sheet.spellcasting.slots.by_level == ((1, 2),)


def test_multiclass_blocked_without_requirement(service: LevelUpService) -> None:
    with pytest.raises(ValidationError) as error:
        service.apply("c-1", {"class_key": "wizard"})
    assert "INT 13" in str(error.value)


def test_subclass_required_at_third_level(rules) -> None:  # noqa: ANN001
    character = make_character(
        rules, classes=[CharacterClass(class_key="fighter", level=2)]
    )
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())

    with pytest.raises(ValidationError) as error:
        service.apply("c-1", {"class_key": "fighter"})
    assert "Martial Archetype" in str(error.value)

    character, report = service.apply(
        "c-1",
        {"class_key": "fighter", "subclass_key": "phb-2014/subclass/champion"},
    )
    assert report.subclass_key == "phb-2014/subclass/champion"
    assert character.classes[0].subclass_key == "phb-2014/subclass/champion"


def test_unknown_subclass_rejected(rules) -> None:  # noqa: ANN001
    character = make_character(
        rules, classes=[CharacterClass(class_key="fighter", level=2)]
    )
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())

    with pytest.raises(ValidationError):
        service.apply("c-1", {"class_key": "fighter", "subclass_key": "нічого"})


def test_asi_increases_two_abilities(rules) -> None:  # noqa: ANN001
    character = make_character(
        rules, classes=[CharacterClass(class_key="fighter", level=3)]
    )
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())

    character, report = service.apply(
        "c-1",
        {
            "class_key": "fighter",
            "subclass_key": "phb-2014/subclass/champion",
            "ability_increases": {"str": 1, "con": 1},
        },
    )

    assert character.ability(Ability.STR).value == 11
    assert character.ability(Ability.CON).value == 11
    assert character.asi_taken == 1
    assert report.ability_increases == (("con", 1), ("str", 1))


def test_asi_needs_a_choice(rules) -> None:  # noqa: ANN001
    character = make_character(
        rules, classes=[CharacterClass(class_key="fighter", level=3)]
    )
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())

    with pytest.raises(ValidationError) as error:
        service.apply(
            "c-1",
            {"class_key": "fighter", "subclass_key": "phb-2014/subclass/champion"},
        )
    assert "покращення характеристик" in str(error.value)


def test_asi_choice_rejected_when_level_gives_none(service: LevelUpService) -> None:
    with pytest.raises(ValidationError):
        service.apply(
            "c-1",
            {"class_key": "fighter", "ability_increases": {"str": 2}},
        )


def test_asi_cannot_pass_twenty(rules) -> None:  # noqa: ANN001
    abilities = {ability: AbilityScore(10) for ability in Ability}
    abilities[Ability.STR] = AbilityScore(19)
    character = make_character(
        rules,
        abilities=abilities,
        classes=[CharacterClass(class_key="fighter", level=3)],
    )
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())

    with pytest.raises(ValidationError) as error:
        service.apply(
            "c-1",
            {
                "class_key": "fighter",
                "subclass_key": "phb-2014/subclass/champion",
                "ability_increases": {"str": 2},
            },
        )
    assert "20" in str(error.value)


def test_species_bonus_counts_toward_twenty(rules) -> None:  # noqa: ANN001
    """Людина має +1 до всього: 19 + 1 = 20, тож +2 уже не пройде."""
    abilities = {ability: AbilityScore(10) for ability in Ability}
    abilities[Ability.STR] = AbilityScore(18)
    character = make_character(
        rules,
        abilities=abilities,
        species_key="human",
        classes=[CharacterClass(class_key="fighter", level=3)],
    )
    assert character.ability_bonus_from_origin(Ability.STR) == 1
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())

    with pytest.raises(ValidationError):
        service.apply(
            "c-1",
            {
                "class_key": "fighter",
                "subclass_key": "phb-2014/subclass/champion",
                "ability_increases": {"str": 2},
            },
        )


def test_feat_instead_of_asi(rules) -> None:  # noqa: ANN001
    character = make_character(
        rules, classes=[CharacterClass(class_key="fighter", level=3)]
    )
    service = LevelUpService(
        characters=Repository(character), subclasses=Subclasses(), feats=Feats()
    )

    character, report = service.apply(
        "c-1",
        {
            "class_key": "fighter",
            "subclass_key": "phb-2014/subclass/champion",
            "feat_key": "PHB-2014/feat/alert",
        },
    )

    assert report.feat_key == "PHB-2014/feat/alert"
    assert character.feats == ("phb-2014/feat/alert",)
    assert character.asi_taken == 1


def test_unknown_feat_rejected(rules) -> None:  # noqa: ANN001
    character = make_character(
        rules, classes=[CharacterClass(class_key="fighter", level=3)]
    )
    service = LevelUpService(
        characters=Repository(character), subclasses=Subclasses(), feats=Feats()
    )

    with pytest.raises(ValidationError):
        service.apply(
            "c-1",
            {
                "class_key": "fighter",
                "subclass_key": "phb-2014/subclass/champion",
                "feat_key": "phb-2014/feat/нічого",
            },
        )


def test_spell_learned_at_level_up(rules) -> None:  # noqa: ANN001
    abilities = {ability: AbilityScore(10) for ability in Ability}
    abilities[Ability.CHA] = AbilityScore(13)
    character = make_character(
        rules,
        abilities=abilities,
        classes=[
            CharacterClass(
                class_key="warlock",
                level=1,
                subclass_key="phb-2014/subclass/the-fiend",
            )
        ],
    )
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())

    # Pact Magic дає 2 відомих закляття на 1 рівні й 3 на 2-му.
    character, report = service.apply(
        "c-1",
        {
            "class_key": "warlock",
            "spells": [
                {"name_en": "hex", "level": 1, "prepared": False},
                {"name_en": "charm person", "level": 1},
            ],
        },
    )

    assert report.spells_added == ("hex", "charm person")
    assert [spell.name_en for spell in character.spells] == ["hex", "charm person"]
    assert character.spells[0].class_key == "warlock"


def test_spell_of_other_class_rejected(rules) -> None:  # noqa: ANN001
    abilities = {ability: AbilityScore(10) for ability in Ability}
    abilities[Ability.CHA] = AbilityScore(13)
    character = make_character(
        rules,
        abilities=abilities,
        classes=[
            CharacterClass(
                class_key="warlock",
                level=1,
                subclass_key="phb-2014/subclass/the-fiend",
            )
        ],
    )
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())

    with pytest.raises(ValidationError):
        service.apply(
            "c-1",
            {
                "class_key": "warlock",
                "spells": [{"name_en": "hex", "level": 1, "class_key": "wizard"}],
            },
        )


def test_version_conflict(service: LevelUpService) -> None:
    with pytest.raises(ConflictError):
        service.apply("c-1", {"class_key": "fighter"}, expected_version=99)


def test_asi_counter_survives_reload(rules, tmp_data) -> None:  # noqa: ANN001
    """Лічильник покращень зберігається у файлі, а не губиться при читанні."""
    from dndsheet.characters.infrastructure.character_json import (
        character_from_record,
        character_to_record,
    )

    character = make_character(
        rules,
        classes=[CharacterClass(class_key="fighter", level=4)],
        asi_taken=1,
    )
    record = character_to_record(character)
    assert record["asi_taken"] == 1
    restored = character_from_record(record, rules)
    assert restored.asi_taken == 1
    assert restored.asi_slots == 1


def test_asi_counter_cannot_exceed_slots(rules) -> None:  # noqa: ANN001
    with pytest.raises(ValidationError):
        make_character(
            rules,
            classes=[CharacterClass(class_key="fighter", level=3)],
            asi_taken=1,
        )


# ---------------------------------------------------------------------------
# ігнорування вимог мультикласу (правило дому)
# ---------------------------------------------------------------------------


def test_ignore_requirements_adds_class_and_marks_it(rules) -> None:  # noqa: ANN001
    character = make_character(rules)  # усі 10: INT 13 для мага немає
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())

    character, report = service.apply(
        "c-1",
        {"class_key": "wizard", "ignore_requirements": True, "hp": {"mode": "average"}},
    )

    assert [entry.class_key for entry in character.classes] == ["fighter", "wizard"]
    assert report.requirements_ignored is True
    assert report.ignored_requirements == ("INT 13",)
    # Позначка не вигадує виконаних вимог: вона каже саме те, що сталося.
    assert [waiver.class_key for waiver in character.multiclass_waivers] == ["wizard"]
    assert character.multiclass_waivers[0].requirements == ("INT 13",)


def test_ignore_flag_marks_nothing_when_requirements_are_met(rules) -> None:  # noqa: ANN001
    character = mage_ready(rules)
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())

    character, report = service.apply(
        "c-1", {"class_key": "wizard", "ignore_requirements": True}
    )

    assert report.requirements_ignored is False
    assert character.multiclass_waivers == ()


def test_waiver_is_removed_with_its_class(rules) -> None:  # noqa: ANN001
    character = make_character(rules)
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())
    character, _ = service.apply(
        "c-1", {"class_key": "wizard", "ignore_requirements": True}
    )

    character.remove_class("wizard")

    assert character.multiclass_waivers == ()


def test_waiver_survives_reload(rules) -> None:  # noqa: ANN001
    """Позначка живе у файлі: після читання лист усе ще знає про обхід."""
    from dndsheet.characters.infrastructure.character_json import (
        character_from_record,
        character_to_record,
    )

    character = make_character(rules)
    service = LevelUpService(characters=Repository(character), subclasses=Subclasses())
    character, _ = service.apply(
        "c-1", {"class_key": "wizard", "ignore_requirements": True}
    )

    record = character_to_record(character)
    assert record["multiclass_waivers"] == [
        {"class_key": "wizard", "requirements": ["INT 13"]}
    ]
    restored = character_from_record(record, rules)
    assert restored.multiclass_waivers[0].class_key == "wizard"
    assert restored.multiclass_waivers[0].requirements == ("INT 13",)


def test_waiver_for_missing_class_rejected(rules) -> None:  # noqa: ANN001
    from dndsheet.characters.domain.class_level import MulticlassWaiver

    with pytest.raises(ValidationError):
        make_character(rules, multiclass_waivers=(MulticlassWaiver(class_key="wizard"),))
