# The character: classes, multiclass, proficiencies with sources

`Character` isn't "six abilities and an armor" but what a sheet is really built from:
multiclass, species, background, proficiencies with their origin, hit points, inventory,
spells. Numbers are computed along one path, and reference characters pin down what must
come out.

## Structure

```
content/raw/_index/  ──scripts/ingest/mechanics.py──>  content/index/class-mechanics.json
                        (5e.tools: hit dice, proficiencies,        origin-mechanics.json
                         slot tables, species bonuses)                     │
                                                                          ▼
shared/rules.py  ◀──parsing──  compendium/infrastructure/mechanics_index.py
   │                                   │
   │ rules value objects          /api/v1/compendium/classes/{name}/mechanics
   ▼                                   │
characters/domain ──RulesSource port◀──┘  (adapter: characters/infrastructure/compendium_rules.py)
   │
   ├── character.py            the aggregate (multiclass, species, background, choices, spells, HP)
   ├── class_level.py          "Fighter 2 + Wizard 3" instead of a single level
   ├── proficiencies.py        proficiencies with a source (class/species/background/manual)
   ├── inventory.py            items, equipped, money, weight
   ├── spells.py               KnownSpell (with its class!), PactMagic, SpellSlots
   ├── vitals.py               HitPointState (current, temporary, rolls, override)
   └── services/
        derived_stats.py      ComputedSheet
        modifier_resolver.py  "where the +1 to Strength came from"
        spell_slots.py        multiclass slots, Pact Magic, DC and attack
        hit_points.py         max HP and the hit dice pool
        level_up.py           level-up planning
        rest.py               short and long rests
```

## Key decisions

**Abilities are base values, not totals.** `Character.abilities` stores what the player
assigned (standard array / point buy / rolls). Species bonuses are added by
`ModifierResolver`, so the sheet can always explain "16 = 15 + 1 (human)". The cap of 30
applies to the total.

**Proficiencies carry a source.** `Proficiency(kind, value, source)` where
`source = GrantSource(kind, key)` ("class:fighter", "species:hill dwarf"). So it's
visible that a skill came from both the class and the background, and changing a class
removes exactly what it granted. Ukrainian labels don't go here: that's the presentation
layer's job.

**Classes and levels.** `Character.classes` is a list of `CharacterClass(class_key,
level, subclass_key)`. Total level ≤ 20, the subclass no earlier than the level at which
the class grants it (cleric and warlock — 1, druid and wizard — 2, the rest — 3).

**The first class is special.** Saving throws, armor and weapons come only from the first
class: per the PHB (p. 164) multiclassing doesn't grant those proficiencies again.

**Spell slots.** Caster level is computed per the PHB (p. 165): full casters in full,
half casters halved (the TCE artificer rounds up), third casters by a third. The
warlock's Pact Magic is computed separately and doesn't add to the sum. In a multiclass
every casting class keeps its own spell save DC and attack bonus.

**Max HP.** Level 1 — the first class's hit die maximum + Constitution; after that the
roll (if recorded) or the average (half the die + 1) + Constitution; each level adds at
least 1 HP. A multiclass uses each class's die.

**Rules tables live in code.** 20 rows of slots and 20 rows of Pact Magic are SRD
content that doesn't change from book to book, and without them the domain can't compute
anything. So they're in `shared/rules.py`, not in the corpus. The mechanics index also
stores the class tables, and `test_real_mechanics.py` checks that the wizard and the
cleric give the same slots at level 3.

## Reference characters (proof of the rules)

`characters/application/golden.py` — three characters whose numbers are pinned by tests.
The same tests run on **two** rules sources: a small fixture (works without the corpus)
and the real index. A divergence fails exactly where it appears.

| Character | What it checks | Numbers |
|---|---|---|
| **Fighter 1** (human, soldier) | d10 maximum, heavy armor + shield, +1 to everything | AC 18, HP 12, proficiency 2, STR 16, saves STR +5 / CON +4, Athletics +5 |
| **Warlock 1** (tiefling, acolyte) | Pact Magic, DC from CHA, fire resistance | AC 12, HP 9, DC 13, attack +5, 1 level-1 slot, darkvision 60 |
| **Fighter 2 / Wizard 3** (human, soldier) | multiclass: level, slots, hit dice | level 5, proficiency 3, caster level 3, slots 4×1 + 2×2, HP 33, dice d10×2 + d6×3 |

A sanity endpoint: `GET /api/v1/characters/golden` returns the fully computed sheets of
these three (`sheet.abilities`, `sheet.hit_points`, `sheet.spellcasting`,
`sheet.proficiencies` with sources).

## Mechanics indexes

`scripts/ingest/mechanics.py` builds two derived files from the 5e.tools mirror:

* `content/index/class-mechanics.json` — 13 classes of 2014: hit die, saving throws,
  skill choices, proficiencies, spellcasting ability, spell progression, slot tables
  (20×9), Pact Magic (20×2), multiclass prerequisites, features by level, optional
  features, starting equipment;
* `content/index/origin-mechanics.json` — 69 species, 64 subraces, 94 backgrounds:
  ability bonuses (fixed and "choose"), size, speed, darkvision, resistances, skills,
  languages, tools.

Subraces already carry the parent's inherited numbers: "Hill Dwarf" is +2 CON and +1 WIS,
speed 25, darkvision 60, dwarven weapons. The mirror keeps these separately, and without
the merge half the rules would be lost.

