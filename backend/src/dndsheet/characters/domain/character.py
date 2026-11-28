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

from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping

from dndsheet.characters.domain import derived_choices
from dndsheet.characters.domain.class_level import CharacterClass, MulticlassWaiver
from dndsheet.characters.domain.custom_features import MAX_CUSTOM_FEATURES, CustomFeature
from dndsheet.characters.domain.inventory import MAX_ATTUNED, Inventory, InventoryItem
from dndsheet.characters.domain.pick_rules import is_choice_label, validate_pick
from dndsheet.characters.domain.ports import RulesSource
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiencies,
    Proficiency,
    ProficiencyKind,
    SourceKind,
)
from dndsheet.characters.domain.spells import OTHER_CLASS, KnownSpell
from dndsheet.characters.domain.state import SheetState
from dndsheet.characters.domain.vitals import HitPointState
from dndsheet.shared.errors import NotFoundError, ValidationError
from dndsheet.shared.events import (
    AbilityScoresChanged,
    DomainEvent,
    LevelGained,
)
from dndsheet.shared.kernel import MAX_LEVEL, Ability, AbilityScore, Money, Skill
from dndsheet.shared.rules import (
    ARTIFICER_ATTUNEMENT,
    SPECIES_WITH_FEAT,
    BackgroundMechanics,
    ClassMechanics,
    DerivedChoice,
    SpeciesMechanics,
    ability_bonus_totals,
    ability_spread,
    class_choice_slots,
    prepared_spell_limit,
    with_subclass_casting,
)

#: Ключ експертизи для злодійських інструментів (плут, PHB p. 96).
THIEVES_TOOLS = "thieves' tools"


