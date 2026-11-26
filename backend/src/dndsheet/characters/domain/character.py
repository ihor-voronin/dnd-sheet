"""Агрегат `Character` (v2): мультиклас, вид, передісторія, володіння, інвентар.

Межі відповідальності:

* **агрегат** тримає стан і незмінні інваріанти — сумарний рівень, узгодженість
  підкласу з рівнем, ліміти заклять за таблицями класу, легітимність вибору
  навичок. Правила він бере через порт `RulesSource`, а не читає сам;
* **сервіси** (`DerivedStatsCalculator`, `ModifierResolver`, `SpellSlotService`)
  рахують похідне й нічого не змінюють;
* **додаток** вирішує, коли викликати методи агрегату.

Характеристики тут — **базові**, тобто те, що гравець узгодив на створенні
(набір, point buy, кидки). Бонуси виду й риси додає `ModifierResolver`, тому
лист завжди може показати «15 + 1 = 16», а не голе 16 без пояснень.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from dndsheet.characters.domain.class_level import CharacterClass
from dndsheet.characters.domain.inventory import Inventory, InventoryItem
from dndsheet.characters.domain.pick_rules import is_choice_label, validate_pick
from dndsheet.characters.domain.ports import RulesSource
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    Proficiencies,
    SourceKind,
)
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.shared.errors import NotFoundError, ValidationError
from dndsheet.shared.events import (
    AbilityScoresChanged,
    CharacterCreated,
    DomainEvent,
    LevelGained,
)
from dndsheet.shared.kernel import MAX_LEVEL, Ability, AbilityScore, Money
from dndsheet.shared.rules import BackgroundMechanics, ClassMechanics, SpeciesMechanics


@dataclass(slots=True)
class Character:
    """Корінь агрегату. Змінюється лише через власні методи."""

    id: str
    name: str
    abilities: dict[Ability, AbilityScore]
    rules: RulesSource = field(repr=False, compare=False)
    classes: list[CharacterClass] = field(default_factory=list)
    ability_bonus_choices: tuple[Ability, ...] = ()
    species_key: str | None = None
    subspecies_key: str | None = None
    background_key: str | None = None
    alignment: str | None = None
    #: Володіння, які гравець обрав або додав сам. Похідні від класу, виду й
    #: передісторії не дублюються тут — їх збирає `all_proficiencies()`.
    chosen: Proficiencies = field(default_factory=Proficiencies)
    inventory: Inventory = field(default_factory=Inventory)
    spells: tuple[KnownSpell, ...] = ()
    feats: tuple[str, ...] = ()
    hp: HitPointState = field(default_factory=HitPointState)
    version: int = 1
    events: list[DomainEvent] = field(default_factory=list, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValidationError("Імʼя персонажа не може бути порожнім")
        self.name = self.name.strip()
        missing = set(Ability) - set(self.abilities)
        if missing:
            names = ", ".join(sorted(ability.value for ability in missing))
            raise ValidationError(f"Не задано характеристики: {names}")
        if self.version < 1:
            raise ValidationError("Версія агрегату має бути >= 1")
        self._normalize_keys()
        self._validate_origins()
        self._validate_classes()
        self._validate_ability_choices()
        self._validate_chosen()
        self._validate_spells()
        self._validate_hit_points()

    # ------------------------------------------------------------------
    # похідні властивості
    # ------------------------------------------------------------------

    @property
    def total_level(self) -> int:
        return sum(class_level.level for class_level in self.classes)

    @property
    def species(self) -> SpeciesMechanics | None:
        """Діючий вид: підраса вже несе успадковані числа батька."""
        key = self.subspecies_key or self.species_key
        return self.rules.species_mechanics(key) if key else None

    @property
    def background(self) -> BackgroundMechanics | None:
        return self.rules.background_mechanics(self.background_key) if self.background_key else None

    def class_definition(self, class_key: str) -> ClassMechanics:
        definition = self.rules.class_mechanics(class_key)
        if definition is None:
            raise NotFoundError(f"немає правил класу {class_key!r}")
        return definition

    def class_level(self, class_key: str) -> int:
        wanted = class_key.strip().casefold()
        for entry in self.classes:
            if entry.class_key == wanted:
                return entry.level
        return 0

    def has_class(self, class_key: str) -> bool:
        return self.class_level(class_key) > 0

    def class_entries(self) -> tuple[tuple[CharacterClass, ClassMechanics], ...]:
        return tuple((entry, self.class_definition(entry.class_key)) for entry in self.classes)

    def spellcasting_classes(self) -> tuple[tuple[CharacterClass, ClassMechanics], ...]:
        return tuple(
            (entry, definition)
            for entry, definition in self.class_entries()
            if definition.casts_spells
        )

    @property
    def hit_dice_pool(self) -> dict[int, int]:
        """Скільки хіт-дайсів якого розміру: {10: 2, 6: 3} — Воїн 2 / Волшебник 3."""
        pool: dict[int, int] = {}
        for entry in self.classes:
            die = self.class_definition(entry.class_key).hit_die
            pool[die] = pool.get(die, 0) + entry.level
        return pool

    # ------------------------------------------------------------------
    # зміни: імʼя, характеристики
    # ------------------------------------------------------------------

    def rename(self, name: str) -> None:
        cleaned = name.strip()
        if not cleaned:
            raise ValidationError("Імʼя персонажа не може бути порожнім")
        if cleaned == self.name:
            return
        self.name = cleaned
        self.bump_version()

    def set_alignment(self, alignment: str | None) -> None:
        cleaned = alignment.strip() if alignment else None
        if cleaned == self.alignment:
            return
        self.alignment = cleaned
        self.bump_version()

    def ability(self, ability: Ability) -> AbilityScore:
        return self.abilities[ability]

    def set_ability(self, ability: Ability, score: int) -> None:
        new_score = AbilityScore(score)
        if self.abilities.get(ability) == new_score:
            return
        self.abilities[ability] = new_score
        self.events.append(AbilityScoresChanged(character_id=self.id))
        self.bump_version()

    # ------------------------------------------------------------------
    # зміни: класи
    # ------------------------------------------------------------------

    def add_class(self, class_key: str, level: int = 1) -> None:
        """Додати клас до мультикласу. Повторно той самий клас — помилка."""
        key = class_key.strip().casefold()
        definition = self.class_definition(key)
        if self.has_class(key):
            raise ValidationError(f"клас {definition.name_en!r} уже є — змініть його рівень")
        if self.total_level + level > MAX_LEVEL:
            raise ValidationError(f"сумарний рівень не може бути більшим за {MAX_LEVEL}")
        entry = CharacterClass(class_key=key, level=level)
        self.classes.append(entry)
        self.events.append(LevelGained(character_id=self.id, level=self.total_level))
        self.bump_version()

    def set_class_level(self, class_key: str, level: int) -> None:
        wanted = class_key.strip().casefold()
        for index, entry in enumerate(self.classes):
            if entry.class_key != wanted:
                continue
            others = self.total_level - entry.level
            if others + level > MAX_LEVEL:
                raise ValidationError(f"сумарний рівень не може бути більшим за {MAX_LEVEL}")
            if level == entry.level:
                return
            definition = self.class_definition(wanted)
            updated = entry.with_level(level)
            if definition.subclass_level and level < definition.subclass_level:
                # Рівень упав нижче підкласу — вибір більше не дійсний.
                updated = updated.with_subclass(None)
            self.classes[index] = updated
            self.events.append(LevelGained(character_id=self.id, level=self.total_level))
            self.bump_version()
            return
        raise ValidationError(f"персонаж не має класу {class_key!r}")

    def remove_class(self, class_key: str) -> None:
        wanted = class_key.strip().casefold()
        remaining = [entry for entry in self.classes if entry.class_key != wanted]
        if len(remaining) == len(self.classes):
            raise ValidationError(f"персонаж не має класу {class_key!r}")
        if not remaining:
            raise ValidationError("персонаж має мати хоча б один клас")
        self.classes = remaining
        self.spells = tuple(spell for spell in self.spells if spell.class_key != wanted)
        self.chosen = self.chosen.without_source(SourceKind.CLASS, wanted)
        self.bump_version()

    def set_subclass(self, class_key: str, subclass_key: str | None) -> None:
        """Обрати підклас. Дозволено лише з рівня, коли клас його дає."""
        wanted = class_key.strip().casefold()
        for index, entry in enumerate(self.classes):
            if entry.class_key != wanted:
                continue
            if subclass_key is None:
                self.classes[index] = entry.with_subclass(None)
                self.bump_version()
                return
            definition = self.class_definition(wanted)
            if not definition.subclass_level:
                raise ValidationError(f"клас {definition.name_en!r} не має підкласів")
            if entry.level < definition.subclass_level:
                raise ValidationError(
                    f"підклас {definition.subclass_title!r} обирається з "
                    f"{definition.subclass_level} рівня"
                )
            self.classes[index] = entry.with_subclass(subclass_key)
            self.bump_version()
            return
        raise ValidationError(f"персонаж не має класу {class_key!r}")

    # ------------------------------------------------------------------
    # зміни: вид, передісторія, вибір бонусів
    # ------------------------------------------------------------------

    def set_species(self, species_key: str | None, subspecies_key: str | None = None) -> None:
        species = self.rules.species_mechanics(species_key) if species_key else None
        if species_key and species is None:
            raise NotFoundError(f"немає правил виду {species_key!r}")
        if species is not None and species.is_subspecies:
            raise ValidationError(
                f"{species.name_en!r} — підраса; вкажіть базовий вид, а її — підвидом"
            )
        if subspecies_key:
            subspecies = self.rules.species_mechanics(subspecies_key)
            if subspecies is None:
                raise NotFoundError(f"немає правил підраси {subspecies_key!r}")
            if not subspecies.is_subspecies:
                raise ValidationError(f"{subspecies.name_en!r} не є підрасою")
            if species is not None and subspecies.subrace_of not in (None, species.key):
                raise ValidationError(
                    f"{subspecies.name_en!r} не належить виду {species.name_en!r}"
                )
        self.species_key = species.key if species else None
        self.subspecies_key = subspecies_key.strip().casefold() if subspecies_key else None
        self.ability_bonus_choices = tuple(
            choice
            for choice in self.ability_bonus_choices
            if self.species and self.species.ability_choice
            and choice in self.species.ability_choice.options
        )
        self.bump_version()

    def set_background(self, background_key: str | None) -> None:
        background = self.rules.background_mechanics(background_key) if background_key else None
        if background_key and background is None:
            raise NotFoundError(f"немає правил передісторії {background_key!r}")
        self.background_key = background.key if background else None
        self.bump_version()

    def choose_ability_bonuses(self, abilities: Iterable[Ability]) -> None:
        """Розподілити бонуси виду «дві здібності на вибір по +1»."""
        species = self.species
        if species is None or species.ability_choice is None:
            raise ValidationError("вид не дає вибору бонусів характеристик")
        chosen = tuple(abilities)
        if len(set(chosen)) != len(chosen):
            raise ValidationError("здібності на вибір не можуть повторюватися")
        if len(chosen) != species.ability_choice.count:
            raise ValidationError(
                f"треба обрати {species.ability_choice.count} здібності, обрано {len(chosen)}"
            )
        for ability in chosen:
            if ability not in species.ability_choice.options:
                raise ValidationError(f"{ability.value} не входить у вибір виду")
        self.ability_bonus_choices = chosen
        self.bump_version()

    # ------------------------------------------------------------------
    # зміни: володіння
    # ------------------------------------------------------------------

    def pick(self, proficiency: Proficiency) -> None:
        """Обрати володіння, яке дає клас, вид або передісторія."""
        self._validate_pick(proficiency, existing=self.chosen)
        self.chosen = self.chosen.add(proficiency)
        self.bump_version()

    def unpick(self, kind: ProficiencyKind, value: str, source: GrantSource) -> None:
        remaining = [
            item
            for item in self.chosen.items
            if not (
                item.kind is kind
                and item.value.casefold() == value.casefold()
                and item.source == source
            )
        ]
        if len(remaining) == len(self.chosen.items):
            raise ValidationError(f"володіння {value!r} не було обране з цього джерела")
        self.chosen = Proficiencies(items=tuple(remaining))
        self.bump_version()

    def add_manual_proficiency(self, kind: ProficiencyKind, value: str) -> None:
        self.pick(Proficiency(kind=kind, value=value, source=GrantSource.manual()))

    def all_proficiencies(self) -> Proficiencies:
        """Усі володіння: правила класу, виду, передісторії + вибір гравця.

        Володіння кидками порятунку, бронею й зброєю дає **лише перший клас**:
        за PHB (p. 164) мультиклас не додає цих володінь, тільки частину
        (легка броня, проста зброя) — її візард додає окремо, коли бере рівень.
        """
        items: list[Proficiency] = []
        for index, (entry, definition) in enumerate(self.class_entries()):
            source = GrantSource.of(SourceKind.CLASS, entry.class_key)
            if index == 0:
                items.extend(
                    Proficiency(
                        kind=ProficiencyKind.SAVING_THROW, value=ability.value, source=source
                    )
                    for ability in sorted(definition.saving_throws, key=lambda a: a.value)
                )
                items.extend(
                    Proficiency(kind=ProficiencyKind.ARMOR, value=name, source=source)
                    for name in definition.armor_training
                )
                items.extend(
                    Proficiency(kind=ProficiencyKind.WEAPON, value=name, source=source)
                    for name in definition.weapon_training
                )
            items.extend(
                Proficiency(kind=ProficiencyKind.TOOL, value=name, source=source)
                for name in definition.tool_training
                if not is_choice_label(name)
            )
        species = self.species
        if species is not None:
            source = GrantSource.of(SourceKind.SPECIES, species.key)
            items.extend(
                Proficiency(kind=ProficiencyKind.SKILL, value=skill.value, source=source)
                for skill in sorted(species.skill_proficiencies, key=lambda s: s.value)
            )
            items.extend(
                Proficiency(kind=ProficiencyKind.WEAPON, value=name, source=source)
                for name in species.weapon_proficiencies
            )
            items.extend(
                Proficiency(kind=ProficiencyKind.TOOL, value=name, source=source)
                for name in species.tool_proficiencies
            )
            items.extend(
                Proficiency(kind=ProficiencyKind.LANGUAGE, value=name, source=source)
                for name in species.languages
            )
        background = self.background
        if background is not None:
            source = GrantSource.of(SourceKind.BACKGROUND, background.key)
            items.extend(
                Proficiency(kind=ProficiencyKind.SKILL, value=skill.value, source=source)
                for skill in sorted(background.skill_proficiencies, key=lambda s: s.value)
            )
            items.extend(
                Proficiency(kind=ProficiencyKind.TOOL, value=name, source=source)
                for name in background.tool_proficiencies
                if not is_choice_label(name)
            )
        collected = Proficiencies(items=tuple(items)).merge(self.chosen)
        return collected

    # ------------------------------------------------------------------
    # зміни: інвентар, хіти, закляття, риси
    # ------------------------------------------------------------------

    def add_item(self, item: InventoryItem) -> None:
        self.inventory = self.inventory.add(item)
        self.bump_version()

    def equip_item(self, name: str, equipped: bool = True) -> None:
        self.inventory = self.inventory.equip(name, equipped)
        self.bump_version()

    def set_money(self, money: Money) -> None:
        self.inventory = self.inventory.with_money(money)
        self.bump_version()

    def set_hit_points(self, hp: HitPointState) -> None:
        if len(hp.rolls) > max(0, self.total_level - 1):
            raise ValidationError(
                f"кидків хіт-дайсів не може бути більше за {max(0, self.total_level - 1)}"
            )
        self.hp = hp
        self.bump_version()

    def learn_spell(self, spell: KnownSpell) -> None:
        self._validate_spell_limits(self.spells + (spell,))
        if spell in self.spells:
            return
        self.spells = self.spells + (spell,)
        self.bump_version()

    def forget_spell(self, name_en: str, class_key: str) -> None:
        wanted_name = name_en.strip().casefold()
        wanted_class = class_key.strip().casefold()
        remaining = tuple(
            spell
            for spell in self.spells
            if not (
                spell.name_en.casefold() == wanted_name and spell.class_key == wanted_class
            )
        )
        if len(remaining) == len(self.spells):
            raise ValidationError(f"закляття {name_en!r} немає у списку персонажа")
        self.spells = remaining
        self.bump_version()

    def prepare_spell(self, name_en: str, class_key: str, prepared: bool = True) -> None:
        wanted_name = name_en.strip().casefold()
        wanted_class = class_key.strip().casefold()
        updated: list[KnownSpell] = []
        found = False
        for spell in self.spells:
            if spell.name_en.casefold() == wanted_name and spell.class_key == wanted_class:
                found = True
                updated.append(spell.prepare(prepared))
            else:
                updated.append(spell)
        if not found:
            raise ValidationError(f"закляття {name_en!r} немає у списку персонажа")
        self.spells = tuple(updated)
        self.bump_version()

    def add_feat(self, feat_key: str) -> None:
        key = feat_key.strip().casefold()
        if key in self.feats:
            return
        self.feats = self.feats + (key,)
        self.bump_version()

    def spells_of(self, class_key: str) -> tuple[KnownSpell, ...]:
        wanted = class_key.strip().casefold()
        return tuple(spell for spell in self.spells if spell.class_key == wanted)

    # ------------------------------------------------------------------
    # службове
    # ------------------------------------------------------------------

    def bump_version(self) -> None:
        self.version += 1

    def pull_events(self) -> tuple[DomainEvent, ...]:
        """Забрати накопичені події (шина зʼявиться разом зі збереженням)."""
        collected = tuple(self.events)
        self.events.clear()
        return collected

    # ------------------------------------------------------------------
    # інваріанти
    # ------------------------------------------------------------------

    def _normalize_keys(self) -> None:
        self.species_key = self.species_key.strip().casefold() if self.species_key else None
        self.subspecies_key = (
            self.subspecies_key.strip().casefold() if self.subspecies_key else None
        )
        self.background_key = (
            self.background_key.strip().casefold() if self.background_key else None
        )
        self.classes = list(self.classes)

    def _validate_origins(self) -> None:
        if self.subspecies_key and not self.species_key:
            raise ValidationError("підраса без базового виду")
        if self.species_key:
            species = self.rules.species_mechanics(self.species_key)
            if species is None:
                raise NotFoundError(f"немає правил виду {self.species_key!r}")
            if species.is_subspecies:
                raise ValidationError(f"{species.name_en!r} — підраса, а не базовий вид")
        if self.subspecies_key:
            subspecies = self.rules.species_mechanics(self.subspecies_key)
            if subspecies is None:
                raise NotFoundError(f"немає правил підраси {self.subspecies_key!r}")
            if subspecies.subrace_of and subspecies.subrace_of != self.species_key:
                raise ValidationError(
                    f"підраса {subspecies.name_en!r} не належить виду {self.species_key!r}"
                )
        if self.background_key and self.rules.background_mechanics(self.background_key) is None:
            raise NotFoundError(f"немає правил передісторії {self.background_key!r}")

    def _validate_classes(self) -> None:
        seen: set[str] = set()
        total = 0
        for entry in self.classes:
            if entry.class_key in seen:
                raise ValidationError(f"клас {entry.class_key!r} повторюється")
            seen.add(entry.class_key)
            definition = self.rules.class_mechanics(entry.class_key)
            if definition is None:
                raise NotFoundError(f"немає правил класу {entry.class_key!r}")
            total += entry.level
            if total > MAX_LEVEL:
                raise ValidationError(f"сумарний рівень не може бути більшим за {MAX_LEVEL}")
            self._check_subclass(entry, definition)

    def _check_subclass(self, entry: CharacterClass, definition: ClassMechanics) -> None:
        if entry.subclass_key is None:
            return
        if not definition.subclass_level:
            raise ValidationError(f"клас {definition.name_en!r} не має підкласів")
        if entry.level < definition.subclass_level:
            raise ValidationError(
                f"підклас {definition.subclass_title!r} обирається з "
                f"{definition.subclass_level} рівня"
            )

    @staticmethod
    def _subclass_level_of(entry: CharacterClass) -> int:  # pragma: no cover - сумісність
        # Рівень, з якого клас дає підклас; 0 означає «підкласів немає» —
        # тоді наявний вибір не скидаємо.
        return 0 if entry.subclass_key is None else 1

    def _validate_ability_choices(self) -> None:
        choices = self.ability_bonus_choices
        if not choices:
            return
        species = self.species
        if species is None or species.ability_choice is None:
            raise ValidationError("вид не дає вибору бонусів характеристик")
        if len(set(choices)) != len(choices):
            raise ValidationError("здібності на вибір не можуть повторюватися")
        if len(choices) != species.ability_choice.count:
            raise ValidationError(
                f"треба обрати {species.ability_choice.count} здібності, обрано {len(choices)}"
            )
        for ability in choices:
            if ability not in species.ability_choice.options:
                raise ValidationError(f"{ability.value} не входить у вибір виду")

    def _validate_chosen(self) -> None:
        accepted = Proficiencies()
        for item in self.chosen.items:
            validate_pick(self.rules, item, existing=accepted)
            accepted = accepted.add(item)

    def _validate_pick(self, pick: Proficiency, *, existing: Proficiencies) -> None:
        """Ті самі правила, що й у візарді — див. `pick_rules.validate_pick`."""
        validate_pick(self.rules, pick, existing=existing)

    def _validate_spells(self) -> None:
        self._validate_spell_limits(self.spells)

    def _validate_spell_limits(self, spells: tuple[KnownSpell, ...]) -> None:
        for spell in spells:
            if not self.has_class(spell.class_key):
                raise ValidationError(
                    f"немає класу {spell.class_key!r} для закляття {spell.name_en!r}"
                )
        for entry, definition in self.class_entries():
            own = tuple(spell for spell in spells if spell.class_key == entry.class_key)
            if not own:
                continue
            cantrips = sum(1 for spell in own if spell.is_cantrip)
            if cantrips > definition.cantrips_at(entry.level):
                raise ValidationError(
                    f"{definition.name_en}: заговори перевищують ліміт "
                    f"({cantrips} > {definition.cantrips_at(entry.level)})"
                )
            known = tuple(spell for spell in own if not spell.is_cantrip)
            limit = definition.spells_known_at(entry.level)
            if limit is not None and len(known) > limit:
                raise ValidationError(
                    f"{definition.name_en}: відомих заклять більше за ліміт "
                    f"({len(known)} > {limit})"
                )
            if known:
                max_level = self._max_spell_level(entry, definition)
                for spell in known:
                    if max_level and spell.level > max_level:
                        raise ValidationError(
                            f"{definition.name_en}: на {entry.level} рівні немає "
                            f"заклять {spell.level} рівня (максимум {max_level})"
                        )

    @staticmethod
    def _max_spell_level(entry: CharacterClass, definition: ClassMechanics) -> int:
        if definition.is_pact_magic:
            slots, level = definition.pact_at(entry.level)
            return level if slots else 0
        table = definition.slots_at(entry.level)
        levels = [index for index, count in enumerate(table, start=1) if count]
        return max(levels, default=0)

    def _validate_hit_points(self) -> None:
        if len(self.hp.rolls) > max(0, self.total_level - 1):
            raise ValidationError(
                f"кидків хіт-дайсів не може бути більше за {max(0, self.total_level - 1)}"
            )
