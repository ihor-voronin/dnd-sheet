"""Character + ComputedSheet -> SheetDocument: увесь лист, а не перша сторінка.

Це єдине місце, де вирішується, **що** потрапляє в документ і з яким
`origin`. Рендери (PDF, Markdown, React) нічого не вирішують — вони лише
малюють. Тому «на екрані є, а в PDF немає» неможливо за конструкцією:
розділи тут повторюють вкладки листа.

Три види полів за походженням:

* `computed` — порахував домен (КЗ, рятівні кидки, навички, максимум хітів, комірки);
* `input` — стан, який гравець змінює за столом (поточні хіти, витрачені
  комірки, кидки смерті, натхнення, виснаження, нотатки);
* `override` — гравець вписав своє число замість обчисленого.

Стан листа потрапляє в документ **тим самим шляхом, що й на екран**: числа
беруться з `ComputedSheet`, лічильники — з `character.state`. Тому PDF,
надрукований посеред бою, показує «3 з 12 хітів», а не «12 з 12».
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable, Iterable, Mapping

from dndsheet.characters.application.rows import (
    SpellRow,
    feature_rows,
    item_rows,
    proficiency_rows,
    spell_rows,
    spell_sort_key,
)
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
    alignment_label,
    english_name,
    hint,
    item_kind_label,
    language_label,
    note_label,
    proficiency_kind_label,
    save_label,
    skill_label,
    source_kind_label,
    spell_level_label,
    spell_source_label,
)

IDENTITY_SECTION = LocalizedText(uk="Особа", en="Identity")
ABILITIES_SECTION = LocalizedText(uk="Характеристики", en="Ability Scores")
COMBAT_SECTION = LocalizedText(uk="Бій", en="Combat")
SAVES_SECTION = LocalizedText(uk="Рятівні кидки", en="Saving Throws")
SKILLS_SECTION = LocalizedText(uk="Навички", en="Skills")
ATTACKS_SECTION = LocalizedText(uk="Атаки", en="Attacks")
FEATURES_SECTION = LocalizedText(uk="Уміння й риси", en="Features")
PROFICIENCIES_SECTION = LocalizedText(uk="Володіння", en="Proficiencies")
SPELLS_SECTION = LocalizedText(uk="Чарування", en="Spellcasting")
KNOWN_SPELLS_SECTION = LocalizedText(uk="Відомі закляття", en="Spells")
INVENTORY_SECTION = LocalizedText(uk="Інвентар", en="Equipment")
MONEY_SECTION = LocalizedText(uk="Гроші й вага", en="Money and Weight")
NOTES_SECTION = LocalizedText(uk="Нотатки", en="Notes")
WARNINGS_SECTION = LocalizedText(uk="Застереження", en="Warnings")

#: Володіння з довідника приходять англійськими ключами («simple», «light»).
TRAINING_LABELS: dict[str, tuple[str, str]] = {
    "light": ("легка броня", "light armor"),
    "medium": ("середня броня", "medium armor"),
    "heavy": ("важка броня", "heavy armor"),
    "shield": ("щити", "shields"),
    "simple": ("проста зброя", "simple weapons"),
    "martial": ("воєнна зброя", "martial weapons"),
}


#: Як показати назву з довідника («Warlock» → «Чаклун (Warlock)»); за замовчуванням — як є.
#: ContextVar, а не параметр кожної функції: назви потрібні в десятку місць документа.
_NAME: ContextVar[Callable[[str], str]] = ContextVar("sheet_name", default=lambda name: name)


def _n(name: str) -> str:
    return _NAME.get()(name)


def build_sheet_document(
    character: Character,
    computed: ComputedSheet,
    attacks: Iterable[Mapping[str, Any]] | None = None,
    feat_titles: Mapping[str, str] | None = None,
    name: Callable[[str], str] | None = None,
) -> SheetDocument:
    """Документ листа; `name` перекладає назви з довідника за правилом «Українська (English)»."""
    token = _NAME.set(name or (lambda value: value))
    try:
        return _build(character, computed, attacks, feat_titles)
    finally:
        _NAME.reset(token)


def _build(
    character: Character,
    computed: ComputedSheet,
    attacks: Iterable[Mapping[str, Any]] | None = None,
    feat_titles: Mapping[str, str] | None = None,
) -> SheetDocument:
    """Повний документ листа: шість розділів, як на екрані.

    `attacks` і `feat_titles` приходять ззовні (з довідника), бо домен не
    читає корпус: немає списку атак — немає й розділу, а не порожній
    заголовок; немає назви риси — показуємо її ключ, а не вигаданий текст.
    """
    fields: dict[str, Field] = {}
    pages: list[Page] = []

    identity = _identity_fields(character, computed, feat_titles)
    fields.update(identity)
    ability_ids = _ability_fields(fields, computed)
    combat_ids = _combat_fields(character, computed, fields)

    pages.append(
        Page(
            size="A4",
            sections=[
                Section(
                    id="identity",
                    title=IDENTITY_SECTION,
                    columns=2,
                    fields=list(identity),
                ),
                Section(id="abilities", title=ABILITIES_SECTION, columns=6, fields=ability_ids),
                Section(id="combat", title=COMBAT_SECTION, columns=4, fields=combat_ids),
            ],
        )
    )

    save_ids, skill_ids = _save_and_skill_fields(computed, fields)
    pages.append(
        Page(
            size="A4",
            sections=[
                Section(id="saves", title=SAVES_SECTION, columns=3, fields=save_ids),
                Section(id="skills", title=SKILLS_SECTION, columns=3, fields=skill_ids),
            ],
        )
    )

    action_sections = _action_sections(character, attacks, fields)
    if action_sections:
        pages.append(Page(size="A4", sections=action_sections))

    spell_sections = _spell_sections(character, computed, fields)
    if spell_sections:
        pages.append(Page(size="A4", sections=spell_sections))

    inventory_sections = _inventory_sections(character, computed, fields)
    if inventory_sections:
        pages.append(Page(size="A4", sections=inventory_sections))

    note_sections = _note_sections(character, fields)
    warnings = _warning_section(computed, fields)
    tail = [*note_sections, *([warnings] if warnings else [])]
    if tail:
        pages.append(Page(size="A4", sections=tail))

    return SheetDocument(
        schema_version=SCHEMA_VERSION,
        edition="2014",
        title=LocalizedText(uk=character.name, en=character.name),
        pages=pages,
        fields=fields,
    )


# ---------------------------------------------------------------------------
# розділи
# ---------------------------------------------------------------------------


def _identity_fields(
    character: Character,
    computed: ComputedSheet,
    feat_titles: Mapping[str, str] | None = None,
) -> dict[str, Field]:
    fields: dict[str, Field] = {
        "identity.level": _computed_number(
            "identity.level",
            computed.total_level,
            LocalizedText(uk="Рівень", en="Level"),
        ),
        "identity.classes": _text(
            "identity.classes",
            _classes_text(character),
            LocalizedText(uk="Класи", en="Classes"),
        ),
    }
    species = character.species
    if species is not None:
        name = _n(species.name_en)
        if character.subspecies_key:
            name = f"{name}, {_n(character.subspecies_key)}"
        fields["identity.species"] = _text(
            "identity.species", name, LocalizedText(uk="Вид", en="Species")
        )
    background = character.background
    if background is not None:
        fields["identity.background"] = _text(
            "identity.background",
            _n(background.name_en),
            LocalizedText(uk="Передісторія", en="Background"),
        )
    if character.alignment:
        fields["identity.alignment"] = _text(
            "identity.alignment",
            alignment_label(character.alignment).uk,
            LocalizedText(uk="Світогляд", en="Alignment"),
        )
    if computed.darkvision:
        fields["identity.darkvision"] = _computed_number(
            "identity.darkvision",
            computed.darkvision,
            LocalizedText(uk="Темний зір, фути", en="Darkvision, feet"),
        )
    if computed.resistances:
        fields["identity.resistances"] = _computed_list(
            "identity.resistances",
            list(computed.resistances),
            LocalizedText(uk="Стійкість до урону", en="Damage Resistances"),
        )
    if character.feats:
        titles = feat_titles or {}
        fields["identity.feats"] = _computed_list(
            "identity.feats",
            [titles.get(key, key) for key in character.feats],
            LocalizedText(uk="Риси", en="Feats"),
        )
    if character.multiclass_waivers:
        # Не похідне число, а слід рішення: вимоги обійшли свідомо.
        fields["identity.waivers"] = _computed_list(
            "identity.waivers",
            [_waiver_text(character, waiver) for waiver in character.multiclass_waivers],
            LocalizedText(
                uk="Вимоги мультикласу проігноровано",
                en="Multiclass requirements ignored",
            ),
        )
    return fields


def _waiver_text(character: Character, waiver) -> str:  # noqa: ANN001 — MulticlassWaiver
    definition = character.rules.class_mechanics(waiver.class_key)
    name = _n(definition.name_en) if definition is not None else waiver.class_key
    required = " або ".join(waiver.requirements)
    return f"{name} ({required})" if required else name


def _classes_text(character: Character) -> str:
    return " / ".join(
        f"{_n(definition.name_en)} {entry.level}"
        for entry, definition in character.class_entries()
    )


def _ability_fields(fields: dict[str, Field], computed: ComputedSheet) -> list[str]:
    ids: list[str] = []
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
        ids.extend([score_id, mod_id])
    return ids


def _combat_fields(
    character: Character, computed: ComputedSheet, fields: dict[str, Field]
) -> list[str]:
    state = character.state

    def origin(key: str) -> str:
        return "override" if key in computed.overridden else "computed"

    fields["ac.total"] = Field(
        id="ac.total",
        type="number",
        value=computed.armor_class,
        origin=origin("armor_class"),
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
        origin=origin("initiative"),
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
        label=LocalizedText(
            uk="Бонус майстерності", en="Proficiency Bonus", glossary_id="rules.proficiency_bonus"
        ),
        hint=hint("rules.proficiency_bonus"),
        formula=Formula(expr="proficiency()"),
        editable=False,
    )
    fields["speed"] = Field(
        id="speed",
        type="number",
        value=computed.speed,
        origin=origin("speed"),
        label=LocalizedText(uk="Швидкість, фути", en="Speed, feet"),
        editable=True,
    )
    fields["passive.perception"] = Field(
        id="passive.perception",
        type="number",
        value=computed.passive_perception,
        origin=origin("passive_perception"),
        label=LocalizedText(
            uk="Пасивна Спостережливість", en="Passive Perception", glossary_id="combat.passive_perception"
        ),
        hint=hint("combat.passive_perception"),
        editable=True,
    )
    fields["hp.max"] = Field(
        id="hp.max",
        type="number",
        value=computed.hit_points.maximum,
        origin=origin("hit_points_max"),
        label=LocalizedText(uk="Хіти: максимум", en="Hit Points: maximum"),
        formula=Formula(
            expr=" + ".join(str(part.value) for part in computed.hit_points.parts) or "0"
        ),
        editable=True,
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
        type="text",
        value=", ".join(f"d{die} × {count}" for die, count in sorted(computed.hit_dice.items())),
        origin="computed",
        label=LocalizedText(uk="Кістки хітів", en="Hit Dice"),
        editable=False,
    )
    fields["hitdice.left"] = Field(
        id="hitdice.left",
        type="text",
        value=_hit_dice_left(character, computed),
        origin="input",
        label=LocalizedText(uk="Кістки хітів: вільно", en="Hit Dice: available"),
        editable=True,
    )
    fields["inspiration"] = Field(
        id="inspiration",
        type="checkbox",
        value=state.inspiration,
        origin="input",
        label=LocalizedText(uk="Натхнення", en="Inspiration"),
        editable=True,
    )
    fields["exhaustion"] = Field(
        id="exhaustion",
        type="number",
        value=state.exhaustion,
        origin="input",
        label=LocalizedText(uk="Виснаження", en="Exhaustion"),
        editable=True,
    )
    fields["death_saves"] = Field(
        id="death_saves",
        type="text",
        value=(
            f"успіхи {state.death_saves.successes} / провали {state.death_saves.failures}"
        ),
        origin="input",
        label=LocalizedText(uk="Кидки смерті", en="Death Saves"),
        editable=True,
    )
    return [
        "ac.total",
        "initiative",
        "prof",
        "speed",
        "passive.perception",
        "hp.current",
        "hp.max",
        "hp.temp",
        "hitdice",
        "hitdice.left",
        "inspiration",
        "exhaustion",
        "death_saves",
    ]


def _hit_dice_left(character: Character, computed: ComputedSheet) -> str:
    parts: list[str] = []
    for die, total in sorted(computed.hit_dice.items()):
        used = character.state.hit_die_used(die)
        if total:
            parts.append(f"d{die}: {total - used} з {total}")
    return ", ".join(parts)


def _save_and_skill_fields(
    computed: ComputedSheet, fields: dict[str, Field]
) -> tuple[list[str], list[str]]:
    save_ids: list[str] = []
    for ability in Ability:
        save_id = f"save.{ability.value}"
        fields[save_id] = Field(
            id=save_id,
            type="number",
            value=computed.saving_throws[ability],
            origin="override" if f"save:{ability.value}" in computed.overridden else "computed",
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
            origin="override" if f"skill:{skill.value}" in computed.overridden else "computed",
            label=skill_label(skill),
            hint=hint("skill.check"),
            editable=True,
        )
        skill_ids.append(skill_id)
    return save_ids, skill_ids


def _action_sections(
    character: Character,
    attacks: Iterable[Mapping[str, Any]] | None,
    fields: dict[str, Field],
) -> list[Section]:
    sections: list[Section] = []

    attack_ids: list[str] = []
    for index, attack in enumerate(attacks or (), start=1):
        field_id = f"attack.{index}"
        name = str(attack.get("name_en") or "?")
        bonus = int(attack.get("attack_bonus") or 0)
        damage = str(attack.get("damage") or "—")
        ability = ability_label(Ability(str(attack.get("ability") or Ability.STR.value)))
        notes = str(attack.get("notes") or "").strip()
        fields[field_id] = Field(
            id=field_id,
            type="text",
            value=f"{bonus:+d} · {damage}",
            origin="computed",
            label=english_name(name),
            hint=LocalizedText(
                uk=f"{ability.uk} · {notes}" if notes else ability.uk,
                en=f"{ability.en} · {notes}" if notes else ability.en,
            ),
            editable=False,
        )
        attack_ids.append(field_id)
    if attack_ids:
        sections.append(
            Section(id="attacks", title=ATTACKS_SECTION, columns=1, fields=attack_ids)
        )

    feature_ids: list[str] = []
    for index, row in enumerate(feature_rows(character), start=1):
        field_id = f"feature.{index}"
        fields[field_id] = Field(
            id=field_id,
            type="text",
            value=f"{_n(row.class_name)} {row.level}",
            origin="computed",
            label=english_name(row.name_en),
            editable=False,
        )
        feature_ids.append(field_id)
    if feature_ids:
        sections.append(
            Section(id="features", title=FEATURES_SECTION, columns=2, fields=feature_ids)
        )

    # Володіння друкуємо групами «вид + джерело»: чотири рядки «броня: …»
    # займають пів сторінки, а один «броня: легка, середня, важка, щити» читається
    # так само й не губить джерела.
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for row in proficiency_rows(character.all_proficiencies()):
        key = (row.kind.value, row.source_kind, row.source_key)
        grouped.setdefault(key, []).append(_proficiency_value(row.kind.value, row.value))

    proficiency_ids: list[str] = []
    for index, ((kind, source_kind, source_key), values) in enumerate(grouped.items(), start=1):
        field_id = f"prof.{index}"
        fields[field_id] = Field(
            id=field_id,
            type="text",
            value=f"{', '.join(values)} · {source_kind_label(source_kind).uk} {_n(source_key)}",
            origin="computed",
            label=proficiency_kind_label(kind),
            editable=False,
        )
        proficiency_ids.append(field_id)
    if proficiency_ids:
        sections.append(
            Section(
                id="proficiencies",
                title=PROFICIENCIES_SECTION,
                columns=2,
                fields=proficiency_ids,
            )
        )
    return sections


def _proficiency_value(kind: str, value: str) -> str:
    if kind == "skill":
        return skill_label(Skill(value)).uk
    if kind == "saving_throw":
        return ability_label(Ability(value)).uk
    if kind == "language":
        return language_label(value).uk
    pair = TRAINING_LABELS.get(value.strip().casefold())
    if pair is not None:
        return pair[0]
    return value


def _spell_sections(
    character: Character, computed: ComputedSheet, fields: dict[str, Field]
) -> list[Section]:
    sections: list[Section] = []
    casting = computed.spellcasting

    casting_ids: list[str] = []
    for item in casting.classes:
        dc_id = f"spell.dc.{item.class_key}"
        attack_id = f"spell.attack.{item.class_key}"
        fields[dc_id] = Field(
            id=dc_id,
            type="number",
            value=item.save_dc,
            origin="computed",
            label=LocalizedText(
                uk=f"КС рятівного кидка закляття: {_n(item.name_en)}", en=f"Spell save DC: {item.name_en}"
            ),
            formula=Formula(
                expr=f"8 + proficiency() + mod('{item.ability.value}')",
                deps=[f"{item.ability.value}.score"],
            ),
            editable=False,
        )
        fields[attack_id] = Field(
            id=attack_id,
            type="number",
            value=item.attack_bonus,
            origin="computed",
            label=LocalizedText(
                uk=f"Бонус атаки закляттям: {_n(item.name_en)}",
                en=f"Spell attack bonus: {item.name_en}",
            ),
            formula=Formula(
                expr=f"proficiency() + mod('{item.ability.value}')",
                deps=[f"{item.ability.value}.score"],
            ),
            editable=False,
        )
        casting_ids.extend([dc_id, attack_id])

    for level, total in casting.slots.by_level:
        field_id = f"spell.slots.{level}"
        used = character.state.slot_used(level)
        fields[field_id] = Field(
            id=field_id,
            type="counter",
            value=f"{max(0, total - used)}/{total}",
            origin="input",
            label=LocalizedText(uk=f"Комірки {level} рівня", en=f"Spell slots, level {level}"),
            hint=LocalizedText(uk=f"витрачено {used}", en=f"used {used}"),
            editable=True,
        )
        casting_ids.append(field_id)

    pact = casting.slots.pact
    if pact is not None:
        used = character.state.pact_used
        fields["spell.pact"] = Field(
            id="spell.pact",
            type="counter",
            value=f"{max(0, pact.slots - used)}/{pact.slots}",
            origin="input",
            label=LocalizedText(
                uk=f"{_n('Pact Magic')}, {pact.slot_level} рівень", en=f"Pact Magic, level {pact.slot_level}"
            ),
            hint=LocalizedText(uk=f"витрачено {used}", en=f"used {used}"),
            editable=True,
        )
        casting_ids.append("spell.pact")

    if casting_ids:
        sections.append(
            Section(id="spells", title=SPELLS_SECTION, columns=2, fields=casting_ids)
        )

    rows = sorted(spell_rows(character, computed), key=spell_sort_key)
    spell_ids: list[str] = []
    for index, row in enumerate(rows, start=1):
        field_id = f"spell.{index}"
        fields[field_id] = Field(
            id=field_id,
            type="text",
            value=_spell_value(row),
            origin="computed",
            label=english_name(row.name_en),
            # Власне закляття не має тексту в книзі: у документ іде те, що
            # гравець написав сам (у підказці, щоб не ламати сітку).
            hint=(
                LocalizedText(uk=row.description, en=row.description)
                if row.custom and row.description
                else None
            ),
            editable=False,
        )
        spell_ids.append(field_id)
    if spell_ids:
        sections.append(
            Section(
                id="known-spells",
                title=KNOWN_SPELLS_SECTION,
                columns=2,
                fields=spell_ids,
            )
        )
    return sections


def _spell_value(row: SpellRow) -> str:
    level = spell_level_label(row.level).uk
    if row.custom:
        return f"{level} · власне"
    if row.source != "class":
        return f"{level} · {spell_source_label(row.source).uk}"
    if row.always_prepared:
        return f"{level} · завжди підготовлене"
    if row.prepared:
        return f"{level} · підготовлене"
    return level


def _inventory_sections(
    character: Character, computed: ComputedSheet, fields: dict[str, Field]
) -> list[Section]:
    sections: list[Section] = []

    item_ids: list[str] = []
    for index, row in enumerate(item_rows(character), start=1):
        field_id = f"item.{index}"
        parts = [item_kind_label(row.kind).uk]
        if row.quantity > 1:
            parts.append(f"× {row.quantity}")
        if row.armor_base:
            parts.append(f"КЗ {row.armor_base}")
        if row.weight_lb:
            parts.append(f"{row.weight_lb:g} фнт")
        parts.append("споряджено" if row.equipped else "не споряджено")
        if row.attuned:
            parts.append("настроєно")
        fields[field_id] = Field(
            id=field_id,
            type="text",
            value=" · ".join(parts),
            origin="input",
            label=english_name(row.name_en),
            editable=True,
        )
        item_ids.append(field_id)
    if item_ids:
        sections.append(
            Section(id="inventory", title=INVENTORY_SECTION, columns=2, fields=item_ids)
        )

    money = character.inventory.money
    money_fields: list[str] = []
    for coin, (uk, en) in (("gp", ("Золото", "Gold")), ("sp", ("Срібло", "Silver")), ("cp", ("Мідь", "Copper"))):
        field_id = f"money.{coin}"
        fields[field_id] = Field(
            id=field_id,
            type="number",
            value=getattr(money, coin),
            origin="input",
            label=LocalizedText(uk=uk, en=en),
            editable=True,
        )
        money_fields.append(field_id)
    fields["carrying"] = Field(
        id="carrying",
        type="text",
        value=f"{computed.carried_weight:g} з {computed.carrying_capacity} фнт",
        origin="computed",
        label=LocalizedText(uk="Вага", en="Weight carried"),
        hint=LocalizedText(
            uk="Сила × 15 — вантажопідйомність",
            en="Strength × 15 — carrying capacity",
        ),
        editable=False,
    )
    money_fields.append("carrying")
    sections.append(
        Section(id="money", title=MONEY_SECTION, columns=4, fields=money_fields)
    )
    return sections


def _note_sections(character: Character, fields: dict[str, Field]) -> list[Section]:
    note_ids: list[str] = []
    for key, value in character.state.notes.items():
        if not str(value).strip():
            continue
        field_id = f"note.{key}"
        fields[field_id] = Field(
            id=field_id,
            type="longtext",
            value=str(value),
            origin="input",
            label=note_label(key),
            editable=True,
        )
        note_ids.append(field_id)
    if not note_ids:
        return []
    return [Section(id="notes", title=NOTES_SECTION, columns=1, fields=note_ids)]


def _warning_section(computed: ComputedSheet, fields: dict[str, Field]) -> Section | None:
    if not computed.warnings:
        return None
    fields["warnings"] = Field(
        id="warnings",
        type="list",
        value=list(computed.warnings),
        origin="computed",
        label=LocalizedText(uk="Лист попереджає", en="Sheet warnings"),
        editable=False,
    )
    return Section(id="warnings", title=WARNINGS_SECTION, columns=1, fields=["warnings"])


# ---------------------------------------------------------------------------
# дрібні конструктори полів
# ---------------------------------------------------------------------------


def _text(field_id: str, value: str, label: LocalizedText) -> Field:
    return Field(id=field_id, type="text", value=value, origin="computed", label=label)


def _computed_number(field_id: str, value: int, label: LocalizedText) -> Field:
    return Field(id=field_id, type="number", value=value, origin="computed", label=label)


def _computed_list(field_id: str, values: list[str], label: LocalizedText) -> Field:
    return Field(id=field_id, type="list", value=values, origin="computed", label=label)