@dataclass(slots=True)
class Character:
    """Корінь агрегату. Змінюється лише через власні методи."""

    id: str
    name: str
    abilities: dict[Ability, AbilityScore]
    rules: RulesSource = field(repr=False, compare=False)
    classes: list[CharacterClass] = field(default_factory=list)
    #: Класи, узяті без вимог мультикласу (правило дому). Не впливає на числа:
    #: це позначка для листа, щоб персонаж не виглядав узгодженим із PHB.
    multiclass_waivers: tuple[MulticlassWaiver, ...] = ()
    ability_bonus_choices: tuple[Ability, ...] = ()
    #: Вільний розподіл бонусів виду (правила 2022): +2 і +1 або три +1.
    #: Діє лише для видів, у яких бонуси не фіксовані (`ability_unresolved`).
    ability_spread: dict[Ability, int] = field(default_factory=dict)
    species_key: str | None = None
    subspecies_key: str | None = None
    background_key: str | None = None
    #: Власна передісторія: текст, який гравець написав сам (назва, опис,
    #: риса, спорядження). Правила вибору при цьому стандартні.
    custom_background: dict[str, Any] | None = None
    alignment: str | None = None
    #: Володіння, які гравець обрав або додав сам. Похідні від класу, виду й
    #: передісторії не дублюються тут — їх збирає `all_proficiencies()`.
    chosen: Proficiencies = field(default_factory=Proficiencies)
    inventory: Inventory = field(default_factory=Inventory)
    spells: tuple[KnownSpell, ...] = ()
    #: Обрані заговори виду («один заговір візарда» у високого ельфа).
    #: Самі бонуси виду (thaumaturgy тифлінга) не зберігаються — вони похідні.
    spell_choices: tuple[str, ...] = ()
    feats: tuple[str, ...] = ()
    #: Власні вміння (дар майстра, сила предмета): текст гравця, без чисел.
    custom_features: tuple[CustomFeature, ...] = ()
    #: Експертиза (PHB: плут 1/6, бард 3/10): навички або злодійські
    #: інструменти з подвоєним бонусом майстерності. Значення — ключі навичок
    #: (`stealth`) або `thieves' tools`.
    expertise: tuple[str, ...] = ()
    #: Риса → характеристика, яку вона підвищила на 1 (Actor, Resilient…).
    feat_abilities: dict[str, Ability] = field(default_factory=dict)
    #: Вибори класу «клас:група» → назви: {"fighter:Fighting Style": ("Defense",)}.
    #: Тут же вибори рис і стилів: «feat:skilled:Skills or Tools» (див. `derived_choices`).
    class_choices: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Риса виду на 1 рівні (варіантна людина, власна лінія) — ключ із `feats`.
    species_feat: str | None = None
    #: Книга, за якою граєте вид («MPMM», «VGM»); порожньо — книга запису виду.
    species_source: str | None = None
    #: Рівні заклять, обраних у виборах (Магічні таємниці): назва (нижній регістр) → рівень.
    #: Домен довідника не читає, тож рівень приходить разом із вибором.
    choice_spell_levels: dict[str, int] = field(default_factory=dict)
    #: Скільки разів гравець уже взяв покращення характеристик або рису.
    #: Їх дають рівні з рисою «Ability Score Improvement», тож кількість
    #: використаних мусить бути не більшою за кількість таких рівнів.
    asi_taken: int = 0
    hp: HitPointState = field(default_factory=HitPointState)
    #: Лічильники й виправлення листа (комірки, кістки хітів, кидки смерті, нотатки).
    state: SheetState = field(default_factory=SheetState)
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
        self._validate_waivers()
        self._validate_ability_choices()
        self._validate_ability_spread()
        self._validate_chosen()
        self._validate_spells()
        self._validate_spell_choices()
        self._validate_custom_features(self.custom_features)
        self._validate_hit_points()
        self._validate_asi()

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
        return tuple(
            (entry, with_subclass_casting(self.class_definition(entry.class_key), entry.subclass_key))
            for entry in self.classes
        )

    def spellcasting_classes(self) -> tuple[tuple[CharacterClass, ClassMechanics], ...]:
        return tuple((entry, definition) for entry, definition in self.class_entries() if definition.casts_spells)

    @property
    def hit_dice_pool(self) -> dict[int, int]:
        """Скільки кісток хітів якого розміру: {10: 2, 6: 3} — Воїн 2 / Волшебник 3."""
        pool: dict[int, int] = {}
        for entry in self.classes:
            die = self.class_definition(entry.class_key).hit_die
            pool[die] = pool.get(die, 0) + entry.level
        return pool

    @property
    def asi_slots(self) -> int:
        """Скільки покращень характеристик (або рис) персонаж уже заробив.

        Рівні з рисою «Ability Score Improvement» рахуються з правил класу, а
        не з окремого списку: у Воїна їх більше, ніж у мага, і це вже є в
        індексі механік.
        """
        return sum(
            1
            for entry, definition in self.class_entries()
            for feature in definition.features_at(entry.level)
            if feature.name_en == "Ability Score Improvement"
        )

    @property
    def expertise_slots(self) -> int:
        """Скільки експертиз дали рівні: кожне вміння «Expertise» — дві.

        Рахується з умінь класу, як і покращення характеристик: плут має його
        на 1 і 6 рівнях, бард — на 3 і 10.
        """
        from_classes = 2 * sum(
            1
            for entry, definition in self.class_entries()
            for feature in definition.features_at(entry.level)
            if feature.name_en == "Expertise"
        )
        # Skill Expert, Prodigy — ще одна експертиза (TCoE, p. 79; XGtE, p. 74).
        return from_classes + sum(
            derived_choices.FEAT_EXPERTISE.get(derived_choices.feat_slug(feat), 0) for feat in self.feats
        )

    def expertise_options(self) -> tuple[str, ...]:
        """Що можна взяти в експертизу: навички з володінням + злодійські інструменти плута."""
        proficiencies = self.all_proficiencies()
        options = [skill.value for skill in Skill if proficiencies.has(ProficiencyKind.SKILL, skill.value)]
        is_rogue = any(entry.class_key == "rogue" for entry, _ in self.class_entries())
        if is_rogue and (
            proficiencies.has(ProficiencyKind.TOOL, "thieves' tools")
            or proficiencies.has(ProficiencyKind.TOOL, "thieves’ tools")
        ):
            options.append(THIEVES_TOOLS)
        return tuple(options)

    @property
    def derived_choice_groups(self) -> dict[str, DerivedChoice]:
        """Вибори, які дали підкласи, дар угоди, риси й бойові стилі (див. `derived_choices`)."""
        return derived_choices.derived_groups(self.feats, self.class_choices, self.classes)

    @property
    def class_choice_slots(self) -> dict[str, int]:
        """Скільки бойових стилів, втаємничень, прийомів… дали рівні, риси й стилі."""
        slots = class_choice_slots(self.class_entries())
        for key, choice in self.derived_choice_groups.items():
            slots[key] = slots.get(key, 0) + choice.count
        return slots

    @property
    def active_class_choices(self) -> dict[str, tuple[str, ...]]:
        """Лише ті вибори, які ще дають рівні чи риси: прибрана риса не діє."""
        slots = self.class_choice_slots
        return {key: values[: slots[key]] for key, values in self.class_choices.items() if key in slots}

    @property
    def invocations(self) -> tuple[str, ...]:
        """Обрані містичні виклики — класом чаклуна чи рисою «Містичний адепт»."""
        return tuple(
            value
            for key, values in self.active_class_choices.items()
            if key.endswith(":Eldritch Invocations")
            for value in values
        )

    def has_class_choice(self, name: str) -> bool:
        """Чи обрано варіант (без регістру): `has_class_choice("archery")`."""
        wanted = name.casefold()
        return any(value.casefold() == wanted for values in self.active_class_choices.values() for value in values)

    @property
    def grants_species_feat(self) -> bool:
        """Варіантна людина й власна лінія беруть рису на 1 рівні (PHB, p. 31; TCoE, p. 8)."""
        return any((key or "").casefold() in SPECIES_WITH_FEAT for key in (self.species_key, self.subspecies_key))

    @property
    def species_sources(self) -> tuple[str, ...]:
        """Книги, у яких є вид: між ними можна обирати (VGM чи MPMM)."""
        species = self.rules.species_mechanics(self.species_key) if self.species_key else None
        return tuple(species.variants) if species is not None else ()

    def set_species_source(self, source: str | None) -> None:
        """Обрати книгу виду; `None` — книга запису за замовчуванням."""
        value = (source or "").strip().upper() or None
        if value is not None and value not in {item.upper() for item in self.species_sources}:
            raise ValidationError(f"вид не має версії з книги {source!r}")
        self.species_source = value
        self.bump_version()

    def set_species_feat(self, feat_key: str, feat_ability: Ability | None = None) -> None:
        """Обрати чи замінити рису виду; вибори попередньої риси прибираються."""
        if not self.grants_species_feat:
            raise ValidationError("вид персонажа не дає риси на 1 рівні")
        key = feat_key.strip().casefold()
        if not key:
            raise ValidationError("риса без ключа")
        old = self.species_feat
        if key != old and key in self.feats:
            raise ValidationError("цю рису персонаж уже має")
        feats = tuple(feat for feat in self.feats if feat != old)
        abilities = {name: value for name, value in self.feat_abilities.items() if name != old}
        choices = dict(self.class_choices)
        if old and old != key:
            prefix = f"{derived_choices.FEAT_PREFIX}{derived_choices.feat_slug(old)}:"
            choices = {name: values for name, values in choices.items() if not name.startswith(prefix)}
        self.feats = feats + (key,)
        if feat_ability is not None:
            abilities[key] = feat_ability
        self.feat_abilities = abilities
        self.class_choices = choices
        self.species_feat = key
        # Експертиза від попередньої риси (Skill Expert) більше не дана.
        self.expertise = self.expertise[: self.expertise_slots]
        self.bump_version()

    def set_class_choice(
        self,
        group_key: str,
        values: Iterable[str],
        allowed: Iterable[str],
        levels: Mapping[str, int] | None = None,
    ) -> None:
        """Обрати варіанти групи; `allowed` — назви з довідника або книги."""
        slots = self.class_choice_slots.get(group_key, 0)
        if not slots:
            raise ValidationError(f"рівні персонажа не дають вибору {group_key!r}")
        options = {option.casefold(): option for option in allowed}
        chosen: list[str] = []
        for raw in values:
            value = options.get(str(raw).strip().casefold())
            if value is None:
                raise ValidationError(f"{raw!r} не є варіантом {group_key}")
            if value not in chosen:
                chosen.append(value)
        if len(chosen) > slots:
            raise ValidationError(f"{group_key}: можна обрати {slots}, надіслано {len(chosen)}")
        if levels:
            known = {name.casefold(): int(level) for name, level in levels.items()}
            self.choice_spell_levels = {
                **self.choice_spell_levels,
                **{value.casefold(): known[value.casefold()] for value in chosen if value.casefold() in known},
            }
        updated = {**self.class_choices, group_key: tuple(chosen)}
        # Інший клас «Учня магії» — інший список: обрані з попереднього закляття скидаються.
        if group_key.endswith(":Spell Class") and tuple(chosen) != self.class_choices.get(group_key, ()):
            prefix = group_key.rsplit(":", 1)[0] + ":"
            groups = self.derived_choice_groups
            for key in list(updated):
                if key.startswith(prefix) and key in groups and groups[key].kind == "spell":
                    updated.pop(key)
        self.class_choices = updated
        self.bump_version()

    def set_expertise(self, values: Iterable[str]) -> None:
        """Обрати експертизу (PHB, p. 96 і 54): не більше, ніж дали рівні."""
        chosen: list[str] = []
        for raw in values:
            value = str(raw).strip().casefold().replace("’", "'")
            if value and value not in chosen:
                chosen.append(value)
        slots = self.expertise_slots
        if len(chosen) > slots:
            raise ValidationError(f"експертиз можна обрати {slots}, надіслано {len(chosen)}")
        allowed = set(self.expertise_options())
        wrong = [value for value in chosen if value not in allowed]
        if wrong:
            raise ValidationError(
                "експертизу можна взяти лише для навичок, якими персонаж володіє"
                f" (або злодійських інструментів плута): {', '.join(wrong)}"
            )
        self.expertise = tuple(chosen)
        self.bump_version()

    def roll_index_for(self, class_key: str) -> int:
        """Місце кидка кості хітів для наступного рівня в `hp.rolls`.

        Кидки впорядковані за рівнями всіх класів (спершу рівні 2..N першого,
        далі 1..M другого), тому рівень узятий у класі, який стоїть не
        останнім, вимагає вставки в середину, а не дописування в кінець.
        """
        wanted = class_key.strip().casefold()
        passed = 0
        for entry in self.classes:
            if entry.class_key == wanted:
                return max(0, passed + entry.level - 1)
            passed += entry.level
        return max(0, self.total_level - 1)

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

    def waive_multiclass_requirements(self, class_key: str, requirements: Iterable[str] = ()) -> None:
        """Позначити клас як узятий без вимог мультикласу (правило дому).

        Вимоги не стають «виконаними»: вони саме **проігноровані**, і лист
        показує це окремим рядком. Повторний виклик нічого не додає.
        """
        key = class_key.strip().casefold()
        if not self.has_class(key):
            raise ValidationError(f"персонаж не має класу {class_key!r}")
        if self.waiver_for(key) is not None:
            return
        waiver = MulticlassWaiver(class_key=key, requirements=tuple(requirements))
        self.multiclass_waivers = self.multiclass_waivers + (waiver,)
        self.bump_version()

    def waiver_for(self, class_key: str) -> MulticlassWaiver | None:
        wanted = class_key.strip().casefold()
        for waiver in self.multiclass_waivers:
            if waiver.class_key == wanted:
                return waiver
        return None

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

    def raise_level(self, class_key: str) -> None:
        """Узяти наступний рівень у наявному класі (мультиклас не додає).

        Числа (хіти, комірки, вміння) не змінюються тут: вони похідні від
        рівнів. Цей метод лише рухає рівень і тримає інваріант сумарного.
        """
        wanted = class_key.strip().casefold()
        if not self.has_class(wanted):
            raise ValidationError(f"персонаж не має класу {class_key!r}")
        self.set_class_level(wanted, self.class_level(wanted) + 1)

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
        self.multiclass_waivers = tuple(waiver for waiver in self.multiclass_waivers if waiver.class_key != wanted)
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
                    f"підклас {definition.subclass_title!r} обирається з {definition.subclass_level} рівня"
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
            raise ValidationError(f"{species.name_en!r} — підраса; вкажіть базовий вид, а її — підвидом")
        if subspecies_key:
            subspecies = self.rules.species_mechanics(subspecies_key)
            if subspecies is None:
                raise NotFoundError(f"немає правил підраси {subspecies_key!r}")
            if not subspecies.is_subspecies:
                raise ValidationError(f"{subspecies.name_en!r} не є підрасою")
            if species is not None and subspecies.subrace_of not in (None, species.key):
                raise ValidationError(f"{subspecies.name_en!r} не належить виду {species.name_en!r}")
        self.species_key = species.key if species else None
        self.subspecies_key = subspecies_key.strip().casefold() if subspecies_key else None
        # Вільний розподіл належить виду: змінили вид — розподіл скидається.
        if self.species is None or not self.species.ability_unresolved:
            self.ability_spread = {}
        self.ability_bonus_choices = tuple(
            choice
            for choice in self.ability_bonus_choices
            if self.species and self.species.ability_choice and choice in self.species.ability_choice.options
        )
        self.bump_version()

    def set_background(self, background_key: str | None) -> None:
        background = self.rules.background_mechanics(background_key) if background_key else None
        if background_key and background is None:
            raise NotFoundError(f"немає правил передісторії {background_key!r}")
        self.background_key = background.key if background else None
        if self.background_key != "custom":
            self.custom_background = None
        self.bump_version()

    def set_custom_background(self, data: Mapping[str, Any]) -> None:
        """Власна передісторія: текст гравця + стандартні правила вибору."""
        self.background_key = "custom"
        items = [
            {
                "name_en": str(item.get("name_en") or "").strip(),
                "quantity": max(1, int(item.get("quantity") or 1)),
            }
            for item in (data.get("items") or [])
            if str(item.get("name_en") or "").strip()
        ]
        self.custom_background = {
            "name": str(data.get("name") or "").strip() or "Власна передісторія",
            "description": str(data.get("description") or "").strip(),
            "feature_name": str(data.get("feature_name") or "").strip(),
            "feature_text": str(data.get("feature_text") or "").strip(),
            "equipment": str(data.get("equipment") or "").strip(),
            "items": items,
            "money_gp": max(0, int(data.get("money_gp") or 0)),
        }
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
            raise ValidationError(f"треба обрати {species.ability_choice.count} здібності, обрано {len(chosen)}")
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
            if not (item.kind is kind and item.value.casefold() == value.casefold() and item.source == source)
        ]
        if len(remaining) == len(self.chosen.items):
            raise ValidationError(f"володіння {value!r} не було обране з цього джерела")
        self.chosen = Proficiencies(items=tuple(remaining))
        self.bump_version()

    def add_manual_proficiency(self, kind: ProficiencyKind, value: str) -> None:
        self.pick(Proficiency(kind=kind, value=value, source=GrantSource.manual()))

    def all_proficiencies(self) -> Proficiencies:
        """Усі володіння: правила класу, виду, передісторії + вибір гравця.

        Перший клас дає все: рятівні кидки, броню, зброю, інструменти. Кожен
        наступний — лише те, що таблиця мультикласу (PHB, p. 164) називає для
        нього: у воїна легка й середня броня, щити, проста й військова зброя, у
        плута — легка броня й злодійські інструменти, у мага — нічого. Рятівних кидків
        мультиклас не дає взагалі. Навички на вибір (бард, слідопит, плут) — це
        вибір гравця, вони живуть у `chosen`.
        """
        items: list[Proficiency] = []
        for index, (entry, definition) in enumerate(self.class_entries()):
            source = GrantSource.of(SourceKind.CLASS, entry.class_key)
            if index == 0:
                items.extend(
                    Proficiency(kind=ProficiencyKind.SAVING_THROW, value=ability.value, source=source)
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
                tools = definition.tool_training
            else:
                items.extend(
                    Proficiency(kind=ProficiencyKind.ARMOR, value=name, source=source)
                    for name in definition.multiclass_armor
                )
                items.extend(
                    Proficiency(kind=ProficiencyKind.WEAPON, value=name, source=source)
                    for name in definition.multiclass_weapons
                )
                tools = definition.multiclass_tools
            items.extend(
                Proficiency(kind=ProficiencyKind.TOOL, value=name, source=source)
                for name in tools
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
                Proficiency(kind=ProficiencyKind.LANGUAGE, value=name, source=source) for name in species.languages
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
        # Resilient: володіння рятівним кидком обраної характеристики (PHB, p. 168).
        items.extend(
            Proficiency(
                kind=ProficiencyKind.SAVING_THROW,
                value=ability.value,
                source=GrantSource.of(SourceKind.FEAT, feat),
            )
            for feat, ability in self.feat_abilities.items()
            if feat.rsplit("/", 1)[-1] == "resilient"
        )
        # Риси (броня, обрані навички, інструменти, мови, зброя) і виклики.
        items.extend(derived_choices.feat_proficiencies(self))
        collected = Proficiencies(items=tuple(items)).merge(self.chosen)
        return collected

    # ------------------------------------------------------------------
    # зміни: інвентар, хіти, закляття, риси
    # ------------------------------------------------------------------

    def add_item(self, item: InventoryItem) -> None:
        inventory = self.inventory.add(item)
        self._check_kensei(inventory)
        self._check_attunement(inventory)
        self.inventory = inventory
        self.bump_version()

    def update_item(self, index: int, fields: Mapping[str, Any]) -> None:
        """Змінити предмет інвентаря за порядком: назва, тип, урон, вага тощо."""
        item = self.inventory.item_at(index)
        inventory = self.inventory.replace_at(index, replace(item, **fields))
        self._check_kensei(inventory)
        self._check_attunement(inventory)
        self.inventory = inventory
        self.bump_version()

    @property
    def kensei_slots(self) -> int:
        """Скільки зброї кенсея: 2 на 3 рівні ченця, +1 на 6, 11 і 17 (XGtE, p. 34)."""
        entry = next((item for item in self.classes if item.class_key == "monk"), None)
        if entry is None or not (entry.subclass_key or "").endswith("kensei") or entry.level < 3:
            return 0
        return 2 + sum(1 for mark in (6, 11, 17) if entry.level >= mark)

    @property
    def attunement_limit(self) -> int:
        """Скільком предметам можна настроїтися: 3, артифіцер 10/14/18 — 4/5/6."""
        level = self.class_level("artificer")
        return next((count for threshold, count in ARTIFICER_ATTUNEMENT if level >= threshold), MAX_ATTUNED)

    def _check_attunement(self, inventory: Inventory) -> None:
        limit = self.attunement_limit
        if inventory.attuned_count > limit:
            raise ValidationError(f"одночасно можна настроїтися не більше ніж на {limit} предмети")

    def _check_kensei(self, inventory: Inventory) -> None:
        marked = sum(1 for item in inventory.items if item.kensei_weapon)
        slots = self.kensei_slots
        if marked > slots:
            raise ValidationError(
                f"зброї кенсея можна обрати {slots}, позначено {marked}"
                if slots
                else "зброю кенсея обирає чернець Шляху кенсея з 3 рівня"
            )

    def remove_item(self, index: int) -> None:
        self.inventory = self.inventory.remove_at(index)
        self.bump_version()

    def equip_item(self, name: str, equipped: bool = True) -> None:
        self.inventory = self.inventory.equip(name, equipped)
        self.bump_version()

    def set_money(self, money: Money) -> None:
        self.inventory = self.inventory.with_money(money)
        self.bump_version()

    def set_hit_points(self, hp: HitPointState) -> None:
        if len(hp.rolls) > max(0, self.total_level - 1):
            raise ValidationError(f"кидків кісток хітів не може бути більше за {max(0, self.total_level - 1)}")
        self.hp = hp
        self.bump_version()

    def set_hp(self, *, current: int | None = None, temporary: int | None = None) -> None:
        """Змінити поточні або тимчасові хіти (не максимум — він похідний)."""
        updated = self.hp
        if temporary is not None:
            updated = updated.with_temporary(temporary)
        if current is not None:
            updated = updated.with_current(current)
        if updated == self.hp:
            return
        self.hp = updated
        self.bump_version()

    def apply_damage(self, amount: int) -> None:
        """Урон спершу знімає тимчасові хіти (PHB, p. 197)."""
        self.hp = self.hp.apply_damage(amount)
        self.bump_version()

    def heal(self, amount: int) -> None:
        self.hp = self.hp.apply_healing(amount)
        self.bump_version()

    def set_state(self, state: SheetState) -> None:
        """Замінити стан листа. Кість хітівів не може бути більше, ніж є."""
        pool = self.hit_dice_pool
        for die, used in state.hit_dice_used.items():
            if used > pool.get(die, 0):
                raise ValidationError(f"витрачених d{die} ({used}) більше, ніж є ({pool.get(die, 0)})")
        if state == self.state:
            return
        self.state = state
        self.bump_version()

    def set_override(self, field: str, value: int) -> None:
        self.set_state(self.state.with_override(field, value))

    def clear_override(self, field: str) -> None:
        self.set_state(self.state.without_override(field))

    def set_notes(self, notes: dict[str, str]) -> None:
        self.set_state(self.state.with_notes(notes))

    def learn_spell(self, spell: KnownSpell) -> None:
        self._validate_spell_limits(self.spells + (spell,))
        self._check_prepared_limit(self.spells + (spell,), spell.class_key)
        if spell in self.spells:
            return
        if spell.custom and self._spell_index(spell.name_en, spell.class_key) is not None:
            # Два записи з однією назвою й класом не розрізнити ні при
            # редагуванні, ні при видаленні — тож другий не додаємо.
            raise ValidationError(f"закляття {spell.name_en!r} уже є в листі")
        self.spells = self.spells + (spell,)
        self.bump_version()

    def update_custom_spell(self, name_en: str, class_key: str, spell: KnownSpell) -> None:
        """Замінити власне закляття новою версією (назва, рівень, клас, текст).

        Книжкові не редагуються: їхній текст і дані — з довідника. Нова
        версія проходить ті самі ліміти, що й нове закляття: зміна рівня чи
        класу не має обходити правила.
        """
        index = self._spell_index(name_en, class_key)
        if index is None:
            raise ValidationError(f"закляття {name_en!r} немає у списку персонажа")
        if not self.spells[index].custom or not spell.custom:
            raise ValidationError(f"{name_en}: змінювати можна лише власне закляття")
        clash = self._spell_index(spell.name_en, spell.class_key)
        if clash is not None and clash != index:
            raise ValidationError(f"закляття {spell.name_en!r} уже є в листі")
        updated = self.spells[:index] + (spell,) + self.spells[index + 1 :]
        self._validate_spell_limits(updated)
        self._check_prepared_limit(updated, spell.class_key)
        if updated == self.spells:
            return
        self.spells = updated
        self.bump_version()

    def _spell_index(self, name_en: str, class_key: str) -> int | None:
        wanted_name = name_en.strip().casefold()
        wanted_class = class_key.strip().casefold()
        for index, spell in enumerate(self.spells):
            if spell.name_en.casefold() == wanted_name and spell.class_key == wanted_class:
                return index
        return None

    def forget_spell(self, name_en: str, class_key: str) -> None:
        wanted_name = name_en.strip().casefold()
        wanted_class = class_key.strip().casefold()
        remaining = tuple(
            spell
            for spell in self.spells
            if not (spell.name_en.casefold() == wanted_name and spell.class_key == wanted_class)
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

    def set_spell_choices(self, names: Iterable[str]) -> None:
        """Обрати заговори, які вид дає на вибір (високий ельф)."""
        self.spell_choices = tuple(name.strip() for name in names if name.strip())
        self._validate_spell_choices()
        self.bump_version()

    # ------------------------------------------------------------------
    # власні вміння
    # ------------------------------------------------------------------

    def add_custom_feature(self, feature: CustomFeature) -> None:
        updated = self.custom_features + (feature,)
        self._validate_custom_features(updated)
        self.custom_features = updated
        self.bump_version()

    def update_custom_feature(self, feature: CustomFeature) -> None:
        """Замінити вміння з тим самим `id`; лічильник обрізається до нового максимуму."""
        index = self._custom_feature_index(feature.id)
        previous = self.custom_features[index]
        if previous == feature:
            return
        updated = self.custom_features[:index] + (feature,) + self.custom_features[index + 1 :]
        self._validate_custom_features(updated)
        self.custom_features = updated
        key = previous.resource_key
        used = self.state.feature_used.get(key, 0) if key is not None else 0
        if used:
            # Без лічильника — забути витрачене; менший максимум — не більше за нього.
            values = {name: count for name, count in self.state.feature_used.items() if name != key}
            if feature.uses is not None:
                values[key] = min(used, feature.uses)
            self.state = self.state.with_feature_used(values)
        self.bump_version()

    def remove_custom_feature(self, feature_id: str) -> None:
        index = self._custom_feature_index(feature_id)
        removed = self.custom_features[index]
        self.custom_features = self.custom_features[:index] + self.custom_features[index + 1 :]
        if removed.resource_key in self.state.feature_used:
            self.state = self.state.reset_features([removed.resource_key])
        self.bump_version()

    def custom_feature(self, feature_id: str) -> CustomFeature:
        return self.custom_features[self._custom_feature_index(feature_id)]

    def _custom_feature_index(self, feature_id: str) -> int:
        wanted = (feature_id or "").strip()
        for index, feature in enumerate(self.custom_features):
            if feature.id == wanted:
                return index
        raise NotFoundError(f"немає власного вміння {feature_id!r}")

    @staticmethod
    def _validate_custom_features(features: tuple[CustomFeature, ...]) -> None:
        if len(features) > MAX_CUSTOM_FEATURES:
            raise ValidationError(f"власних умінь не може бути більше за {MAX_CUSTOM_FEATURES}")
        ids = [feature.id for feature in features]
        if len(set(ids)) != len(ids):
            raise ValidationError("id власних умінь повторюються")

    def add_feat(self, feat_key: str) -> None:
        key = feat_key.strip().casefold()
        if key in self.feats:
            return
        self.feats = self.feats + (key,)
        self.bump_version()

    def ability_bonus_from_origin(self, ability: Ability) -> int:
        """Бонус характеристики від виду: фіксовані, вибір і вільний розподіл."""
        return ability_bonus_totals(self.species, self.ability_bonus_choices)[ability] + self.ability_spread.get(
            ability, 0
        )

    def increase_ability(self, ability: Ability, amount: int) -> None:
        """Покращення характеристики за рівень (PHB, p. 165).

        Межа 20 рахується **після** бонусів виду: гравець підвищує базову
        оцінку, але підсумок на листі не може перевищити 20.
        """
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 1:
            raise ValidationError("покращення характеристики має бути додатним цілим")
        base = self.abilities[ability].value
        total = base + self.ability_bonus_from_origin(ability) + self.ability_bonus_from_feats(ability) + amount
        if total > 20:
            raise ValidationError(
                f"{ability.value}: підсумок не може бути більшим за 20 "
                f"({base} + {self.ability_bonus_from_origin(ability)} бонус виду + {amount})"
            )
        self.set_ability(ability, base + amount)

    def take_asi(
        self,
        *,
        increases: Mapping[Ability, int] | None = None,
        feat_key: str | None = None,
        feat_ability: Ability | None = None,
    ) -> None:
        """Використати одне покращення характеристик: +2/+1+1 **або** риса."""
        if self.asi_taken >= self.asi_slots:
            raise ValidationError(
                f"покращень характеристик більше немає (зароблено {self.asi_slots}, використано {self.asi_taken})"
            )
        given = {ability: amount for ability, amount in (increases or {}).items() if amount}
        if given and feat_key:
            raise ValidationError("покращення характеристик і риса — це окремий вибір")
        if not given and not feat_key:
            raise ValidationError("треба обрати покращення характеристик або рису")
        if given:
            if len(given) > 2:
                raise ValidationError("покращити можна не більше двох характеристик")
            if sum(given.values()) != 2:
                raise ValidationError(f"покращення дає рівно +2 (або +1 і +1), надіслано {sum(given.values())}")
            if any(amount != 1 for amount in given.values()) and len(given) > 1:
                raise ValidationError("дві характеристики покращуються лише по +1")
            for ability, amount in given.items():
                self.increase_ability(ability, amount)
        if feat_key:
            self.add_feat(feat_key)
            if feat_ability is not None:
                self.feat_abilities = {**self.feat_abilities, feat_key.strip().casefold(): feat_ability}
        self.asi_taken += 1
        self.bump_version()

    def spells_of(self, class_key: str) -> tuple[KnownSpell, ...]:
        wanted = class_key.strip().casefold()
        return tuple(spell for spell in self.spells if spell.class_key == wanted)

    # ------------------------------------------------------------------
    # закляття: щоденна підготовка (PHB, p. 201)
    # ------------------------------------------------------------------

    def prepared_limit(self, class_key: str) -> int:
        """Скільки заклять клас готує на день: модифікатор + рівень, мінімум 1."""
        wanted = class_key.strip().casefold()
        if not self.has_class(wanted):
            raise ValidationError(f"персонаж не має класу {class_key!r}")
        definition = self.class_definition(wanted)
        ability = definition.spellcasting_ability
        if not definition.prepares_spells or ability is None:
            raise ValidationError(f"{definition.name_en}: клас не готує закляття на день")
        modifier = (self.ability_total(ability) - 10) // 2
        return prepared_spell_limit(modifier, self.class_level(wanted), definition.caster_progression)

    def ability_total(self, ability: Ability) -> int:
        """Підсумок характеристики на листі: база + бонуси виду."""
        return (
            self.abilities[ability].value
            + self.ability_bonus_from_origin(ability)
            + self.ability_bonus_from_feats(ability)
        )

    def ability_bonus_from_feats(self, ability: Ability) -> int:
        """+1 від рис на кшталт Actor, але не вище 20 (PHB, p. 165)."""
        count = sum(1 for chosen in self.feat_abilities.values() if chosen is ability)
        room = 20 - self.abilities[ability].value - self.ability_bonus_from_origin(ability)
        return max(0, min(count, room))

    def prepare_spells(self, class_key: str, spells: Iterable[KnownSpell]) -> None:
        """Підготовка на день: **замінити** підготовлені закляття класу.

        Чому заміна, а не позначка по одному: у книгах підготовка — це вибір
        набору на день («prepare the list of spells available to you»), а не
        прапорець. Заговори й власні закляття лишаються як були: перші
        змінюються лише з рівнем, другі гравець додав сам, і правило про них
        нічого не каже.

        Ліміт і найвищий рівень беруться з правил класу: клас без підготовки
        сюди не доходить, рівень закляття понад комірки — відмова.
        """
        wanted = class_key.strip().casefold()
        limit = self.prepared_limit(wanted)
        definition = self.class_definition(wanted)
        entry = next(item for item in self.classes if item.class_key == wanted)
        max_level = self._max_spell_level(entry, definition)

        chosen: list[KnownSpell] = []
        seen: set[str] = set()
        for spell in spells:
            if spell.class_key != wanted:
                raise ValidationError(
                    f"{spell.name_en}: закляття належить класу {spell.class_key!r}, а підготовка — для {wanted!r}"
                )
            if spell.is_cantrip:
                raise ValidationError(f"{spell.name_en}: заговори не змінюються під час підготовки")
            if spell.custom:
                raise ValidationError(
                    f"{spell.name_en}: власне закляття не входить у підготовку — воно завжди доступне"
                )
            key = spell.name_en.casefold()
            if key in seen:
                raise ValidationError(f"{spell.name_en}: закляття повторюється")
            seen.add(key)
            if max_level and spell.level > max_level:
                raise ValidationError(
                    f"{definition.name_en}: на {entry.level} рівні немає заклять "
                    f"{spell.level} рівня (максимум {max_level})"
                )
            chosen.append(spell.prepare(True))

        if len(chosen) > limit:
            raise ValidationError(f"{definition.name_en}: підготувати можна {limit}, обрано {len(chosen)}")

        kept = tuple(spell for spell in self.spells if spell.class_key != wanted or spell.is_cantrip or spell.custom)
        if wanted == "wizard":
            # Маг готує лише з книги заклять, а непідготовлені лишаються в ній
            # (PHB, p. 114) — інакше підготовка стирала б книгу.
            book = {
                spell.name_en.casefold(): spell
                for spell in self.spells
                if spell.class_key == wanted and not spell.is_cantrip and not spell.custom
            }
            missing = [spell.name_en for spell in chosen if spell.name_en.casefold() not in book]
            if missing:
                raise ValidationError(f"маг готує лише закляття зі своєї книги; немає: {', '.join(missing)}")
            picked = {spell.name_en.casefold() for spell in chosen}
            kept += tuple(spell.prepare(False) for key, spell in book.items() if key not in picked)
        updated = kept + tuple(chosen)
        # Власні закляття теж рахуються: вони вже підготовлені й займають місце.
        prepared_total = sum(
            1 for spell in updated if spell.class_key == wanted and spell.prepared and not spell.is_cantrip
        )
        if prepared_total > limit:
            raise ValidationError(
                f"{definition.name_en}: з власними закляттями підготовлено {prepared_total}, а можна {limit}"
            )
        self._validate_spell_limits(updated)
        self.spells = updated
        self.bump_version()

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
        self.subspecies_key = self.subspecies_key.strip().casefold() if self.subspecies_key else None
        self.background_key = self.background_key.strip().casefold() if self.background_key else None
        self.classes = list(self.classes)
        self.multiclass_waivers = tuple(self.multiclass_waivers)

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
                raise ValidationError(f"підраса {subspecies.name_en!r} не належить виду {self.species_key!r}")
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

    def _validate_waivers(self) -> None:
        """Позначка «вимоги проігноровано» має вказувати на наявний клас."""
        seen: set[str] = set()
        unique: list[MulticlassWaiver] = []
        for waiver in self.multiclass_waivers:
            if waiver.class_key in seen:
                continue
            seen.add(waiver.class_key)
            if not self.has_class(waiver.class_key):
                raise ValidationError(f"вимоги проігноровано для класу {waiver.class_key!r}, якого немає")
            unique.append(waiver)
        self.multiclass_waivers = tuple(unique)

    def _check_subclass(self, entry: CharacterClass, definition: ClassMechanics) -> None:
        if entry.subclass_key is None:
            return
        if not definition.subclass_level:
            raise ValidationError(f"клас {definition.name_en!r} не має підкласів")
        if entry.level < definition.subclass_level:
            raise ValidationError(
                f"підклас {definition.subclass_title!r} обирається з {definition.subclass_level} рівня"
            )

    @staticmethod
    def _subclass_level_of(entry: CharacterClass) -> int:  # pragma: no cover - сумісність
        # Рівень, з якого клас дає підклас; 0 означає «підкласів немає» —
        # тоді наявний вибір не скидаємо.
        return 0 if entry.subclass_key is None else 1

    def _validate_ability_spread(self) -> None:
        """Вільний розподіл (правила 2022) — лише там, де вид його дає."""
        spread = ability_spread(self.ability_spread)
        species = self.species
        if spread and (species is None or not species.ability_unresolved):
            raise ValidationError("вид не дає вільного розподілу бонусів характеристик (правила 2022)")
        self.ability_spread = spread

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
            raise ValidationError(f"треба обрати {species.ability_choice.count} здібності, обрано {len(choices)}")
        for ability in choices:
            if ability not in species.ability_choice.options:
                raise ValidationError(f"{ability.value} не входить у вибір виду")

    def _validate_chosen(self) -> None:
        accepted = Proficiencies()
        for item in self.chosen.items:
            validate_pick(self.rules, item, existing=accepted, multiclass=self._is_multiclass_source(item))
            accepted = accepted.add(item)

    def _is_multiclass_source(self, pick: Proficiency) -> bool:
        """Навичка від класу, який не перший у списку, — вибір мультикласу."""
        return (
            pick.source.kind is SourceKind.CLASS
            and bool(self.classes)
            and pick.source.key != self.classes[0].class_key
        )

    def _validate_pick(self, pick: Proficiency, *, existing: Proficiencies) -> None:
        """Ті самі правила, що й у візарді — див. `pick_rules.validate_pick`."""
        validate_pick(self.rules, pick, existing=existing, multiclass=self._is_multiclass_source(pick))

    def _validate_spell_choices(self) -> None:
        species = self.species
        allowed = species.cantrip_choice_count if species is not None and species.cantrip_choice_class else 0
        if len(set(self.spell_choices)) != len(self.spell_choices):
            raise ValidationError("заговори виду не можуть повторюватися")
        if allowed == 0:
            if self.spell_choices:
                raise ValidationError("вид не дає вибору заговорів")
            return
        if len(self.spell_choices) != allowed:
            raise ValidationError(f"вид дає {allowed} заговорів на вибір, обрано {len(self.spell_choices)}")

    def _validate_spells(self) -> None:
        self._validate_spell_limits(self.spells)

    def _validate_spell_limits(self, spells: tuple[KnownSpell, ...]) -> None:
        for spell in spells:
            # Власне закляття поза класом не належить класу й не займає лімітів.
            if spell.class_key == OTHER_CLASS:
                continue
            if not self.has_class(spell.class_key):
                raise ValidationError(f"немає класу {spell.class_key!r} для закляття {spell.name_en!r}")
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
                    f"{definition.name_en}: відомих заклять більше за ліміт ({len(known)} > {limit})"
                )
            if known:
                max_level = self._max_spell_level(entry, definition)
                for spell in known:
                    if max_level and spell.level > max_level:
                        raise ValidationError(
                            f"{definition.name_en}: на {entry.level} рівні немає "
                            f"заклять {spell.level} рівня (максимум {max_level})"
                        )

    def _check_prepared_limit(self, spells: tuple[KnownSpell, ...], class_key: str) -> None:
        """Підготовлених не більше за ліміт класу; клас без підготовки — без ліміту."""
        wanted = class_key.strip().casefold()
        if not self.has_class(wanted):
            return
        definition = self.class_definition(wanted)
        if not definition.prepares_spells:
            return
        limit = self.prepared_limit(wanted)
        prepared = sum(1 for spell in spells if spell.class_key == wanted and spell.prepared and not spell.is_cantrip)
        if prepared > limit:
            raise ValidationError(f"{definition.name_en}: підготовлених заклять {prepared}, а можна {limit}")

    @staticmethod
    def _max_spell_level(entry: CharacterClass, definition: ClassMechanics) -> int:
        return definition.max_spell_level(entry.level)

    def _validate_hit_points(self) -> None:
        if len(self.hp.rolls) > max(0, self.total_level - 1):
            raise ValidationError(f"кидків кісток хітів не може бути більше за {max(0, self.total_level - 1)}")

    def _validate_asi(self) -> None:
        if isinstance(self.asi_taken, bool) or not isinstance(self.asi_taken, int):
            raise ValidationError("лічильник покращень характеристик має бути цілим")
        if self.asi_taken < 0:
            raise ValidationError("лічильник покращень характеристик не може бути відʼємним")
        if self.asi_taken > self.asi_slots:
            raise ValidationError(f"покращень характеристик {self.asi_taken}, а рівні дають лише {self.asi_slots}")
