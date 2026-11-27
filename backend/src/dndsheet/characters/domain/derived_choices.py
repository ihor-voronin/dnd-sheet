"""Вибори й ефекти, які дають риси, бойові стилі та містичні виклики.

Риса «Умілий» (Skilled) дає три навички на вибір, «Учень магії» (Magic
Initiate) — клас і три закляття, стиль «Благословенний воїн» (Blessed Warrior)
— два заговори жерця. Такі вибори живуть у тому ж `class_choices`, що й
бойові стилі класу, лише з ключем іншого виду:

* `feat:<риса>:<група>` — вибір риси (`feat:skilled:Skills or Tools`);
* `style:<стиль>:<група>` — вибір бойового стилю (`style:blessed warrior:Cantrips`);
* `sub:<підклас>:<група>` — вибір підкласу (`sub:knowledge-domain:Skills`);
* `boon:<дар>:<група>` — вибір дару угоди (`boon:pact of the tome:Cantrips`).

Тоді один механізм на листі показує й зберігає все, а ефекти (володіння,
закляття, числа) збираються тут — з того, що справді обрано.
"""

from __future__ import annotations

from typing import Any, Iterable

from dndsheet.characters.domain.proficiencies import (
    GrantSource,
    Proficiency,
    ProficiencyKind,
    SourceKind,
)
from dndsheet.shared.kernel import Ability, Skill
from dndsheet.shared.rules import (
    FEAT_CHOICE_SPELL_NOTE,
    FEAT_CHOICES,
    FEAT_PROFICIENCIES,
    FEAT_SPELLS,
    INVOCATION_SPELLS,
    BOON_CHOICES,
    CLASS_FEATURE_CHOICES,
    INVOCATION_CHOICES,
    STYLE_CHOICES,
    SUBCLASS_CHOICES,
    SUBCLASS_EXPERTISE,
    SUBCLASS_PROFICIENCIES,
    DerivedChoice,
)

FEAT_PREFIX = "feat:"
STYLE_PREFIX = "style:"
SUBCLASS_PREFIX = "sub:"
BOON_PREFIX = "boon:"
FEATURE_PREFIX = "feature:"
INVOCATION_PREFIX = "inv:"

#: Риси, що дають одну експертизу (TCoE, p. 79; XGtE, p. 74).
FEAT_EXPERTISE = {"skill-expert": 1, "prodigy": 1}

#: Виклики, що дають володіння навичками (XGtE, p. 56).
INVOCATION_SKILLS = {"beguiling influence": (Skill.DECEPTION, Skill.PERSUASION)}

_PROFICIENCY_KIND = {
    "armor": ProficiencyKind.ARMOR,
    "weapon": ProficiencyKind.WEAPON,
    "tool": ProficiencyKind.TOOL,
    "language": ProficiencyKind.LANGUAGE,
}


def feat_slug(feat_key: str) -> str:
    """`phb-2014/feat/magic-initiate` → `magic-initiate`."""
    return feat_key.strip().casefold().rsplit("/", 1)[-1]


def skill_of(value: str) -> Skill | None:
    """«Sleight of Hand» або `sleight_of_hand` → навичка; інакше `None`."""
    key = value.strip().casefold().replace(" ", "_").replace("-", "_")
    try:
        return Skill(key)
    except ValueError:
        return None


def fighting_styles(class_choices: dict[str, tuple[str, ...]]) -> tuple[str, ...]:
    """Обрані бойові стилі — класом чи рисою «Учень бою» (Fighting Initiate)."""
    return tuple(
        value
        for key, values in class_choices.items()
        if key.endswith(":Fighting Style")
        for value in values
    )


def subclass_slug(subclass_key: str | None) -> str:
    return (subclass_key or "").casefold().rsplit("/", 1)[-1]


def derived_groups(
    feats: Iterable[str],
    class_choices: dict[str, tuple[str, ...]],
    classes: Iterable[Any] = (),  # noqa: ANN401 — CharacterClass
) -> dict[str, DerivedChoice]:
    """Групи виборів від підкласів, дару угоди, рис і стилів: ключ → що й скільки обрати."""
    groups: dict[str, DerivedChoice] = {}
    for entry in classes:
        # Вміння класу з вибором (Магічні таємниці барда), далі — підклас.
        for level, choice in CLASS_FEATURE_CHOICES.get(entry.class_key, ()):
            if entry.level >= level:
                groups[f"{FEATURE_PREFIX}{entry.class_key}:{choice.group}"] = choice
        slug = subclass_slug(entry.subclass_key)
        for level, choice in SUBCLASS_CHOICES.get(slug, ()):
            if entry.level >= level:
                groups[f"{SUBCLASS_PREFIX}{slug}:{choice.group}"] = choice
    for key, values in class_choices.items():
        if key.endswith(":Pact Boon"):
            for boon in values:
                for choice in BOON_CHOICES.get(boon.casefold(), ()):
                    groups[f"{BOON_PREFIX}{boon.casefold()}:{choice.group}"] = choice
        if key.endswith(":Eldritch Invocations"):
            for invocation in values:
                for choice in INVOCATION_CHOICES.get(invocation.casefold(), ()):
                    groups[f"{INVOCATION_PREFIX}{invocation.casefold()}:{choice.group}"] = choice
    for feat in feats:
        slug = feat_slug(feat)
        for choice in FEAT_CHOICES.get(slug, ()):
            groups[f"{FEAT_PREFIX}{slug}:{choice.group}"] = choice
    for style in fighting_styles(class_choices):
        slug = style.casefold()
        for choice in STYLE_CHOICES.get(slug, ()):
            groups[f"{STYLE_PREFIX}{slug}:{choice.group}"] = choice
    return groups


