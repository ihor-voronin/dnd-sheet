"""Експертність плута й барда: слоти, вибір і подвоєний бонус майстерності."""

from __future__ import annotations

import pytest

from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiencies,
    Proficiency,
    ProficiencyKind,
    SourceKind,
)
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.infrastructure.character_json import (
    character_from_record,
    character_to_record,
)
from dndsheet.compendium.infrastructure.mechanics_index import JsonMechanicsRepository
from dndsheet.shared.errors import ValidationError
from dndsheet.shared.kernel import Skill

from helpers import make_character


@pytest.fixture()
def corpus_rules():
    repository = JsonMechanicsRepository()
    if not repository.available():
        pytest.skip("немає індексу механік (content/index/*-mechanics.json)")
    return repository


def _pick(skill: Skill) -> Proficiency:
    return Proficiency(
        kind=ProficiencyKind.SKILL,
        value=skill.value,
        source=GrantSource.of(SourceKind.CLASS, "rogue"),
    )


def _rogue(rules, level: int = 1):
    return make_character(
        rules,
        classes=[CharacterClass(class_key="rogue", level=level)],
        chosen=Proficiencies(
            items=tuple(
                _pick(skill)
                for skill in (Skill.STEALTH, Skill.ACROBATICS, Skill.PERCEPTION, Skill.DECEPTION)
            )
        ),
    )


def test_rogue_gets_two_then_four_expertise_slots(corpus_rules) -> None:
    assert _rogue(corpus_rules, 1).expertise_slots == 2
    assert _rogue(corpus_rules, 5).expertise_slots == 2
    assert _rogue(corpus_rules, 6).expertise_slots == 4


def test_fighter_has_no_expertise(corpus_rules) -> None:
    assert make_character(corpus_rules).expertise_slots == 0


def test_expertise_doubles_proficiency_bonus(corpus_rules) -> None:
    character = _rogue(corpus_rules)
    before = DerivedStatsCalculator().compute(character).skills[Skill.STEALTH]
    character.set_expertise(["stealth", "perception"])
    computed = DerivedStatsCalculator().compute(character)
    assert computed.skills[Skill.STEALTH] == before + 2  # бонус майстерності 1 рівня
    assert computed.skill_expertise[Skill.STEALTH] is True
    assert computed.skill_expertise[Skill.ATHLETICS] is False


def test_expertise_limited_by_slots(corpus_rules) -> None:
    character = _rogue(corpus_rules)
    with pytest.raises(ValidationError):
        character.set_expertise(["stealth", "perception", "acrobatics"])


def test_expertise_requires_proficiency(corpus_rules) -> None:
    character = _rogue(corpus_rules)
    with pytest.raises(ValidationError):
        character.set_expertise(["athletics"])


def test_expertise_survives_json(corpus_rules) -> None:
    character = _rogue(corpus_rules)
    character.set_expertise(["stealth"])
    restored = character_from_record(character_to_record(character), corpus_rules)
    assert restored.expertise == ("stealth",)
