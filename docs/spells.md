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

A player can write in a spell that isn't in any book — homebrew, a DM's boon, an item's
power: name, level 0–9 and text in their own words, plus, if they like, the short data a
book spell has: school, casting time, range, duration, components (free text, up to 120
characters each), concentration and ritual. It's stored with a `custom` flag and marked on
the sheet as «власне» ("custom"; in PDF/Markdown — "level 1 · custom" + the data and the
text).

The domain derives no rules from it: the short data are the player's words shown as they
are, not numbers the sheet computes with. The compendium doesn't apply to custom spells
even when the name matches a book spell: otherwise "Fireball" with a custom description
would show the book one.

Whose spell it is:

* **a class of the character** (`class_key: "cleric"`) — a homebrew spell the class
  learned. It's **always prepared** (it has no class list to prepare from) and **counts
  toward the class's limits** — otherwise custom spells could bypass the preparation rule.
  If there's no room, the server refuses: "2 spells prepared, only 1 allowed";
* **outside any class** (`class_key: "other"`) — a DM's boon or an item's power. Any
  character can have one, a fighter too; it takes no room in any limit and has no class
  save DC or attack bonus (the player writes them in the text). On the sheet it's tagged
  «поза класом» ("outside a class"), in a multiclass it gets its own group.

Only custom spells can be **edited** (`PATCH`): name, level, class, text and the short
data; the new version passes the same limits as a new spell. Book spells come from the
compendium and aren't edited. Two spells with the same name and class can't coexist —
editing and removing find a spell by that pair.

## API

```
POST   /api/v1/characters/{id}/spells           add (from the compendium or custom)
PATCH  /api/v1/characters/{id}/spells           edit a custom spell (name_en + class_key + fields)
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

A DM's boon outside any class, with the short data:

```json
{"class_key": "other", "name_en": "Полумʼя перстня", "level": 2, "custom": true,
 "description": "Струмінь вогню: 3d6, рятунок Спритності — половина.",
 "school": "втілення", "casting_time": "1 дія", "range": "18 м", "duration": "миттєво",
 "components": "В", "concentration": false, "ritual": false}
```

Edit it (only the fields sent change; `name_en` and `class_key` in `fields` rename or
move it):

```json
{"name_en": "Полумʼя перстня", "class_key": "other",
 "fields": {"level": 3, "concentration": true}}
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
* `spells[].custom` + `spells[].description` — a custom spell and its text; a custom
  spell also keeps `school`, `casting_time`, `range`, `duration`, `components`,
  `concentration`, `ritual` (book spells get these from the compendium, so their records
  don't have them); `class_key: "other"` — outside any class;
* the order and composition of the class's spells — that is the "prepared set".

## Limits (honestly)

* **The wizard's spellbook isn't modeled separately.** In the corpus the wizard is marked
  as "prepares spells" without a known-spells limit, so it prepares from the whole class
  list, like a cleric. In the 2014 book it also has a spellbook (6 at level 1, +2 per
  level) — adding that needs a separate "in the book" list, not a flag.
* **Cantrips don't change daily** — neither by preparation nor by removal from the
  prepared set; they change only with a level (or by hand: remove and add again).
* **A custom spell's data are text, not rules**: time, range, duration are shown as the
  player wrote them; there's no damage die or save the sheet could use.
* **Actions know no more about custom spells than their data**: the Actions tab sorts a
  custom spell as an action / bonus action / reaction by its casting time ("1 дія",
  "бонусна дія", "реакція"), but has no damage or hit for it — and a spell outside any
  class has no DC there.
