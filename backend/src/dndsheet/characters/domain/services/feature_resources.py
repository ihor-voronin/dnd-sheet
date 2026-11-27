"""Обмежені класові ресурси: скільки разів і коли відновлюються.

Це не «риси класу» (їхній текст живе в довіднику), а **лічильники**, які
гравець витрачає за столом: Друге дихання, Дія-сплеск, Канал божественності,
Кі, Очкова магії тощо. Без них лист не може чесно відпочити: «короткий
відпочинок» має повернути саме ті ресурси, які за правилами повертає.

Таблиця нижче — правила PHB у стислому вигляді (рівні, кількість, коли
відновлюється). Вона навмисно не парсить текст книг: текст описує ефект, а
не структуру, і «прочитати» з нього кількість було б вгадуванням.

Ресурс без рівня в персонажа не показується. Ресурси підкласів
(`subclass`) вмикаються лише тоді, коли в персонажа саме цей підклас.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping

from dndsheet.shared.kernel import Ability

if TYPE_CHECKING:  # pragma: no cover — лише для типів
    from dndsheet.characters.domain.character import Character

#: Коли ресурс відновлюється.
SHORT = "short"
LONG = "long"


@dataclass(frozen=True, slots=True)
class FeatureResource:
    """Лічильник класового вміння на листі."""

    key: str
    name_en: str
    class_key: str
    class_name: str
    level: int
    total: int
    used: int
    recharge: str
    action: str = "other"

    @property
    def available(self) -> int:
        return max(0, self.total - self.used)

    @property
    def recharge_label(self) -> str:
        return "короткий або тривалий" if self.recharge == SHORT else "тривалий"


@dataclass(frozen=True, slots=True)
class _Rule:
    key: str
    name_en: str
    class_key: str
    #: (рівень, скільки) — береться останній поріг, який уже досягнуто.
    #: `None` замість числа означає «дорівнює рівню класу».
    steps: tuple[tuple[int, int | None], ...]
    recharge: str = LONG
    #: З якого рівня ресурс відновлюється й на короткому відпочинку.
    short_from: int | None = None
    #: Здібність, що додає використання (або задає їх).
    ability: Ability | None = None
    #: `min1` — кількість = max(1, модифікатор); `add` — база + модифікатор.
    ability_mode: str = "min1"
    #: Суфікс ключа підкласу («war-domain»), якщо ресурс підкласовий.
    subclass: str | None = None


#: Порядок — як у книзі: класи, потім підкласи.
RULES: tuple[_Rule, ...] = (
    _Rule(
        key="fighter:second-wind",
        name_en="Second Wind",
        class_key="fighter",
        steps=((1, 1),),
        recharge=SHORT,
    ),
    _Rule(
        key="fighter:action-surge",
        name_en="Action Surge",
        class_key="fighter",
        steps=((2, 1), (17, 2)),
        recharge=SHORT,
    ),
    _Rule(
        key="fighter:indomitable",
        name_en="Indomitable",
        class_key="fighter",
        steps=((9, 1), (13, 2), (17, 3)),
        recharge=LONG,
    ),
    _Rule(
        key="barbarian:rage",
        name_en="Rage",
        class_key="barbarian",
        steps=((1, 2), (3, 3), (6, 4), (12, 5), (17, 6)),
        recharge=LONG,
    ),
    _Rule(
        key="bard:bardic-inspiration",
        name_en="Bardic Inspiration",
        class_key="bard",
        steps=((1, 1),),
        ability=Ability.CHA,
        ability_mode="min1",
        short_from=5,
    ),
    _Rule(
        key="cleric:channel-divinity",
        name_en="Channel Divinity",
        class_key="cleric",
        steps=((2, 1), (6, 2), (18, 3)),
        recharge=SHORT,
    ),
    _Rule(
        key="cleric:divine-intervention",
        name_en="Divine Intervention",
        class_key="cleric",
        steps=((10, 1),),
        recharge=LONG,
    ),
    _Rule(
        key="cleric:war-priest",
        name_en="War Priest",
        class_key="cleric",
        steps=((1, 1),),
        ability=Ability.WIS,
        ability_mode="min1",
        recharge=LONG,
        subclass="war-domain",
    ),
    _Rule(
        key="druid:wild-shape",
        name_en="Wild Shape",
        class_key="druid",
        steps=((2, 2),),
        recharge=SHORT,
    ),
    _Rule(
        key="druid:natural-recovery",
        name_en="Natural Recovery",
        class_key="druid",
        steps=((2, 1),),
        recharge=LONG,
    ),
    _Rule(
        key="monk:ki",
        name_en="Ki",
        class_key="monk",
        steps=((2, None),),
        recharge=SHORT,
    ),
    _Rule(
        key="monk:wholeness-of-body",
        name_en="Wholeness of Body",
        class_key="monk",
        steps=((6, 1),),
        recharge=LONG,
    ),
    _Rule(
        key="paladin:divine-sense",
        name_en="Divine Sense",
        class_key="paladin",
        steps=((1, 1),),
        ability=Ability.CHA,
        ability_mode="add",
        recharge=LONG,
    ),
    _Rule(
        key="paladin:cleansing-touch",
        name_en="Cleansing Touch",
        class_key="paladin",
        steps=((14, 1),),
        ability=Ability.CHA,
        ability_mode="min1",
        recharge=LONG,
    ),
    _Rule(
        key="artificer:flash-of-genius",
        name_en="Flash of Genius",
        class_key="artificer",
        steps=((7, 1),),
        ability=Ability.INT,
        ability_mode="min1",
        recharge=LONG,
    ),
    _Rule(
        key="paladin:channel-divinity",
        name_en="Channel Divinity",
        class_key="paladin",
        steps=((3, 1),),
        recharge=SHORT,
    ),
    _Rule(
        key="rogue:stroke-of-luck",
        name_en="Stroke of Luck",
        class_key="rogue",
        steps=((20, 1),),
        recharge=SHORT,
    ),
    _Rule(
        key="sorcerer:sorcery-points",
        name_en="Sorcery Points",
        class_key="sorcerer",
        steps=((2, None),),
        recharge=LONG,
    ),
    _Rule(
        key="warlock:eldritch-master",
        name_en="Eldritch Master",
        class_key="warlock",
        steps=((20, 1),),
        recharge=LONG,
    ),
    _Rule(
        key="warlock:dark-ones-luck",
        name_en="Dark One's Own Luck",
        class_key="warlock",
        steps=((6, 1),),
        recharge=SHORT,
        subclass="the-fiend",
    ),
    _Rule(
        key="fighter:superiority-dice",
        name_en="Superiority Dice",
        class_key="fighter",
        steps=((3, 4), (7, 5), (15, 6)),
        recharge=SHORT,
        subclass="battle-master",
    ),
    _Rule(
        key="wizard:arcane-recovery",
        name_en="Arcane Recovery",
        class_key="wizard",
        steps=((2, 1),),
        recharge=LONG,
    ),
)


#: Тип дії для ресурсу: з чим його показувати у вкладці «Дії».
ACTIONS: dict[str, str] = {
    "fighter:second-wind": "bonus",
    "fighter:action-surge": "other",
    "fighter:indomitable": "other",
    "fighter:superiority-dice": "other",
    "barbarian:rage": "bonus",
    "bard:bardic-inspiration": "bonus",
    "cleric:channel-divinity": "action",
    "cleric:divine-intervention": "action",
    "cleric:war-priest": "bonus",
    "druid:wild-shape": "action",
    "druid:natural-recovery": "other",
    "monk:ki": "bonus",
    "monk:wholeness-of-body": "action",
    "paladin:divine-sense": "action",
    "paladin:channel-divinity": "action",
    "rogue:stroke-of-luck": "other",
    "sorcerer:sorcery-points": "other",
    "warlock:eldritch-master": "action",
    "warlock:dark-ones-luck": "other",
    "wizard:arcane-recovery": "other",
}


def name_of(key: str) -> str | None:
    """Назва ресурсу за ключем («fighter:action-surge» → «Action Surge»)."""
    cleaned = (key or "").strip()
    for rule in RULES:
        if rule.key == cleaned:
            return rule.name_en
    return None


def _uses(
    rule: _Rule, level: int, ability_modifiers: Mapping[Ability, int]
) -> int:
    count = 0
    for threshold, value in rule.steps:
        if level >= threshold:
            count = level if value is None else value
    if not count:
        return 0
    if rule.ability is not None:
        modifier = ability_modifiers.get(rule.ability, 0)
        if rule.ability_mode == "min1":
            count = max(1, modifier)
        else:
            count = max(1, count + modifier)
    return count


def resources_for(
    character: "Character", ability_modifiers: Mapping[Ability, int]
) -> tuple[FeatureResource, ...]:
    """Ресурси, доступні цьому персонажу зараз (у порядку класів)."""
    resources: list[FeatureResource] = []
    for entry, definition in character.class_entries():
        level = entry.level
        subclass = (entry.subclass_key or "").split("/")[-1]
        for rule in RULES:
            if rule.class_key != definition.key:
                continue
            if rule.subclass is not None and rule.subclass != subclass:
                continue
            if level < rule.steps[0][0]:
                continue
            total = _uses(rule, level, ability_modifiers)
            if total <= 0:
                continue
            used = min(character.state.feature_used.get(rule.key, 0), total)
            recharge = (
                SHORT if rule.short_from is not None and level >= rule.short_from else rule.recharge
            )
            resources.append(
                FeatureResource(
                    key=rule.key,
                    name_en=rule.name_en,
                    class_key=definition.key,
                    class_name=definition.name_en,
                    level=level,
                    total=total,
                    used=used,
                    recharge=recharge,
                    action=ACTIONS.get(rule.key, "other"),
                )
            )
    paladin = character.class_level("paladin")
    if paladin:
        # Накладання рук: запас хітів 5 × рівень паладина (PHB, p. 84).
        total = 5 * paladin
        resources.insert(
            0,
            FeatureResource(
                key="paladin:lay-on-hands",
                name_en="Lay on Hands",
                class_key="paladin",
                class_name="Paladin",
                level=paladin,
                total=total,
                used=min(character.state.feature_used.get("paladin:lay-on-hands", 0), total),
                recharge=LONG,
                action="action",
            ),
        )
    return tuple(_with_feat_resources(character, resources))


#: Риси й стилі з лічильником: ключ, назва, скільки, коли відновлюється.
_FEAT_RESOURCES = {
    # Lucky: 3 очки удачі на тривалий відпочинок (PHB, p. 167).
    "lucky": ("feat:luck-points", "Luck Points", 3, LONG),
}


def _with_feat_resources(character: "Character", resources: list[FeatureResource]) -> list[FeatureResource]:
    """Лічильники рис: очки удачі; кістки переваги Бойового адепта й Вищої техніки.

    Martial Adept (PHB, p. 168) і Superior Technique (TCoE, p. 41) дають по одній
    кістці переваги d6; якщо персонаж уже майстер битви, кістка додається до його
    запасу, а не стає окремим лічильником.
    """
    feats = {feat.casefold().rsplit("/", 1)[-1] for feat in character.feats}
    extra_dice = int("martial-adept" in feats) + int(character.has_class_choice("superior technique"))
    if extra_dice:
        index = next((i for i, item in enumerate(resources) if item.key == "fighter:superiority-dice"), None)
        if index is not None:
            current = resources[index]
            total = current.total + extra_dice
            resources[index] = FeatureResource(
                key=current.key,
                name_en=current.name_en,
                class_key=current.class_key,
                class_name=current.class_name,
                level=current.level,
                total=total,
                used=min(character.state.feature_used.get(current.key, 0), total),
                recharge=current.recharge,
                action=current.action,
            )
        else:
            resources.append(_feat_resource(character, "feat:superiority-dice", "Superiority Dice", extra_dice, SHORT))
    for slug, (key, name, total, recharge) in _FEAT_RESOURCES.items():
        if slug in feats:
            resources.append(_feat_resource(character, key, name, total, recharge))
    return resources


def _feat_resource(character: "Character", key: str, name: str, total: int, recharge: str) -> FeatureResource:
    return FeatureResource(
        key=key,
        name_en=name,
        class_key="feat",
        class_name="Feat",
        level=character.total_level,
        total=total,
        used=min(character.state.feature_used.get(key, 0), total),
        recharge=recharge,
        action="other",
    )
