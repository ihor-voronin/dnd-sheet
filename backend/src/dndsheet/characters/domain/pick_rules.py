"""Правила вибору володінь — спільні для агрегату й чернетки візарда.

Вибір навички не є вільним: клас дає «дві з цього списку», передісторія — свої
дві фіксовані, вид — іноді «будь-яку» навичку, мову чи інструмент. Той самий
код перевіряє і готового персонажа (`Character.pick`), і крок візарда, який ще
не став персонажем. Тому правила живуть окремо від агрегату, а не в ньому.

Помилки тут — `ValidationError` з людським текстом: візард показує їх просто
на кроці, не перекладаючи код у повідомлення.
"""

from __future__ import annotations

from dndsheet.characters.domain.ports import RulesSource
from dndsheet.characters.domain.proficiencies import (
    Proficiencies,
    Proficiency,
    ProficiencyKind,
    SourceKind,
)
from dndsheet.shared.errors import NotFoundError, ValidationError
from dndsheet.shared.kernel import Skill
from dndsheet.shared.rules import MULTICLASS_SKILLS, MUSICAL_INSTRUMENTS

#: Підписи, які не є володінням, а описують вибір («three musical instruments
#: of your choice»). Такий вибір робить гравець, і він приходить як `pick`.
CHOICE_MARKERS = ("of your choice", "choose", "any ")


def is_choice_label(value: str) -> bool:
    """Чи це не володіння, а запрошення обрати («any two skills»)."""
    text = value.casefold()
    return any(marker in text for marker in CHOICE_MARKERS)


def count_picks(existing: Proficiencies, kind: ProficiencyKind, source) -> int:  # noqa: ANN001
    """Скільки вже обрано володінь цього виду з цього джерела."""
    return sum(1 for item in existing.items if item.kind is kind and item.source == source)


def validate_pick(
    rules: RulesSource,
    pick: Proficiency,
    *,
    existing: Proficiencies,
    multiclass: bool = False,
) -> None:
    """Перевірити одне володіння проти правил його джерела.

    `existing` — уже прийняті володіння (без цього). Так ліміти «не більше
    двох навичок» рахуються без окремого стану.
    """
    source = pick.source
    if source.kind is SourceKind.CLASS:
        definition = rules.class_mechanics(source.key)
        if definition is None:
            raise NotFoundError(f"немає правил класу {source.key!r}")
        if (
            pick.kind is ProficiencyKind.TOOL
            and multiclass
            and any("musical instrument" in tool.casefold() for tool in definition.multiclass_tools)
        ):
            if pick.value.strip().casefold() not in MUSICAL_INSTRUMENTS:
                raise ValidationError(f"{pick.value!r} — не музичний інструмент")
            if count_picks(existing, ProficiencyKind.TOOL, source) >= 1:
                raise ValidationError(f"клас {definition.name_en!r} дає при мультикласі один інструмент")
            return
        if pick.kind is not ProficiencyKind.SKILL:
            raise ValidationError(f"клас {definition.name_en!r} дає володіння навичками — оберіть навичку")
        try:
            skill = Skill(pick.value.strip().casefold().replace(" ", "_"))
        except ValueError as exc:
            raise ValidationError(f"невідома навичка {pick.value!r}") from exc
        if definition.skill_any == 0 and skill not in definition.skill_options():
            raise ValidationError(f"клас {definition.name_en!r} не дає навички {skill.value!r}")
        used = count_picks(existing, ProficiencyKind.SKILL, source)
        # Другий клас дає не «2 зі списку», а таблицю мультикласу (PHB, p. 164).
        limit = MULTICLASS_SKILLS.get(definition.key, 0) if multiclass else definition.skill_limit
        if used + 1 > limit:
            raise ValidationError(
                f"клас {definition.name_en!r} дає не більше {limit} навичок"
                + (" при мультикласі" if multiclass else "")
            )
        return
    if source.kind is SourceKind.SPECIES:
        species = rules.species_mechanics(source.key)
        if species is None:
            raise NotFoundError(f"немає правил виду {source.key!r}")
        validate_origin_pick(
            pick,
            existing,
            skills={skill.value for skill in species.skill_proficiencies},
            skill_any=species.skill_any,
            tool_any=species.tools_any,
            language_any=species.languages_any_standard,
            label=species.name_en,
        )
        return
    if source.kind is SourceKind.BACKGROUND:
        background = rules.background_mechanics(source.key)
        if background is None:
            raise NotFoundError(f"немає правил передісторії {source.key!r}")
        validate_origin_pick(
            pick,
            existing,
            skills={skill.value for skill in background.skill_proficiencies},
            skill_any=background.skill_any,
            tool_any=background.tools_any,
            language_any=background.languages_any_standard,
            label=background.name_en,
        )
        return
    # FEAT, ITEM, MANUAL — без обмежень: їх дає не таблиця, а гра.


def validate_origin_pick(
    pick: Proficiency,
    existing: Proficiencies,
    *,
    skills: set[str],
    skill_any: int,
    tool_any: int,
    language_any: int,
    label: str,
) -> None:
    """Вибір у межах виду або передісторії: навички, інструменти, мови."""
    value = pick.value.strip().casefold()
    if pick.kind is ProficiencyKind.SKILL:
        if skill_any == 0 and value not in skills:
            raise ValidationError(f"{label!r} не дає навички {value!r}")
        used = count_picks(existing, ProficiencyKind.SKILL, pick.source)
        if used + 1 > len(skills) + skill_any:
            raise ValidationError(f"{label!r}: вичерпано вибір навичок")
        return
    if pick.kind is ProficiencyKind.TOOL:
        used = count_picks(existing, ProficiencyKind.TOOL, pick.source)
        if tool_any == 0 or used + 1 > tool_any:
            raise ValidationError(f"{label!r}: вичерпано вибір інструментів")
        return
    if pick.kind is ProficiencyKind.LANGUAGE:
        used = count_picks(existing, ProficiencyKind.LANGUAGE, pick.source)
        if language_any == 0 or used + 1 > language_any:
            raise ValidationError(f"{label!r}: вичерпано вибір мов")
        return
    raise ValidationError(f"{label!r}: такий вид володіння не передбачений")
