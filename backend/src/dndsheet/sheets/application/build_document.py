"""Character + ComputedSheet -> SheetDocument.

Application-шар контексту `sheets`: перетворює доменні дані на канонічний документ.
Тут же — єдине місце, де вирішується, які поля показати й з яким `origin`.
"""

from __future__ import annotations

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.services.derived_stats import ComputedSheet
from dndsheet.shared.kernel import Ability, Skill
from dndsheet.sheets.domain.document import (
    SCHEMA_VERSION,
    Field,
    Formula,
    LocalizedText,
    Page,
    Section,
    SheetDocument,
)
from dndsheet.sheets.domain.labels import (
    ability_label,
    ability_mod_label,
    hint,
    save_label,
    skill_label,
)

ABILITIES_SECTION = LocalizedText(uk="Характеристики", en="Ability Scores")
COMBAT_SECTION = LocalizedText(uk="Бій", en="Combat")
SAVES_SECTION = LocalizedText(uk="Рятівні кидки", en="Saving Throws")
SKILLS_SECTION = LocalizedText(uk="Навички", en="Skills")


def build_sheet_document(character: Character, computed: ComputedSheet) -> SheetDocument:
    fields: dict[str, Field] = {}

    ability_field_ids: list[str] = []
    for ability in Ability:
        score_id = f"{ability.value}.score"
        mod_id = f"{ability.value}.mod"
        fields[score_id] = Field(
            id=score_id,
            type="number",
            value=character.ability(ability).value,
            origin="input",
            label=ability_label(ability),
            hint=hint(f"ability.{ability.value}"),
            editable=True,
        )
        fields[mod_id] = Field(
            id=mod_id,
            type="number",
            value=computed.ability_modifiers[ability],
            origin="computed",
            label=ability_mod_label(ability),
            formula=Formula(expr=f"mod('{ability.value}')", deps=[score_id]),
            editable=False,
        )
        ability_field_ids.extend([score_id, mod_id])

    fields["ac.total"] = Field(
        id="ac.total",
        type="number",
        value=computed.armor_class,
        origin="computed",
        label=LocalizedText(uk="Клас захисту", en="Armor Class", glossary_id="combat.ac"),
        hint=hint("combat.ac"),
        editable=True,
    )
    fields["initiative"] = Field(
        id="initiative",
        type="number",
        value=computed.initiative,
        origin="computed",
        label=LocalizedText(uk="Ініціатива", en="Initiative", glossary_id="combat.initiative"),
        hint=hint("combat.initiative"),
        formula=Formula(expr="mod('dex')", deps=["dex.score"]),
        editable=True,
    )
    fields["prof"] = Field(
        id="prof",
        type="number",
        value=computed.proficiency_bonus,
        origin="computed",
        label=LocalizedText(uk="Бонус майстерності", en="Proficiency Bonus", glossary_id="rules.proficiency_bonus"),
        hint=hint("rules.proficiency_bonus"),
        formula=Formula(expr="proficiency()"),
        editable=False,
    )
    fields["passive.perception"] = Field(
        id="passive.perception",
        type="number",
        value=computed.passive_perception,
        origin="computed",
        label=LocalizedText(uk="Пасивна Спостережливість", en="Passive Perception"),
        hint=hint("combat.passive_perception"),
        editable=False,
    )

    save_ids: list[str] = []
    for ability in Ability:
        save_id = f"save.{ability.value}"
        fields[save_id] = Field(
            id=save_id,
            type="number",
            value=computed.saving_throws[ability],
            origin="computed",
            label=save_label(ability),
            hint=hint("combat.saving_throw"),
            editable=True,
        )
        save_ids.append(save_id)

    skill_ids: list[str] = []
    for skill in Skill:
        skill_id = f"skill.{skill.value}"
        fields[skill_id] = Field(
            id=skill_id,
            type="number",
            value=computed.skills[skill],
            origin="computed",
            label=skill_label(skill),
            hint=hint("skill.check"),
            editable=True,
        )
        skill_ids.append(skill_id)

    pages = [
        Page(
            size="A4",
            sections=[
                Section(id="abilities", title=ABILITIES_SECTION, columns=6, fields=ability_field_ids),
                Section(
                    id="combat",
                    title=COMBAT_SECTION,
                    columns=4,
                    fields=["ac.total", "initiative", "prof", "passive.perception"],
                ),
            ],
        ),
        Page(
            size="A4",
            sections=[
                Section(id="saves", title=SAVES_SECTION, columns=3, fields=save_ids),
                Section(id="skills", title=SKILLS_SECTION, columns=3, fields=skill_ids),
            ],
        ),
    ]

    return SheetDocument(
        schema_version=SCHEMA_VERSION,
        edition="2014",
        title=LocalizedText(uk=character.name, en=character.name),
        pages=pages,
        fields=fields,
    )