Format — [`contract/mechanics-format.json`](../contract/mechanics-format.json), checked by
`tests/contract/test_mechanics_format.py` on the built files.

`content/index/` is derived from book texts, so in git it's encrypted together with the
corpus. A locked clone works, but `mechanics_available()` returns `false` and the wizard
honestly shows that mechanics are missing.

## Level 1 choices the server actually enforces

Level 1 isn't "just a class and abilities": three classes require a subclass right away,
and some species grant cantrips and spells. Here's the full list of what is checked and
where the numbers come from.

### Classes that choose a subclass at level 1

| Class | What is chosen | What it gives at level 1 |
|---|---|---|
| Cleric | Divine Domain | domain spells **always prepared** (`bless`, `cure wounds` for Life) |
| Sorcerer | Sorcerous Origin | no numeric mechanics in the data — only the recorded choice |
| Warlock | Otherworldly Patron | an **expanded spell list** (The Fiend: `burning hands`, `command`) |
| the other 10 | — | subclass at level 2 (druid, wizard) or 3 |

`subclass_level == 1` is exactly these three; the class step doesn't pass without the
choice and doesn't allow picking a subclass too early.

### Species that require choices

| Species | What to choose | How it's checked |
|---|---|---|
| any with subraces | a subrace (Dwarf 2, Elf 8, Gnome 5, Halfling 3, Dragonborn 2) | the subrace must belong to the species |
| half-elf | two +1 abilities, two skills, one language | `ability_choice`, `skill_any=2`, `languages_any=1` |
| high elf | one cantrip from the wizard list | `cantrip_choice` + the class list from the corpus |
| human | nothing: +1 to everything | fixed bonuses |

The human was long marked `ability_unresolved` because of a builder bug: merging the
"standard" variant added bonuses but didn't recompute the flag. Fixed — `unresolved` now
means exactly what it should: "the numbers aren't encoded in the mirror". Such species
(MPMM, VRGR, TCE) get the "+2/+1 or +1/+1/+1" choice in the wizard; the bonuses live in
`Character.ability_spread` and are added in `ModifierResolver` (on the sheet
"13 + 1 = 14").

### Species that grant spells right away

| Species | What it gives at level 1 |
|---|---|
| Tiefling | `thaumaturgy` |
| Drow | `dancing lights` |
| Forest gnome | `minor illusion` |
| Yuan-ti Pureblood | `animal friendship` |
| Triton | `fog cloud` |
| Firbolg | `detect magic`, `disguise self` |
| Aasimar | `light` |
| Genasi (each) | its own cantrip (`produce flame`, `shocking grasp`, …) |
| Dragonmarks | their own cantrip / level-1 spell |

All of this comes from the mirror's `additionalSpells` and is folded into the index
(`shared_cantrips`, `cantrip_choice`, `granted_spells`). The character file stores **only
the choice** (`spell_choices`); the species' grants themselves are derived and recomputed
on every read — like ability bonuses.

## Slots: one class ≠ multiclass

The multiclass table and the class table are **not the same** for half casters.
Paladin 5 has 4 level-1 slots and 2 level-2 slots, while the multiclass table at caster
level 2 gives only 3 level-1 slots: the class gets a new slot level on odd levels, and
halving with rounding down eats that step.

So `SpellSlotService`:

* **one** casting class → slots from the class's own table (`slots_from: "class"`);
  non-casters (Fighter 5 alongside Paladin 5) don't affect the choice of table;
* **two or more** → the multiclass table by total caster level
  (`slots_from: "multiclass"`), Pact Magic separately, as before.

This isn't the literal reading of PHB p. 164 (there the multiclass table applies as soon
as there's more than one class), but a deliberate choice: otherwise a dip into a
non-caster would **reduce** a paladin's slots, which nobody plays at the table. The
divergence is pinned by `test_half_caster_keeps_its_table_when_dipping_a_non_caster`.

The 20-level check (`test_twenty_levels.py`) runs every class and every pair of casting
classes: 260 "class × level" rows and 6840 splits between two classes. That's what found
the half-caster bug.

## Tests

| File | What it holds |
|---|---|
| `tests/characters/test_golden.py` | three reference characters on two rules sources |
| `tests/characters/test_invariants.py` | levels, subclasses, spell limits, skill choices, HP |
| `tests/characters/test_derived_stats.py` | AC, skills, saves, speed, passive Perception, warnings |
| `tests/characters/test_spell_slots.py` | caster level, tables, Pact Magic, DC |
| `tests/characters/test_hit_points.py` | max at level 1, average, rolls, multiclass |
| `tests/characters/test_multiclass_matrix.py` | multiclass combinations: slots, DC and attack per class |
| `tests/compendium/test_mechanics.py` | the index reader: a broken file doesn't crash the app |
| `tests/compendium/test_real_mechanics.py` | real numbers from the books (skipped without the corpus), level-1 choices |
| `tests/contract/test_mechanics_format.py` | index format, bounds, keys, tables |
| `tests/api/test_characters_api.py` | `/characters/golden`, export, compendium mechanics |
| `tests/characters/test_twenty_levels.py` | 13 classes × 20 levels and all caster pairs (6840 splits) |
| `tests/characters/test_granted_spells.py` | species cantrips, the high elf's choice, the cleric's domain |
