"""Рядки володінь: одне й те саме володіння не має друкуватися двічі.

Домен зберігає володіння разом із джерелом, і «Атлетика від класу» та
«Атлетика від передісторії» — це справді два записи. Але два записи з
однаковим джерелом — це той самий факт, записаний двічі; саме так виглядав
лист, коли чернетка зберегла вибір повторно.
"""

from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    Proficiencies,
    SourceKind,
)
from dndsheet.characters.application.rows import proficiency_rows


def test_identical_grants_collapse_to_one_row() -> None:
    source = GrantSource.of(SourceKind.CLASS, "fighter")
    collected = Proficiencies(
        items=(
            Proficiency(kind=ProficiencyKind.SKILL, value="athletics", source=source),
            Proficiency(kind=ProficiencyKind.SKILL, value="athletics", source=source),
            Proficiency(kind=ProficiencyKind.SKILL, value="Athletics", source=source),
        )
    )

    rows = proficiency_rows(collected)

    assert len(rows) == 1
    assert rows[0].value == "athletics"
    assert rows[0].source_kind == "class"


def test_same_grant_from_different_sources_stays() -> None:
    collected = Proficiencies(
        items=(
            Proficiency(
                kind=ProficiencyKind.SKILL,
                value="athletics",
                source=GrantSource.of(SourceKind.CLASS, "fighter"),
            ),
            Proficiency(
                kind=ProficiencyKind.SKILL,
                value="athletics",
                source=GrantSource.of(SourceKind.BACKGROUND, "soldier"),
            ),
        )
    )

    rows = proficiency_rows(collected)

    assert [row.source_kind for row in rows] == ["class", "background"]


def test_different_kinds_with_the_same_value_stay() -> None:
    source = GrantSource.of(SourceKind.SPECIES, "dwarf")
    collected = Proficiencies(
        items=(
            Proficiency(kind=ProficiencyKind.TOOL, value="tools", source=source),
            Proficiency(kind=ProficiencyKind.LANGUAGE, value="tools", source=source),
        )
    )

    assert len(proficiency_rows(collected)) == 2