def split_key(key: str) -> tuple[str, str, str]:
    """`feat:skilled:Skills or Tools` → («feat», «skilled», «Skills or Tools»)."""
    kind, _, rest = key.partition(":")
    owner, _, group = rest.partition(":")
    return kind, owner, group


def spell_class_for(key: str, choice: DerivedChoice, class_choices: dict[str, tuple[str, ...]]) -> str | None:
    """Клас списку для вибору закляття: фіксований або з «Spell Class» тієї ж риси."""
    if choice.spell_class:
        return choice.spell_class
    kind, owner, _ = split_key(key)
    chosen = class_choices.get(f"{kind}:{owner}:Spell Class", ())
    return chosen[0] if chosen else None


def feat_proficiencies(character: Any) -> list[Proficiency]:  # noqa: ANN401 — Character
    """Володіння від рис (броня, інструменти, обрані навички), підкласів і викликів."""
    items: list[Proficiency] = []
    active = character.active_class_choices
    for feat in character.feats:
        slug = feat_slug(feat)
        source = GrantSource.of(SourceKind.FEAT, slug)
        for kind, value in FEAT_PROFICIENCIES.get(slug, ()):
            items.append(Proficiency(kind=_PROFICIENCY_KIND[kind], value=value, source=source))
    # Обране в групах рис, стилів, підкласів і дарів — навички, інструменти, мови, зброя.
    for key, choice in character.derived_choice_groups.items():
        source = source_of(character, key)
        for value in active.get(key, ()):
            proficiency = proficiency_of(choice.kind, value, source)
            if proficiency is not None:
                items.append(proficiency)
    for entry in character.classes:
        slug = (entry.subclass_key or "").casefold().rsplit("/", 1)[-1]
        source = GrantSource.of(SourceKind.CLASS, entry.class_key)
        for kind, value in SUBCLASS_PROFICIENCIES.get(slug, ()):
            if kind == "skill":
                items.append(Proficiency(kind=ProficiencyKind.SKILL, value=value, source=source))
            else:
                items.append(Proficiency(kind=_PROFICIENCY_KIND[kind], value=value, source=source))
    for invocation in character.invocations:
        for skill in INVOCATION_SKILLS.get(invocation.casefold(), ()):
            items.append(
                Proficiency(
                    kind=ProficiencyKind.SKILL,
                    value=skill.value,
                    source=GrantSource.of(SourceKind.CLASS, "warlock"),
                )
            )
    return items


def source_of(character: Any, key: str) -> GrantSource:  # noqa: ANN401 — Character
    """Хто дав вибір: риса — FEAT, підклас чи стиль — клас, у якого він є."""
    kind, owner, _ = split_key(key)
    if kind == "feat":
        return GrantSource.of(SourceKind.FEAT, owner)
    if kind in ("boon", "inv"):
        return GrantSource.of(SourceKind.CLASS, "warlock")
    if kind == "feature":
        return GrantSource.of(SourceKind.CLASS, owner)
    if kind == "sub":
        entry = next((item for item in character.classes if subclass_slug(item.subclass_key) == owner), None)
        return GrantSource.of(SourceKind.CLASS, entry.class_key if entry else owner)
    return GrantSource.of(SourceKind.CLASS, "fighting-style")


def auto_expertise(character: Any) -> frozenset[str]:  # noqa: ANN401 — Character
    """Навички з подвоєним бонусом без окремого вибору: Blessings of Knowledge (PHB, p. 59)."""
    active = character.active_class_choices
    chosen: set[str] = set()
    for slug in SUBCLASS_EXPERTISE:
        for value in active.get(f"{SUBCLASS_PREFIX}{slug}:Skills", ()):
            skill = skill_of(value)
            if skill is not None:
                chosen.add(skill.value)
    return frozenset(chosen)


