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
SPELLS_SECTION = LocalizedText(uk="Закляття", en="Spellcasting")


def build_sheet_document(character: Character, computed: ComputedSheet) -> SheetDocument:
    fields: dict[str, Field] = {}
    pages: list[Page] = []

    ability_field_ids: list[str] = []
    for ability in Ability:
        score_id = f"{ability.value}.score"
        mod_id = f"{ability.value}.mod"
        viewed = computed.abilities[ability]
        fields[score_id] = Field(
            id=score_id,
            type="number",
            value=viewed.total,
            origin="computed" if viewed.bonus else "input",
            label=ability_label(ability),
            hint=hint(f"ability.{ability.value}"),
            formula=(
                Formula(expr=f"base('{ability.value}') + {viewed.bonus}", deps=[])
                if viewed.bonus
                else None
            ),
            editable=True,
        )
        fields[mod_id] = Field(
            id=mod_id,
            type="number",
            value=viewed.modifier,
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
        formula=Formula(
            expr=" + ".join(str(part.value) for part in computed.armor_class_parts) or "0",
            deps=[],
        ),
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
    fields["speed"] = Field(
        id="speed",
        type="number",
        value=computed.speed,
        origin="computed",
        label=LocalizedText(uk="Швидкість, фути", en="Speed, feet"),
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
    fields["hp.max"] = Field(
        id="hp.max",
        type="number",
        value=computed.hit_points.maximum,
        origin="computed",
        label=LocalizedText(uk="Хіти: максимум", en="Hit Points: maximum"),
        formula=Formula(
            expr=" + ".join(str(part.value) for part in computed.hit_points.parts) or "0"
        ),
        editable=False,
    )
    fields["hp.current"] = Field(
        id="hp.current",
        type="number",
        value=computed.hit_points.current,
        origin="input",
        label=LocalizedText(uk="Хіти: зараз", en="Hit Points: current"),
        editable=True,
    )
    fields["hp.temp"] = Field(
        id="hp.temp",
        type="number",
        value=computed.hit_points.temporary,
        origin="input",
        label=LocalizedText(uk="Тимчасові хіти", en="Temporary Hit Points"),
        editable=True,
    )
    fields["hitdice"] = Field(
        id="hitdice",
        type="list",
        value=[f"d{die} × {count}" for die, count in sorted(computed.hit_dice.items())],
        origin="computed",
        label=LocalizedText(uk="Кубики хітів", en="Hit Dice"),
        editable=True,
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

    pages.append(
        Page(
            size="A4",
            sections=[
                Section(id="abilities", title=ABILITIES_SECTION, columns=6, fields=ability_field_ids),
                Section(
                    id="combat",
                    title=COMBAT_SECTION,
                    columns=4,
                    fields=[
                        "ac.total",
                        "initiative",
                        "prof",
                        "speed",
                        "passive.perception",
                        "hp.max",
                        "hp.current",
                        "hp.temp",
                        "hitdice",
                    ],
                ),
            ],
        )
    )
    pages.append(
        Page(
            size="A4",
            sections=[
                Section(id="saves", title=SAVES_SECTION, columns=3, fields=save_ids),
                Section(id="skills", title=SKILLS_SECTION, columns=3, fields=skill_ids),
            ],
        )
    )

    spell_fields = _spellcasting_fields(character, computed)
    if spell_fields:
        pages.append(
            Page(
                size="A4",
                sections=[
                    Section(
                        id="spells",
                        title=SPELLS_SECTION,
                        columns=2,
                        fields=list(spell_fields),
                    )
                ],
            )
        )
    fields.update(spell_fields)

    return SheetDocument(
        schema_version=SCHEMA_VERSION,
        edition="2014",
        title=LocalizedText(uk=character.name, en=character.name),
        pages=pages,
        fields=fields,
    )


def _spellcasting_fields(character: Character, computed: ComputedSheet) -> dict[str, Field]:
    """Поля заклинателя: DC, бонус атаки, слоти — по одному блоку на клас."""
    casting = computed.spellcasting
    if not casting.casts_spells:
        return {}
    fields: dict[str, Field] = {}
    for item in casting.classes:
        dc_id = f"spell.dc.{item.class_key}"
        attack_id = f"spell.attack.{item.class_key}"
        fields[dc_id] = Field(
            id=dc_id,
            type="number",
            value=item.save_dc,
            origin="computed",
            label=LocalizedText(uk=f"Опір закляттям: {item.name_en}", en=f"Spell save DC: {item.name_en}"),
            formula=Formula(
                expr=f"8 + proficiency() + mod('{item.ability.value}')", deps=[f"{item.ability.value}.score"]
            ),
            editable=False,
        )
        fields[attack_id] = Field(
            id=attack_id,
            type="number",
            value=item.attack_bonus,
            origin="computed",
            label=LocalizedText(
                uk=f"Бонус атаки закляттям: {item.name_en}",
                en=f"Spell attack bonus: {item.name_en}",
            ),
            formula=Formula(
                expr=f"proficiency() + mod('{item.ability.value}')", deps=[f"{item.ability.value}.score"]
            ),
            editable=False,
        )
    slots = [
        f"{level} рівень × {count}" for level, count in casting.slots.by_level if count
    ]
    if casting.slots.pact is not None:
        slots.append(
            f"Pact Magic: {casting.slots.pact.slots} × {casting.slots.pact.slot_level} рівень"
        )
    fields["spell.slots"] = Field(
        id="spell.slots",
        type="list",
        value=slots,
        origin="computed",
        label=LocalizedText(uk="Слоти заклять", en="Spell Slots"),
        editable=False,
    )
    return fields
