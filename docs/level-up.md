# Level-up

A character grows **on the same document**: a class level is the
`CharacterClass.level` field, not a new character. So "taking a level" recreates
nothing: it moves the level, and every number on the sheet (hit points, proficiency
bonus, slots, spell limits, features, resources) is recomputed by the same
`DerivedStatsCalculator` as before the level-up.

## What the screen does

One screen instead of the wizard's six steps, in the Player's Handbook order (PHB,
*Leveling Up*):

1. **Class** — an existing one (next level) or a new one (multiclass). A new class is
   shown with its prerequisites and is **disabled** if the character doesn't meet them.
   The "ignore multiclass prerequisites" checkbox lifts that restriction (a house rule),
   but the sheet then states the bypass explicitly (see "Prerequisites ignored").
2. **Hit points** — the average by the "half the die + 1" rule or a roll; the increase
   includes Constitution and the "at least 1 HP" floor.
3. **New class features** — the name in Ukrainian with English in parentheses and the
   **rules text** (translated from the classes layer; without a translation — the book's
   original). Previously this showed only a line like "Second Wind" with no explanation.
   The text comes from **all of the class's books** (PHB + TCoE), so optional features
   ("Magical Guidance", "Harness Divine Power") are explained too. Names from the
   mechanics index that are glued together ("Channel Divinity: Harness Divine Power") or
   carry a qualifier ("Destroy Undead (CR 1/2)") are matched to the chapter's sections
   (`features.feature_text_for`); the level caption in the body ("2nd-level cleric
   feature") is trimmed, because the level is already in the heading.
4. **Subclass** — only if this level grants it (cleric 1, wizard 2, fighter 3, rogue 3).
   Options come from the compendium with **all** their features and levels: you can see
   what a specialization gives not only today but later. Features of the current level
   are shown with rules text, the rest by name and level (otherwise the response would
   grow to kilobytes).
5. **Ability Score Improvement** — +2 to one, +1 and +1 to two, or a feat. The number of
   earned improvements is counted from class features ("Ability Score Improvement" at
   4/6/8/…), so a fighter gets more than a wizard.
6. **Spells** — new spells are chosen on the same screen, from the class list up to the
   level the class can cast; in a multiclass each class has its own maximum spell level.
   Later changes go through the sheet: **Spells tab → Add spells** (see `docs/spells.md`).
7. **What changes** — level, hit points, proficiency bonus, slots, features, resources.
   These are the same numbers that appear on the sheet after confirming: the server
   computed them, not the screen.

## Rules applied

| Rule | Source | Where |
|---|---|---|
| total level ≤ 20 | PHB, p. 15 | `Character.add_class` / `set_class_level` |
| multiclass: 13 in the key ability of the new class **and** the existing ones | PHB, p. 163 | `LevelUpPlanner._check_multiclass` |
| a first level in a class gives the average/roll, not the maximum | PHB, p. 164 | `hit_point_maximum` (maximum only at character level 1) |
| subclass — from the level named by the class | PHB, class table | `Character.set_subclass` |
| improvement: +2 or +1/+1, no more than two abilities | PHB, p. 165 | `Character.take_asi` |
| ability total ≤ 20 **after** species bonuses | PHB, p. 173 | `Character.increase_ability` |
| a feat instead of an improvement | PHB, p. 165 | `Character.take_asi(feat_key=…)` |
| limits on cantrips, known and prepared spells | class tables | `Character._validate_spell_limits` |
| multiclass slots by combined caster level, Pact Magic separately; per-class spell DC and attack | PHB, p. 164–165 | `spell_slots.py`, `derived_stats.py` |

The position of a hit die roll isn't "the end of the list" but the level's place in the
pool (`Character.roll_index_for` + `HitPointState.with_roll_at`): a class level that
isn't last in the list must not shift other classes' rolls. A place where the average was
taken is marked `None` — otherwise there'd be no way to mark "average" between two rolls.

## API

```
GET  /api/v1/characters/{id}/level-up       a plan for every class
POST /api/v1/characters/{id}/level-up       take a level
```

`GET` returns a plan for each existing class and each new one (the 13 classes of 2014),
with the domain's numbers, subclasses and prerequisites. At total level 20
`can_level_up: false` and an empty list — that's not an error.

`POST` takes the choices:

```json
{
  "version": 31,
  "class_key": "fighter",
  "hp": {"mode": "roll", "roll": 8},
  "subclass_key": "phb-2014/subclass/champion",
  "ability_increases": {"str": 1, "con": 1},
  "feat_key": null,
  "spells": [{"name_en": "hex", "level": 1, "class_key": "warlock"}]
}
```

`version` is the same optimistic lock as in the sheet's `PATCH`: two tabs can't overwrite
each other (409). Success returns `sheet` (the new sheet), `version` and `level_up` — a
"before → after" report for the message on screen.

## Prerequisites ignored (house rule)

Multiclass prerequisites (PHB, p. 163) are an entry requirement, not a derived number,
so they can be bypassed only **deliberately**: a checkbox above the class list enables
buttons that are disabled without it. The request then carries `ignore_requirements: true`.

The domain doesn't pretend the prerequisites were met. It records the bypass:

```json
POST /api/v1/characters/{id}/level-up
{"class_key": "bard", "ignore_requirements": true}
```

```json
"character": {
  "classes": [{"key": "bard", "level": 1, "requirements_ignored": true}],
  "multiclass_waivers": [{"class_key": "bard", "requirements": ["CHA 13"]}]
}
```

On the sheet this is a separate line above the abilities ("Multiclass prerequisites
ignored: Bard · CHA 13"), in PDF/Markdown — the `identity.waivers` field, in the report
`level_up.requirements_ignored`. Without the checkbox the response is a 422 with an
explanation, as before. The mark is removed only together with the class.

## What is stored

* `classes[].level` — the class level;
* `hp.rolls` — rolls per level (`null` where the average was taken);
* `asi_taken` — how many improvements/feats are used (checked against the number of
  levels that grant them: editing the file by hand won't fake it);
* `feats` — feat keys (compendium entry ids);
* `multiclass_waivers` — which classes were taken without prerequisites and what was missing.

Feats are shown on the Features tab as a separate list with the book's text, and go into
the export (PDF/Markdown) by name, not by key.

## Limits (honestly)

* **Numeric effects of feats aren't applied automatically** ("Actor" gives +1 Charisma,
  "Tough" +2 HP per level). They're entered as field overrides: feat texts aren't
  structured in the corpus, and "reading" a number out of them would be guessing. Ability
  Score Improvements, by contrast, are applied mechanically.
* **Spells outside of level-up** — a separate sheet screen: daily preparation and adding
  spells (including custom ones). See `docs/spells.md`.
* **There's no level rollback** in the UI: the data can be fixed by hand, and the
  `asi_taken` counter must then be decreased too (otherwise the validator refuses to read
  it — by design).
