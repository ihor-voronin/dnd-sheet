"""Підвищення рівня: перевірити вибори й застосувати їх до агрегату.

Розділення праці, як і в решті застосунку:

* **план** (`LevelUpPlanner`) каже, що рівень дає й чого він вимагає;
* **застосунок** (цей файл) перевіряє те, що залежить від довідника (чи існує
  підклас, чи існує риса) і від порядку кроків: спершу рівень, потім кидок
  хітів, підклас, покращення характеристик, закляття;
* **агрегат** тримає інваріанти: сумарний рівень ≤ 20, межа 20 для
  характеристики, ліміти заклять.

Запит із аркуша D&D Beyond звучить як «беру рівень мага, кидаю 5 на d6, беру
підклас, +1 до ІНТ і +1 до СПР, вчу два закляття». Саме цю форму й приймає
`apply`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from dndsheet.characters.domain.character import Character
from dndsheet.characters.domain.ports import (
    CharacterRepository,
    FeatCatalog,
    SubclassCatalog,
)
from dndsheet.characters.domain.services.derived_stats import DerivedStatsCalculator
from dndsheet.characters.domain.services.feature_resources import name_of
from dndsheet.characters.domain.services.level_up import (
    LevelPlan,
    LevelUpPlanner,
    SlotRow,
)
from dndsheet.characters.domain.spells import KnownSpell
from dndsheet.shared.errors import ConflictError, NotFoundError, ValidationError
from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    SourceKind,
)
from dndsheet.shared.kernel import Ability
from dndsheet.shared.rules import MULTICLASS_SKILLS


@dataclass(frozen=True, slots=True)
class LevelUpReport:
    """Що саме сталося — для повідомлення на екрані, а не для нових чисел."""

    class_key: str
    class_name: str
    is_new_class: bool
    from_level: int
    to_level: int
    total_level_before: int
    total_level_after: int
    hp_max_before: int
    hp_max_after: int
    hp_current_before: int
    hp_current_after: int
    proficiency_bonus_before: int
    proficiency_bonus_after: int
    features: tuple[str, ...] = ()
    subclass_key: str | None = None
    ability_increases: tuple[tuple[str, int], ...] = ()
    feat_key: str | None = None
    slots: tuple[SlotRow, ...] = ()
    spells_added: tuple[str, ...] = ()
    resources_added: tuple[str, ...] = ()
    #: Клас узято всупереч вимогам мультикласу (галочка на екрані рівня).
    requirements_ignored: bool = False
    #: Що саме проігноровано: «INT 13», «STR 13 або DEX 13».
    ignored_requirements: tuple[str, ...] = ()


@dataclass(slots=True)
class LevelUpService:
    """Сценарій підвищення рівня: план і застосування."""

    characters: CharacterRepository
    subclasses: SubclassCatalog | None = None
    feats: FeatCatalog | None = None
    calculator: DerivedStatsCalculator | None = None
    planner: LevelUpPlanner | None = None

    def __post_init__(self) -> None:
        if self.calculator is None:
            self.calculator = DerivedStatsCalculator()
        if self.planner is None:
            self.planner = LevelUpPlanner(self.calculator)

    # ------------------------------------------------------------------
    # читання
    # ------------------------------------------------------------------

    def load(self, character_id: str) -> Character:
        character = self.characters.get(character_id)
        if character is None:
            raise NotFoundError(f"немає персонажа {character_id!r}")
        return character

    def preview(self, character_id: str) -> tuple[Character, tuple[LevelPlan, ...]]:
        character = self.load(character_id)
        return character, self.planner.plans(character)

    def plan_for(self, character: Character, class_key: str) -> LevelPlan:
        return self.planner.plan(character, class_key)

    # ------------------------------------------------------------------
    # застосування
    # ------------------------------------------------------------------

    def apply(
        self,
        character_id: str,
        body: Mapping[str, Any],
        *,
        expected_version: int | None = None,
    ) -> tuple[Character, LevelUpReport]:
        character = self.load(character_id)
        if expected_version is not None and expected_version != character.version:
            raise ConflictError(
                f"лист змінено (версія {character.version}, надіслано {expected_version})"
            )
        payload = dict(body or {})
        class_key = _text(payload.get("class_key"), "клас").casefold()
        plan = self.planner.plan(character, class_key)
        # Правило дому: вимоги мультикласу можна обійти свідомо. Тоді клас
        # усе одно додається, але лист памʼятає, що вимог не було.
        ignore_requirements = _flag(payload.get("ignore_requirements"))
        if not plan.allowed and not ignore_requirements:
            raise ValidationError(plan.blocked_reason or f"клас {class_key!r} недоступний")
        waived = ignore_requirements and not plan.allowed

        subclass_key = self._subclass(plan, payload.get("subclass_key"))
        hp_mode, hp_roll = _hp_choice(payload.get("hp"), plan)
        increases, feat_key = self._asi_choice(plan, payload)
        feat_ability = self._feat_ability(feat_key, payload.get("feat_ability"))
        spells = _spells(payload.get("spells"), plan.class_key)

        before = self.calculator.compute(character)
        roll_index = character.roll_index_for(plan.class_key)

        # 1. рівень
        if plan.is_new_class:
            character.add_class(plan.class_key, 1)
        else:
            character.raise_level(plan.class_key)

        # 1б. навичка від мультикласу (бард, слідопит, плут — PHB, p. 164)
        skill = _optional_text(payload.get("skill"))
        if skill is not None:
            if not plan.is_new_class or plan.class_key not in MULTICLASS_SKILLS:
                raise ValidationError(f"{plan.class_name}: цей рівень не дає навички на вибір")
            character.pick(
                Proficiency(
                    kind=ProficiencyKind.SKILL,
                    value=skill.casefold().replace(" ", "_"),
                    source=GrantSource.of(SourceKind.CLASS, plan.class_key),
                )
            )

        # 1а. позначка «взято без вимог» — уже після появи класу в списку
        if waived:
            character.waive_multiclass_requirements(plan.class_key, plan.requirements)

        # 2. кидок хітів — на місце, яке цей рівень займає в пулі
        if hp_mode == "roll":
            character.set_hit_points(character.hp.with_roll_at(roll_index, hp_roll))

        # 3. підклас
        if subclass_key is not None:
            character.set_subclass(plan.class_key, subclass_key)

        # 4. покращення характеристик або риса
        if increases or feat_key:
            character.take_asi(increases=increases, feat_key=feat_key, feat_ability=feat_ability)

        # 5. закляття
        added: list[str] = []
        # Скільки ще можна підготувати: рівень міг дати більше заклять, ніж
        # клас готує на день (жрець з низькою МУД). Такі лишаються відомими,
        # а не ламають увесь запит: підготовку можна змінити на листі.
        prepared_room = None
        # З урахуванням підкласу: містичний лицар має ліміт відомих заклять.
        definition = dict(
            (entry.class_key, item) for entry, item in character.class_entries()
        )[plan.class_key]
        if definition.prepares_spells:
            prepared_room = character.prepared_limit(plan.class_key) - sum(
                1
                for spell in character.spells_of(plan.class_key)
                if spell.prepared and not spell.is_cantrip
            )
        # Заміна одного відомого закляття на новому рівні (бард, чаклун,
        # чародій, слідопит, третинки — PHB, p. 53, 101, 107, 91).
        replaced = _optional_text(payload.get("replace_spell"))
        if replaced is not None:
            if definition.spells_known_at(plan.new_level) is None:
                raise ValidationError(f"{plan.class_name} не замінює закляття з рівнем — він їх готує")
            character.forget_spell(replaced, plan.class_key)
        for spell in spells:
            character.learn_spell(spell.prepare(False))
            added.append(spell.name_en)
            if spell.prepared and not spell.always_prepared:
                if prepared_room is None or prepared_room > 0:
                    character.prepare_spell(spell.name_en, spell.class_key, True)
                    if prepared_room is not None:
                        prepared_room -= 1

        after = self.calculator.compute(character)
        # 6. поточні хіти ростуть разом із максимумом, якщо їх задано
        gain = after.hit_points.maximum - before.hit_points.maximum
        if character.hp.current is not None and gain > 0:
            character.set_hp(current=character.hp.current + gain)

        self.characters.save(character)
        report = LevelUpReport(
            class_key=plan.class_key,
            class_name=plan.class_name,
            is_new_class=plan.is_new_class,
            from_level=plan.current_level,
            to_level=plan.new_level,
            total_level_before=before.total_level,
            total_level_after=character.total_level,
            hp_max_before=before.hit_points.maximum,
            hp_max_after=after.hit_points.maximum,
            hp_current_before=before.hit_points.current,
            hp_current_after=(
                after.hit_points.current
                if character.hp.current is not None
                else after.hit_points.maximum
            ),
            proficiency_bonus_before=before.proficiency_bonus,
            proficiency_bonus_after=after.proficiency_bonus,
            features=tuple(feature.name_en for feature in plan.features),
            subclass_key=subclass_key,
            ability_increases=tuple(
                (ability.value, amount) for ability, amount in sorted(increases.items())
            ),
            feat_key=feat_key,
            slots=plan.slots,
            spells_added=tuple(added),
            resources_added=tuple(
                name_of(key) or key
                for key in plan.resources_after
                if key not in plan.resources_before
            ),
            requirements_ignored=waived,
            ignored_requirements=plan.requirements if waived else (),
        )
        return character, report

    # ------------------------------------------------------------------
    # вибори
    # ------------------------------------------------------------------

    def _subclass(self, plan: LevelPlan, raw: Any) -> str | None:
        key = _optional_text(raw)
        if key is None:
            if plan.subclass_required:
                raise ValidationError(
                    f"{plan.class_name} на {plan.new_level} рівні обирає "
                    f"{plan.subclass_title or 'підклас'}"
                )
            return None
        if plan.subclass_level is None:
            raise ValidationError(f"{plan.class_name} не має підкласів")
        if plan.new_level < plan.subclass_level:
            raise ValidationError(
                f"підклас {plan.subclass_title!r} обирається з {plan.subclass_level} рівня"
            )
        if self.subclasses is not None:
            known = self.subclasses.subclass_keys(plan.class_key)
            if known is not None and key.casefold() not in {item.casefold() for item in known}:
                raise ValidationError(f"невідомий підклас {key!r}")
        return key

    def _asi_choice(
        self, plan: LevelPlan, payload: Mapping[str, Any]
    ) -> tuple[dict[Ability, int], str | None]:
        raw = payload.get("ability_increases") or {}
        if not isinstance(raw, Mapping):
            raise ValidationError("ability_increases має бути обʼєктом «характеристика: +»")
        increases: dict[Ability, int] = {}
        for name, amount in raw.items():
            try:
                ability = Ability(str(name).strip().casefold())
            except ValueError as exc:
                raise ValidationError(f"невідома характеристика {name!r}") from exc
            if isinstance(amount, bool) or not isinstance(amount, int):
                raise ValidationError(f"{name}: покращення має бути цілим числом")
            if amount:
                increases[ability] = amount
        feat_key = _optional_text(payload.get("feat_key"))
        if not plan.asi_pending:
            if increases or feat_key:
                raise ValidationError(
                    f"{plan.class_name} на {plan.new_level} рівні не дає "
                    f"покращення характеристик"
                )
            return {}, None
        if not increases and not feat_key:
            raise ValidationError(
                "це рівень покращення характеристик: оберіть +2 (або +1 і +1) чи рису"
            )
        if increases and feat_key:
            raise ValidationError("покращення характеристик і риса — це окремий вибір")
        if feat_key is not None:
            if self.feats is not None and not self.feats.has(feat_key):
                raise ValidationError(f"невідома риса {feat_key!r}")
            return {}, feat_key
        return increases, None

    def _feat_ability(self, feat_key: str | None, raw: Any) -> Ability | None:  # noqa: ANN401
        """Яку характеристику підвищує риса: одна можлива — сама, кілька — вибір гравця."""
        if feat_key is None or self.feats is None:
            return None
        options = self.feats.ability_options(feat_key)
        if not options:
            return None
        if raw is None and len(options) == 1:
            return options[0]
        try:
            chosen = Ability(str(raw or "").strip().casefold())
        except ValueError as exc:
            names = ", ".join(option.value.upper() for option in options)
            raise ValidationError(f"риса дає +1 до однієї з: {names} — оберіть характеристику") from exc
        if chosen not in options:
            names = ", ".join(option.value.upper() for option in options)
            raise ValidationError(f"ця риса підвищує лише {names}")
        return chosen


# ---------------------------------------------------------------------------
# розбір вхідних значень
# ---------------------------------------------------------------------------


def _hp_choice(raw: Any, plan: LevelPlan) -> tuple[str, int | None]:
    """Як рахувати хіти нового рівня: середнє чи кидок."""
    if raw is None:
        return "average", None
    if not isinstance(raw, Mapping):
        raise ValidationError("hp має бути обʼєктом {mode, roll}")
    mode = str(raw.get("mode") or "average").strip().casefold()
    if mode in {"average", "середнє", "mean"}:
        return "average", None
    if mode not in {"roll", "кидок"}:
        raise ValidationError(f"невідомий спосіб рахувати хіти {mode!r}")
    roll = raw.get("roll")
    if isinstance(roll, bool) or not isinstance(roll, int):
        raise ValidationError("кидок хіт-дайса має бути цілим числом")
    if not 1 <= roll <= plan.hit_die:
        raise ValidationError(f"кидок d{plan.hit_die} має бути в межах 1..{plan.hit_die}")
    return "roll", roll


def _spells(raw: Any, class_key: str) -> tuple[KnownSpell, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValidationError("spells має бути списком заклять")
    spells: list[KnownSpell] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValidationError("закляття має бути обʼєктом")
        name = _text(item.get("name_en"), "назва закляття")
        level = item.get("level")
        if isinstance(level, bool) or not isinstance(level, int):
            raise ValidationError(f"{name}: рівень закляття має бути цілим числом")
        own_class = _optional_text(item.get("class_key")) or class_key
        if own_class.casefold() != class_key.casefold():
            raise ValidationError(
                f"{name}: закляття належить класу {own_class!r}, "
                f"а рівень узято в {class_key!r}"
            )
        spells.append(
            KnownSpell(
                name_en=name,
                level=level,
                class_key=class_key,
                entry_id=_optional_text(item.get("entry_id")),
                prepared=bool(item.get("prepared", False)),
                always_prepared=bool(item.get("always_prepared", False)),
            )
        )
    return tuple(spells)


def _text(value: Any, what: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError(f"{what} обовʼязковий")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _flag(value: Any) -> bool:
    """Галочка з JSON. Рядок "false" не має ставати істиною."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    text = str(value).strip().casefold()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no", ""}:
        return False
    raise ValidationError(f"ignore_requirements має бути true або false, надіслано {value!r}")


__all__ = ["LevelUpReport", "LevelUpService"]
