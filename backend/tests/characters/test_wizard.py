"""Чернетка візарда: кроки, їхній порядок, повернення назад."""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.inventory import InventoryItem, ItemKind
from dndsheet.characters.domain.pick_rules import (
    validate_origin_pick,
    validate_pick,
)
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    Proficiencies,
    SourceKind,
)
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.characters.domain.wizard import (
    STEP_ORDER,
    AbilityMethod,
    Draft,
    WizardStep,
)
from dndsheet.shared.errors import NotFoundError, ValidationError
from dndsheet.shared.kernel import Ability, Money

from helpers import make_character  # noqa: F401

A = Ability


@pytest.fixture()
def draft(rules) -> Draft:
    return Draft(id="draft-1", rules=rules)


def _pick(kind: ProficiencyKind, value: str, source: SourceKind, key: str) -> Proficiency:
    return Proficiency(kind=kind, value=value, source=GrantSource.of(source, key))


def _skills(*values: str, source: SourceKind = SourceKind.CLASS, key: str = "fighter"):
    return [_pick(ProficiencyKind.SKILL, value, source, key) for value in values]


def _scores(**values: int) -> dict[Ability, int]:
    return {A(name): score for name, score in values.items()}


def _fill_fighter(draft: Draft) -> Draft:
    draft.apply_species(name="Дарія", species_key="human")
    draft.apply_class(class_key="fighter")
    draft.apply_abilities(
        method=AbilityMethod.STANDARD_ARRAY,
        scores=_scores(str=15, dex=14, con=13, int=12, wis=10, cha=8),
    )
    draft.apply_background(
        background_key="soldier",
        picks=_skills("athletics", "intimidation", "perception", "survival")[:2],
    )
    return draft


# ---------------------------------------------------------------------------
# порядок кроків і навігація
# ---------------------------------------------------------------------------


def test_steps_cannot_be_skipped(draft: Draft) -> None:
    statuses = {status.step: status for status in draft.statuses()}
    assert statuses[WizardStep.SPECIES].unlocked is True
    for step in STEP_ORDER[1:]:
        assert statuses[step].unlocked is False, f"{step} не має бути доступним"
    assert draft.next_step() is WizardStep.SPECIES


def test_steps_unlock_one_by_one(draft: Draft) -> None:
    draft.apply_species(name="Дарія", species_key="human")
    statuses = {status.step: status for status in draft.statuses()}
    assert statuses[WizardStep.SPECIES].complete is True
    assert statuses[WizardStep.CLASS].unlocked is True
    assert statuses[WizardStep.ABILITIES].unlocked is False


def test_going_back_and_forth_keeps_state(draft: Draft) -> None:
    _fill_fighter(draft)
    revision = draft.revision
    draft.apply_species(name="Дарія", species_key="human")
    assert draft.revision == revision + 1, "повторне підтвердження кроку теж ревізія"
    assert draft.class_key == "fighter"
    assert draft.name == "Дарія"
    draft.apply_class(class_key="fighter")
    assert draft.ability_scores[A.CON] == 13


# ---------------------------------------------------------------------------
# вид
# ---------------------------------------------------------------------------


def test_name_is_required(draft: Draft) -> None:
    with pytest.raises(ValidationError, match="імʼя"):
        draft.apply_species(name="  ", species_key="human")


def test_unknown_species(draft: Draft) -> None:
    with pytest.raises(NotFoundError, match="немає правил виду"):
        draft.apply_species(name="Хтось", species_key="gnome")


def test_subspecies_must_belong_to_species(draft: Draft) -> None:
    with pytest.raises(ValidationError, match="не належить"):
        draft.apply_species(name="Хтось", species_key="human", subspecies_key="wood elf")


def test_subspecies_required_where_it_gives_numbers(draft: Draft) -> None:
    """Ельф без підраси — незакінчений вибір, а не «ельф без уточнень»."""
    with pytest.raises(ValidationError, match="оберіть підрасу"):
        draft.apply_species(name="Хтось", species_key="elf")

    draft.apply_species(name="Хтось", species_key="elf", subspecies_key="wood elf")
    assert draft.species_key == "elf"
    assert draft.subspecies_key == "wood elf"


