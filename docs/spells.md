# Spells outside of level-up

Level-up isn't the only moment the spell list changes. At the table a player does two
different things, and the sheet supports both:

* **prepares a set for the day** — cleric, druid, paladin, wizard, artificer (PHB, p. 201);
* **adds a spell** — from the class list or a custom one that isn't in any book.

Previously this happened only together with a level, and the sheet couldn't keep up with
play: a cleric prepares spells every morning, and DMs often allow a custom spell
mid-session.

## Daily preparation

UI: the **Spells → Preparation for the day** tab. For each preparing class there is a
search over the class list, checkboxes and a "selected N / limit" counter.

Rules applied:

| Rule | Source | Where |
|---|---|---|
| prepared ≤ modifier + class level, minimum 1 | PHB, p. 201 | `Character.prepared_limit` (`shared.rules.prepared_spell_limit`) |
| preparation is **a set for the day**; yesterday's spells don't stay | PHB, p. 201 | `Character.prepare_spells` |
| cantrips aren't changed by preparation | PHB, p. 201 | `Character.prepare_spells` (refusal) |
| spell level no higher than the class's slots | class table | `ClassMechanics.max_spell_level` |
| a class without preparation (Fighter, Warlock…) can't prepare | class rules | `Character.prepared_limit` |

The limit is computed by **one** formula — `shared.rules.prepared_spell_limit`: the sheet
calculator uses it too (`ClassCasting.prepared_limit`), so the UI and the validation
can't diverge.

## Custom (homebrew) spells

A player can write in a spell that isn't in any book: name, level and text in their own
words. It's stored with a `custom` flag and marked on the sheet as «власне» ("custom";
in PDF/Markdown — "level 1 · custom" + the text).

The domain derives no rules from it: no school, damage or casting time — it's the
player's text. The compendium doesn't apply to custom spells even when the name matches a
book spell: otherwise "Fireball" with a custom description would show the book one.

A custom spell is **always prepared** (it has no class list to prepare from) and **counts
toward the limit** — otherwise custom spells could bypass the preparation rule. If there's
no room, the server refuses: "2 spells prepared, only 1 allowed".

## API

```
POST   /api/v1/characters/{id}/spells           add (from the compendium or custom)
DELETE /api/v1/characters/{id}/spells           remove (name_en + class_key)
POST   /api/v1/characters/{id}/spells/prepare   replace the class's prepared set
```

Add a book spell:

```json
{"class_key": "cleric", "name_en": "Bless", "level": 1,
 "entry_id": "phb-2014/spell/bless", "prepared": true}
```

Add a custom spell:

```json
{"class_key": "cleric", "name_en": "Благословення столу", "level": 1,
 "custom": true, "description": "Усі союзники за столом отримують +1…"}
```

Prepare the set for the day (the level can be omitted if the spell is already on the
sheet):

```json
{"class_key": "cleric", "spells": [{"name_en": "Bless", "level": 1},
                                    {"name_en": "Cure Wounds", "level": 1}]}
```

`version` is the same optimistic lock as in the sheet's `PATCH` (409 on a stale version).
Success returns `sheet` and `version`; a refusal is a 422 with the reason ("only 5
allowed", "the class doesn't prepare", "maximum 1").

## What is stored

* `spells[]` — name, level, class, `entry_id` (for book spells), `prepared`;
* `spells[].custom` + `spells[].description` — a custom spell and its text;
* the order and composition of the class's spells — that is the "prepared set".

## Limits (honestly)

* **The wizard's spellbook isn't modeled separately.** In the corpus the wizard is marked
  as "prepares spells" without a known-spells limit, so it prepares from the whole class
  list, like a cleric. In the 2014 book it also has a spellbook (6 at level 1, +2 per
  level) — adding that needs a separate "in the book" list, not a flag.
* **Cantrips don't change daily** — neither by preparation nor by removal from the
  prepared set; they change only with a level (or by hand: remove and add again).
* **A custom spell has no structured fields** (time, range, damage): everything the sheet
  shows is the player's text.
* **Actions know no more about custom spells than their text**: there's no damage die,
  because it isn't structured.
