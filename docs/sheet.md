# The sheet during play

The character is created — now it's played. The sheet shows computed numbers but lets
you **override** them, keeps counters (HP, slots, hit dice, death saves, inspiration,
exhaustion), computes weapon attacks and handles rests. Every change is saved
immediately (SQLite) and is visible from any device.

```
Character.state ── DerivedStatsCalculator ──> ComputedSheet ──> PATCH/rest ──> SQLite (versioned)
      ▲                                                                            │
      └──────────────────────── read: numbers + state + attacks ◄──────────────────┘
```

The level isn't edited here: the **"+1 level"** button in the header leads to the
separate level-up screen ([`level-up.md`](level-up.md)) — a level changes classes, HP,
features and resources at once, so it isn't a "field edit".

## What is stored and what is computed

This is the main boundary: **rules** (AC, max HP, slots, DC) aren't stored — they're
recomputed from classes, species and items. What's stored is **state**: current HP,
spent slots, death saves, exhaustion, overrides, notes.

| State (`SheetState`) | Rules (`ComputedSheet`) |
|---|---|
| `hp.current`, `hp.temporary` | `hit_points.maximum` |
| `slots_used`, `pact_used` | total slots |
| `hit_dice_used` | the hit dice pool |
| `death_saves`, `inspiration`, `exhaustion` | AC, initiative, speed, skills |
| `overrides`, `notes` | DC, spell attack bonus |

`hp.current = None` means "the player hasn't touched HP yet", the sheet shows the
maximum; `0` is an unconscious character making death saves. The two states never merge:
a character at zero HP shows zero both on screen and in the export.

There are deliberately no maximums in the state: if a rule changes tomorrow (a new item,
a level), the sheet is recomputed, and "2 of 4 spent" stays meaningful.

## Manual overrides

Clicking a number opens a field. A computed field (AC, initiative, speed, passive
Perception, a skill, a save) changes **only as an override**: the server stores it
separately, and the sheet shows "manual", highlights the number and offers a "↺" button
that restores the computed value.