def test_subspecies_optional_for_human(draft: Draft) -> None:
    """«Variant Human» — варіант, а не обовʼязок: звичайна людина теж грає."""
    draft.apply_species(name="Хтось", species_key="human")
    assert draft.subspecies_key is None


def test_species_ability_choice_must_match(draft: Draft) -> None:
    with pytest.raises(ValidationError, match="обрати 2"):
        draft.apply_species(name="Хтось", species_key="half-elf", ability_choices=(A.STR,))
    draft.apply_species(
        name="Хтось", species_key="half-elf", ability_choices=(A.STR, A.DEX)
    )
    assert draft.ability_choices == (A.STR, A.DEX)


# ---------------------------------------------------------------------------
# вільний розподіл характеристик (правила 2022)
# ---------------------------------------------------------------------------


def test_unresolved_species_requires_spread(draft: Draft) -> None:
    with pytest.raises(ValidationError, match="2022"):
        draft.apply_species(name="Хтось", species_key="custom lineage")

    draft.apply_species(
        name="Хтось",
        species_key="custom lineage",
        ability_spread={"int": 2, "con": 1},
        species_feat="phb-2014/feat/alert",
    )
    assert draft.ability_spread == {A.INT: 2, A.CON: 1}
    assert draft.ability_bonuses[A.INT] == 2
    assert draft.ability_bonuses[A.CON] == 1


def test_spread_accepts_three_ones(draft: Draft) -> None:
    draft.apply_species(
        name="Хтось",
        species_key="custom lineage",
        ability_spread={"str": 1, "dex": 1, "con": 1},
        species_feat="phb-2014/feat/alert",
    )
    assert draft.ability_bonuses[A.STR] == 1
    assert draft.ability_bonuses[A.DEX] == 1
    assert draft.ability_bonuses[A.CON] == 1


@pytest.mark.parametrize(
    "spread",
    [
        {"str": 3},
        {"str": 2, "dex": 2},
        {"str": 1, "dex": 1},
        {"str": 2, "dex": 1, "con": 1},
        {"str": 1, "dex": 1, "con": 1, "wis": 1},
        {"str": 1, "str2": 2},
    ],
)
def test_spread_shape_is_validated(draft: Draft, spread: dict) -> None:
    with pytest.raises(ValidationError):
        draft.apply_species(
            name="Хтось", species_key="custom lineage", ability_spread=spread
        )


def test_spread_is_not_allowed_for_fixed_species(draft: Draft) -> None:
    """Людина має фіксовані +1 до всіх — вільний розподіл для неї зайвий."""
    with pytest.raises(ValidationError, match="фіксовані"):
        draft.apply_species(
            name="Хтось", species_key="human", ability_spread={"str": 2, "dex": 1}
        )


def test_character_spread_counts_and_survives_reload(rules) -> None:  # noqa: ANN001
    from dndsheet.characters.infrastructure.character_json import (
        character_from_record,
        character_to_record,
    )

    character = make_character(
        rules,
        species_key="custom lineage",
        ability_spread={A.INT: 2, A.CON: 1},
    )
    assert character.ability_bonus_from_origin(A.INT) == 2
    assert character.ability_total(A.INT) == 12
    restored = character_from_record(character_to_record(character), rules)
    assert restored.ability_spread == {A.INT: 2, A.CON: 1}
    assert restored.ability_bonus_from_origin(A.INT) == 2


def test_character_spread_rejected_for_fixed_species(rules) -> None:  # noqa: ANN001
    with pytest.raises(ValidationError):
        make_character(rules, species_key="human", ability_spread={A.STR: 2})


# ---------------------------------------------------------------------------
# клас
# ---------------------------------------------------------------------------


def test_subclass_required_at_level_one(draft: Draft) -> None:
    with pytest.raises(ValidationError, match="Otherworldly Patron"):
        draft.apply_class(class_key="warlock")
    draft.apply_class(class_key="warlock", subclass_key="the-fiend")
    assert draft.subclass_key == "the-fiend"


def test_subclass_forbidden_before_its_level(draft: Draft) -> None:
    with pytest.raises(ValidationError, match="з 3 рівня"):
        draft.apply_class(class_key="fighter", subclass_key="champion")


def test_unknown_class(draft: Draft) -> None:
    with pytest.raises(NotFoundError, match="немає правил класу"):
        draft.apply_class(class_key="mystic")


