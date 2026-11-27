"""Обчислення похідних характеристик (правила 2014, v2).

Чистий доменний сервіс: жодного репозиторію, жодного I/O. Усе, що йому
потрібно, він бере з агрегату `Character` (разом із портом правил) і з
`ModifierResolver`, який каже, **звідки** взялася кожна цифра.

Що тут рахується: характеристики (база + бонуси), модифікатори, бонус
майстерності, рятівні кидки, навички, ініціатива, швидкість, пасивна
уважність, КЗ (броня/щит/безбронний захист), максимум хітів, кістки хітів,
комірки заклять і DC, вантажопідйомність.

Чого тут немає: атак зброєю (потрібні дані предметів — етап 4) і рис із
числовими бонусами (етап 7). Обидва місця позначені в коді.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.inventory import CARRY_PER_STRENGTH
from dndsheet.characters.domain.proficiencies import ProficiencyKind, Proficiencies
from dndsheet.characters.domain.services.hit_points import (
    HitPointPart,
    HitPointsView,
    hit_dice_pool,
    hit_point_maximum,
)
from dndsheet.characters.domain.services.modifier_resolver import (
    ModifierKind,
    ModifierResolver,
    ModifierSet,
)
from dndsheet.characters.domain.services.spell_slots import (
    ClassCasting,
    Spellcasting,
    SpellSlotService,
)
from dndsheet.shared.kernel import (
    SKILL_ABILITY,
    Ability,
    Skill,
    proficiency_bonus,
)
from dndsheet.characters.domain import derived_choices
from dndsheet.shared.rules import (
    ELDRITCH_BLAST_INVOCATIONS,
    ClassMechanics,
    dragon_damage_type,
    armor_category,
    armor_dex_cap,
)

SHIELD_AC_BONUS = 2
UNARMORED_BASE = 10
PASSIVE_BASE = 10

#: Безбронний захист: клас → друга характеристика до КЗ (PHB, 2014).
#: Це правило, а не дані книги, тому воно тут, а не в корпусі.
UNARMORED_DEFENSE: dict[str, Ability] = {
    "barbarian": Ability.CON,
    "monk": Ability.WIS,
}


@dataclass(frozen=True, slots=True)
class AbilityView:
    """Характеристика очима листа: база, бонус, підсумок, модифікатор."""

    base: int
    bonus: int
    total: int
    modifier: int


@dataclass(frozen=True, slots=True)
class GrantedSpellView:
    """Закляття не з класу: вид (thaumaturgy) або підклас (домен жреця)."""

    name_en: str
    spell_level: int
    source: str  # "species" | "subclass" | "feat" | "fighting-style" | "invocation" | "pact-boon" | "secrets"
    prepared: bool = False
    #: Як чарується поза класом: «at will», «1/long rest», «ritual only».
    usage: str = ""
    #: Характеристика чарування поза класом (Учень магії — клас риси).
    ability: Ability | None = None
    #: Клас, чий підклас дав закляття: у мультикласі від нього залежать
    #: складність рятівного кидка й бонус атаки (домен жреця — від Мудрості).
    class_key: str | None = None


@dataclass(frozen=True, slots=True)
class ArmorClassPart:
    """Доданок КЗ: назва (ключ, не текст) і число."""

    label: str
    value: int


@dataclass(frozen=True, slots=True)
class ComputedSheet:
    """Обчислений зріз персонажа. Не зберігається, будується щоразу."""

    total_level: int
    proficiency_bonus: int
    abilities: dict[Ability, AbilityView]
    ability_modifiers: dict[Ability, int]
    saving_throws: dict[Ability, int]
    saving_throw_proficiency: dict[Ability, bool]
    skills: dict[Skill, int]
    skill_proficiency: dict[Skill, bool]
    initiative: int
    speed: int
    armor_class: int
    armor_class_parts: tuple[ArmorClassPart, ...]
    passive_perception: int
    hit_points: HitPointsView
    hit_dice: dict[int, int]
    spellcasting: Spellcasting
    granted_spells: tuple[GrantedSpellView, ...]
    proficiencies: Proficiencies
    darkvision: int
    resistances: tuple[str, ...]
    carrying_capacity: int
    carried_weight: float
    modifiers: ModifierSet
    feats: tuple[str, ...]
    #: Які поля гравець виправив вручну (ключі зі `SheetState.overrides`).
    overridden: frozenset[str] = frozenset()
    warnings: tuple[str, ...] = ()
    #: Навички з експертизою: бонус майстерності додано двічі.
    skill_expertise: dict[Skill, bool] = field(default_factory=dict)
    passive_investigation: int = 10
    passive_insight: int = 10
    #: Вдягнене без володіння (PHB, p. 144): завада на СИЛ/СПР і заборона чарувати.
    armor_untrained: tuple[str, ...] = ()
    #: Сліпе чуття (Blind Fighting, TCoE, p. 41), фути.
    blindsight: int = 0
    #: КЗ, що діє лише за умови (Пісня клинка): готові рядки для листа.
    armor_class_notes: tuple[str, ...] = ()
    #: Опір, що діє лише за умови (у люті, за очко чаклунства): готові рядки.
    resistance_notes: tuple[str, ...] = ()
    #: Перевага й особливі правила кидків (Відчуття небезпеки, Надійний талант…).
    roll_notes: tuple[str, ...] = ()
    #: Примітки до заклять за назвою (нижній регістр): виклики Містичного розряду.
    spell_notes: dict[str, str] = field(default_factory=dict)

    # --- зручні похідні для рендерів --------------------------------------

    @property
    def casting_classes(self) -> tuple[ClassCasting, ...]:
        return self.spellcasting.classes

    def ability(self, ability: Ability) -> AbilityView:
        return self.abilities[ability]

    def skill_bonus(self, skill: Skill) -> int:
        return self.skills[skill]


class DerivedStatsCalculator:
    """Рахує лист. Нічого не змінює й нічого не зберігає."""

    def __init__(self, resolver: ModifierResolver | None = None) -> None:
        self._resolver = resolver or ModifierResolver()

    def compute(self, character: Character) -> ComputedSheet:
        overrides = dict(character.state.overrides)
        applied: set[str] = set()
        modifiers = self._resolver.resolve(character)
        abilities = self._abilities(character, modifiers)
        modifiers_map = {ability: view.modifier for ability, view in abilities.items()}
        total_level = max(1, character.total_level)
        proficiency = proficiency_bonus(total_level)
        proficiencies = character.all_proficiencies()
        warnings: list[str] = []
        worn = (
            (character.inventory.worn_armor, armor_category(character.inventory.worn_armor)),
            (character.inventory.worn_shield, "shield"),
        )
        armor_untrained = tuple(
            item.name_en
            for item, kind in worn
            if item is not None and not proficiencies.has(ProficiencyKind.ARMOR, kind)
        )
        if armor_untrained:
            warnings.append(
                f"Без володіння: {', '.join(armor_untrained)} — завада на перевірки, рятівні кидки й "
                "атаки Сили та Спритності; чарувати закляття не можна (PHB, p. 144)"
            )

        saving_proficiency = {
            ability: proficiencies.has(ProficiencyKind.SAVING_THROW, ability.value)
            for ability in Ability
        }
        saving_throws = {
            ability: modifiers_map[ability]
            + (proficiency if saving_proficiency[ability] else 0)
            + modifiers.total(ModifierKind.SAVING_THROW)
            for ability in Ability
        }
        for ability in Ability:
            key = f"save:{ability.value}"
            if key in overrides:
                saving_throws[ability] = overrides[key]
                applied.add(key)

        skill_proficiency = {
            skill: proficiencies.has(ProficiencyKind.SKILL, skill.value) for skill in Skill
        }
        # Blessings of Knowledge — подвоєний бонус без окремого вибору експертизи.
        expert = set(character.expertise) | derived_choices.auto_expertise(character)
        skill_expertise = {
            skill: skill_proficiency[skill] and skill.value in expert for skill in Skill
        }
        skills = {
            skill: modifiers_map[SKILL_ABILITY[skill]]
            + (proficiency if skill_proficiency[skill] else 0)
            + (proficiency if skill_expertise[skill] else 0)
            + modifiers.total(ModifierKind.SKILL, skill.value)
            for skill in Skill
        }
        for skill in Skill:
            key = f"skill:{skill.value}"
            if key in overrides:
                skills[skill] = overrides[key]
                applied.add(key)

        armor_class, ac_parts = self._armor_class(character, modifiers_map, modifiers)
        if "armor_class" in overrides:
            armor_class = overrides["armor_class"]
            ac_parts = (ArmorClassPart(label="override", value=armor_class),)
            applied.add("armor_class")
        hit_points = self._hit_points(character, modifiers_map, warnings, modifiers)
        if "hit_points_max" in overrides:
            maximum = overrides["hit_points_max"]
            current = character.hp.current
            hit_points = HitPointsView(
                maximum=maximum,
                current=maximum if current is None else current,
                temporary=character.hp.temporary,
                parts=(HitPointPart(label="override", value=maximum),),
            )
            applied.add("hit_points_max")
        spellcasting = SpellSlotService().compute(
            character.class_entries(),
            {ability: view.total for ability, view in abilities.items()},
            proficiency,
        )
        self._check_prepared(character, spellcasting, warnings)

        species = character.species
        speed = species.speed if species is not None else 30
        speed += modifiers.total(ModifierKind.SPEED)
        if "speed" in overrides:
            speed = overrides["speed"]
            applied.add("speed")

        initiative = modifiers_map[Ability.DEX] + modifiers.total(ModifierKind.INITIATIVE)
        if "initiative" in overrides:
            initiative = overrides["initiative"]
            applied.add("initiative")

        passive = (
            PASSIVE_BASE
            + skills[Skill.PERCEPTION]
            + modifiers.total(ModifierKind.PASSIVE, "perception")
        )
        passive_investigation = (
            PASSIVE_BASE
            + skills[Skill.INVESTIGATION]
            + modifiers.total(ModifierKind.PASSIVE, "investigation")
        )
        passive_insight = PASSIVE_BASE + skills[Skill.INSIGHT]
        if "passive_perception" in overrides:
            passive = overrides["passive_perception"]
            applied.add("passive_perception")

        strength = abilities[Ability.STR].total
        return ComputedSheet(
            total_level=character.total_level,
            proficiency_bonus=proficiency,
            abilities=abilities,
            ability_modifiers=modifiers_map,
            saving_throws=saving_throws,
            saving_throw_proficiency=saving_proficiency,
            skills=skills,
            skill_proficiency=skill_proficiency,
            skill_expertise=skill_expertise,
            initiative=initiative,
            speed=speed,
            armor_class=armor_class,
            armor_class_parts=ac_parts,
            passive_perception=passive,
            passive_investigation=passive_investigation,
            passive_insight=passive_insight,
            hit_points=hit_points,
            hit_dice=hit_dice_pool(character.class_entries()),
            spellcasting=spellcasting,
            granted_spells=self._granted_spells(character),
            proficiencies=proficiencies,
            darkvision=self._darkvision(character, species),
            blindsight=10 if character.has_class_choice("blind fighting") else 0,
            armor_class_notes=self._armor_class_notes(character, modifiers_map),
            resistance_notes=self._resistance_notes(character),
            roll_notes=self._roll_notes(character),
            spell_notes=self._spell_notes(character, modifiers_map),
            resistances=species.resistances if species is not None else (),
            # Аспект звіра: Ведмідь — подвоєна вантажопідйомність (PHB, p. 50).
            carrying_capacity=strength * CARRY_PER_STRENGTH * (2 if character.has_class_choice("bear") and any(
                value.casefold() == "bear"
                for value in character.active_class_choices.get("sub:path-of-the-totem-warrior:Aspect of the Beast", ())
            ) else 1),
            carried_weight=character.inventory.total_weight,
            modifiers=modifiers,
            feats=character.feats,
            overridden=frozenset(applied),
            warnings=tuple(warnings),
            armor_untrained=armor_untrained,
        )

    # --- частини ------------------------------------------------------------

    @staticmethod
    def _abilities(
        character: Character, modifiers: ModifierSet
    ) -> dict[Ability, AbilityView]:
        views: dict[Ability, AbilityView] = {}
        for ability in Ability:
            base = character.ability(ability).value
            bonus = modifiers.ability_bonus(ability.value)
            total = min(30, base + bonus)  # межа 5e: 30 — максимум (PHB, p. 173)
            views[ability] = AbilityView(
                base=base, bonus=bonus, total=total, modifier=(total - 10) // 2
            )
        return views

    @staticmethod
    def _armor_class(
        character: Character,
        modifiers: dict[Ability, int],
        collected: ModifierSet,
    ) -> tuple[int, tuple[ArmorClassPart, ...]]:
        parts: list[ArmorClassPart] = []
        armor = character.inventory.worn_armor
        dexterity = modifiers[Ability.DEX]
        if armor is not None and armor.armor_base is not None:
            parts.append(ArmorClassPart(label=f"armor:{armor.name_en}", value=armor.armor_base))
            # Межа — за категорією броні: предмет із власного спорядження може не мати dex_cap.
            cap = armor_dex_cap(armor)
            # Medium Armor Master: до +3 Спритності в середній броні (PHB, p. 168).
            if cap == 2 and "medium-armor-master" in {derived_choices.feat_slug(f) for f in character.feats}:
                cap = 3
            capped = dexterity if cap is None else min(dexterity, cap)
            if capped:
                parts.append(ArmorClassPart(label="dexterity", value=capped))
        else:
            # Без броні — найкращий з доступних способів, а не перший і не сума
            # (PHB, p. 14: «якщо кілька способів рахувати КЗ — оберіть один»):
            # 10 + СПР; варвар 10 + СПР + СТА (щит дозволено); чернець 10 + СПР
            # + МУД, лише без щита; драконячий родовід 13 + СПР.
            has_shield = character.inventory.worn_shield is not None
            options: list[list[ArmorClassPart]] = [
                [
                    ArmorClassPart(label="unarmored", value=UNARMORED_BASE),
                    ArmorClassPart(label="dexterity", value=dexterity),
                ]
            ]
            for entry in character.classes:
                if entry.level <= 0:
                    continue
                second = UNARMORED_DEFENSE.get(entry.class_key)
                if second is not None and not (entry.class_key == "monk" and has_shield):
                    options.append(
                        [
                            ArmorClassPart(label="unarmored", value=UNARMORED_BASE),
                            ArmorClassPart(label="dexterity", value=dexterity),
                            ArmorClassPart(
                                label=f"unarmored-defense:{second.value}", value=modifiers[second]
                            ),
                        ]
                    )
                if entry.class_key == "sorcerer" and (entry.subclass_key or "").endswith(
                    "draconic-bloodline"
                ):
                    options.append(
                        [
                            ArmorClassPart(label="draconic-resilience", value=13),
                            ArmorClassPart(label="dexterity", value=dexterity),
                        ]
                    )
            # Броня тіней (Armor of Shadows): Обладунок мага за бажанням — 13 + СПР
            # (PHB, p. 110, 256); риса Dragon Hide — 13 + СПР (XGtE, p. 74).
            if any(name.casefold() == "armor of shadows" for name in character.invocations):
                options.append(
                    [
                        ArmorClassPart(label="mage-armor", value=13),
                        ArmorClassPart(label="dexterity", value=dexterity),
                    ]
                )
            if "dragon-hide" in {derived_choices.feat_slug(feat) for feat in character.feats}:
                options.append(
                    [
                        ArmorClassPart(label="dragon-hide", value=13),
                        ArmorClassPart(label="dexterity", value=dexterity),
                    ]
                )
            best = max(options, key=lambda option: sum(part.value for part in option))
            parts.extend(part for part in best if part.value or part.label != "dexterity")
        if character.inventory.worn_shield is not None:
            parts.append(ArmorClassPart(label="shield", value=SHIELD_AC_BONUS))
        bonus = collected.total(ModifierKind.ARMOR_CLASS)
        if bonus:
            parts.append(ArmorClassPart(label="bonus", value=bonus))
        return sum(part.value for part in parts), tuple(parts)

    @staticmethod
    def _darkvision(character: Character, species) -> int:  # noqa: ANN001 — SpeciesMechanics | None
        """Темний зір виду; Диявольський зір (Devil's Sight) — 120 фт (PHB, p. 110)."""
        base = species.darkvision if species is not None else 0
        if any(name.casefold() == "devil's sight" for name in character.invocations):
            return max(base, 120)
        return base

    @staticmethod
    def _armor_class_notes(character: Character, modifiers: dict[Ability, int]) -> tuple[str, ...]:
        """КЗ, що діє лише за умови: Клинкова пісня (TCoE, p. 76), Бойовий стиль «Захист»…"""
        notes: list[str] = []
        for entry in character.classes:
            if entry.class_key == "wizard" and (entry.subclass_key or "").endswith("bladesinging"):
                bonus = max(1, modifiers[Ability.INT])
                notes.append(
                    f"Клинкова пісня (Bladesong): +{bonus} до КЗ (Інтелект), поки діє — без середньої й "
                    "важкої броні та щита"
                )
        return tuple(notes)

    @staticmethod
    def _roll_notes(character: Character) -> tuple[str, ...]:
        """Перевага й особливі правила кидків від умінь класу (PHB 2014)."""
        level = character.class_level
        notes: list[str] = []
        if level("barbarian") >= 2:
            notes.append("Відчуття небезпеки (Danger Sense): перевага на рятівні кидки Спритності від видимих ефектів")
        if level("barbarian") >= 7:
            notes.append("Дикий інстинкт (Feral Instinct): перевага на ініціативу")
        if level("rogue") >= 11:
            notes.append("Надійний талант (Reliable Talent): у перевірках із володінням 9 і менше на d20 — це 10")
        if level("rogue") >= 14:
            notes.append("Сліпе чуття (Blindsense): чуєте схованих і невидимих істот у межах 10 фт")
        if level("ranger") >= 18:
            notes.append("Дикі чуття (Feral Senses): атаки по невидимих без завади; знаєте про невидимих у межах 30 фт")
        if level("monk") >= 7:
            notes.append("Спокій розуму (Stillness of Mind): дією знімаєте з себе зачарування чи переляк")
        if any(name.casefold() == "war caster" for name in (feat.rsplit("/", 1)[-1].replace("-", " ") for feat in character.feats)):
            notes.append("Бойовий заклинатель (War Caster): перевага на рятівні кидки Статури для концентрації")
        return tuple(notes)

    @staticmethod
    def _resistance_notes(character: Character) -> tuple[str, ...]:
        """Опір за умови: лють варвара, тотем Ведмедя, Стихійна спорідненість (PHB, p. 48, 50, 102)."""
        notes: list[str] = []
        choices = character.active_class_choices
        if character.class_level("barbarian"):
            bear = "bear" in {value.casefold() for value in choices.get("sub:path-of-the-totem-warrior:Totem Spirit", ())}
            notes.append(
                "У люті (Rage): опір усім видам урону, крім психічного — Тотемний дух Ведмедя"
                if bear
                else "У люті (Rage): опір дробильному, колючому й рубаному урону"
            )
        if character.class_level("monk") >= 10:
            notes.append("Імунітет до отрути й хвороб (Purity of Body)")
        if character.class_level("paladin") >= 3:
            notes.append("Імунітет до хвороб (Divine Health)")
        sorcerer = next((entry for entry in character.classes if entry.class_key == "sorcerer"), None)
        ancestor = choices.get("sub:draconic-bloodline:Dragon Ancestor", ())
        if sorcerer is not None and sorcerer.level >= 6 and ancestor:
            damage = dragon_damage_type(ancestor[0])
            if damage:
                notes.append(
                    f"Стихійна спорідненість (Elemental Affinity): 1 очко чаклунства — опір урону «{damage}» на 1 годину"
                )
        return tuple(notes)

    @staticmethod
    def _spell_notes(character: Character, modifiers: dict[Ability, int]) -> dict[str, str]:
        """Примітки до заклять: Містичний розряд з викликами (PHB, p. 110)."""
        notes: list[str] = []
        charisma = modifiers[Ability.CHA]
        labels = {
            "agonizing blast": f"Болісний розряд (Agonizing Blast): {charisma:+d} до урону кожного променя",
            "eldritch spear": "Містичний спис (Eldritch Spear): дальність 300 фт",
            "repelling blast": "Відштовхувальний розряд (Repelling Blast): відштовхує на 10 фт",
            "grasp of hadar": "Хватка Хадара (Grasp of Hadar): притягує на 10 фт раз на хід",
            "lance of lethargy": "Спис млявості (Lance of Lethargy): −10 фт швидкості раз на хід",
        }
        for name in character.invocations:
            if name.casefold() in ELDRITCH_BLAST_INVOCATIONS:
                notes.append(labels[name.casefold()])
        return {"eldritch blast": "; ".join(notes)} if notes else {}

    @staticmethod
    def _hit_points(
        character: Character,
        modifiers: dict[Ability, int],
        warnings: list[str],
        collected: ModifierSet | None = None,
    ) -> HitPointsView:
        maximum, parts = hit_point_maximum(
            character.class_entries(), modifiers[Ability.CON], character.hp
        )
        # Правила, що додають хіти за рівні: пагорбовий дворф, драконячий
        # родовід, риса Tough. Ручне значення максимуму (override) їх не чіпає.
        if collected is not None and character.hp.override_max is None:
            extra = collected.of(ModifierKind.MAX_HIT_POINTS)
            for item in extra:
                maximum += item.value
            parts = parts + tuple(
                HitPointPart(label=item.note_en or "bonus", value=item.value, source=item.source)
                for item in extra
            )
        state = character.hp
        # Незадані хіти показуємо як максимум; нуль лишається нулем, бо це
        # непритомний персонаж, а не «повний».
        current = maximum if state.current is None else state.current
        if current > maximum:
            warnings.append(
                f"поточні хіти ({current}) більші за максимум ({maximum})"
            )
        return HitPointsView(
            maximum=maximum,
            current=current,
            temporary=state.temporary,
            parts=parts,
        )

    @staticmethod
    def _granted_spells(character: Character) -> tuple[GrantedSpellView, ...]:
        """Що персонаж отримав від виду й підкласу — без класових лімітів.

        `expanded` патрона сюди не входить: це лише розширений список, з якого
        гравець обирає, а не готові закляття.
        """
        views: list[GrantedSpellView] = []
        species = character.species
        if species is not None:
            level = max(1, character.total_level)
            for name in species.shared_cantrips:
                views.append(GrantedSpellView(name_en=name, spell_level=0, source="species"))
            for spell in species.granted_spells:
                if spell.min_level <= level:
                    views.append(
                        GrantedSpellView(
                            name_en=spell.name_en,
                            spell_level=spell.spell_level,
                            source="species",
                        )
                    )
            for name in character.spell_choices:
                views.append(GrantedSpellView(name_en=name, spell_level=0, source="species"))
        for name, level, source, usage, ability in derived_choices.granted_spells(character):
            views.append(
                GrantedSpellView(name_en=name, spell_level=level, source=source, usage=usage, ability=ability)
            )
        for entry, definition in character.class_entries():
            spells = definition.subclass_spells_for(entry.subclass_key)
            if spells is None:
                continue
            terrain = character.class_choices.get(f"{entry.class_key}:Circle Terrain", ())
            table = (
                spells.by_terrain.get(terrain[0], {}) if spells.by_terrain and terrain
                else spells.by_level or ({1: spells.prepared} if spells.prepared else {})
            )
            for class_level, names in sorted(table.items()):
                if class_level > entry.level:
                    continue
                # Рівень закляття — найвищий, що клас має на рівні таблиці:
                # жрець 3 → 2-й, паладин 9 → 3-й.
                spell_level = definition.max_spell_level(class_level) or 1
                views.extend(
                    GrantedSpellView(
                        name_en=name,
                        spell_level=spell_level,
                        source="subclass",
                        prepared=True,
                        class_key=entry.class_key,
                    )
                    for name in names
                )
        return tuple(views)

    @staticmethod
    def _check_prepared(
        character: Character, spellcasting: Spellcasting, warnings: list[str]
    ) -> None:
        for casting in spellcasting.classes:
            if casting.prepared_limit is None:
                continue
            prepared = sum(
                1
                for spell in character.spells_of(casting.class_key)
                if not spell.is_cantrip and (spell.prepared or spell.always_prepared)
            )
            if prepared > casting.prepared_limit:
                warnings.append(
                    f"{casting.name_en}: підготовлено {prepared} заклять, "
                    f"ліміт {casting.prepared_limit}"
                )

    # --- для сумісності з рендерами ---------------------------------------

    @staticmethod
    def class_mechanics_of(character: Character, class_key: str) -> ClassMechanics:
        return character.class_definition(class_key)