The allowed keys are a whitelist (`SheetState.OVERRIDABLE` + `skill:*`, `save:*`). The
level or the proficiency bonus can't be overridden: that would break every derived
number. Every override is a conscious compromise ("AC 19 from a magic cloak that isn't in
the compendium"), which is why it's marked.

## Counters and rests

| Action | What it does |
|---|---|
| short rest | Pact Magic and short-rest resources (Second Wind, Action Surge, Ki…); HP and hit dice by hand |
| long rest | HP to maximum, all slots, half of the **total** hit dice (rounded down, minimum 1), all resources, death saves 0, exhaustion −1 |
| damage | removes temporary HP first, then current; doesn't go below zero (PHB, p. 197) |
| healing | adds HP, **not above the maximum** |
| spend a hit die | roll + Constitution, heals, marks the die as spent |
| slots | `+/-` on each level; not above the maximum (the app enforces it) |
| class resources | `+/-` on each resource (Second Wind, Ki, Channel Divinity…); the domain computes the limit |
| death saves | three successes / three failures, by clicking |
| inspiration, exhaustion | a toggle and a number 0..6 |

Rests **don't remove** temporary HP: per the rules they last until removed or replaced
(the rest message says so too).

Damage and healing are **separate actions**, not "type a number": `hp.damage` and
`hp.heal` are applied by the server per the rules. You can't spend more hit dice than you
have — that's an aggregate invariant, not a UI check.

A rest returns a `rest` report (`hp_before`, `hp_after`, `hit_dice_*`, `features_reset`,
`exhaustion_*`), and the screen shows exactly that, not a guess from the previous state.

## Attacks

For each weapon in the inventory the sheet computes an attack from compendium data
(`data.damage`, `data.properties`):

* melee — Strength; `finesse` — the better of Strength and Dexterity; `ammunition` —
  Dexterity;
* attack bonus = proficiency + modifier; damage = die + modifier.

Item data is looked up by `entry_id` or the exact name and cached for the app's lifetime.
No die in the compendium — no attack row (better than an invented "1d6"), **but** if the
item has its own `damage`, the row is built from it: the player may have added a magic
weapon that isn't in the corpus.

## Inventory

Items are added from the catalog (search, filters by type, magic and book) or by hand;
every row can be edited (name, type, quantity, weight, armor AC and Dexterity cap, weapon
damage, properties) or removed. These are the fields `InventoryItem` carries:

| Field | Purpose |
|---|---|
| `name_en`, `kind`, `quantity`, `weight_lb` | what it is and how much it weighs |
| `equipped` | armor/shield affect AC; equipping armor unequips the previous one |
| `attuned` | attunement to a magic item |
| `armor_base`, `dex_cap` | armor numbers (only `kind = armor`) |
| `damage`, `notes` | the weapon's own damage and properties (override the compendium) |
| `entry_id` | where the item came from (for the compendium) |

The server checks invariants: one armor and one shield at a time, only weapons have
damage, the item index must exist, **no more than three attuned items** (PHB, p. 138 —
`Inventory.__post_init__`). The catalog removes duplicates from different books (the same
item in the PHB and the Basic Rules is one row).

Attunement shows only where it applies: the "attune" chip appears when the compendium
says `attunement: true` (or the item is already attuned), the "attuned N of 3" count is
in the heading, and a fourth item hits the limit with a hint. In PDF/Markdown the item
row gets "attuned".

## Features

The Features tab shows class and subclass features **with the rules text**, translated
into Ukrainian where a translation exists:

* `characters/api/features.py` cuts sections out of the class Markdown
  (`### Second Wind`) and the subclass (`## War Priest`), and reads a subclass feature's
  level from the caption `*1st-level Cleric feature*`;
* subclass features above the character's level aren't shown (The Fiend at level 1 gives
  only Dark One's Blessing, not Dark One's Own Luck).

Limited class resources (`feature_resources`) are a separate layer:

* the table in `domain/services/feature_resources.py` knows levels, amounts (including
  "CHA modifier", "monk level") and when a resource recovers;
* subclass resources switch on only with the matching subclass (War Priest — War Domain,
  Superiority Dice — Battle Master);
* the counters live in `SheetState.feature_used`, are checked against the limit and reset
  by rests by their own rule.

## Actions in combat

The Actions tab gathers everything that can be done on a turn into one model:

* weapon rows (attack, range, damage, properties), an **Unarmed Strike** (1 + STR
  bludgeoning, grapple and shove) and available spells;
* class resources with counters (Second Wind, War Priest…) under their action type;
* an **"Attacks per action"** heading — 1 plus each Extra Attack feature;
* filters **All / Attack / Action / Bonus action / Reaction / Other / Limited** and groups
  by action type (a spell with "1 bonus action" casting time goes to bonus actions,
  reactions to reactions);
* standard turn actions with a short Ukrainian rules hint in each group (Attack, Dash,
  Disengage, Dodge, Grapple, Help, Hide, Improvise, Use an Object, Magic, Ready, Search,
  Shove, Study, Utilize).

## Background

The tab shows the name and book, alignment, the **specific** skills, tools and languages
(the ones actually chosen, not "how many may be chosen"), equipment from the `Equipment`
line, the background feature with its text and the full description from the
compendium. Appearance moved here from the notes: it's part of "who I am", not a note
taken during play.

## Notes

Four sections: allies, enemies, backstory, notes. The field grows with the text, changes
go to the server after an 800 ms pause (no "save" button), next to it you see "saving /
saved at 14:32" and word and character counts. "Clear" takes two clicks, so a section
can't be lost by accident. All sections (with the appearance) can be exported to `.md`
(not inside Telegram, where the webview can't save files). The set of sections is fixed:
the domain validates note keys.

## Live sync between devices

Every 4 seconds the open sheet asks for its version number (`GET …/version`) and reloads
when it changed — for example after an edit from a phone. Every write carries `version`;
a stale one gets `409` and the screen shows the fresh sheet with "the sheet was changed
on another device".

## API

| Method | Path | Purpose |
|---|---|---|
| `PATCH` | `/api/v1/characters/{id}` | partial state change |
| `POST` | `/api/v1/characters/{id}/rest` | `{"kind": "short"\|"long"}` + a `rest` report in the response |
| `POST` | `/api/v1/characters/{id}/hit-dice` | `{"die": 10, "roll": 6}` |
| `POST` | `/api/v1/characters/{id}/items` | `{"item": {...}}` — add an item |
| `PATCH` | `/api/v1/characters/{id}/items/{index}` | `{"fields": {...}}` — change it |
| `DELETE` | `/api/v1/characters/{id}/items/{index}` | remove an item |
| `GET` | `/api/v1/characters/{id}` | the full sheet |
| `GET` | `/api/v1/characters/{id}/version` | the version number (live sync) |
| `GET` | `/api/v1/characters/{id}/export/pdf`, `/print` | printing (see [`export.md`](export.md)) |
| `GET/POST/DELETE` | `/api/v1/characters/{id}/share` | the read-only share link |

`PATCH` accepts any subset of fields:

```json
{"version": 5,
 "hp": {"current": 4, "temporary": 2},
 "death_saves": {"successes": 1, "failures": 0},
 "inspiration": true, "exhaustion": 1,
 "slots": {"1": 2}, "pact_used": 1,
 "hit_dice": {"d10": 1},
 "feature_used": {"fighter:second-wind": 1},
 "overrides": {"armor_class": 19, "skill:stealth": null},
 "equip": {"name": "chain mail", "equipped": true},
 "notes": {"appearance": "шрам на щоці"}}
```

Damage and healing are `{"hp": {"damage": 7}}` or `{"hp": {"heal": 7}}`. `version` is
optional, but if it's sent and stale — `409`: two tabs can't silently overwrite each
other. A rules violation is a `422` with the reason.

The response always contains **the full sheet** — the client doesn't assemble it from
pieces.

## Spells

The Actions tab shows spells available right now (cantrips, prepared, or all known if
the class doesn't prepare), with short data from the compendium:

* casting time, range, duration (in Ukrainian, with units);
* the first damage die and type, the saving throw, a mention of a spell attack,
  concentration and ritual.

The Spells tab shows **full cards of known spells**: the same plus components, school,
the full description and the "At Higher Levels" block. The `2nd-level abjuration` line is
cut from the text — level and school are already in the labels. Cards are grouped by
level (and by class in a multiclass, each with its own DC and attack) and collapsed by
default. Daily preparation and custom spells are described in [`spells.md`](spells.md).

This is a hint, not an effect calculation: `characters/api/spell_meta.py` takes the
record's `data` (time, range, components, higher levels) and `text_en` (description),
caching the result in the app.

## Screen

`frontend/src/features/character/CharacterView.tsx` — a dark sheet in the spirit of D&D
Beyond: a header, a row of ability hexagons and the HP block, then three columns (saves
and proficiencies / initiative and skills / state and the work panel). On a phone the
layout becomes a single column with sticky tabs and an "actions" toggle in the header.
The work panel has tabs:

* **Actions** — weapons, Unarmed Strike, available spells and resources with action-type
  filters, "attacks per action" and standard action hints;
* **Spells** — spellcasting, slot counters, full cards of known spells, preparation;
* **Inventory** — compendium search, add, edit, remove, "equipped" (changes AC), money, weight;
* **Features** — class resources with counters, class and subclass features with
  expandable rules text, proficiencies with sources;
* **Background** — what it gives (skills, tools, languages, equipment), the feature and
  description from the compendium, appearance;
* **Notes** — four sections with autosave and counters.

`hp.tsx` — the HP block (large current/max/temporary, an amount field, "Damage"/"Heal"
buttons, quick ±1/±5/±10) and hit dice (roll or enter a roll, "beads" of the free pool).
`inventory.tsx` — search, the item form, rows with edit and remove.
`editing.tsx` — `NumberField` (an always-visible number with steppers), `EditableNumber`
(click → field → Enter/blur), `Counter`, `Pips`.

## Deliberately not done

* **Conditions (poisoned, prone…) and concentration tracking** — a separate layer.
* **Mechanical effects of items** — the corpus has name, type, weight, AC and weapon
  damage, but not "Ring of Regeneration" and the like; so a rest accounts for features,
  slots, HP and hit dice, not magic item properties.
* **Item images** — the compendium has text, not pictures; the character portrait is a
  placeholder with initials.

## Tests

| File | What it holds |
|---|---|
| `tests/characters/test_sheet_state.py` | state validation, overrides, rests, hit dice, attacks, 0 HP ≠ "not set" |
| `tests/api/test_sheet_api.py` | PATCH/rest/hit-dice over HTTP, damage and temporary HP, healing not above max, inventory (add/change/remove, own damage), class resources and rests (`rest` report, subclass resources, resets), background from the compendium, 409, attacks from the compendium |
| `tests/api/test_characters_api.py` | short spell data on the sheet (time, range, damage, save), class feature text, the Second Wind counter |
| `tests/api/test_spell_meta.py` | components, description without the level line, higher levels, damage and save from the text |
| `tests/api/test_export_api.py` | exporting a player's sheet with its state |
| `tests/identity/test_auth.py` | ownership, sync conflicts, share links, Telegram sign-in |