# ---------------------------------------------------------------------------
# характеристики
# ---------------------------------------------------------------------------


def test_standard_array_is_a_multiset(draft: Draft) -> None:
    draft.apply_class(class_key="fighter")
    with pytest.raises(ValidationError, match="15, 14, 13"):
        draft.apply_abilities(
            method=AbilityMethod.STANDARD_ARRAY,
            scores=_scores(str=15, dex=15, con=13, int=12, wis=10, cha=8),
        )
    draft.apply_abilities(
        method=AbilityMethod.STANDARD_ARRAY,
        scores=_scores(str=15, dex=14, con=13, int=12, wis=10, cha=8),
    )
    assert draft.ability_scores[A.STR] == 15


def test_point_buy_budget(draft: Draft) -> None:
    draft.apply_class(class_key="fighter")
    draft.apply_abilities(
        method=AbilityMethod.POINT_BUY,
        scores=_scores(str=15, dex=15, con=14, int=10, wis=8, cha=8),
    )
    with pytest.raises(ValidationError, match="0 8..15|8..15"):
        draft.apply_abilities(
            method=AbilityMethod.POINT_BUY,
            scores=_scores(str=16, dex=15, con=14, int=10, wis=8, cha=8),
        )
    with pytest.raises(ValidationError, match="з 27"):
        draft.apply_abilities(
            method=AbilityMethod.POINT_BUY,
            scores=_scores(str=15, dex=15, con=15, int=10, wis=8, cha=8),
        )


def test_rolls_must_be_used_exactly(draft: Draft) -> None:
    draft.apply_class(class_key="fighter")
    draft.apply_abilities(
        method=AbilityMethod.ROLLS,
        scores=_scores(str=16, dex=14, con=13, int=12, wis=10, cha=8),
        rolls=(16, 14, 13, 12, 10, 8),
    )
    with pytest.raises(ValidationError, match="кожен кидок"):
        draft.apply_abilities(
            method=AbilityMethod.ROLLS,
            scores=_scores(str=16, dex=14, con=13, int=12, wis=10, cha=8),
            rolls=(16, 14, 13, 12, 10, 9),
        )


def test_ability_cap_counts_species_bonus(draft: Draft) -> None:
    draft.apply_species(name="Хтось", species_key="human")
    draft.apply_class(class_key="fighter")
    with pytest.raises(ValidationError, match="межа"):
        draft.apply_abilities(
            method=AbilityMethod.MANUAL,
            scores=_scores(str=20, dex=10, con=10, int=10, wis=10, cha=10),
        )


# ---------------------------------------------------------------------------
# передісторія й володіння
# ---------------------------------------------------------------------------


def test_class_skills_must_be_chosen(draft: Draft) -> None:
    draft.apply_species(name="Хтось", species_key="human")
    draft.apply_class(class_key="fighter")
    draft.apply_abilities(
        method=AbilityMethod.STANDARD_ARRAY,
        scores=_scores(str=15, dex=14, con=13, int=12, wis=10, cha=8),
    )
    with pytest.raises(ValidationError, match="обрано 0"):
        draft.apply_background(background_key="soldier", picks=[])


def test_pick_must_belong_to_class_list(draft: Draft) -> None:
    draft.apply_species(name="Хтось", species_key="human")
    draft.apply_class(class_key="fighter")
    draft.apply_abilities(
        method=AbilityMethod.STANDARD_ARRAY,
        scores=_scores(str=15, dex=14, con=13, int=12, wis=10, cha=8),
    )
    with pytest.raises(ValidationError, match="не дає навички"):
        draft.apply_background(
            background_key="soldier",
            picks=_skills("arcana", "stealth"),
        )


def test_species_skill_choices_are_required(draft: Draft) -> None:
    draft.apply_species(
        name="Хтось", species_key="half-elf", ability_choices=(A.STR, A.DEX)
    )
    draft.apply_class(class_key="fighter")
    draft.apply_abilities(
        method=AbilityMethod.STANDARD_ARRAY,
        scores=_scores(str=15, dex=14, con=13, int=12, wis=10, cha=8),
    )
    picks = _skills("athletics", "intimidation")
    with pytest.raises(ValidationError, match="Half-Elf"):
        draft.apply_background(background_key="soldier", picks=picks)
    picks += _skills("perception", "survival", source=SourceKind.SPECIES, key="half-elf")
    draft.apply_background(background_key="soldier", picks=picks)
    assert draft.is_complete(WizardStep.BACKGROUND)