def proficiency_of(kind: str, value: str, source: GrantSource) -> Proficiency | None:
    skill = skill_of(value)
    if kind in ("skill", "skill_or_tool", "skill_or_language") and skill is not None:
        return Proficiency(kind=ProficiencyKind.SKILL, value=skill.value, source=source)
    if kind == "skill_or_language":
        return Proficiency(kind=ProficiencyKind.LANGUAGE, value=value.casefold(), source=source)
    if kind in ("tool", "skill_or_tool") or (kind == "fixed" and value.endswith(("tools", "supplies", "utensils"))):
        return Proficiency(kind=ProficiencyKind.TOOL, value=value.casefold(), source=source)
    if kind == "language":
        return Proficiency(kind=ProficiencyKind.LANGUAGE, value=value.casefold(), source=source)
    if kind == "weapon":
        return Proficiency(kind=ProficiencyKind.WEAPON, value=value.casefold(), source=source)
    return None


#: Характеристика чарування класу (PHB, розділи класів; TCoE, p. 9).
CLASS_CASTING_ABILITY = {
    "artificer": Ability.INT,
    "bard": Ability.CHA,
    "cleric": Ability.WIS,
    "druid": Ability.WIS,
    "sorcerer": Ability.CHA,
    "warlock": Ability.CHA,
    "wizard": Ability.INT,
}

#: Риси, де характеристика чарування — та, яку риса підвищила (TCoE, p. 79–80).
_FEAT_ABILITY_CASTING = frozenset({"fey-touched", "shadow-touched", "telekinetic", "telepathic"})

#: Риси з фіксованою характеристикою чарування (XGtE, p. 74–75).
_FEAT_FIXED_CASTING = {
    "drow-high-magic": Ability.CHA,
    "wood-elf-magic": Ability.WIS,
    "fey-teleportation": Ability.INT,
}


def _feat_casting(character: Any, feat: str, spell_class: str | None) -> Ability | None:  # noqa: ANN401
    slug = feat_slug(feat)
    if slug in _FEAT_ABILITY_CASTING:
        return character.feat_abilities.get(feat)
    if slug in _FEAT_FIXED_CASTING:
        return _FEAT_FIXED_CASTING[slug]
    return CLASS_CASTING_ABILITY.get(spell_class or "")


def _spell_level(character: Any, name: str) -> int:  # noqa: ANN401 — Character
    """Рівень обраного закляття таємниць: домен довідника не читає, тож береться з рівнів, збережених під час вибору."""
    return int(character.choice_spell_levels.get(name.casefold(), 1))


def granted_spells(character: Any) -> list[tuple[str, int, str, str, Ability | None]]:  # noqa: ANN401
    """Закляття від рис, стилів і викликів: (назва, рівень, джерело, як чарується, характеристика)."""
    rows: list[tuple[str, int, str, str, Ability | None]] = []
    active = character.active_class_choices
    groups = character.derived_choice_groups
    by_slug = {feat_slug(feat): feat for feat in character.feats}
    for slug, feat in by_slug.items():
        for name, level, usage in FEAT_SPELLS.get(slug, ()):
            rows.append((name, level, "feat", usage, _feat_casting(character, feat, None)))
    for key, choice in groups.items():
        if choice.kind != "spell":
            continue
        kind, owner, _ = split_key(key)
        usage = FEAT_CHOICE_SPELL_NOTE.get(owner, "") if choice.spell_level > 0 else ""
        spell_class = spell_class_for(key, choice, character.class_choices)
        if choice.group.endswith("Magical Secrets"):
            # Магічні таємниці: закляття барда з будь-якого списку, Харизма (PHB, p. 54).
            for name in active.get(key, ()):
                rows.append((name, _spell_level(character, name), "secrets", "", Ability.CHA))
            continue
        if kind == "inv":
            # Книга давніх таємниць: ритуали будь-якого класу, лише як ритуал (PHB, p. 110).
            rows.extend((name, choice.spell_level, "invocation", "ritual only", Ability.CHA) for name in active.get(key, ()))
            continue
        if kind == "feat":
            source, ability = "feat", _feat_casting(character, by_slug.get(owner, owner), spell_class)
        elif kind == "boon":
            # Угода фоліанта: заговори будь-якого класу, але для чаклуна — Харизма (PHB, p. 108).
            source, ability = "pact-boon", Ability.CHA
        elif kind == "sub":
            entry = next((item for item in character.classes if subclass_slug(item.subclass_key) == owner), None)
            source, ability = "subclass", CLASS_CASTING_ABILITY.get(entry.class_key if entry else "")
        else:
            # Благословенний і Друїдський воїн чарують Мудрістю (TCoE, p. 41, 57).
            source, ability = "fighting-style", Ability.WIS
        rows.extend((name, choice.spell_level, source, usage, ability) for name in active.get(key, ()))
    for invocation in character.invocations:
        spell = INVOCATION_SPELLS.get(invocation.casefold())
        if spell is not None:
            rows.append((spell[0], spell[1], "invocation", spell[2], Ability.CHA))
    return rows