def test_changing_class_drops_its_picks(draft: Draft) -> None:
    _fill_fighter(draft)
    assert len(draft.picks) == 2
    draft.apply_class(class_key="rogue")
    assert draft.picks == (), "навички воїна більше не дійсні"
    assert draft.is_complete(WizardStep.BACKGROUND) is False


def test_changing_class_drops_spells(draft: Draft) -> None:
    draft.apply_species(name="Хтось", species_key="human")
    draft.apply_class(class_key="warlock", subclass_key="the-fiend")
    draft.apply_abilities(
        method=AbilityMethod.STANDARD_ARRAY,
        scores=_scores(str=8, dex=14, con=13, int=12, wis=10, cha=15),
    )
    draft.apply_background(
        background_key="soldier",
        picks=_skills("deception", "intimidation", source=SourceKind.CLASS, key="warlock"),
    )
    draft.apply_spells(
        spells=(
            KnownSpell(name_en="Eldritch Blast", level=0, class_key="warlock"),
            KnownSpell(name_en="Hex", level=1, class_key="warlock"),
        )
    )
    draft.apply_class(class_key="fighter")
    assert draft.spells == ()


# ---------------------------------------------------------------------------
# спорядження й закляття
# ---------------------------------------------------------------------------


def test_equipment_validates_inventory(draft: Draft) -> None:
    _fill_fighter(draft)
    draft.apply_equipment(
        items=(
            InventoryItem(
                name_en="chain mail",
                kind=ItemKind.ARMOR,
                armor_base=16,
                dex_cap=0,
                equipped=True,
            ),
            InventoryItem(name_en="longsword", kind=ItemKind.WEAPON, weight_lb=3),
        ),
        money=Money(gp=10),
    )
    with pytest.raises(ValidationError, match="одну броню"):
        draft.apply_equipment(
            items=(
                InventoryItem(name_en="chain mail", kind=ItemKind.ARMOR, armor_base=16, equipped=True),
                InventoryItem(name_en="leather", kind=ItemKind.ARMOR, armor_base=11, equipped=True),
            )
        )


def test_spell_limits_for_warlock(draft: Draft) -> None:
    draft.apply_species(name="Хтось", species_key="human")
    draft.apply_class(class_key="warlock", subclass_key="the-fiend")
    draft.apply_abilities(
        method=AbilityMethod.STANDARD_ARRAY,
        scores=_scores(str=8, dex=14, con=13, int=12, wis=10, cha=15),
    )
    draft.apply_background(
        background_key="soldier",
        picks=_skills("deception", "intimidation", source=SourceKind.CLASS, key="warlock"),
    )
    with pytest.raises(ValidationError, match="заговорів"):
        draft.apply_spells(
            spells=tuple(
                KnownSpell(name_en=f"Cantrip {index}", level=0, class_key="warlock")
                for index in range(3)
            )
        )
    with pytest.raises(ValidationError, match="рівня"):
        draft.apply_spells(
            spells=(KnownSpell(name_en="Misty Step", level=2, class_key="warlock"),)
        )
    draft.apply_spells(
        spells=(
            KnownSpell(name_en="Eldritch Blast", level=0, class_key="warlock"),
            KnownSpell(name_en="Hex", level=1, class_key="warlock"),
        )
    )
    assert draft.is_complete(WizardStep.SPELLS)


def test_non_caster_cannot_have_spells(draft: Draft) -> None:
    _fill_fighter(draft)
    with pytest.raises(ValidationError, match="не чарує"):
        draft.apply_spells(
            spells=(KnownSpell(name_en="Fire Bolt", level=0, class_key="fighter"),)
        )
    assert draft.is_complete(WizardStep.SPELLS) is True


# ---------------------------------------------------------------------------
# готовий персонаж
# ---------------------------------------------------------------------------


def test_to_character_builds_level_one(draft: Draft) -> None:
    _fill_fighter(draft)
    draft.apply_equipment(
        items=(
            InventoryItem(
                name_en="chain mail",
                kind=ItemKind.ARMOR,
                armor_base=16,
                dex_cap=0,
                equipped=True,
            ),
        ),
        money=Money(gp=10),
    )
    character = draft.to_character("c-1")
    assert character.total_level == 1
    assert character.name == "Дарія"
    assert character.class_level("fighter") == 1
    assert character.ability(A.STR).value == 15, "характеристики — базові, без бонусу виду"
    assert character.all_proficiencies().has(ProficiencyKind.SKILL, "athletics")
    # Навички передісторії приходять із правил, а не з вибору.
    assert character.all_proficiencies().has(ProficiencyKind.SKILL, "athletics")
    assert character.inventory.money.gp == 10


def test_to_character_requires_all_steps(draft: Draft) -> None:
    _fill_fighter(draft)
    draft.apply_class(class_key="rogue")
    with pytest.raises(ValidationError):
        draft.to_character("c-1")


def test_wizard_needs_cantrips_and_can_prepare(draft: Draft) -> None:
    draft.apply_species(name="Мірта", species_key="human")
    draft.apply_class(class_key="wizard")
    draft.apply_abilities(
        method=AbilityMethod.STANDARD_ARRAY,
        scores=_scores(str=8, dex=14, con=13, int=15, wis=12, cha=10),
    )
    draft.apply_background(
        background_key="acolyte",
        picks=_skills("arcana", "history", source=SourceKind.CLASS, key="wizard"),
    )
    draft.apply_spells(
        spells=(
            KnownSpell(name_en="Fire Bolt", level=0, class_key="wizard"),
            KnownSpell(name_en="Mage Hand", level=0, class_key="wizard"),
            KnownSpell(name_en="Light", level=0, class_key="wizard"),
            KnownSpell(name_en="Magic Missile", level=1, class_key="wizard", prepared=True),
        )
    )
    character = draft.to_character("c-2")
    assert character.species_key == "human"
    assert len(character.spells) == 4


# ---------------------------------------------------------------------------
# самі правила вибору (спільні з агрегатом)
# ---------------------------------------------------------------------------


def test_pick_rules_reject_foreign_source(rules) -> None:
    pick = _pick(ProficiencyKind.SKILL, "arcana", SourceKind.CLASS, "fighter")
    with pytest.raises(ValidationError, match="не дає навички"):
        validate_pick(rules, pick, existing=Proficiencies())


def test_origin_pick_language_limit(rules) -> None:
    pick = _pick(ProficiencyKind.LANGUAGE, "dwarvish", SourceKind.SPECIES, "half-elf")
    validate_origin_pick(
        pick,
        Proficiencies(),
        skills=set(),
        skill_any=2,
        tool_any=0,
        language_any=1,
        label="Half-Elf",
    )
    with pytest.raises(ValidationError, match="вичерпано"):
        validate_origin_pick(
            pick,
            Proficiencies(items=(pick,)),
            skills=set(),
            skill_any=2,
            tool_any=0,
            language_any=1,
            label="Half-Elf",
        )


# ---------------------------------------------------------------------------
# заговори виду й підклас на 1 рівні
# ---------------------------------------------------------------------------


def test_high_elf_must_choose_one_cantrip(draft: Draft) -> None:
    with pytest.raises(ValidationError, match="заговорів"):
        draft.apply_species(name="Ельф", species_key="elf", subspecies_key="high elf")
    draft.apply_species(
        name="Ельф",
        species_key="elf",
        subspecies_key="high elf",
        spell_choices=("fire bolt",),
    )
    assert draft.spell_choices == ("fire bolt",)
    with pytest.raises(ValidationError, match="заговорів"):
        draft.apply_species(
            name="Ельф",
            species_key="elf",
            subspecies_key="high elf",
            spell_choices=("fire bolt", "light"),
        )


def test_2022_species_are_rejected(draft: Draft) -> None:
    with pytest.raises(ValidationError, match="2022"):
        draft.apply_species(name="Хтось", species_key="custom lineage")


def test_class_without_choice_rejects_spell_choices(draft: Draft) -> None:
    with pytest.raises(ValidationError, match="не дає вибору"):
        draft.apply_species(name="Людина", species_key="human", spell_choices=("light",))

